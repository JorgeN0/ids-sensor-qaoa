"""Run the IDS sensor-placement QAOA on a real IBM quantum computer.

Submits two jobs to the same machine, each with the same four circuits:
    1. QAOA with CVaR-optimized angles   (the method)
    2. QAOA with naive-optimized angles  (the baseline that fails)
    3. readout calibration: all qubits in 0
    4. readout calibration: all qubits in 1
Job "raw"       : no error suppression
Job "mitigated" : dynamical decoupling + Pauli twirling (gates and measurement)
Readout-error mitigation is applied afterwards in post-processing, using circuits 3 and 4.

Usage
    python run_on_hardware.py --submit           # pick least-busy machine, submit, save job IDs
    python run_on_hardware.py --fetch            # check status; when done, save + summarize results
    python run_on_hardware.py --fake             # full dry run on a simulated noisy Heron (no account needed)

Your API key is read from the QISKIT_IBM_TOKEN environment variable (never put it in this file).
Optionally set QISKIT_IBM_INSTANCE to your instance CRN.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import SamplerV2

import sensor_qaoa as sq

HERE = Path(__file__).parent
PARAMS_FILE = HERE / "qaoa_params.json"
JOBS_FILE = HERE / "hardware_jobs.json"
RESULTS_FILE = HERE / "hardware_results.json"
FAKE_RESULTS_FILE = HERE / "hardware_results_fake.json"
PUB_NAMES = ["qaoa_cvar", "qaoa_naive", "cal_all0", "cal_all1"]


# --------------------------------------------------------------------------- params
def load_or_make_params(net: sq.Network) -> dict:
    """Use the angles saved by the notebook; recompute them (deterministic, ~15 s) if missing."""
    if PARAMS_FILE.exists():
        return json.loads(PARAMS_FILE.read_text())
    print("qaoa_params.json not found; optimizing angles on the simulator now...")
    cvar = sq.optimize_qaoa(net, reps=2, alpha=0.2)
    naive = sq.optimize_qaoa(net, reps=2, alpha=1.0)
    data = {"reps": 2, "cvar_alpha": 0.2, "cvar_params": cvar.params.tolist(), "naive_params": naive.params.tolist()}
    PARAMS_FILE.write_text(json.dumps(data, indent=2))
    return data


# --------------------------------------------------------------------------- circuits
def build_pubs(net: sq.Network, params: dict, backend, shots: int):
    H, _, _ = sq.ising_hamiltonian(net, sq.default_penalty(net))
    qaoa = sq.measured(sq.qaoa_circuit(H, params["reps"]))
    pm = generate_preset_pass_manager(optimization_level=3, backend=backend, seed_transpiler=7)
    isa_qaoa = pm.run(qaoa)
    # Physical qubit that ends up holding each logical qubit at measurement time.
    layout = isa_qaoa.layout.final_index_layout()
    cal_pm = generate_preset_pass_manager(optimization_level=1, backend=backend, initial_layout=layout)
    isa_cal0, isa_cal1 = (cal_pm.run(c) for c in sq.calibration_circuits(net.n))
    pubs = [
        (isa_qaoa, np.array(params["cvar_params"]), shots),
        (isa_qaoa, np.array(params["naive_params"]), shots),
        (isa_cal0, None, shots),  # the Runtime sampler requires equal shots across circuits
        (isa_cal1, None, shots),
    ]
    ops = isa_qaoa.count_ops()
    info = {
        "layout": [int(q) for q in layout],
        "depth": isa_qaoa.depth(),
        "two_qubit_gates": int(sum(v for k, v in ops.items() if k in ("cz", "ecr", "cx"))),
    }
    return pubs, info


def make_sampler(backend, mitigated: bool) -> SamplerV2:
    sampler = SamplerV2(mode=backend)
    sampler.options.dynamical_decoupling.enable = mitigated
    sampler.options.twirling.enable_gates = mitigated
    sampler.options.twirling.enable_measure = mitigated
    if mitigated:
        sampler.options.dynamical_decoupling.sequence_type = "XpXm"
    return sampler


# --------------------------------------------------------------------------- results
def counts_of(pub_result) -> dict[str, int]:
    return pub_result.data.meas.get_counts()


def analyze(net: sq.Network, all_counts: dict) -> dict:
    """all_counts[job_label][pub_name] -> counts. Returns P(optimal) etc. for every variant."""
    exact = sq.brute_force(net, sq.default_penalty(net))
    table = {}
    for label, pubs in all_counts.items():
        mats = sq.readout_matrices(pubs["cal_all0"], pubs["cal_all1"], net.n)
        readout_err = float(np.mean([(m[1, 0] + m[0, 1]) / 2 for m in mats]))
        for angles in ("qaoa_cvar", "qaoa_naive"):
            raw = sq.counts_to_probs(pubs[angles], net.n)
            for variant, probs in (("", raw), ("+readout", sq.mitigate_readout(raw, mats))):
                s = sq.summarize(probs, exact)
                table[f"{angles} | {label}{variant}"] = {
                    "p_optimal": s.p_optimal,
                    "x_random": s.advantage_over_random,
                    "p_valid": s.p_valid,
                    "most_likely_cost": s.most_likely_cost,
                    "most_likely_is_optimal": s.most_likely_is_optimal,
                }
        table[f"mean readout error | {label}"] = readout_err
    return table


def print_table(table: dict) -> None:
    print(f"\n{'variant':<40} {'P(opt)':>7} {'x random':>9} {'P(valid)':>9} {'top answer':>11}")
    for key, row in table.items():
        if isinstance(row, dict):
            top = "optimal" if row["most_likely_is_optimal"] else f"cost {row['most_likely_cost']:g}"
            print(f"{key:<40} {row['p_optimal']:7.3f} {row['x_random']:9.1f} {row['p_valid']:9.3f} {top:>11}")
    for key, val in table.items():
        if not isinstance(val, dict):
            print(f"{key}: {val:.4f}")


# --------------------------------------------------------------------------- modes
def get_service():
    from qiskit_ibm_runtime import QiskitRuntimeService

    token = os.environ.get("QISKIT_IBM_TOKEN")
    if not token:
        sys.exit("Set the QISKIT_IBM_TOKEN environment variable to your IBM Quantum API key first.")
    kwargs = {"channel": "ibm_quantum_platform", "token": token}
    if os.environ.get("QISKIT_IBM_INSTANCE"):
        kwargs["instance"] = os.environ["QISKIT_IBM_INSTANCE"]
    return QiskitRuntimeService(**kwargs)


def submit(args) -> None:
    net = sq.enterprise_network()
    params = load_or_make_params(net)
    service = get_service()
    backend = service.backend(args.backend) if args.backend else service.least_busy(
        operational=True, simulator=False, min_num_qubits=net.n)
    print(f"Machine: {backend.name}  (pending jobs: {backend.status().pending_jobs})")
    pubs, info = build_pubs(net, params, backend, args.shots)
    print(f"Transpiled QAOA: depth {info['depth']}, {info['two_qubit_gates']} two-qubit gates, qubits {info['layout']}")
    jobs = {}
    for label, mitigated in (("raw", False), ("mitigated", True)):
        job = make_sampler(backend, mitigated).run(pubs)
        jobs[label] = job.job_id()
        print(f"Submitted {label:<9} job: {job.job_id()}")
    JOBS_FILE.write_text(json.dumps({
        "backend": backend.name,
        "submitted_utc": datetime.now(timezone.utc).isoformat(),
        "jobs": jobs, "circuit": info, "shots": args.shots,
    }, indent=2))
    print(f"\nSaved job IDs to {JOBS_FILE.name}. Check later with:  python run_on_hardware.py --fetch")


def fetch(args) -> None:
    if not JOBS_FILE.exists():
        sys.exit("No hardware_jobs.json yet. Run --submit first.")
    meta = json.loads(JOBS_FILE.read_text())
    service = get_service()
    all_counts, usage = {}, {}
    for label, job_id in meta["jobs"].items():
        job = service.job(job_id)
        status = str(job.status())
        print(f"{label:<9} job {job_id}: {status}")
        if "DONE" not in status.upper():
            continue
        result = job.result()
        all_counts[label] = {name: counts_of(result[i]) for i, name in enumerate(PUB_NAMES)}
        try:
            usage[label] = job.usage()  # QPU seconds
        except Exception:
            usage[label] = None
    if len(all_counts) < len(meta["jobs"]):
        print("\nNot all jobs are finished yet. Run --fetch again later.")
        if not all_counts:
            return
    net = sq.enterprise_network()
    table = analyze(net, all_counts)
    RESULTS_FILE.write_text(json.dumps({**meta, "qpu_seconds": usage, "counts": all_counts, "summary": table}, indent=2))
    print_table(table)
    print(f"\nQPU seconds used: {usage}")
    print(f"Saved everything to {RESULTS_FILE.name} (the notebook reads this file).")


def fake(args) -> None:
    from qiskit_ibm_runtime.fake_provider import FakeFez

    net = sq.enterprise_network()
    params = load_or_make_params(net)
    backend = FakeFez()
    pubs, info = build_pubs(net, params, backend, args.shots)
    print(f"[dry run] {backend.name}: depth {info['depth']}, {info['two_qubit_gates']} two-qubit gates, qubits {info['layout']}")
    # Local simulators ignore dynamical decoupling / twirling, so only the raw job is meaningful here.
    result = make_sampler(backend, mitigated=False).run(pubs).result()
    all_counts = {"raw": {name: counts_of(result[i]) for i, name in enumerate(PUB_NAMES)}}
    table = analyze(net, all_counts)
    FAKE_RESULTS_FILE.write_text(json.dumps({"backend": backend.name, "circuit": info, "counts": all_counts, "summary": table}, indent=2))
    print_table(table)
    print(f"\nSaved to {FAKE_RESULTS_FILE.name}. Pipeline works; run --submit for the real machine.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--submit", action="store_true")
    mode.add_argument("--fetch", action="store_true")
    mode.add_argument("--fake", action="store_true")
    ap.add_argument("--backend", help="machine name, e.g. ibm_fez (default: least busy)")
    ap.add_argument("--shots", type=int, default=4000)
    a = ap.parse_args()
    {"submit": submit, "fetch": fetch, "fake": fake}[next(k for k in ("submit", "fetch", "fake") if getattr(a, k))](a)

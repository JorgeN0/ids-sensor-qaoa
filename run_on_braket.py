"""Run the IDS sensor-placement QAOA on a real quantum computer through Amazon Braket.

Same experiment as run_on_hardware.py (which targets IBM Quantum), sent through Amazon Braket
using Qiskit and the official qiskit-braket-provider. Four circuits, all on the same physical qubits:
    1. QAOA with CVaR-optimized angles   (the method)
    2. QAOA with naive-optimized angles  (the baseline that fails)
    3. readout calibration: all qubits in 0
    4. readout calibration: all qubits in 1
Qiskit compiles the circuits to the device's native gates and qubit layout, and they are submitted
"verbatim" so Braket runs them exactly as compiled (no re-placement of qubits). Readout-error
mitigation is applied afterwards, as in the IBM script. Braket has no built-in dynamical decoupling
or twirling, so there is only the raw run.

Usage
    python run_on_braket.py --local                      # free: ideal local simulator, full pipeline check
    python run_on_braket.py --emulate --device garnet    # free: runs locally on an emulator of the real device
    python run_on_braket.py --test --device garnet       # small cost: one 100-shot task on the real machine
    python run_on_braket.py --submit --device garnet     # prints the cost and stops; add --yes to submit
    python run_on_braket.py --fetch                      # check status; when done, save + summarize results

Needs AWS credentials (run `aws login` first) for everything except --local. No keys are stored here.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

import run_on_hardware as rh
import sensor_qaoa as sq

HERE = Path(__file__).parent
JOBS_FILE = HERE / "braket_jobs.json"
RESULTS_FILE = HERE / "braket_results.json"
LOCAL_RESULTS_FILE = HERE / "braket_results_local.json"

# Device ARN and per-shot price in USD (AWS Braket pricing page, Nov 2026). Every task also costs TASK_FEE.
DEVICES = {
    "cepheus": ("arn:aws:braket:us-west-1::device/qpu/rigetti/Cepheus-1-108Q", 0.000425),  # price unconfirmed
    "garnet": ("arn:aws:braket:eu-north-1::device/qpu/iqm/Garnet", 0.00145),
    "emerald": ("arn:aws:braket:eu-north-1::device/qpu/iqm/Emerald", 0.00160),
}
TASK_FEE = 0.30


# --------------------------------------------------------------------------- backends
def aws_backend(device: str):
    from qiskit_braket_provider import BraketAwsBackend

    arn = DEVICES[device][0]
    os.environ.setdefault("AWS_DEFAULT_REGION", arn.split(":")[3])  # the device's own region
    return BraketAwsBackend(arn=arn)


# --------------------------------------------------------------------------- circuits
def measured_qubits(circ: QuantumCircuit) -> list[int]:
    """Physical qubit read into each classical bit, in classical-bit order."""
    out = {}
    for inst in circ.data:
        if inst.operation.name == "measure":
            out[circ.find_bit(inst.clbits[0]).index] = circ.find_bit(inst.qubits[0]).index
    return [out[i] for i in sorted(out)]


def build_circuits(net: sq.Network, params: dict, backend) -> tuple[dict[str, QuantumCircuit], dict]:
    H, _, _ = sq.ising_hamiltonian(net, sq.default_penalty(net))
    qaoa = sq.measured(sq.qaoa_circuit(H, params["reps"]))
    pm = generate_preset_pass_manager(optimization_level=3, target=backend.target, seed_transpiler=7)
    isa = pm.run(qaoa)  # compiled once; both angle sets are bound into the same compiled circuit
    # A real device always gets a layout; an ideal simulator with no wiring keeps qubits where they are.
    layout = isa.layout.final_index_layout() if isa.layout else list(range(net.n))
    cal_pm = generate_preset_pass_manager(optimization_level=1, target=backend.target,
                                          initial_layout=layout, seed_transpiler=7)
    cal0, cal1 = (cal_pm.run(c) for c in sq.calibration_circuits(net.n))
    circuits = {
        "qaoa_cvar": isa.assign_parameters(params["cvar_params"]),
        "qaoa_naive": isa.assign_parameters(params["naive_params"]),
        "cal_all0": cal0,
        "cal_all1": cal1,
    }
    # Readout mitigation is only valid if every circuit reads out the same physical qubits.
    readout = {name: measured_qubits(c) for name, c in circuits.items()}
    if len({tuple(q) for q in readout.values()}) != 1:
        sys.exit(f"Calibration and QAOA circuits measure different qubits: {readout}")
    ops = isa.count_ops()
    two_q = sum(1 for inst in isa.data if inst.operation.num_qubits == 2 and inst.operation.name != "barrier")
    info = {"measured_qubits": readout["qaoa_cvar"], "depth": isa.depth(), "two_qubit_gates": two_q,
            "gates": {k: int(v) for k, v in ops.items()}}
    return circuits, info


def shots_for(name: str, args) -> int:
    return args.cal_shots if name.startswith("cal_") else args.shots


def cost(device: str, args) -> float:
    shots = 2 * args.shots + 2 * args.cal_shots
    return 4 * TASK_FEE + shots * DEVICES[device][1]


def clean_counts(counts: dict[str, int], n: int) -> dict[str, int]:
    """Strip register spaces and pad to n bits so the analysis code sees n-bit little-endian strings."""
    out: dict[str, int] = {}
    for k, v in counts.items():
        k = k.replace(" ", "").zfill(n)
        out[k] = out.get(k, 0) + int(v)
    return out


def report(net: sq.Network, label: str, counts: dict) -> dict:
    table = rh.analyze(net, {label: counts})
    rh.print_table(table)
    return table


# --------------------------------------------------------------------------- modes
def run_locally(args, backend, label: str, out_file: Path) -> None:
    net = sq.enterprise_network()
    params = rh.load_or_make_params(net)
    circuits, info = build_circuits(net, params, backend)
    print(f"[{label}] depth {info['depth']}, {info['two_qubit_gates']} two-qubit gates, "
          f"measured qubits {info['measured_qubits']}, gates {info['gates']}")
    counts = {}
    for name, circ in circuits.items():
        res = backend.run(circ, shots=shots_for(name, args), verbatim=True).result()
        counts[name] = clean_counts(res.get_counts(), net.n)
    table = report(net, label, counts)
    out_file.write_text(json.dumps({"backend": label, "circuit": info, "counts": counts, "summary": table}, indent=2))
    print(f"\nSaved to {out_file.name}. No AWS charges for this mode.")


def local(args) -> None:
    from qiskit_braket_provider import BraketLocalBackend

    run_locally(args, BraketLocalBackend(), "braket_local_ideal", LOCAL_RESULTS_FILE)


def emulate(args) -> None:
    backend = aws_backend(args.device).emulator()
    run_locally(args, backend, f"{args.device}_emulator", HERE / f"braket_results_emulator_{args.device}.json")


def test(args) -> None:
    """One small real task: the all-1 calibration circuit, 100 shots. Checks access, billing and qubit mapping."""
    net = sq.enterprise_network()
    backend = aws_backend(args.device)
    circuits, info = build_circuits(net, rh.load_or_make_params(net), backend)
    price = TASK_FEE + 100 * DEVICES[args.device][1]
    print(f"Device {backend.name}; test task: all-1 calibration, 100 shots, about ${price:.2f}")
    if not args.yes:
        sys.exit("Nothing submitted. Re-run with --yes to submit the test task.")
    job = backend.run(circuits["cal_all1"], shots=100, verbatim=True)
    print(f"Submitted test task: {job.task_id()}\nWaiting for it to run (this can take a while if there is a queue)...")
    counts = clean_counts(job.result().get_counts(), net.n)
    top = max(counts, key=counts.get)
    print(f"Most common result: {top} ({counts[top]}/100). Expected '{'1' * net.n}' for most shots.")


def submit(args) -> None:
    net = sq.enterprise_network()
    params = rh.load_or_make_params(net)
    backend = aws_backend(args.device)
    circuits, info = build_circuits(net, params, backend)
    print(f"Device {backend.name}: depth {info['depth']}, {info['two_qubit_gates']} two-qubit gates, "
          f"measured qubits {info['measured_qubits']}")
    print(f"4 tasks: QAOA {args.shots} shots x2, calibration {args.cal_shots} shots x2. "
          f"Estimated cost: ${cost(args.device, args):.2f}")
    if not args.yes:
        sys.exit("Nothing submitted. Re-run with --yes to submit and pay for these tasks.")
    tasks = {}
    for name, circ in circuits.items():
        job = backend.run(circ, shots=shots_for(name, args), verbatim=True)
        tasks[name] = job.task_id()
        print(f"Submitted {name:<10} task: {tasks[name]}")
        JOBS_FILE.write_text(json.dumps({  # saved after every task, so nothing is lost if one fails
            "device": args.device, "backend": backend.name,
            "submitted_utc": datetime.now(timezone.utc).isoformat(),
            "tasks": tasks, "circuit": info, "shots": args.shots, "cal_shots": args.cal_shots,
            "estimated_cost_usd": round(cost(args.device, args), 2),
        }, indent=2))
    print(f"\nSaved task IDs to {JOBS_FILE.name}. Check later with:  python run_on_braket.py --fetch")


def fetch(args) -> None:
    if not JOBS_FILE.exists():
        sys.exit("No braket_jobs.json yet. Run --submit first.")
    meta = json.loads(JOBS_FILE.read_text())
    net = sq.enterprise_network()
    backend = aws_backend(meta["device"])
    counts = {}
    for name, task_id in meta["tasks"].items():
        job = backend.retrieve_job(task_id)
        status = str(job.status())
        print(f"{name:<10} {status}")
        if "DONE" in status.upper():
            counts[name] = clean_counts(job.result().get_counts(), net.n)
    if len(counts) < len(rh.PUB_NAMES):
        sys.exit("\nNot all tasks are finished yet. Run --fetch again later.")
    table = report(net, meta["device"], counts)
    RESULTS_FILE.write_text(json.dumps({**meta, "counts": counts, "summary": table}, indent=2))
    print(f"\nSaved everything to {RESULTS_FILE.name}.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    for m in ("local", "emulate", "test", "submit", "fetch"):
        mode.add_argument(f"--{m}", action="store_true")
    ap.add_argument("--device", choices=sorted(DEVICES), default="garnet")
    ap.add_argument("--shots", type=int, default=4000, help="shots for each QAOA circuit")
    ap.add_argument("--cal-shots", type=int, default=1000, help="shots for each calibration circuit")
    ap.add_argument("--yes", action="store_true", help="actually submit paid tasks")
    a = ap.parse_args()
    {"local": local, "emulate": emulate, "test": test, "submit": submit, "fetch": fetch}[
        next(m for m in ("local", "emulate", "test", "submit", "fetch") if getattr(a, m))](a)

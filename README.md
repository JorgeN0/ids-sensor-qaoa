# Where should a defender put intrusion-detection sensors?

**USC × IBM Qiskit Fall Fest 2026 — Quantum Optimization track**

A network defender wants every link watched by at least one intrusion-detection (IDS) sensor. A sensor on a device watches all of that device's links, and sensors cost different amounts on different devices. Choosing the cheapest set of devices is the **weighted minimum vertex cover** problem (NP-hard). This project writes it as a QUBO, solves it with **QAOA** in Qiskit, checks every quantum result against an exact classical answer, and tests it on a noisy simulated IBM Heron processor. A script for real IBM hardware is included and tested end to end on the simulated device; real-hardware runs were not completed for this submission.

## Key findings (ideal and noisy simulators)

| 8-device enterprise network | P(sample is optimal) | vs. random guessing | Most likely answer |
|---|---|---|---|
| Random guessing | 0.012 | 1× | — |
| Standard QAOA (minimize average cost) | 0.033 | 2.8× | sensors on **all 8 devices** (cost 20) |
| **CVaR QAOA (α = 0.2)** | **0.203** | **17.3×** | **an optimal placement (cost 8)** |
| CVaR QAOA on noisy simulated IBM Heron (`FakeFez`) | 0.166 | 14.1× | an optimal placement |
| … plus readout-error mitigation | 0.172 | 14.7× | an optimal placement |

1. **Standard QAOA fails on this problem.** With a penalty for unwatched links, the easiest way to lower the *average* cost is to put sensors almost everywhere, so that is what it learns.
2. **Switching the objective to CVaR fixes it** (Barkoutsos et al., 2020): optimizing only the best 20% of outcomes makes the optimal placements the most likely outputs. The trade-off is more invalid samples (P(valid) 0.52 vs 0.97), which are harmless because each sample is checked classically.
3. **It survives realistic noise.** On a noisy model of IBM's 156-qubit Heron chip (depth 134, 57 two-qubit gates), the top answer is still optimal.
4. **Scaling (15 random networks, 6–14 devices):** CVaR beat standard QAOA on every network (15/15). Standard QAOA's most likely answer was never optimal (0/15); CVaR's was optimal on 7/15. As networks grow, the chance of sampling an optimum falls (mean 0.17 at 6 devices → 0.006 at 14) while the advantage over random guessing rises (7× → 58×), and the compiled circuit grows from ~42 to ~142 two-qubit gates at fixed QAOA depth.

**No quantum advantage is claimed.** Brute force solves these networks instantly. The point is to measure, honestly, how well today's QAOA and today's hardware handle a security-relevant optimization problem, and which choices make the difference.

## Method

* **QUBO:** `C(x) = Σ wᵢxᵢ + P · Σ_(u,v) (1−x_u)(1−x_v)` with `xᵢ = 1` meaning "sensor on device i" and penalty `P = Σwᵢ + 1`. Substituting `xᵢ = (1−Zᵢ)/2` gives a diagonal Ising Hamiltonian, one qubit per device (Lucas, 2014, §4.3). The code checks that the Hamiltonian reproduces the QUBO cost for **all 2ⁿ placements**.
* **Ground truth:** brute force over all placements.
* **QAOA:** depth `reps = 2`, angles optimized with COBYLA (6 random starts) on an ideal statevector simulator. Two objectives: the standard expectation value and CVaR with α = 0.2.
* **Noise:** compiled with Qiskit's level-3 preset pass manager for a Heron device model and run through the same Runtime `SamplerV2` code used on real hardware.
* **Error mitigation on hardware:** (a) raw; (b) dynamical decoupling (XpXm) + Pauli twirling of gates and measurements; plus (c) tensored readout-error mitigation from all-0 / all-1 calibration circuits on the same physical qubits, applied in post-processing to both.

## Files

| File | What it is |
|---|---|
| `ids_sensor_qaoa.ipynb` | Main notebook, pre-run with outputs: problem, ground truth, standard vs CVaR, noisy simulation, scaling study, hardware results |
| `sensor_qaoa.py` | Core library: networks, QUBO/Ising, brute force, QAOA + CVaR, readout mitigation |
| `run_on_hardware.py` | Submits / fetches the IBM hardware jobs; `--fake` does a full dry run on a simulated Heron |
| `qaoa_params.json` | Optimized QAOA angles (written by the notebook, used by the hardware script) |
| `scaling_results.json` | Raw numbers from the scaling study |
| `hardware_results.json` | Created by `run_on_hardware.py --fetch` (counts, QPU seconds, summary) |

## How to run

```bash
pip install -r requirements.txt
jupyter notebook ids_sensor_qaoa.ipynb        # reproduces all simulator results (~4 min)
```

Real hardware (uses your IBM Quantum Open Plan minutes):

```bash
export QISKIT_IBM_TOKEN="your-api-key"        # Windows PowerShell: $env:QISKIT_IBM_TOKEN="your-api-key"
python run_on_hardware.py --fake              # optional dry run, no account needed
python run_on_hardware.py --submit            # least-busy machine; saves job IDs to hardware_jobs.json
python run_on_hardware.py --fetch             # run again until both jobs are DONE; prints the results table
```

Then re-run Section 7 of the notebook to add the hardware plot. The API key is read only from the environment and is never written to any file.

## Limitations

* Readout mitigation assumes independent (tensored) readout errors per qubit.
* Dynamical decoupling and twirling only take effect on real hardware; local simulators ignore them.
* QAOA depth is fixed at `reps = 2`; deeper circuits might help on simulators but add noise on hardware.
* The model assumes one sensor watches every link on its device; real deployments also weigh traffic volume, encryption, and sensor capacity.

## References

* E. Farhi, J. Goldstone, S. Gutmann, *A Quantum Approximate Optimization Algorithm*, arXiv:1411.4028 (2014).
* A. Lucas, *Ising formulations of many NP problems*, Frontiers in Physics 2, 5 (2014), arXiv:1302.5843.
* P. Kl. Barkoutsos, G. Nannicini, A. Robert, I. Tavernelli, S. Woerner, *Improving Variational Quantum Optimization using CVaR*, Quantum 4, 256 (2020), arXiv:1907.04769.

## Acknowledgments

Built with Qiskit and IBM Quantum Platform. Developed with AI assistance (Claude), as permitted by the event rules.

Licensed under the MIT License (see `LICENSE`).

# Where should a defender put intrusion-detection sensors?

**USC × IBM Qiskit Fall Fest 2026 — Quantum Optimization track**

A network defender wants every link watched by at least one intrusion-detection (IDS) sensor. A sensor on a device watches all of that device's links, and sensors cost different amounts on different devices. Choosing the cheapest set of devices is the **weighted minimum vertex cover** problem (NP-hard). This project writes it as a QUBO, solves it with **QAOA** in Qiskit, checks every quantum result against an exact classical answer, tests it on noisy simulated quantum chips, and runs it on a real quantum computer (Rigetti Cepheus-1-108Q via Amazon Braket).

## Key findings

| 8-device enterprise network | P(sample is optimal) | vs. random guessing | Most likely answer |
|---|---|---|---|
| Random guessing | 0.012 | 1× | — |
| Standard QAOA (minimize average cost) | 0.033 | 2.8× | sensors on **all 8 devices** (cost 20) |
| **CVaR QAOA (α = 0.2)** | **0.203** | **17.3×** | **an optimal placement (cost 8)** |
| CVaR QAOA on noisy simulated IBM Heron (`FakeFez`) | 0.166 | 14.1× | an optimal placement |
| … plus readout-error mitigation | 0.172 | 14.7× | an optimal placement |
| CVaR QAOA on the Braket emulator of Rigetti Cepheus (+ readout mitigation) | 0.109 | 9.3× | an optimal placement |
| **CVaR QAOA on real Rigetti Cepheus hardware** (+ readout mitigation) | **0.020** | **1.7×** | an invalid placement (output close to random) |
| Standard QAOA on real Rigetti Cepheus hardware (+ readout mitigation) | 0.051 | 4.4× | an invalid placement (output close to random) |

Noisy-simulator numbers vary from run to run (the simulator is not seeded); across runs, CVaR on the Heron model stayed at roughly 13–16× random, with an optimal top answer every time.

1. **Standard QAOA fails on this problem.** With a penalty for unwatched links, the easiest way to lower the *average* cost is to put sensors almost everywhere, so that is what it learns.
2. **Switching the objective to CVaR fixes it** (Barkoutsos et al., 2020): optimizing only the best 20% of outcomes makes the optimal placements the most likely outputs. The trade-off is more invalid samples (P(valid) 0.52 vs 0.97), which are harmless because each sample is checked classically.
3. **It survives simulated noise.** On a noisy model of IBM's 156-qubit Heron chip (depth 134, 57 two-qubit gates), the top answer is still optimal.
4. **Scaling (15 random networks, 6–14 devices):** CVaR beat standard QAOA on every network (15/15). Standard QAOA's most likely answer was never optimal (0/15); CVaR's was optimal on 7/15. As networks grow, the chance of sampling an optimum falls (mean 0.17 at 6 devices → 0.006 at 14) while the advantage over random guessing rises (7× → 58×), and the compiled circuit grows from ~42 to ~142 two-qubit gates at fixed QAOA depth.
5. **On real hardware, noise wins.** On Rigetti Cepheus-1-108Q (Nov 14, 2026; 45 two-qubit gates, depth 135; 4,000 shots per circuit), both QAOA circuits produced close-to-random output. All 256 placements appeared, the spread of outcomes was 7.7 of a possible 8 bits (8 = uniformly random), and CVaR's P(valid) of 0.19 matched random guessing (0.18). Readout was not the cause: the all-0 and all-1 calibration circuits read back correctly (per-qubit readout error 0–8%, mean 3.4%), so the errors built up during the gates. The device's own Braket emulator predicted a clearly better result (P(opt) 0.11, optimal top answer), so the noise models were optimistic for this circuit. CVaR's advantage needs fewer two-qubit gates, or better hardware, to show up on a real device.

**No quantum advantage is claimed.** Brute force solves these networks instantly. The point is to measure, honestly, how well today's QAOA and today's hardware handle a security-relevant optimization problem, and which choices make the difference.

## Method

* **QUBO:** `C(x) = Σ wᵢxᵢ + P · Σ_(u,v) (1−x_u)(1−x_v)` with `xᵢ = 1` meaning "sensor on device i" and penalty `P = Σwᵢ + 1`. Substituting `xᵢ = (1−Zᵢ)/2` gives a diagonal Ising Hamiltonian, one qubit per device (Lucas, 2014, §4.3). The code checks that the Hamiltonian reproduces the QUBO cost for **all 2ⁿ placements**.
* **Ground truth:** brute force over all placements.
* **QAOA:** depth `reps = 2`, angles optimized with COBYLA (6 random starts) on an ideal statevector simulator. Two objectives: the standard expectation value and CVaR with α = 0.2.
* **Noise:** compiled with Qiskit's level-3 preset pass manager for a Heron device model and run through the same Runtime `SamplerV2` code used on real hardware.
* **Real hardware (Amazon Braket):** Qiskit compiles the circuits to the device's native gates and qubit layout (`qiskit-braket-provider`), and they are submitted *verbatim*, so the device runs them exactly as compiled. The same optimized angles are used; no optimization runs on hardware. Tensored readout-error mitigation uses all-0 / all-1 calibration circuits on the same physical qubits as the QAOA circuit.
* **IBM hardware script (prepared, not run):** `run_on_hardware.py` adds dynamical decoupling (XpXm) and Pauli twirling on IBM machines. It was tested end to end on the simulated Heron, but an IBM Quantum account could not be created during the event.

## Files

| File | What it is |
|---|---|
| `ids_sensor_qaoa.ipynb` | Main notebook, pre-run with outputs: problem, ground truth, standard vs CVaR, noisy simulation, scaling study, hardware results |
| `sensor_qaoa.py` | Core library: networks, QUBO/Ising, brute force, QAOA + CVaR, readout mitigation |
| `run_on_braket.py` | Runs the experiment on real hardware through Amazon Braket; `--local` and `--emulate` are free dry runs |
| `braket_results.json` | Real Rigetti Cepheus run: task IDs, raw counts, summary |
| `braket_results_emulator_*.json` | Same circuits on Braket's local emulators of IQM Garnet and Rigetti Cepheus |
| `run_on_hardware.py` | IBM Quantum version (prepared, not run on hardware); `--fake` does a full dry run on a simulated Heron |
| `qaoa_params.json` | Optimized QAOA angles (written by the notebook, used by both hardware scripts) |
| `scaling_results.json` | Raw numbers from the scaling study |

## How to run

```bash
pip install -r requirements.txt
jupyter notebook ids_sensor_qaoa.ipynb        # reproduces all simulator results (~4 min)
```

Real hardware through Amazon Braket (needs AWS credentials, e.g. `aws login`; paid per task and shot):

```bash
python run_on_braket.py --local                        # free: ideal local simulator
python run_on_braket.py --emulate --device cepheus     # free: local emulator of the real device
python run_on_braket.py --submit --device cepheus      # prints the estimated cost and stops
python run_on_braket.py --submit --device cepheus --yes   # submits (about $5.45 at Nov 2026 prices)
python run_on_braket.py --fetch                        # when the tasks finish: saves braket_results.json
```

Check a device's operating hours before submitting: IQM Garnet, for example, only runs on weekdays.

IBM Quantum version (uses Open Plan minutes; the API key is read only from the environment and never written to a file):

```bash
export QISKIT_IBM_TOKEN="your-api-key"
python run_on_hardware.py --fake              # dry run on a simulated Heron, no account needed
python run_on_hardware.py --submit            # then --fetch until both jobs are DONE
```

## Limitations

* Readout mitigation assumes independent (tensored) readout errors per qubit.
* The hardware result is a single run on one device on one day (Rigetti Cepheus, Nov 14, 2026), with no error suppression beyond readout mitigation. Braket does not offer IBM-style dynamical decoupling or twirling, so they were not used.
* Dynamical decoupling and twirling only take effect on real IBM hardware; local simulators ignore them.
* QAOA depth is fixed at `reps = 2`; deeper circuits might help on simulators but add noise on hardware.
* The model assumes one sensor watches every link on its device; real deployments also weigh traffic volume, encryption, and sensor capacity.

## References

* E. Farhi, J. Goldstone, S. Gutmann, *A Quantum Approximate Optimization Algorithm*, arXiv:1411.4028 (2014).
* A. Lucas, *Ising formulations of many NP problems*, Frontiers in Physics 2, 5 (2014), arXiv:1302.5843.
* P. Kl. Barkoutsos, G. Nannicini, A. Robert, I. Tavernelli, S. Woerner, *Improving Variational Quantum Optimization using CVaR*, Quantum 4, 256 (2020), arXiv:1907.04769.

## Acknowledgments

Built with Qiskit (including IBM's Heron noise model from `qiskit-ibm-runtime`) and run on Rigetti hardware through Amazon Braket. Developed with AI assistance (Claude), as permitted by the event rules.

Licensed under the MIT License (see `LICENSE`).

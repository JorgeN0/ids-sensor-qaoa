# Where should a defender put intrusion-detection sensors?

**USC × IBM Qiskit Fall Fest 2026 — Quantum Optimization track**

A network defender wants every link watched by at least one intrusion-detection (IDS) sensor. A sensor on a device watches all of that device's links, and sensors cost different amounts on different devices. Choosing the cheapest set of devices is the **weighted minimum vertex cover** problem (NP-hard). This project writes it as a QUBO, solves it with **QAOA** in Qiskit, checks every quantum result against an exact classical answer, tests it on noisy simulated quantum chips, and runs it on two real quantum computers: IBM's `ibm_fez` (Heron) and Rigetti Cepheus-1-108Q (via Amazon Braket).

## Key findings

| 8-device enterprise network | P(sample is optimal) | vs. random guessing | Most likely answer |
|---|---|---|---|
| Random guessing | 0.012 | 1× | — |
| Standard QAOA (minimize average cost) | 0.033 | 2.8× | sensors on **all 8 devices** (cost 20) |
| **CVaR QAOA (α = 0.2)** | **0.203** | **17.3×** | **an optimal placement (cost 8)** |
| CVaR QAOA on noisy simulated IBM Heron (`FakeFez`) | 0.166 | 14.1× | an optimal placement |
| … plus readout-error mitigation | 0.172 | 14.7× | an optimal placement |
| **CVaR QAOA on real IBM `ibm_fez`**, dynamical decoupling + twirling (+ readout mitigation) | **0.057** | **4.9×** | **an optimal placement** (the top two answers are both optimal) |
| Standard QAOA on real IBM `ibm_fez`, dynamical decoupling + twirling (+ readout mitigation) | 0.016 | 1.3× | sensors on **all 8 devices** (cost 20) |
| CVaR QAOA on real IBM `ibm_fez`, no error suppression (+ readout mitigation) | 0.041 | 3.5× | an invalid placement |
| CVaR QAOA on the Braket emulator of Rigetti Cepheus (+ readout mitigation) | 0.109 | 9.3× | an optimal placement |
| CVaR QAOA on real Rigetti Cepheus (+ readout mitigation; no error suppression available) | 0.020 | 1.7× | an invalid placement (output close to random) |
| Standard QAOA on real Rigetti Cepheus (+ readout mitigation) | 0.051 | 4.4× | an invalid placement (some structure survived) |

Noisy-simulator numbers vary from run to run (the simulator is not seeded); across runs, CVaR on the Heron model stayed at roughly 13–16× random, with an optimal top answer every time. Hardware rows are single runs of 4,000 shots per circuit on Nov 14, 2026.

1. **Standard QAOA fails on this problem.** With a penalty for unwatched links, the easiest way to lower the *average* cost is to put sensors almost everywhere, so that is what it learns.
2. **Switching the objective to CVaR fixes it** (Barkoutsos et al., 2020): optimizing only the best 20% of outcomes makes the optimal placements the most likely outputs. The trade-off is more invalid samples (P(valid) 0.52 vs 0.97), which are harmless because each sample is checked classically.
3. **It survives simulated noise.** On a noisy model of IBM's 156-qubit Heron chip (depth 134, 57 two-qubit gates), the top answer is still optimal.
4. **Scaling (15 random networks, 6–14 devices):** CVaR beat standard QAOA on every network (15/15). Standard QAOA's most likely answer was never optimal (0/15); CVaR's was optimal on 7/15. As networks grow, the chance of sampling an optimum falls (mean 0.17 at 6 devices → 0.006 at 14) while the advantage over random guessing rises (7× → 58×), and the compiled circuit grows from ~42 to ~142 two-qubit gates at fixed QAOA depth.
5. **On real IBM hardware, the result holds once error suppression is on.** On `ibm_fez` (the same 156-qubit Heron chip that `FakeFez` models; 57 two-qubit gates, depth 135; 13 QPU seconds in total), two jobs ran the same circuits: one raw, and one with dynamical decoupling and Pauli twirling.
   * **With error suppression, the simulator story reappears.** CVaR's two most common answers were both optimal placements, and its raw P(opt) of 0.053 (95% CI 0.047–0.061; 0.057 with readout mitigation) is 4.5× random (z = 24). Standard QAOA's most common answer was sensors on all 8 devices, its top four answers all had 6–8 sensors, and its P(opt) was 0.015 (1.3×).
   * **CVaR beat standard QAOA on IBM hardware in both jobs** (P(opt) higher by z = 8.7 raw and z = 9.3 with suppression).
   * **Error suppression mattered.** It raised CVaR's P(opt) from 0.035 to 0.053 (z = 4.0) and moved its top answer from an invalid placement to an optimal one. Without it, CVaR's P(valid) (0.184) was no better than random guessing.
   * **The signal is still weak.** The two optimal answers led by a small margin (89 and 81 shots out of 4,000, against 70 for the next answer), and the simulated chip predicted about three times the real P(opt) (≈ 0.16 vs 0.053).
6. **On Rigetti hardware without error suppression, noise wins, and it hits CVaR hardest.** On Rigetti Cepheus-1-108Q (Nov 14, 2026; 45 two-qubit gates, depth 135; 4,000 shots per circuit), all 256 placements appeared for both circuits and neither top answer was a valid placement.
   * **CVaR's output was essentially random.** Its P(valid) of 0.187 is statistically indistinguishable from random guessing (0.184; z = 0.6), and its P(opt) of 0.018 (95% CI 0.015–0.023) is only 1.6× random. The spread of outcomes was 7.7 of a possible 8 bits (8 = uniformly random).
   * **Standard QAOA kept some structure.** P(valid) 0.27 and P(opt) 0.043 (95% CI 0.037–0.050, 3.7× random) are well above random (z > 13) and above CVaR (z = 6.4).
   * **A likely reason (not tested here):** standard QAOA's coarse lean toward "more sensors" survives noise, while CVaR's sharp peak on the exact optima depends on fine interference that 45 noisy two-qubit gates wipe out.
   * **Readout was not the cause.** The all-0 and all-1 calibration circuits read back correctly (per-qubit readout error 0–8%, mean 3.4%), so the errors built up during the gates.
   * **The noise models were optimistic.** The device's own Braket emulator predicted CVaR P(opt) 0.11 with an optimal top answer.

   Braket offers no IBM-style dynamical decoupling or twirling, and the IBM results suggest that error suppression is what CVaR needs on today's hardware.

**No quantum advantage is claimed.** Brute force solves these networks instantly. The point is to measure, honestly, how well today's QAOA and today's hardware handle a security-relevant optimization problem, and which choices make the difference.

## Method

* **QUBO:** `C(x) = Σ wᵢxᵢ + P · Σ_(u,v) (1−x_u)(1−x_v)` with `xᵢ = 1` meaning "sensor on device i" and penalty `P = Σwᵢ + 1`. Substituting `xᵢ = (1−Zᵢ)/2` gives a diagonal Ising Hamiltonian, one qubit per device (Lucas, 2014, §4.3). The code checks that the Hamiltonian reproduces the QUBO cost for **all 2ⁿ placements**.
* **Ground truth:** brute force over all placements.
* **QAOA:** depth `reps = 2`, angles optimized with COBYLA (6 random starts) on an ideal statevector simulator. Two objectives: the standard expectation value and CVaR with α = 0.2.
* **Noise:** compiled with Qiskit's level-3 preset pass manager for a Heron device model and run through the same Runtime `SamplerV2` code used on real hardware.
* **Real hardware:** the same optimized angles are used everywhere; no optimization runs on hardware. Every hardware run includes all-0 / all-1 calibration circuits on the same physical qubits as the QAOA circuit, for tensored readout-error mitigation in post-processing.
  * **IBM (`run_on_hardware.py`):** Qiskit Runtime `SamplerV2` on the least-busy machine (`ibm_fez`), as two jobs: raw, and with dynamical decoupling (XpXm) plus Pauli twirling of gates and measurements.
  * **Rigetti via Amazon Braket (`run_on_braket.py`):** Qiskit compiles the circuits to the device's native gates and qubit layout (`qiskit-braket-provider`), and they are submitted *verbatim*, so the device runs them exactly as compiled.

## Files

| File | What it is |
|---|---|
| `ids_sensor_qaoa.ipynb` | Main notebook, pre-run with outputs: problem, ground truth, standard vs CVaR, noisy simulation, scaling study, hardware results |
| `sensor_qaoa.py` | Core library: networks, QUBO/Ising, brute force, QAOA + CVaR, readout mitigation |
| `run_on_hardware.py` | Runs the experiment on IBM Quantum hardware (`--submit`, `--fetch`); `--fake` does a full dry run on a simulated Heron |
| `hardware_results.json` | Real IBM `ibm_fez` run: job IDs, raw counts, QPU seconds, summary |
| `run_on_braket.py` | Runs the experiment on real hardware through Amazon Braket; `--local` and `--emulate` are free dry runs |
| `braket_results.json` | Real Rigetti Cepheus run: task IDs, raw counts, summary |
| `braket_results_emulator_*.json` | Same circuits on Braket's local emulators of IQM Garnet and Rigetti Cepheus |
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

IBM Quantum (uses Open Plan minutes; this run used 13 QPU seconds). The API key is read from the `QISKIT_IBM_TOKEN` environment variable, or else from the `apikey.json` file IBM offers when you create a key, at `~/Downloads/apikey.json` or the path in `QISKIT_IBM_KEY_FILE`. **Keep that file outside this folder.** The script refuses to read a key file inside the repository, and `.gitignore` excludes `apikey*.json`.

```bash
python run_on_hardware.py --fake              # dry run on a simulated Heron, no account needed
python run_on_hardware.py --submit            # least-busy machine; saves job IDs to hardware_jobs.json
python run_on_hardware.py --fetch             # run again until both jobs are DONE; saves hardware_results.json
```

## Limitations

* Readout mitigation assumes independent (tensored) readout errors per qubit.
* Each hardware result is a single run on one device on one day (Nov 14, 2026). The IBM and Rigetti runs used different chips, qubit layouts and error-suppression options, so they are not a controlled comparison of the two vendors. Braket does not offer IBM-style dynamical decoupling or twirling.
* Dynamical decoupling and twirling only take effect on real IBM hardware; local simulators ignore them.
* QAOA depth is fixed at `reps = 2`; deeper circuits might help on simulators but add noise on hardware.
* The model assumes one sensor watches every link on its device; real deployments also weigh traffic volume, encryption, and sensor capacity.

## References

* E. Farhi, J. Goldstone, S. Gutmann, *A Quantum Approximate Optimization Algorithm*, arXiv:1411.4028 (2014).
* A. Lucas, *Ising formulations of many NP problems*, Frontiers in Physics 2, 5 (2014), arXiv:1302.5843.
* P. Kl. Barkoutsos, G. Nannicini, A. Robert, I. Tavernelli, S. Woerner, *Improving Variational Quantum Optimization using CVaR*, Quantum 4, 256 (2020), arXiv:1907.04769.

## Acknowledgments

Built with Qiskit and run on IBM Quantum Platform (`ibm_fez`, Open Plan) and on Rigetti hardware through Amazon Braket. Developed with AI assistance (Claude), as permitted by the event rules.

Licensed under the MIT License (see `LICENSE`).

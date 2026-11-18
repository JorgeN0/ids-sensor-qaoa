# Devpost submission text

Copy each section into the matching Devpost field.

---

## Project name

Where Should a Defender Put Intrusion-Detection Sensors?

## Tagline (short description)

Placing network security sensors at the lowest cost with QAOA in Qiskit. Graded against the exact answer and run on real IBM and Rigetti quantum computers.

---

## Inspiration

A data breach now costs about $5 million on average, according to IBM's 2026 Cost of a Data Breach Report. Once attackers get inside a network, they move from machine to machine along its links, and every link nobody watches is a blind spot. Every link should be watched by an intrusion-detection (IDS) sensor, but sensors cost money, and some devices are more expensive to instrument than others. Picking the cheapest set of devices that still watches every link is a real security planning problem. It is also a classic hard optimization problem, weighted minimum vertex cover, which maps naturally onto qubits. I wanted to find out whether QAOA can solve it, and what happens when it runs on real hardware instead of a perfect simulator.

## What it does

The project takes a small enterprise network of 8 devices and 9 links (gateway, firewall, core switch, two access switches, web server, database server, admin PC), each with a sensor cost. It finds the cheapest sensor placement with QAOA, and grades every quantum result against the exact answer from brute force.

- **One qubit per device.** A 1 means "put a sensor here."
- **Cost function:** sensor costs plus a penalty of 21 for every unwatched link. 21 is one more than the cost of every sensor, so leaving a link uncovered is never worth it.
- **The optimum costs 8.** Three of the 256 possible placements reach it, so random guessing finds an optimum 1.2% of the time.

Main findings:

1. **Standard QAOA fails.** On an ideal simulator, its most likely answer is "sensors on all 8 devices" (cost 20). It finds an optimum only 3.3% of the time (2.8× random), because minimizing the *average* cost with a big penalty rewards covering everything.
2. **CVaR QAOA fixes it.** Scoring only the best 20% of samples (CVaR, α = 0.2) makes the optimal placements the most likely answers: P(optimal) = 0.203, 17× random.
3. **It survives a noise model of IBM's Heron chip** (FakeFez, 57 two-qubit gates): P(optimal) ≈ 0.17, 14× random, with an optimal top answer.
4. **On real IBM hardware (`ibm_fez`), with error suppression, CVaR's two most common answers were both optimal placements.** P(optimal) was 0.053, 4.5× random and about 24 standard errors above chance. Standard QAOA's favorite was still "sensors on everything" (0.015). Dynamical decoupling and Pauli twirling raised CVaR from 0.035 to 0.053 and turned its top answer from invalid to optimal.
5. **On Rigetti Cepheus (through Amazon Braket, no comparable error suppression), noise won.** CVaR's output was statistically indistinguishable from random guessing. Standard QAOA kept a little structure, but neither top answer was a valid placement.
6. **Scaling (15 random networks, 6–14 devices, simulator):** CVaR beat standard QAOA on all 15.

**No quantum advantage is claimed.** Brute force solves this size instantly. The project measures how QAOA and today's hardware behave on a security problem, and which choices make the difference.

## How I built it

- **Formulation:** wrote the problem as a QUBO and converted it to an Ising Hamiltonian (8 single-qubit and 9 two-qubit terms). Checked that the Hamiltonian matches the plain cost on all 256 placements.
- **Ground truth:** brute force over every placement, so every quantum answer can be graded exactly.
- **QAOA in Qiskit:** depth 2 (4 angles), angles tuned with COBYLA on an ideal statevector simulator, with two objectives: standard expectation value and CVaR. No optimizer loop runs on hardware.
- **Noise testing:** compiled with Qiskit's level-3 pass manager for the FakeFez Heron model and run through the same Runtime `SamplerV2` code used on hardware.
- **IBM hardware:** Qiskit Runtime on `ibm_fez` (Open Plan, 13 QPU seconds), as two jobs: raw, and with dynamical decoupling plus Pauli twirling. 4,000 shots per circuit.
- **Rigetti hardware:** the same circuits compiled by Qiskit to Rigetti's native gates with `qiskit-braket-provider`, submitted verbatim to Cepheus-1-108Q on Amazon Braket.
- **Readout mitigation:** all-0 and all-1 calibration circuits on the same physical qubits as the QAOA circuit, used to correct the counts.
- **Statistics:** Wilson 95% confidence intervals and z-tests on every hardware comparison. Every hardware number was recomputed from the raw counts with separate code.

## Challenges I ran into

- **Standard QAOA's failure was the first real result.** It took a while to understand why the optimizer kept choosing "sensors everywhere," and that led to CVaR.
- **Getting hardware access.** IBM account signup failed during the event, so I first ran on Rigetti through Amazon Braket, still from Qiskit. The IBM account worked later the same day, and I ran there too. One planned Braket device (IQM Garnet) only runs on weekdays, so those queued tasks were cancelled before they ran.
- **Bit order.** Qiskit puts qubit 0 on the right of a bitstring, and a mistake there would silently ruin every result. I tested it with deliberately shuffled qubits.
- **Interpreting a negative result honestly.** On Rigetti, standard QAOA beat CVaR, but neither worked. Reporting that accurately, rather than hiding it or overclaiming, took careful statistics.
- **Hardware is much noisier than the models.** IBM's noise model predicted about three times the P(optimal) the real chip gave.

## Accomplishments that I'm proud of

- A clear, explainable result: changing the objective turns QAOA from "cover everything" into finding the optimum.
- Running the same experiment on two real quantum computers from two vendors, and showing that error suppression is what let the result survive on IBM.
- Every claim is backed by raw counts, job IDs and confidence intervals in a public repository.

## What I learned

- The objective function matters as much as the circuit. CVaR is a small code change with a large effect.
- On today's hardware, error suppression (dynamical decoupling, twirling) can decide whether an algorithm works at all.
- Noise models are useful for debugging but optimistic. Real hardware has to be measured.
- How QUBOs, Ising Hamiltonians, transpilation and readout mitigation fit together in Qiskit.

## What's next

- Fewer two-qubit gates: QAOA with one layer, or a qubit layout that needs less routing.
- More shots and repeated runs to tighten the error bars.
- IBM's error *mitigation* (not just suppression), and larger networks once circuits are short enough to survive.

## Built with

Qiskit, Qiskit Runtime (SamplerV2), Qiskit Aer, IBM Quantum Platform (`ibm_fez`), Amazon Braket, qiskit-braket-provider, Rigetti Cepheus-1-108Q, Python, NumPy, SciPy (COBYLA), NetworkX, Matplotlib, Jupyter

## Links

- Code, notebook and raw hardware results: https://github.com/JorgeN0/ids-sensor-qaoa

## AI disclosure

Developed with AI assistance (Claude) for setup, coding and analysis, as permitted by the event rules. All results were checked against brute force and recomputed from raw hardware counts.

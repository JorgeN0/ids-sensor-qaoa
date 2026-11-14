# Pitch notes (about 3 minutes)

1. **Hook (15 s).** "Every link in a network should be watched by an intrusion-detection sensor, but sensors cost money. Where do you put them so every link is covered at the lowest cost? That's minimum vertex cover, an NP-hard problem."
2. **Formulation (30 s).** One qubit per device. Cost = sensor costs + a big penalty for every unwatched link. "I checked that my Hamiltonian matches the classical cost on all 256 possible placements, and I solved it exactly by brute force so every quantum answer can be graded."
3. **The failure (30 s).** Show the left bar chart. "Standard QAOA's favorite answer is: put a sensor on everything. With a penalty, that's the easiest way to lower the average, so the optimizer learns it."
4. **The fix (30 s).** Show the right bar chart. "I changed the objective to CVaR, which only scores the best 20% of outcomes. Now the two most likely answers are optimal: 17× better than random guessing, and still 14× on a noisy model of IBM's Heron chip."
5. **Real hardware (30 s).** "Then I ran it on a real Rigetti quantum computer through Amazon Braket. The output was close to random: 45 two-qubit gates were enough for noise to wipe out the pattern. Readout wasn't the problem; my calibration circuits read back correctly. And the device's own emulator predicted it would work, so the noise models are optimistic. Today's hardware is the limit here, not the algorithm."
6. **Scaling and honesty (30 s).** "CVaR beat standard QAOA on all 15 random networks I tested. But the chance of hitting the exact optimum drops as networks grow, and brute force still wins at this size. No quantum advantage claimed; this measures what today's hardware can do."

## Likely judge questions

* **Why not just use brute force?** At this size you should, and I do, as ground truth. The question is how QAOA behaves as a method, which choices make it work, and how hardware noise affects it.
* **Why is the penalty so large?** It guarantees an unwatched link always costs more than covering it. A smaller penalty is valid too, but in my tests it didn't make the top answer optimal.
* **Why α = 0.2?** It's a common choice from the CVaR paper. Smaller α focuses harder on the best outcomes but makes the objective noisier to estimate.
* **Why does CVaR have lower P(valid)?** It trades average quality for a better best tail. Invalid samples are discarded classically, so only the best valid sample matters.
* **What does readout mitigation assume?** That each qubit's readout errors are independent. It's measured with two calibration circuits on the same physical qubits.
* **Why Rigetti and not IBM?** IBM Quantum signup failed on IBM's side during the event, so I ran through Amazon Braket instead, still using Qiskit (the `qiskit-braket-provider`). The IBM version of the script is in the repo and tested on IBM's Heron noise model.
* **How do you know the hardware run wasn't just a bug?** Three checks. (1) The all-0 and all-1 calibration circuits read back correctly, with 0–8% error per qubit. (2) The same script reproduces the ideal results on Braket's local simulator. (3) Bit order was tested with deliberately shuffled qubits. The QAOA output itself was near-uniform: all 256 placements appeared, and the share of valid placements matched random guessing.
* **Standard QAOA scored higher than CVaR on hardware. Doesn't that contradict you?** Both were close to random (1.7× vs 4.4× random, with invalid top answers), so neither result means much. At that noise level the comparison isn't meaningful; the simulator results are where the methods differ.
* **What would you try next?** Fewer two-qubit gates (QAOA with reps = 1, or a qubit layout that needs less routing), IBM's dynamical decoupling and twirling, or a lower-noise device.
* **Why reps = 2?** It's enough to work on the simulator while keeping the circuit at 57 two-qubit gates. Deeper circuits add noise on hardware.

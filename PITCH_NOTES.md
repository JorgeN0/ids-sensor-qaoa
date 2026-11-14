# Pitch notes (about 3 minutes)

1. **Hook (15 s).** "Every link in a network should be watched by an intrusion-detection sensor, but sensors cost money. Where do you put them so every link is covered at the lowest cost? That's minimum vertex cover, an NP-hard problem."
2. **Formulation (30 s).** One qubit per device. Cost = sensor costs + a big penalty for every unwatched link. "I checked that my Hamiltonian matches the classical cost on all 256 possible placements, and I solved it exactly by brute force so every quantum answer can be graded."
3. **The failure (30 s).** Show the left bar chart. "Standard QAOA's favorite answer is: put a sensor on everything. With a penalty, that's the easiest way to lower the average, so the optimizer learns it."
4. **The fix (30 s).** Show the right bar chart. "I changed the objective to CVaR, which only scores the best 20% of outcomes. Now the two most likely answers are optimal: 17× better than random guessing, and still 14× on a noisy model of IBM's Heron chip."
5. **Noise (30 s).** Show the Section 5 noisy-simulation result. "On a noise model of IBM's Heron chip (57 two-qubit gates), the top answer is still optimal, and readout-error mitigation nudges it up. The hardware script is built and tested end to end; it's ready to run on a real machine."
6. **Scaling and honesty (30 s).** "CVaR beat standard QAOA on all 15 random networks I tested. But the chance of hitting the exact optimum drops as networks grow, and brute force still wins at this size. No quantum advantage claimed; this measures what today's hardware can do."

## Likely judge questions

* **Why not just use brute force?** At this size you should, and I do, as ground truth. The question is how QAOA behaves as a method, which choices make it work, and how hardware noise affects it.
* **Why is the penalty so large?** It guarantees an unwatched link always costs more than covering it. A smaller penalty is valid too, but in my tests it didn't make the top answer optimal.
* **Why α = 0.2?** It's a common choice from the CVaR paper. Smaller α focuses harder on the best outcomes but makes the objective noisier to estimate.
* **Why does CVaR have lower P(valid)?** It trades average quality for a better best tail. Invalid samples are discarded classically, so only the best valid sample matters.
* **What does readout mitigation assume?** That each qubit's readout errors are independent. It's measured with two calibration circuits on the same physical qubits.
* **Why no real hardware?** I couldn't get an IBM Quantum account set up in time (signup failed on IBM's side). The rules allow simulator results, and I used a noise model of a real Heron chip run through the same Runtime sampler code, so moving to hardware only means changing the backend.
* **Why reps = 2?** It's enough to work on the simulator while keeping the circuit at 57 two-qubit gates. Deeper circuits add noise on hardware.

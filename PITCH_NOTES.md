# Presentation script (5 min, then questions)

Read this straight through. Each slide ends with a lead-in to the next one: say it, then click. **[NEXT]** marks the click. Take a breath at each one, and slow down on slide 4.

---

## Problem

**Slide 1 · Cover**

According to IBM's own report this year, the average data breach now costs about five million dollars. Once attackers get into a network, they move from machine to machine, so any connection nobody's watching becomes a blind spot. Intrusion-detection sensors catch this, but they cost money, so you can't just put them everywhere. So the real question is: where do you put them so every connection is covered, for the lowest cost? Here's the network I used.

**[NEXT] Slide 2 · The network**

It's got 8 devices and 9 connections, and a sensor costs a different amount on each device. If you put a sensor on a device, it watches every connection coming out of it. This is called minimum vertex cover, and it's NP-hard, so the number of options doubles with every device you add. Since this one's small, I just brute-forced it: the cheapest is 8, and three placements tie. That's my answer key. Now, to hand this to a quantum computer, I had to translate it into qubits.

## Method

**[NEXT] Slide 3 · One qubit per device**

The translation is pretty simple. Every device gets one qubit, and a 1 means there's a sensor on it. The cost is what the sensors cost, plus a penalty of 21 for every connection left open. 21 is more than putting sensors on everything, so leaving a connection open is never worth it. I turned that into a Hamiltonian and checked it gives the right cost for all 256 options. From there, QAOA goes looking for the cheapest answer, so here's how it works.

**[NEXT] Slide 4 · How QAOA works** *(slow down)*

QAOA starts with every option equally likely, and then goes back and forth between two layers. The cost layer marks each option based on how expensive it is, and the mixer shuffles probability around between options. With the right angles, the good answers build up and the bad ones cancel out, so when you measure, you get good answers more often. I used two rounds, so four angles, and on IBM's chip that came out to 57 two-qubit gates. So how do you find those angles? Here's the whole process.

**[NEXT] Slide 5 · How it fits together**

I tune the angles on a normal simulator, so the quantum computer only runs the final circuit, 4,000 times. Then every answer gets checked against the answer key. My score is how often it gives an optimal answer, and random guessing gets about 1 percent. With that in mind, here's what happened on my first try.

## Results

**[NEXT] Slide 6 · Standard QAOA fails**

Even on a perfect simulator, standard QAOA's favorite answer was a sensor on everything, which costs 20 when the best is 8. That's because it optimizes the average, and covering everything is the easiest way to make the average look good. So the problem wasn't the circuit, it was how I was grading it.

**[NEXT] Slide 7 · CVaR fixes it**

So I changed how it gets graded. CVaR only looks at the best 20 percent of results instead of the average. With that one change, its top answer became optimal, 17 times better than random guessing, and still about 14 times with IBM's noise model. But simulators are one thing, so the real test was actual hardware.

**[NEXT] Slide 8 · Real IBM hardware**

I ran it on IBM's real quantum computer, ibm_fez, with error suppression on. Its two most common answers were both optimal, while standard QAOA still picked sensors on everything. It's weaker than the simulator, about 4.5 times better than random, and the lead was small, so I won't say it always finds the answer. But its most common answers were the right ones, and a big reason for that was error suppression.

**[NEXT] Slide 9 · Error suppression**

Error suppression keeps idle qubits from drifting and smooths out gate errors. On the same IBM chip without it, the top answer was wrong. And on a Rigetti chip through Amazon, which didn't have that suppression, the noise just won. It was barely better than random. So here's where all of that leaves me.

## Conclusion

**[NEXT] Slide 10 · Is QAOA good for this?**

So, is QAOA good for this problem? In principle, yes. With CVaR, it found the best placements on the simulator, on all 15 test networks, and on real IBM hardware. In practice, not yet. Brute force solves this instantly, and as networks grow, noise takes over. So I'm not claiming any quantum advantage. But I did learn that two choices decide whether QAOA works at all: how you grade the answers, and whether you suppress the noise. Next, I'd shrink the circuit and try IBM's error mitigation so it can handle bigger networks. So, back to where I started: every unwatched connection is a blind spot. Right now a regular computer still covers them faster, but this is a first step toward quantum computers helping defenders do it. Thank you, and I'm happy to take questions.

---

**Timing:** about 768 words, roughly 5 minutes read at a normal pace. Practice it out loud 2 or 3 times with a timer. If you run over 5 minutes, shorten slide 5 first.

## If they ask...

- **Why not just brute force it?** At this size you should, and I do. It's my answer key. The point is to see how QAOA behaves.
- **What is QAOA?** A short circuit that switches between a cost layer and a mixer, tuned so good answers show up more often.
- **Why a penalty of 21?** So leaving a link open always costs more than covering it.
- **Why the best 20%?** It's a common choice from the CVaR paper. Going lower focuses harder but gets noisier.
- **Why does CVaR give more invalid answers?** It cares about the best answers, not the average. Invalid ones get thrown out anyway.
- **How strong is the IBM result?** 5.3% optimal vs about 1% random, way above chance. But the top answers only won by a few shots (89 and 81 vs 70). So I say "its most common answers were optimal."
- **What did error suppression do?** CVaR went from 3.5% to 5.3% optimal, and its top answer went from wrong to optimal.
- **Why two companies?** IBM signup broke during the event, so I used Rigetti on Amazon first. IBM worked later that day. Different chips, so it's not a fair comparison.
- **Standard beat CVaR on Rigetti?** Yes, but neither one worked there. My guess, not tested: standard's general lean toward more sensors survives noise, CVaR's sharp peak doesn't.
- **How do you know it's not a bug?** The calibration circuits read back fine on both chips, the simulator results match, and I recomputed everything from the raw counts.
- **What does the readout correction assume?** That each qubit's measurement errors are independent. I measure them with an all-0 and an all-1 circuit.
- **Why only two rounds?** That was enough on the simulator. More rounds means more gates, and more gates means more noise.
- **How much hardware did you use?** 13 seconds on IBM's free plan, and about $5 on Rigetti.
- **Did you use AI?** Yes, Claude helped with setup, code and analysis, which the rules allow. I checked everything against brute force and the raw data, and I can explain any part.
- **Where's the $5 million from?** IBM's 2026 Cost of a Data Breach report, the global average.

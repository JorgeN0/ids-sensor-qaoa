# CLAUDE.md — context for AI assistants working on this repo

## What this is
Jorge Naranjo's **solo** entry in the **USC × IBM Qiskit Fall Fest 2026** hackathon (about 20 participants).
- **Track:** Quantum Optimization, **Beginner** level (Beginner and Advanced are judged separately).
- **Schedule:** opening Fri Nov 13 · talks, mini-challenge and office hours Sat Nov 14 · **presentations and judging Sun Nov 15 (morning)**.
- **Organizer rules (info-meeting deck):** must use Qiskit and address the prompt; AI is allowed for setup *and* coding; Open Plan gives **10 minutes** of real-hardware time; simulator-only results are acceptable, but hardware "will make your submission stronger."
- The prompt is open: "choose a problem or method to implement these methods in."

## The project in one paragraph
Where should a defender put intrusion-detection (IDS) sensors so that every network link is watched at the lowest total cost? That is **weighted minimum vertex cover**. It is written as a QUBO (one qubit per device, penalty `P = Σw + 1` per uncovered link), converted to a diagonal Ising Hamiltonian, and solved with **QAOA (reps = 2)**. Every quantum result is graded against an exact brute-force answer. Headline finding: **standard QAOA fails** (its most likely answer is "sensors on every device"), and a **CVaR objective (α = 0.2)** fixes it.

## Files
| File | Role |
|---|---|
| `sensor_qaoa.py` | Core library: `Network`, `enterprise_network()`, `random_network()`, QUBO/Ising (`ising_hamiltonian`, `verify_hamiltonian`), `brute_force`, `optimize_qaoa` (COBYLA, CVaR), `summarize`, readout mitigation (`calibration_circuits`, `readout_matrices`, `mitigate_readout`) |
| `ids_sensor_qaoa.ipynb` | Main notebook, pre-run with outputs. Sections: 1 network, 2 QUBO, 3 brute force, 4 standard vs CVaR, 5 noisy FakeFez + readout mitigation, 6 scaling study, 7 hardware results, 8 conclusions |
| `run_on_hardware.py` | `--submit` (least-busy IBM machine, two jobs: raw and DD+twirling, each with CVaR circuit, standard circuit, all-0 and all-1 calibration), `--fetch` (writes `hardware_results.json`), `--fake` (full dry run on FakeFez) |
| `qaoa_params.json` | Optimized angles written by the notebook and read by the hardware script |
| `scaling_results.json` | Raw scaling-study numbers |
| `hardware_jobs.json` / `hardware_results.json` | Created by `--submit` / `--fetch`. **Real IBM `ibm_fez` run** (job IDs, counts, QPU seconds, summary) |
| `run_on_braket.py` | Amazon Braket version: `--local`, `--emulate`, `--test`, `--submit [--yes]`, `--fetch`. Compiles to native gates, submits verbatim |
| `braket_results.json` | **Real hardware run** on Rigetti Cepheus-1-108Q (counts + summary). Emulator runs: `braket_results_emulator_{garnet,cepheus}.json` |
| `README.md` | Public write-up for judges |
| `PITCH_NOTES.md` | 3-minute talk outline and likely judge questions |

## Conventions that matter (easy to get wrong)
- **Little-endian everywhere:** basis index `k` gives `x[i] = (k >> i) & 1`. A Qiskit bitstring's **rightmost** character is qubit 0, and `int(bitstring, 2)` gives the index.
- `x[i] = 1` means "sensor on device i".
- QAOA angles are optimized on the **ideal statevector simulator only**. No optimizer loop ever runs on hardware.
- The QAOA circuit is decomposed once to `rz/rzz/rx/h`. Simulating the high-level `QAOAAnsatz` directly is about 400× slower.
- In qiskit-ibm-runtime 0.52, `SamplerV2` requires **equal shots across all circuits in one job**, so the calibration circuits use the same 4000 shots.
- Readout calibration circuits are transpiled with `initial_layout = isa_qaoa.layout.final_index_layout()`, so they measure the same physical qubits as the QAOA circuit.
- Local/fake backends **ignore** dynamical decoupling and twirling. Those only take effect on real hardware.

## Verified results (simulators, from the executed notebook; hardware, recomputed from raw counts)
- 8-device enterprise network: optimum cost **8**, 3 optimal placements out of 256. Random guessing P(opt) = 0.0117.
- Standard QAOA: P(opt) **0.033** (2.8× random); most likely answer = all 8 devices (cost 20); P(valid) 0.972.
- CVaR QAOA: P(opt) **0.203** (17.3× random); most likely answer optimal; P(valid) 0.517.
- Noisy FakeFez (Heron, depth 134, 57 two-qubit gates): CVaR P(opt) **0.166 → 0.172** with readout mitigation (14.1× → 14.7×); top answer still optimal; mean readout error about 0.67%.
- **Real IBM hardware (`ibm_fez`, Nov 14, 5:12 PM ET; 57 two-qubit gates, depth 135; 13 QPU s total).** Headline hardware result. With DD + twirling ("mitigated" job): CVaR's **top two answers both optimal** (00111010: 89 shots, 01001110: 81; next invalid 70), raw P(opt) 0.053 (CI 0.047–0.061) → 0.057 with readout (4.5× → 4.9×, z = 24 vs random), P(valid) 0.25. Standard: P(opt) 0.015 (1.3×), top answer all 8 devices (cost 20), top 4 answers all 6–8 sensors. Raw job: CVaR 0.035 (3.0×), top answer invalid, P(valid) 0.184 = random; standard 0.007, top answer cost 19. CVaR > standard in both jobs (z = 8.7 raw, 9.3 mitigated); suppression raised CVaR 0.035 → 0.053 (z = 4.0). Mean readout error 1.6–1.8%. FakeFez predicted ≈ 0.16, so the noise model is ~3× optimistic. Independently recomputed from raw counts. Framing: "the two most common answers were optimal," not "reliably finds the optimum" (margins are small).
- **Real hardware (Rigetti Cepheus-1-108Q, Nov 14; 45 two-qubit gates, depth 135):** noise won, hardest on CVaR. Both top answers invalid. CVaR essentially random: P(valid) 0.187 vs random 0.184 (z = 0.6), P(opt) 0.018 (95% CI 0.015–0.023) → 0.020 with readout (1.7×), entropy 7.7/8 bits. Standard kept some structure: P(valid) 0.27, P(opt) 0.043 (CI 0.037–0.050) → 0.051 (4.4×), above random (z > 13) and above CVaR (z = 6.4). All numbers independently recomputed from raw counts. Calibration fine (per-qubit readout error 0–8%, mean 3.4%). The device's Braket emulator predicted P(opt) 0.11, optimal top answer. Framing: noise wins at 45 two-qubit gates; standard really did beat CVaR on hardware, but neither worked; likely (untested) reason: standard's broad bias survives noise, CVaR's sharp peak doesn't. Don't say 'the comparison isn't meaningful'. AWS task records: all 4 Cepheus tasks COMPLETED 12:02 PM ET, shots 4000/4000/1000/1000; all 5 Garnet tasks CANCELLED. Actual cost not visible (billing via a university payer account); estimate $5.45.
- Noisy-simulator numbers are unseeded and vary per run: FakeFez CVaR P(opt) seen 0.155–0.182 (about 13–16× random), top answer optimal every time.
- Scaling (15 random networks, 6–14 devices): CVaR beat standard **15/15**; standard's top answer optimal 0/15, CVaR's 7/15; mean CVaR P(opt) 0.171 (n = 6) → 0.006 (n = 14); advantage over random 7× → 58×; two-qubit gates about 42 → 142.

## Hard rules
- **The IBM API key never goes in this repository, a notebook output, a commit, or the chat.** `run_on_hardware.py` reads it from `QISKIT_IBM_TOKEN`, or else from IBM's downloaded `apikey.json` **outside the repo** (default `~/Downloads/apikey.json`, or `QISKIT_IBM_KEY_FILE`); it refuses a key file inside the repo, and `.gitignore` has `apikey*.json`. Never print or read the key's value; check only field names and lengths. The repo is public. (On Nov 14 a key was uploaded to GitHub through the web UI; that commit was removed from history with a force-push and the key must be revoked on IBM.)
- **Do not claim quantum advantage.** Brute force solves these sizes instantly; the project measures how QAOA and hardware behave.
- **Scope is frozen.** No new features before judging. Remaining effort goes to hardware results, understanding, and the presentation.
- Claude's cloud workspace **cannot reach IBM Quantum** (proxy 403). Hardware runs happen on Jorge's laptop; Claude writes code and analyzes pasted output.
- Keep the README's AI-assistance disclosure (AI use is allowed; disclosure protects Jorge in Q&A).

## Status (as of Sat Nov 14, evening ET)
- [x] Project built and verified on simulators; notebook pre-run; zip delivered
- [x] Registered for Optimization (Beginner); GitHub account created
- [x] `--fake` verified on Jorge's laptop (Sat Nov 14): depth 134, 57 two-qubit gates; CVaR P(opt) 0.157 → 0.164, top answer optimal; standard 0.032, top answer cost 20. Project files extracted from the zip into this folder; deps in `.venv` (Python 3.14, pinned requirements install fine)
- [x] **Real hardware done via Amazon Braket (Sat Nov 14):** IBM signup failed ("Error on the call to BSS"), so the run went through Jorge's school AWS account (Jorge confirmed the use is authorized). IQM Garnet runs weekdays only, so those queued tasks were cancelled before running (record in `braket_jobs_garnet_cancelled.json`; check the bill anyway). The full run completed on **Rigetti Cepheus-1-108Q** (est. $5.45). Results are in "Verified results" above. README, PITCH_NOTES and notebook Sections 7–8 now describe this run.
  - The AWS account ID is replaced with `REDACTED` in the public `braket_*.json` files. Unredacted originals are kept locally as `*.private.json` (git-ignored); `--fetch` needs `braket_jobs.private.json` renamed back to `braket_jobs.json` to work again.
  - `.venv` also has `qiskit-braket-provider` and `botocore[crt]` (both in requirements.txt now). Installing them downgraded python-dateutil; `run_on_hardware.py --fake` still works.
- [x] **IBM hardware done (Sat Nov 14, evening):** IBM account works now. Ran on `ibm_fez`; results in "Verified results". README, PITCH_NOTES and notebook Section 7 (7a IBM, 7b Rigetti) and 8 updated to lead with IBM.
  - [ ] **Leaked-key cleanup:** the key uploaded to GitHub (created 22:05 UTC, labelled "Main Key") must be deleted on quantum.cloud.ibm.com. The local copy is `~/Downloads/apikey-LEAKED-delete-me.json`, kept only to verify revocation; delete it once IBM rejects it. The new key (created 22:24 UTC, also labelled "Main Key") is now `~/Downloads/apikey.json`. It authenticates and sees the same instance, but `service.job(...)` said "Job not found" right after creation (likely IAM propagation), so recheck.
- [x] Project files committed and pushed to the public repo `JorgeN0/ids-sensor-qaoa`
- [ ] Build presentation slides from real numbers (core story: problem → one qubit per device → standard fails / CVaR fixes → survives noisy simulators → real IBM `ibm_fez` with error suppression: CVaR's top two answers optimal, standard picks all 8; Rigetti without suppression: noise wins; scaling and mitigation as backup slides)
- [ ] Walk through the notebook section by section until every part can be explained without notes; rehearse the pitch 3× with a timer
- [ ] Sunday morning: final push; check the repo link opens in a private browser window

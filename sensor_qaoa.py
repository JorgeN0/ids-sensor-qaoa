"""Intrusion-detection sensor placement with QAOA.

A defender wants every network link watched by at least one IDS sensor. A sensor placed on a
device watches every link attached to that device. Each device has a sensor cost. Choosing the
cheapest set of devices is the weighted minimum vertex cover problem, written here as a QUBO and
solved with QAOA in Qiskit.

Bit / index convention used everywhere in this module (it matches Qiskit):
    x[i] = 1 means "sensor on device i"
    a basis-state index k encodes x little-endian: x[i] = (k >> i) & 1
    a Qiskit bitstring is little-endian too: its rightmost character is qubit 0
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import networkx as nx
import numpy as np
from scipy.optimize import minimize
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import QAOAAnsatz
from qiskit.quantum_info import SparsePauliOp, Statevector


# --------------------------------------------------------------------------- networks
@dataclass
class Network:
    names: list[str]
    weights: np.ndarray  # sensor cost per device
    edges: list[tuple[int, int]]
    roles: list[str] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.names)

    def graph(self) -> nx.Graph:
        g = nx.Graph()
        for i, name in enumerate(self.names):
            g.add_node(i, name=name, weight=float(self.weights[i]))
        g.add_edges_from(self.edges)
        return g


def enterprise_network() -> Network:
    """Small enterprise network: internet gateway -> firewall -> core switch -> access layer."""
    names = ["gateway", "firewall", "core-sw", "access-A", "access-B", "web-srv", "db-srv", "admin-pc"]
    # Sensor costs (relative): the firewall already has monitoring hooks, so it is cheapest;
    # servers need host agents and tuning; the admin workstation is costly to instrument.
    weights = np.array([3, 1, 2, 2, 2, 3, 3, 4], dtype=float)
    edges = [(0, 1), (1, 2), (1, 5), (2, 3), (2, 4), (3, 5), (3, 7), (4, 6), (5, 6)]
    return Network(names, weights, edges)


def random_network(n: int, seed: int, extra_link_fraction: float = 0.35) -> Network:
    """Connected random network: a random spanning tree plus a few redundant links.

    Trees give the hierarchical shape of real networks; the extra links model redundancy.
    """
    rng = np.random.default_rng(seed)
    prufer = rng.integers(0, n, size=n - 2).tolist()
    g = nx.from_prufer_sequence(prufer)
    candidates = [(u, v) for u, v in itertools.combinations(range(n), 2) if not g.has_edge(u, v)]
    n_extra = int(round(extra_link_fraction * n))
    for idx in rng.choice(len(candidates), size=min(n_extra, len(candidates)), replace=False):
        g.add_edge(*candidates[idx])
    weights = rng.integers(1, 5, size=n).astype(float)
    return Network([f"dev{i}" for i in range(n)], weights, sorted(tuple(sorted(e)) for e in g.edges))


# --------------------------------------------------------------------------- QUBO / Ising
def default_penalty(net: Network) -> float:
    """Penalty per uncovered link. Larger than the total sensor cost, so leaving any link
    uncovered is always worse than covering it (safe, conservative choice)."""
    return float(net.weights.sum() + 1)


def index_to_bits(k: int, n: int) -> np.ndarray:
    return np.array([(k >> i) & 1 for i in range(n)])


def bitstring_to_index(s: str) -> int:
    return int(s, 2)  # Qiskit bitstrings are already little-endian strings of the index


def qubo_cost(net: Network, x: np.ndarray, penalty: float) -> float:
    """sum_i w_i x_i + P * sum_(u,v) (1 - x_u)(1 - x_v)"""
    return float(net.weights @ x + penalty * sum((1 - x[u]) * (1 - x[v]) for u, v in net.edges))


def is_cover(net: Network, x: np.ndarray) -> bool:
    return all(x[u] or x[v] for u, v in net.edges)


def ising_hamiltonian(net: Network, penalty: float, normalize: bool = True):
    """Substitute x_i = (1 - Z_i)/2 into the QUBO. Returns (H, scale, offset) such that
    qubo_cost = scale * <H> + offset for every basis state."""
    terms: dict[tuple[int, ...], float] = {}
    offset = 0.0

    def add(qubits, coeff):
        key = tuple(sorted(qubits))
        terms[key] = terms.get(key, 0.0) + coeff

    for i in range(net.n):  # w_i x_i = w_i/2 - (w_i/2) Z_i
        offset += net.weights[i] / 2
        add((i,), -net.weights[i] / 2)
    for u, v in net.edges:  # P (1 - x_u)(1 - x_v) = (P/4)(1 + Z_u)(1 + Z_v)
        offset += penalty / 4
        add((u,), penalty / 4)
        add((v,), penalty / 4)
        add((u, v), penalty / 4)

    scale = max(abs(c) for c in terms.values()) if normalize else 1.0
    sparse = [("Z" * len(q), list(q), c / scale) for q, c in terms.items() if abs(c) > 1e-12]
    return SparsePauliOp.from_sparse_list(sparse, num_qubits=net.n), scale, offset


# --------------------------------------------------------------------------- exact baseline
@dataclass
class ExactSolution:
    qubo_costs: np.ndarray  # QUBO cost of every basis state (index = little-endian bits)
    sensor_costs: np.ndarray  # true sensor cost, +inf where some link is uncovered
    optimum: float
    optimal_indices: np.ndarray

    @property
    def optimal_mask(self) -> np.ndarray:
        mask = np.zeros(len(self.qubo_costs), dtype=bool)
        mask[self.optimal_indices] = True
        return mask


def brute_force(net: Network, penalty: float) -> ExactSolution:
    size = 2**net.n
    qubo = np.empty(size)
    sensor = np.full(size, np.inf)
    for k in range(size):
        x = index_to_bits(k, net.n)
        qubo[k] = qubo_cost(net, x, penalty)
        if is_cover(net, x):
            sensor[k] = net.weights @ x
    opt = sensor.min()
    return ExactSolution(qubo, sensor, float(opt), np.flatnonzero(np.isclose(sensor, opt)))


def verify_hamiltonian(net: Network, penalty: float) -> float:
    """Max |scale*<H> + offset - QUBO cost| over all basis states (should be ~0)."""
    H, scale, offset = ising_hamiltonian(net, penalty)
    diag = np.real(H.to_matrix(sparse=True).diagonal())
    exact = brute_force(net, penalty).qubo_costs
    return float(np.max(np.abs(scale * diag + offset - exact)))


# --------------------------------------------------------------------------- QAOA
def qaoa_circuit(H: SparsePauliOp, reps: int) -> QuantumCircuit:
    """QAOA ansatz decomposed once into simple gates (simulating the high-level
    evolution gates directly is ~400x slower)."""
    return transpile(QAOAAnsatz(H, reps=reps), basis_gates=["rz", "rzz", "rx", "h"], optimization_level=1)


def cvar(probs: np.ndarray, costs: np.ndarray, alpha: float) -> float:
    """Conditional value at risk: mean cost of the best `alpha` fraction of outcomes.
    alpha = 1 gives the ordinary expectation value."""
    if alpha >= 1:
        return float(probs @ costs)
    order = np.argsort(costs)
    p, c = probs[order], costs[order]
    cum = np.cumsum(p)
    k = int(np.searchsorted(cum, alpha))
    take = p[: k + 1].copy()
    take[-1] -= cum[k] - alpha
    return float(take @ c[: k + 1] / alpha)


@dataclass
class QAOAResult:
    reps: int
    alpha: float
    params: np.ndarray
    circuit: QuantumCircuit  # parametrized, no measurements
    probs: np.ndarray  # ideal output distribution at the optimized parameters
    objective: float
    evaluations: int


def optimize_qaoa(net: Network, reps: int = 2, alpha: float = 1.0, penalty: float | None = None,
                  starts: int = 6, maxiter: int = 400, seed: int = 7) -> QAOAResult:
    """Optimize QAOA angles on an ideal statevector simulator (no hardware time used)."""
    penalty = default_penalty(net) if penalty is None else penalty
    H, _, _ = ising_hamiltonian(net, penalty)
    circ = qaoa_circuit(H, reps)
    costs = brute_force(net, penalty).qubo_costs  # H is diagonal: <H> is a weighted sum of these
    rng = np.random.default_rng(seed)
    evals = 0

    def objective(theta):
        nonlocal evals
        evals += 1
        probs = Statevector(circ.assign_parameters(theta)).probabilities()
        return cvar(probs, costs, alpha)

    best = None
    for _ in range(starts):
        res = minimize(objective, rng.uniform(0, np.pi, circ.num_parameters), method="COBYLA",
                       options={"maxiter": maxiter})
        if best is None or res.fun < best.fun:
            best = res
    probs = Statevector(circ.assign_parameters(best.x)).probabilities()
    return QAOAResult(reps, alpha, best.x, circ, probs, float(best.fun), evals)


def measured(circuit: QuantumCircuit) -> QuantumCircuit:
    c = circuit.copy()
    c.measure_all()
    return c


# --------------------------------------------------------------------------- analysis
def counts_to_probs(counts: dict[str, int], n: int) -> np.ndarray:
    probs = np.zeros(2**n)
    total = sum(counts.values())
    for s, v in counts.items():
        probs[bitstring_to_index(s)] += v / total
    return probs


@dataclass
class Summary:
    p_optimal: float
    p_valid: float  # every link covered
    most_likely_cost: float  # true sensor cost of the most likely outcome (inf if it leaves a link open)
    most_likely_is_optimal: bool
    random_guess_p_optimal: float

    @property
    def advantage_over_random(self) -> float:
        return self.p_optimal / self.random_guess_p_optimal


def summarize(probs: np.ndarray, exact: ExactSolution) -> Summary:
    ml = int(np.argmax(probs))
    return Summary(
        p_optimal=float(probs[exact.optimal_mask].sum()),
        p_valid=float(probs[np.isfinite(exact.sensor_costs)].sum()),
        most_likely_cost=float(exact.sensor_costs[ml]),
        most_likely_is_optimal=bool(exact.optimal_mask[ml]),
        random_guess_p_optimal=len(exact.optimal_indices) / len(probs),
    )


def placement(net: Network, index: int) -> list[str]:
    x = index_to_bits(index, net.n)
    return [net.names[i] for i in range(net.n) if x[i]]


# --------------------------------------------------------------------------- readout mitigation
def calibration_circuits(n: int) -> list[QuantumCircuit]:
    """Prepare all-0 and all-1 and measure: gives each qubit's readout error rates."""
    zero = QuantumCircuit(n, name="cal_all0")
    zero.measure_all()
    one = QuantumCircuit(n, name="cal_all1")
    one.x(range(n))
    one.measure_all()
    return [zero, one]


def readout_matrices(counts_all0: dict[str, int], counts_all1: dict[str, int], n: int) -> list[np.ndarray]:
    """Per-qubit 2x2 assignment matrices A_q[measured, prepared] (tensored-noise assumption)."""
    def p_read_one(counts, q):
        total = sum(counts.values())
        return sum(v for s, v in counts.items() if s[::-1][q] == "1") / total

    mats = []
    for q in range(n):
        e01 = p_read_one(counts_all0, q)  # prepared 0, read 1
        e10 = 1 - p_read_one(counts_all1, q)  # prepared 1, read 0
        mats.append(np.array([[1 - e01, e10], [e01, 1 - e10]]))
    return mats


def mitigate_readout(probs: np.ndarray, mats: list[np.ndarray]) -> np.ndarray:
    """Apply the inverse of each qubit's assignment matrix, then project back onto valid
    probabilities (clip negatives, renormalize)."""
    n = len(mats)
    tensor = probs.reshape((2,) * n)  # axis j <-> qubit n-1-j (little-endian index)
    for q, a in enumerate(mats):
        axis = n - 1 - q
        tensor = np.moveaxis(np.tensordot(np.linalg.inv(a), tensor, axes=([1], [axis])), 0, axis)
    out = np.clip(tensor.reshape(-1), 0, None)
    return out / out.sum()

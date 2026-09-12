"""
ATSP - State and Result Data Structures
Defines uniform data models for TSP Oracle results, Solver results, and performance metrics.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional, Dict, Set


class OracleStatus(Enum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


class SolverStatus(Enum):
    EXACT_SOL_FOUND = "EXACT: OPTIMAL TOUR FOUND"
    EXACT_NO_SOL = "EXACT: NO HAMILTONIAN TOUR"
    UNKNOWN_TIMEOUT = "INCOMPLETE: TIME LIMIT REACHED"
    UNKNOWN_MEMORY = "INCOMPLETE: MEMORY LIMIT REACHED"
    UNKNOWN_RESOURCE = "INCOMPLETE: RESOURCE BUDGET REACHED"


class SearchMode(Enum):
    SHORTEST_TOUR = "Find Shortest Tour (Optimal)"
    DECISION_ONLY = "Decision Only (Tour <= Budget?)"
    ALL_OPTIMAL_TOURS = "Enumerate All Optimal Tours"


@dataclass
class OracleResult:
    status: OracleStatus
    tour_witness: Optional[List[int]] = None
    cost_witness: Optional[float] = None
    reason: str = ""
    cost: float = 0.0


@dataclass
class TSPStats:
    nodes: int = 0
    comparisons: int = 0
    bound_checks: int = 0
    pruned: int = 0
    memo_hits: int = 0
    bound_improvements: int = 0
    elapsed: float = 0.0
    memory_peak_bytes: int = 0
    dead_states_peak: int = 0

    mst_computations: int = 0
    held_karp_calls: int = 0
    degree_prunes: int = 0
    bound_prunes: int = 0
    mst_prunes: int = 0

    oracle_calls: Dict[str, int] = field(default_factory=lambda: {
        "bound": 0, "mst": 0, "degree": 0, "nearest_neighbor": 0, "held_karp": 0
    })
    oracle_feasible: Dict[str, int] = field(default_factory=lambda: {
        "bound": 0, "mst": 0, "degree": 0, "nearest_neighbor": 0, "held_karp": 0
    })
    oracle_infeasible: Dict[str, int] = field(default_factory=lambda: {
        "bound": 0, "mst": 0, "degree": 0, "nearest_neighbor": 0, "held_karp": 0
    })
    oracle_unknown: Dict[str, int] = field(default_factory=lambda: {
        "bound": 0, "mst": 0, "degree": 0, "nearest_neighbor": 0, "held_karp": 0
    })
    oracle_time: Dict[str, float] = field(default_factory=lambda: {
        "bound": 0.0, "mst": 0.0, "degree": 0.0, "nearest_neighbor": 0.0, "held_karp": 0.0
    })
    oracle_useful_prunes: Dict[str, int] = field(default_factory=lambda: {
        "bound": 0, "mst": 0, "degree": 0, "nearest_neighbor": 0, "held_karp": 0
    })

    @property
    def work_units(self) -> int:
        return (
            self.nodes
            + self.comparisons
            + self.bound_checks
            + self.pruned
            + self.memo_hits
            + self.mst_computations
        )

    def add(self, other: "TSPStats"):
        self.nodes += other.nodes
        self.comparisons += other.comparisons
        self.bound_checks += other.bound_checks
        self.pruned += other.pruned
        self.memo_hits += other.memo_hits
        self.bound_improvements += other.bound_improvements
        self.mst_computations += other.mst_computations
        self.held_karp_calls += other.held_karp_calls
        self.degree_prunes += other.degree_prunes
        self.bound_prunes += other.bound_prunes
        self.mst_prunes += other.mst_prunes
        self.memory_peak_bytes = max(self.memory_peak_bytes, other.memory_peak_bytes)
        self.dead_states_peak = max(self.dead_states_peak, other.dead_states_peak)

        for k in set(self.oracle_calls.keys()).union(other.oracle_calls.keys()):
            self.oracle_calls[k] = self.oracle_calls.get(k, 0) + other.oracle_calls.get(k, 0)
            self.oracle_feasible[k] = self.oracle_feasible.get(k, 0) + other.oracle_feasible.get(k, 0)
            self.oracle_infeasible[k] = self.oracle_infeasible.get(k, 0) + other.oracle_infeasible.get(k, 0)
            self.oracle_unknown[k] = self.oracle_unknown.get(k, 0) + other.oracle_unknown.get(k, 0)
            self.oracle_time[k] = self.oracle_time.get(k, 0.0) + other.oracle_time.get(k, 0.0)
            self.oracle_useful_prunes[k] = self.oracle_useful_prunes.get(k, 0) + other.oracle_useful_prunes.get(k, 0)


@dataclass
class TSPResult:
    status: SolverStatus
    tours: List[List[int]]
    best_cost: float
    stats: TSPStats
    elapsed: float
    algorithm_name: str
    is_exact: bool
    diagnostic_message: str = ""
    ranked_tours: List[Tuple[List[int], float]] = field(default_factory=list)

    @property
    def has_solution(self) -> bool:
        return len(self.tours) > 0 and self.best_cost < float("inf")

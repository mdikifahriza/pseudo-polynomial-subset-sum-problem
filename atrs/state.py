"""
ATRS - State and Result Data Structures
Defines uniform data models for Oracle results, Solver results, and performance metrics.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional, Dict, Set


class OracleStatus(Enum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


class SolverStatus(Enum):
    EXACT_SOL_FOUND = "EXACT: SOLUTION FOUND"
    EXACT_NO_SOL = "EXACT: NO SOLUTION"
    UNKNOWN_TIMEOUT = "INCOMPLETE: TIME LIMIT REACHED"
    UNKNOWN_MEMORY = "INCOMPLETE: MEMORY LIMIT REACHED"
    UNKNOWN_RESOURCE = "INCOMPLETE: RESOURCE BUDGET REACHED"


class SearchMode(Enum):
    FIRST_SOLUTION = "Find First Solution"
    DECISION_ONLY = "Decision Only (Exists?)"
    ALL_SOLUTIONS = "Enumerate All Solutions"


@dataclass
class OracleResult:
    status: OracleStatus
    witness: Optional[List[int]] = None
    reason: str = ""
    cost: float = 0.0


@dataclass
class Stats:
    nodes: int = 0
    comparisons: int = 0
    arithmetic: int = 0
    bound_checks: int = 0
    pruned: int = 0
    memo_hits: int = 0
    solutions_count: int = 0
    elapsed: float = 0.0
    memory_peak_bytes: int = 0
    dead_states_peak: int = 0

    upper_prunes: int = 0
    lower_prunes: int = 0
    gcd_prunes: int = 0
    cardinality_prunes: int = 0
    oracle_prunes: int = 0
    trivial_hits: int = 0

    oracle_calls: Dict[str, int] = field(default_factory=lambda: {
        "arithmetic": 0, "bitset": 0, "mitm": 0, "dfs": 0, "trivial": 0
    })
    oracle_feasible: Dict[str, int] = field(default_factory=lambda: {
        "arithmetic": 0, "bitset": 0, "mitm": 0, "dfs": 0, "trivial": 0
    })
    oracle_infeasible: Dict[str, int] = field(default_factory=lambda: {
        "arithmetic": 0, "bitset": 0, "mitm": 0, "dfs": 0, "trivial": 0
    })
    oracle_unknown: Dict[str, int] = field(default_factory=lambda: {
        "arithmetic": 0, "bitset": 0, "mitm": 0, "dfs": 0, "trivial": 0
    })
    oracle_time: Dict[str, float] = field(default_factory=lambda: {
        "arithmetic": 0.0, "bitset": 0.0, "mitm": 0.0, "dfs": 0.0, "trivial": 0.0
    })
    oracle_useful_prunes: Dict[str, int] = field(default_factory=lambda: {
        "arithmetic": 0, "bitset": 0, "mitm": 0, "dfs": 0, "trivial": 0
    })

    bitset_bits_processed: int = 0
    mitm_states_generated: int = 0

    @property
    def work_units(self) -> int:
        return (
            self.nodes
            + self.arithmetic
            + self.comparisons
            + self.bound_checks
            + self.pruned
            + self.memo_hits
        )

    def add(self, other: "Stats"):
        self.nodes += other.nodes
        self.comparisons += other.comparisons
        self.arithmetic += other.arithmetic
        self.bound_checks += other.bound_checks
        self.pruned += other.pruned
        self.memo_hits += other.memo_hits
        self.solutions_count += other.solutions_count
        self.upper_prunes += other.upper_prunes
        self.lower_prunes += other.lower_prunes
        self.gcd_prunes += other.gcd_prunes
        self.cardinality_prunes += other.cardinality_prunes
        self.oracle_prunes += other.oracle_prunes
        self.trivial_hits += other.trivial_hits
        self.memory_peak_bytes = max(self.memory_peak_bytes, other.memory_peak_bytes)
        self.dead_states_peak = max(self.dead_states_peak, other.dead_states_peak)
        self.bitset_bits_processed += other.bitset_bits_processed
        self.mitm_states_generated += other.mitm_states_generated

        for k in set(self.oracle_calls.keys()).union(other.oracle_calls.keys()):
            self.oracle_calls[k] = self.oracle_calls.get(k, 0) + other.oracle_calls.get(k, 0)
            self.oracle_feasible[k] = self.oracle_feasible.get(k, 0) + other.oracle_feasible.get(k, 0)
            self.oracle_infeasible[k] = self.oracle_infeasible.get(k, 0) + other.oracle_infeasible.get(k, 0)
            self.oracle_unknown[k] = self.oracle_unknown.get(k, 0) + other.oracle_unknown.get(k, 0)
            self.oracle_time[k] = self.oracle_time.get(k, 0.0) + other.oracle_time.get(k, 0.0)
            self.oracle_useful_prunes[k] = self.oracle_useful_prunes.get(k, 0) + other.oracle_useful_prunes.get(k, 0)


@dataclass
class SolverResult:
    status: SolverStatus
    solutions: List[Tuple[int, ...]]
    stats: Stats
    elapsed: float
    algorithm_name: str
    is_exact: bool
    diagnostic_message: str = ""

    @property
    def has_solution(self) -> bool:
        return len(self.solutions) > 0 or self.status == SolverStatus.EXACT_SOL_FOUND

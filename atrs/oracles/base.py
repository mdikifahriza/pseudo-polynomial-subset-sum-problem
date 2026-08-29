"""
ATRS - Base Feasibility Oracle Interface
"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from ..state import OracleResult, Stats
from ..resource_guard import ResourceGuard

class BaseFeasibilityOracle(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def query(
        self,
        values: List[int],
        start_idx: int,
        remainder: int,
        suffix_sum: List[int],
        suffix_gcd: List[int],
        stats: Stats,
        guard: ResourceGuard
    ) -> OracleResult:
        """
        Evaluate feasibility of reaching 'remainder' from suffix values[start_idx:].
        Must return FEASIBLE, INFEASIBLE, or UNKNOWN.
        """
        pass

    @abstractmethod
    def estimate_cost(
        self,
        values: List[int],
        start_idx: int,
        remainder: int,
        suffix_sum: List[int],
        guard: ResourceGuard
    ) -> Tuple[float, float, bool]:
        """
        Returns (estimated_time_units, estimated_memory_bytes, is_budget_ok).
        """
        pass

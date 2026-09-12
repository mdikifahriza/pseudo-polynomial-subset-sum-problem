"""
ATSP - Base Feasibility Oracle Interface
"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Set
from ..state import OracleResult, TSPStats
from ..resource_guard import ResourceGuard


class BaseTSPOracle(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def query(
        self,
        adj: List[List[float]],
        current_city: int,
        visited_mask: int,
        unvisited: Tuple[int, ...],
        cost_so_far: float,
        best_known: float,
        min_out_edges: List[float],
        min_in_edges: List[float],
        stats: TSPStats,
        guard: ResourceGuard,
    ) -> OracleResult:
        """
        Evaluate feasibility / lower-bound of completing a tour from current state.
        Returns FEASIBLE, INFEASIBLE, or UNKNOWN.
        """
        pass

    @abstractmethod
    def estimate_cost(
        self,
        n_remaining: int,
        guard: ResourceGuard,
    ) -> Tuple[float, float, bool]:
        """
        Returns (estimated_time_units, estimated_memory_bytes, is_budget_ok).
        """
        pass

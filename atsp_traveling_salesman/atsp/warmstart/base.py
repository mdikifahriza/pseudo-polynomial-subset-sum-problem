"""
ATSP - Base Interface for Warm-Start Heuristic Solvers
Provides initial tight upper bounds before exact search.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from ..resource_guard import ResourceGuard


class BaseWarmStart(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(
        self,
        adj: List[List[float]],
        initial_tour: List[int],
        initial_cost: float,
        time_budget_sec: float,
        guard: Optional[ResourceGuard] = None,
    ) -> Tuple[List[int], float]:
        """
        Executes heuristic refinement on initial_tour within time_budget_sec.
        Guarantees that the returned cost is <= initial_cost and the tour is valid.
        Returns: (best_tour, best_cost)
        """
        pass

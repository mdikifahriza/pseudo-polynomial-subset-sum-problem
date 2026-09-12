"""
ATSP - Adaptive Oracle Manager & Scheduler
Selects and orders TSP feasibility and lower-bound oracles dynamically based on
subproblem size, resource budgets, and live runtime performance feedback.
"""
from typing import List, Tuple, Optional, Dict
from .state import TSPStats, OracleResult, OracleStatus
from .resource_guard import ResourceGuard
from .oracles import (
    BaseTSPOracle,
    BoundCheckOracle,
    MSTLowerBoundOracle,
    DegreeOracle,
    NearestNeighborOracle,
    HeldKarpOracle,
)


class AdaptiveTSPOracleManager:
    def __init__(
        self,
        max_held_karp_cities: int = 10,
        enable_adaptive_learning: bool = True,
    ):
        self.max_held_karp_cities = max_held_karp_cities
        self.enable_adaptive_learning = enable_adaptive_learning

        self.oracle_bound = BoundCheckOracle()
        self.oracle_nn = NearestNeighborOracle()
        self.oracle_degree = DegreeOracle()
        self.oracle_mst = MSTLowerBoundOracle()
        self.oracle_held_karp = HeldKarpOracle(max_dp_cities=max_held_karp_cities)

        self.priority_weights: Dict[str, float] = {
            "bound": 1.0,
            "mst": 1.0,
            "degree": 1.0,
            "nearest_neighbor": 1.0,
            "held_karp": 1.0,
        }

    def choose_oracle_pipeline(
        self,
        n_remaining: int,
        stats: TSPStats,
        guard: ResourceGuard,
    ) -> List[BaseTSPOracle]:
        """
        Determines the sequence of TSP oracles to query for the current subtree state.
        Always starts with lightweight bounds.
        """
        pipeline: List[BaseTSPOracle] = [self.oracle_bound, self.oracle_nn]

        if self.enable_adaptive_learning:
            self._update_adaptive_weights(stats)

        # For very small subtrees (k <= 2), Nearest Neighbor already resolved it trivially
        if n_remaining <= 2:
            return pipeline

        # Degree check is cheap and useful
        pipeline.append(self.oracle_degree)

        # MST Lower Bound is O(k^2) - always evaluate to prune before any expensive DP
        pipeline.append(self.oracle_mst)

        # Held-Karp exact DP is only queried if k <= max_held_karp_cities and unpruned
        if n_remaining <= self.max_held_karp_cities and guard.is_held_karp_allowed(n_remaining):
            pipeline.append(self.oracle_held_karp)

        return pipeline

    def _update_adaptive_weights(self, stats: TSPStats):
        """
        Adjusts priority weights dynamically based on historical utility and compute cost.
        """
        for key in ["mst", "held_karp", "degree"]:
            calls = stats.oracle_calls.get(key, 0)
            time_spent = stats.oracle_time.get(key, 0.0)
            useful = stats.oracle_useful_prunes.get(key, 0)

            if calls >= 5 and time_spent > 0.02:
                efficiency = useful / calls
                if efficiency < 0.1:
                    self.priority_weights[key] = max(0.1, self.priority_weights[key] * 0.8)
                elif efficiency > 0.6:
                    self.priority_weights[key] = min(3.0, self.priority_weights[key] * 1.2)

    def evaluate_state(
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
        Executes oracles along the adaptive pipeline until a decisive answer (FEASIBLE or INFEASIBLE)
        is found, or all return UNKNOWN.
        """
        k = len(unvisited)
        pipeline = self.choose_oracle_pipeline(k, stats, guard)

        last_result = OracleResult(OracleStatus.UNKNOWN, reason="NO_ORACLE_DECIDED")
        for oracle in pipeline:
            res = oracle.query(
                adj,
                current_city,
                visited_mask,
                unvisited,
                cost_so_far,
                best_known,
                min_out_edges,
                min_in_edges,
                stats,
                guard,
            )
            if res.status in (OracleStatus.FEASIBLE, OracleStatus.INFEASIBLE):
                return res
            last_result = res

        return last_result

"""
ATSP - Oracle B: Bound Check & Minimum Out-Edge Sum Oracle
Evaluates immediate necessary conditions and lower bounds on accumulated cost.
"""
import time
from typing import List, Tuple
from .base import BaseTSPOracle
from ..state import OracleResult, OracleStatus, TSPStats
from ..resource_guard import ResourceGuard


class BoundCheckOracle(BaseTSPOracle):
    def __init__(self):
        super().__init__("bound")

    def estimate_cost(self, n_remaining: int, guard: ResourceGuard) -> Tuple[float, float, bool]:
        return (1.0, 32.0, True)

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
        t0 = time.perf_counter()
        stats.oracle_calls["bound"] += 1
        stats.bound_checks += 1

        # 1. Simple Bound Exceeded
        stats.comparisons += 1
        if cost_so_far >= best_known:
            stats.pruned += 1
            stats.bound_prunes += 1
            stats.oracle_infeasible["bound"] += 1
            stats.oracle_useful_prunes["bound"] += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["bound"] += dur
            return OracleResult(OracleStatus.INFEASIBLE, reason="COST_EXCEEDS_BEST_KNOWN", cost=dur)

        # 2. Min-Out-Edge Sum Lower Bound:
        # Every unvisited vertex plus the current vertex must leave via at least their min_out_edge.
        stats.bound_checks += 1
        stats.comparisons += 1
        lb = cost_so_far + min_out_edges[current_city]
        for u in unvisited:
            lb += min_out_edges[u]

        if lb >= best_known:
            stats.pruned += 1
            stats.bound_prunes += 1
            stats.oracle_infeasible["bound"] += 1
            stats.oracle_useful_prunes["bound"] += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["bound"] += dur
            return OracleResult(OracleStatus.INFEASIBLE, reason="MIN_OUT_EDGE_LB_EXCEEDED", cost=dur)

        dur = time.perf_counter() - t0
        stats.oracle_time["bound"] += dur
        stats.oracle_unknown["bound"] += 1
        return OracleResult(OracleStatus.UNKNOWN, reason="BOUND_CHECKS_PASSED", cost=dur)

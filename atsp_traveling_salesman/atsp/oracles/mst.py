"""
ATSP - Oracle M: 1-Tree & Minimum Spanning Tree (MST) Lower Bound Oracle
Computes exact 1-tree relaxation bounds with LRU caching.
"""
import time
from typing import List, Tuple, Dict
from .base import BaseTSPOracle
from ..state import OracleResult, OracleStatus, TSPStats
from ..resource_guard import ResourceGuard
from ..preprocess import compute_mst_cost


class MSTLowerBoundOracle(BaseTSPOracle):
    def __init__(self, max_cache_entries: int = 50_000):
        super().__init__("mst")
        self.mst_cache: Dict[Tuple[int, ...], float] = {}
        self.max_cache_entries = max_cache_entries

    def estimate_cost(self, n_remaining: int, guard: ResourceGuard) -> Tuple[float, float, bool]:
        # Cost of Prim's algorithm is O(k^2) where k = n_remaining
        k = n_remaining
        time_units = float(k * k)
        mem_bytes = float(len(self.mst_cache) * 48)
        return (time_units, mem_bytes, True)

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
        stats.oracle_calls["mst"] += 1
        stats.bound_checks += 1
        k = len(unvisited)

        if k == 0:
            # Only need to return to origin 0
            dur = time.perf_counter() - t0
            stats.oracle_time["mst"] += dur
            return OracleResult(OracleStatus.UNKNOWN, reason="NO_UNVISITED_CITIES", cost=dur)

        # 1. Look up or compute MST for unvisited set
        if unvisited in self.mst_cache:
            stats.memo_hits += 1
            mst_cost = self.mst_cache[unvisited]
        else:
            stats.mst_computations += 1
            mst_cost = compute_mst_cost(adj, unvisited)
            if len(self.mst_cache) < self.max_cache_entries:
                self.mst_cache[unvisited] = mst_cost

        if mst_cost == float("inf"):
            stats.pruned += 1
            stats.mst_prunes += 1
            stats.oracle_infeasible["mst"] += 1
            stats.oracle_useful_prunes["mst"] += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["mst"] += dur
            return OracleResult(OracleStatus.INFEASIBLE, reason="UNVISITED_GRAPH_DISCONNECTED", cost=dur)

        # 2. Connection from current_city to unvisited set
        min_to_unvisited = float("inf")
        min_to_origin = float("inf")

        for u in unvisited:
            w_cur = adj[current_city][u]
            if w_cur < min_to_unvisited:
                min_to_unvisited = w_cur

            w_orig = adj[u][0]
            if w_orig < min_to_origin:
                min_to_origin = w_orig

        # 1-Tree Lower Bound
        total_lb = cost_so_far + mst_cost + min_to_unvisited + min_to_origin

        stats.comparisons += 1
        if total_lb >= best_known:
            stats.pruned += 1
            stats.mst_prunes += 1
            stats.oracle_infeasible["mst"] += 1
            stats.oracle_useful_prunes["mst"] += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["mst"] += dur
            return OracleResult(OracleStatus.INFEASIBLE, reason="MST_1TREE_LB_EXCEEDED", cost=dur)

        dur = time.perf_counter() - t0
        stats.oracle_time["mst"] += dur
        stats.oracle_unknown["mst"] += 1
        return OracleResult(OracleStatus.UNKNOWN, reason="MST_LB_PASSED", cost=dur)

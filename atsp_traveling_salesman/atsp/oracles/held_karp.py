"""
ATSP - Oracle HK: Held-Karp Exact DP Subtree Oracle
Solves remaining subproblems (k <= 16 cities) exactly in O(2^k * k^2) using Dynamic Programming.
"""
import time
from typing import List, Tuple, Dict, Optional
from .base import BaseTSPOracle
from ..state import OracleResult, OracleStatus, TSPStats
from ..resource_guard import ResourceGuard


class HeldKarpOracle(BaseTSPOracle):
    def __init__(self, max_dp_cities: int = 16):
        super().__init__("held_karp")
        self.max_dp_cities = max_dp_cities

    def estimate_cost(self, n_remaining: int, guard: ResourceGuard) -> Tuple[float, float, bool]:
        if n_remaining > self.max_dp_cities:
            return (float("inf"), float("inf"), False)
        states = (1 << n_remaining) * n_remaining
        time_units = float(states * n_remaining)
        mem_bytes = float(states * 24)
        is_ok = guard.is_held_karp_allowed(n_remaining)
        return (time_units, mem_bytes, is_ok)

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
        stats.oracle_calls["held_karp"] += 1
        stats.held_karp_calls += 1
        k = len(unvisited)

        if k == 0:
            dur = time.perf_counter() - t0
            stats.oracle_time["held_karp"] += dur
            return OracleResult(OracleStatus.UNKNOWN, reason="NO_UNVISITED_CITIES", cost=dur)

        if k > self.max_dp_cities or not guard.is_held_karp_allowed(k):
            dur = time.perf_counter() - t0
            stats.oracle_time["held_karp"] += dur
            stats.oracle_unknown["held_karp"] += 1
            return OracleResult(OracleStatus.UNKNOWN, reason="SUBTREE_TOO_LARGE_FOR_HK", cost=dur)

        nodes = list(unvisited)
        # Mapping from index in [0..k-1] to city id
        # dp[mask][i] = min cost to visit subset of 'unvisited' defined by mask, ending at nodes[i]
        # with start from current_city.
        dp: List[List[float]] = [[float("inf")] * k for _ in range(1 << k)]
        parent: List[List[int]] = [[-1] * k for _ in range(1 << k)]

        # Base cases: start from current_city to each unvisited node
        for i in range(k):
            d = adj[current_city][nodes[i]]
            if d < float("inf"):
                dp[1 << i][i] = d

        for mask in range(1, 1 << k):
            for i in range(k):
                if not (mask & (1 << i)):
                    continue
                c_cur = dp[mask][i]
                if c_cur >= float("inf"):
                    continue

                for j in range(k):
                    if mask & (1 << j):
                        continue
                    d_ij = adj[nodes[i]][nodes[j]]
                    if d_ij >= float("inf"):
                        continue
                    next_mask = mask | (1 << j)
                    new_cost = c_cur + d_ij
                    if new_cost < dp[next_mask][j]:
                        dp[next_mask][j] = new_cost
                        parent[next_mask][j] = i

        # Close the tour back to origin 0
        full_mask = (1 << k) - 1
        best_end = -1
        best_hk_cost = float("inf")

        for i in range(k):
            c_end = dp[full_mask][i]
            if c_end < float("inf"):
                d_orig = adj[nodes[i]][0]
                if d_orig < float("inf"):
                    tot = c_end + d_orig
                    if tot < best_hk_cost:
                        best_hk_cost = tot
                        best_end = i

        dur = time.perf_counter() - t0
        stats.oracle_time["held_karp"] += dur

        if best_hk_cost >= float("inf"):
            stats.pruned += 1
            stats.oracle_infeasible["held_karp"] += 1
            stats.oracle_useful_prunes["held_karp"] += 1
            return OracleResult(OracleStatus.INFEASIBLE, reason="HK_PROVED_NO_HAMILTONIAN_COMPLETION", cost=dur)

        total_exact_cost = cost_so_far + best_hk_cost
        if total_exact_cost >= best_known:
            stats.pruned += 1
            stats.oracle_infeasible["held_karp"] += 1
            stats.oracle_useful_prunes["held_karp"] += 1
            return OracleResult(OracleStatus.INFEASIBLE, reason="HK_OPTIMAL_EXCEEDS_BEST_KNOWN", cost=dur)

        # Reconstruct path
        path_indices = []
        curr_mask = full_mask
        curr_node = best_end
        while curr_node != -1:
            path_indices.append(curr_node)
            prev_node = parent[curr_mask][curr_node]
            curr_mask ^= (1 << curr_node)
            curr_node = prev_node

        path_indices.reverse()
        sub_tour = [nodes[idx] for idx in path_indices] + [0]

        stats.oracle_feasible["held_karp"] += 1
        return OracleResult(
            OracleStatus.FEASIBLE,
            tour_witness=sub_tour,
            cost_witness=total_exact_cost,
            reason="HK_EXACT_OPTIMAL_FOUND",
            cost=dur,
        )

"""
ATSP - Oracle NN: Nearest Neighbor & Trivial Exact Subtree Oracle
Constructs greedy upper bound tours and solves trivial 1-2 vertex completions exactly.
"""
import time
from typing import List, Tuple, Optional
from .base import BaseTSPOracle
from ..state import OracleResult, OracleStatus, TSPStats
from ..resource_guard import ResourceGuard


class NearestNeighborOracle(BaseTSPOracle):
    def __init__(self):
        super().__init__("nearest_neighbor")

    def estimate_cost(self, n_remaining: int, guard: ResourceGuard) -> Tuple[float, float, bool]:
        return (float(n_remaining * n_remaining), 64.0, True)

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
        stats.oracle_calls["nearest_neighbor"] += 1
        k = len(unvisited)

        # 1. Exact Trivial Completion for k == 1
        if k == 1:
            u = unvisited[0]
            edge_to_u = adj[current_city][u]
            edge_to_orig = adj[u][0]
            if edge_to_u < float("inf") and edge_to_orig < float("inf"):
                total_cost = cost_so_far + edge_to_u + edge_to_orig
                dur = time.perf_counter() - t0
                stats.oracle_time["nearest_neighbor"] += dur
                stats.oracle_feasible["nearest_neighbor"] += 1
                return OracleResult(
                    OracleStatus.FEASIBLE,
                    tour_witness=[u, 0],
                    cost_witness=total_cost,
                    reason="TRIVIAL_1_CITY_COMPLETION",
                    cost=dur,
                )
            else:
                stats.pruned += 1
                dur = time.perf_counter() - t0
                stats.oracle_time["nearest_neighbor"] += dur
                stats.oracle_infeasible["nearest_neighbor"] += 1
                return OracleResult(OracleStatus.INFEASIBLE, reason="DISCONNECTED_1_CITY", cost=dur)

        # 2. Exact Trivial Completion for k == 2
        if k == 2:
            u, v = unvisited[0], unvisited[1]
            # Order 1: current -> u -> v -> 0
            c1 = adj[current_city][u] + adj[u][v] + adj[v][0]
            # Order 2: current -> v -> u -> 0
            c2 = adj[current_city][v] + adj[v][u] + adj[u][0]

            best_order_cost = min(c1, c2)
            if best_order_cost < float("inf"):
                best_sub_tour = [u, v, 0] if c1 <= c2 else [v, u, 0]
                total_cost = cost_so_far + best_order_cost
                dur = time.perf_counter() - t0
                stats.oracle_time["nearest_neighbor"] += dur
                stats.oracle_feasible["nearest_neighbor"] += 1
                return OracleResult(
                    OracleStatus.FEASIBLE,
                    tour_witness=best_sub_tour,
                    cost_witness=total_cost,
                    reason="TRIVIAL_2_CITY_COMPLETION",
                    cost=dur,
                )

        # 3. Greedy Nearest Neighbor Search for Upper Bound tightening
        cur = current_city
        remaining = set(unvisited)
        greedy_path = []
        greedy_cost = 0.0
        feasible = True

        while remaining:
            best_next = -1
            best_dist = float("inf")
            for cand in remaining:
                d = adj[cur][cand]
                if d < best_dist:
                    best_dist = d
                    best_next = cand

            if best_next == -1 or best_dist == float("inf"):
                feasible = False
                break

            greedy_cost += best_dist
            greedy_path.append(best_next)
            remaining.remove(best_next)
            cur = best_next

        if feasible:
            return_dist = adj[cur][0]
            if return_dist < float("inf"):
                greedy_cost += return_dist
                greedy_path.append(0)
                total_cand_cost = cost_so_far + greedy_cost
                dur = time.perf_counter() - t0
                stats.oracle_time["nearest_neighbor"] += dur
                stats.oracle_unknown["nearest_neighbor"] += 1
                return OracleResult(
                    OracleStatus.UNKNOWN,
                    tour_witness=greedy_path,
                    cost_witness=total_cand_cost,
                    reason="GREEDY_TOUR_CONSTRUCTED",
                    cost=dur,
                )

        dur = time.perf_counter() - t0
        stats.oracle_time["nearest_neighbor"] += dur
        stats.oracle_unknown["nearest_neighbor"] += 1
        return OracleResult(OracleStatus.UNKNOWN, reason="NN_EVALUATED", cost=dur)

"""
ATSP - Oracle D: Degree & Connectivity Feasibility Oracle
Detects unreachable or dead-end vertices in the remaining subgraph.
"""
import time
from typing import List, Tuple
from .base import BaseTSPOracle
from ..state import OracleResult, OracleStatus, TSPStats
from ..resource_guard import ResourceGuard


class DegreeOracle(BaseTSPOracle):
    def __init__(self):
        super().__init__("degree")

    def estimate_cost(self, n_remaining: int, guard: ResourceGuard) -> Tuple[float, float, bool]:
        return (float(n_remaining * n_remaining), 32.0, True)

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
        stats.oracle_calls["degree"] += 1
        k = len(unvisited)

        if k == 0:
            # Check edge back to origin 0
            if adj[current_city][0] >= float("inf") or adj[current_city][0] < 0:
                stats.pruned += 1
                stats.degree_prunes += 1
                stats.oracle_infeasible["degree"] += 1
                stats.oracle_useful_prunes["degree"] += 1
                dur = time.perf_counter() - t0
                stats.oracle_time["degree"] += dur
                return OracleResult(OracleStatus.INFEASIBLE, reason="NO_EDGE_BACK_TO_ORIGIN", cost=dur)
            dur = time.perf_counter() - t0
            stats.oracle_time["degree"] += dur
            return OracleResult(OracleStatus.UNKNOWN, reason="ORIGIN_EDGE_EXISTS", cost=dur)

        # Check in-degree and out-degree feasibility for each unvisited vertex
        for u in unvisited:
            # Can u be reached from current_city or another unvisited vertex?
            has_incoming = (adj[current_city][u] < float("inf"))
            if not has_incoming:
                for v in unvisited:
                    if v != u and adj[v][u] < float("inf"):
                        has_incoming = True
                        break

            if not has_incoming:
                stats.pruned += 1
                stats.degree_prunes += 1
                stats.oracle_infeasible["degree"] += 1
                stats.oracle_useful_prunes["degree"] += 1
                dur = time.perf_counter() - t0
                stats.oracle_time["degree"] += dur
                return OracleResult(OracleStatus.INFEASIBLE, reason=f"VERTEX_{u}_HAS_NO_INCOMING_EDGE", cost=dur)

            # Can u reach origin 0 or another unvisited vertex?
            has_outgoing = (adj[u][0] < float("inf"))
            if not has_outgoing:
                for v in unvisited:
                    if v != u and adj[u][v] < float("inf"):
                        has_outgoing = True
                        break

            if not has_outgoing:
                stats.pruned += 1
                stats.degree_prunes += 1
                stats.oracle_infeasible["degree"] += 1
                stats.oracle_useful_prunes["degree"] += 1
                dur = time.perf_counter() - t0
                stats.oracle_time["degree"] += dur
                return OracleResult(OracleStatus.INFEASIBLE, reason=f"VERTEX_{u}_HAS_NO_OUTGOING_EDGE", cost=dur)

        dur = time.perf_counter() - t0
        stats.oracle_time["degree"] += dur
        stats.oracle_unknown["degree"] += 1
        return OracleResult(OracleStatus.UNKNOWN, reason="CONNECTIVITY_VALID", cost=dur)

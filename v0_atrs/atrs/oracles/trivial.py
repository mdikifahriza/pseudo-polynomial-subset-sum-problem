"""
ATRS - Trivial Exact Solver / Check
Handles trivial exact feasibility cases with witness generation:
1. Exact single element match (a_k == remainder)
2. Exact full suffix sum match (sum_{j=start}^{n-1} a_j == remainder)
Strictly separated from pruning oracles (Pruner != Solver).
"""
import bisect
import time
from typing import List, Optional
from .base import BaseFeasibilityOracle
from ..state import OracleResult, OracleStatus, Stats
from ..resource_guard import ResourceGuard


class TrivialExactSolver(BaseFeasibilityOracle):
    def __init__(self):
        super().__init__("trivial")

    def estimate_cost(self, values, start_idx, remainder, suffix_sum, guard):
        return (1.0, 32.0, True)

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
        t0 = time.perf_counter()
        stats.oracle_calls["trivial"] += 1
        n = len(values)

        if start_idx >= n or remainder <= 0:
            dur = time.perf_counter() - t0
            stats.oracle_time["trivial"] += dur
            stats.oracle_unknown["trivial"] += 1
            return OracleResult(OracleStatus.UNKNOWN, reason="NON_TRIVIAL_INDEX_OR_REMAINDER", cost=dur)

        # 1. Exact Single Element Match: binary search for remainder in values[start_idx:n]
        stats.comparisons += 1
        idx = bisect.bisect_left(values, remainder, lo=start_idx, hi=n)
        if idx < n and values[idx] == remainder:
            stats.oracle_feasible["trivial"] += 1
            stats.trivial_hits += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["trivial"] += dur
            return OracleResult(
                OracleStatus.FEASIBLE,
                witness=[values[idx]],
                reason="EXACT_SINGLE_ELEMENT_MATCH",
                cost=dur
            )

        # 2. Exact Full Suffix Sum Match: check if selecting all remaining elements sums to remainder
        stats.bound_checks += 1
        stats.comparisons += 1
        if suffix_sum[start_idx] == remainder:
            stats.oracle_feasible["trivial"] += 1
            stats.trivial_hits += 1
            witness = values[start_idx:n]
            dur = time.perf_counter() - t0
            stats.oracle_time["trivial"] += dur
            return OracleResult(
                OracleStatus.FEASIBLE,
                witness=witness,
                reason="EXACT_SUFFIX_SUM_MATCH",
                cost=dur
            )

        dur = time.perf_counter() - t0
        stats.oracle_time["trivial"] += dur
        stats.oracle_unknown["trivial"] += 1
        return OracleResult(OracleStatus.UNKNOWN, reason="NOT_TRIVIAL_EXACT", cost=dur)

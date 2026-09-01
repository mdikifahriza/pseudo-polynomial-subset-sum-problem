"""
ATRS - Oracle C: Exact Meet-in-the-Middle (MITM) Feasibility Oracle
Splits suffix candidate elements into L and R subsets to test if x + y = remainder.
Time and memory bounded: O(2^(d/2)), where d = number of elements <= remainder.
"""
import bisect
import time
from typing import List, Tuple, Optional, Dict
from .base import BaseFeasibilityOracle
from ..state import OracleResult, OracleStatus, Stats
from ..resource_guard import ResourceGuard


class MITMOracle(BaseFeasibilityOracle):
    def __init__(self):
        super().__init__("mitm")

    def estimate_cost(
        self,
        values: List[int],
        start_idx: int,
        remainder: int,
        suffix_sum: List[int],
        guard: ResourceGuard
    ) -> Tuple[float, float, bool]:
        n = len(values)
        candidates = [values[j] for j in range(start_idx, n) if values[j] <= remainder]
        d = len(candidates)
        if d <= 0:
            return (0.0, 0.0, True)

        half = d // 2
        if half > 22:
            return (float("inf"), float("inf"), False)

        est_states = 1 << half
        est_bytes = float(est_states * 24)
        is_ok = guard.is_mitm_budget_allowed(d)
        est_time_units = float(est_states)
        return (est_time_units, est_bytes, is_ok)

    def _generate_subset_sums(
        self,
        elements: List[int],
        remainder_limit: int,
        stats: Stats,
        guard: ResourceGuard
    ) -> Dict[int, List[int]]:
        """
        Generates map: sum -> sample witness subset of values.
        Prunes sums exceeding remainder_limit.
        """
        sums_map: Dict[int, List[int]] = {0: []}
        for elem in elements:
            if elem > remainder_limit:
                continue
            new_entries = {}
            for s, subset in sums_map.items():
                ns = s + elem
                if ns <= remainder_limit and ns not in sums_map:
                    new_entries[ns] = subset + [elem]
                stats.arithmetic += 1
            sums_map.update(new_entries)
            stats.mitm_states_generated += len(new_entries)
            guard.periodic_check(interval=2048)
        return sums_map

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
        stats.oracle_calls["mitm"] += 1

        if remainder == 0:
            dur = time.perf_counter() - t0
            stats.oracle_time["mitm"] += dur
            stats.oracle_feasible["mitm"] += 1
            return OracleResult(OracleStatus.FEASIBLE, witness=[], reason="REMAINDER_ZERO", cost=dur)

        n = len(values)
        candidates = [values[j] for j in range(start_idx, n) if values[j] <= remainder]
        d = len(candidates)

        if d == 0:
            dur = time.perf_counter() - t0
            stats.oracle_time["mitm"] += dur
            stats.oracle_infeasible["mitm"] += 1
            stats.oracle_useful_prunes["mitm"] += 1
            stats.pruned += 1
            stats.oracle_prunes += 1
            return OracleResult(OracleStatus.INFEASIBLE, reason="NO_CANDIDATES", cost=dur)

        est_time, est_bytes, is_ok = self.estimate_cost(values, start_idx, remainder, suffix_sum, guard)
        if not is_ok:
            dur = time.perf_counter() - t0
            stats.oracle_time["mitm"] += dur
            stats.oracle_unknown["mitm"] += 1
            return OracleResult(
                OracleStatus.UNKNOWN,
                reason=f"MITM_BUDGET_LIMIT (Candidates d={d}, Est: {est_bytes / (1024*1024):.1f} MB)",
                cost=dur
            )

        mid = d // 2
        left_elems = candidates[:mid]
        right_elems = candidates[mid:]

        left_sums = self._generate_subset_sums(left_elems, remainder, stats, guard)
        if remainder in left_sums:
            dur = time.perf_counter() - t0
            stats.oracle_time["mitm"] += dur
            stats.oracle_feasible["mitm"] += 1
            return OracleResult(OracleStatus.FEASIBLE, witness=left_sums[remainder], reason="MITM_LEFT_MATCH", cost=dur)

        right_sums = self._generate_subset_sums(right_elems, remainder, stats, guard)
        if remainder in right_sums:
            dur = time.perf_counter() - t0
            stats.oracle_time["mitm"] += dur
            stats.oracle_feasible["mitm"] += 1
            return OracleResult(OracleStatus.FEASIBLE, witness=right_sums[remainder], reason="MITM_RIGHT_MATCH", cost=dur)

        for s_left, left_wit in left_sums.items():
            needed = remainder - s_left
            stats.comparisons += 1
            if needed in right_sums:
                dur = time.perf_counter() - t0
                stats.oracle_time["mitm"] += dur
                stats.oracle_feasible["mitm"] += 1
                return OracleResult(
                    OracleStatus.FEASIBLE,
                    witness=left_wit + right_sums[needed],
                    reason="MITM_CROSS_MATCH",
                    cost=dur
                )

        dur = time.perf_counter() - t0
        stats.oracle_time["mitm"] += dur
        stats.oracle_infeasible["mitm"] += 1
        stats.oracle_useful_prunes["mitm"] += 1
        stats.pruned += 1
        stats.oracle_prunes += 1
        return OracleResult(OracleStatus.INFEASIBLE, reason="MITM_PROVEN_UNREACHABLE", cost=dur)

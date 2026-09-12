"""
ATRS - Oracle A: Sound Necessary-Condition Pruning Oracle (Arithmetic & Bound Oracle)
Evaluates exact necessary conditions for subset sum feasibility.
Returns:
  - INFEASIBLE: If mathematically proven that NO subset can reach remainder.
  - UNKNOWN: If all necessary conditions pass (feasibility undecidable without further search).
Never returns FEASIBLE and never constructs witnesses (Pruner != Solver).
"""
import bisect
import time
from typing import List, Tuple
from .base import BaseFeasibilityOracle
from ..state import OracleResult, OracleStatus, Stats
from ..resource_guard import ResourceGuard


class ArithmeticBoundOracle(BaseFeasibilityOracle):
    def __init__(self):
        super().__init__("arithmetic")

    def estimate_cost(
        self,
        values: List[int],
        start_idx: int,
        remainder: int,
        suffix_sum: List[int],
        guard: ResourceGuard
    ) -> Tuple[float, float, bool]:
        return (1.0, 64.0, True)

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
        stats.oracle_calls["arithmetic"] += 1
        stats.bound_checks += 1
        n = len(values)

        # 1. Negative Remainder Pruning
        # Mathematical Reason: All elements a_i > 0, hence any subset sum >= 0. A negative remainder is impossible.
        stats.comparisons += 1
        if remainder < 0:
            stats.pruned += 1
            stats.lower_prunes += 1
            stats.oracle_infeasible["arithmetic"] += 1
            stats.oracle_useful_prunes["arithmetic"] += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["arithmetic"] += dur
            return OracleResult(OracleStatus.INFEASIBLE, reason="NEGATIVE_REMAINDER", cost=dur)

        # 2. Suffix Exhaustion Pruning
        # Mathematical Reason: No available candidates remaining (start_idx >= n) while remainder > 0.
        stats.comparisons += 1
        if start_idx >= n:
            stats.pruned += 1
            stats.oracle_infeasible["arithmetic"] += 1
            stats.oracle_useful_prunes["arithmetic"] += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["arithmetic"] += dur
            return OracleResult(OracleStatus.INFEASIBLE, reason="SUFFIX_EXHAUSTED", cost=dur)

        # 3. Smallest Candidate Pruning
        # Mathematical Reason: Since values are sorted ascending, values[start_idx] is the minimum available element.
        # If min(available) > remainder, every available element exceeds remainder, making target sum unreachable.
        stats.comparisons += 1
        if values[start_idx] > remainder:
            stats.pruned += (n - start_idx)
            stats.lower_prunes += 1
            stats.oracle_infeasible["arithmetic"] += 1
            stats.oracle_useful_prunes["arithmetic"] += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["arithmetic"] += dur
            return OracleResult(OracleStatus.INFEASIBLE, reason="SMALLEST_ELEMENT_EXCEEDS_REMAINDER", cost=dur)

        # 4. Suffix Sum Upper Bound Pruning
        # Mathematical Reason: sum_{j=start}^{n-1} a_j is the maximum possible sum achievable from the suffix.
        # If suffix_sum[start_idx] < remainder, even selecting all remaining elements cannot reach remainder.
        stats.bound_checks += 1
        stats.comparisons += 1
        cur_suffix_sum = suffix_sum[start_idx]
        if cur_suffix_sum < remainder:
            stats.pruned += 1
            stats.upper_prunes += 1
            stats.oracle_infeasible["arithmetic"] += 1
            stats.oracle_useful_prunes["arithmetic"] += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["arithmetic"] += dur
            return OracleResult(OracleStatus.INFEASIBLE, reason="SUFFIX_SUM_TOO_SMALL", cost=dur)

        # 5. Suffix GCD Divisibility Pruning
        # Mathematical Reason: Every element a_j (j >= start) is a multiple of g = gcd(a_{start}, ..., a_{n-1}).
        # Any linear combination sum_{j} x_j a_j with integer x_j is necessarily divisible by g.
        # Therefore, if g > 1 and remainder mod g != 0, no subset sum can equal remainder.
        stats.comparisons += 1
        g = suffix_gcd[start_idx]
        if g > 1:
            stats.comparisons += 1
            if remainder % g != 0:
                stats.pruned += 1
                stats.gcd_prunes += 1
                stats.oracle_infeasible["arithmetic"] += 1
                stats.oracle_useful_prunes["arithmetic"] += 1
                dur = time.perf_counter() - t0
                stats.oracle_time["arithmetic"] += dur
                return OracleResult(OracleStatus.INFEASIBLE, reason=f"GCD_DIVISIBILITY_VIOLATION(g={g})", cost=dur)

        # 6. Candidate Cardinality Lower Bound Pruning
        # Mathematical Reason: Let max_cand be the largest available element <= remainder.
        # Any valid subset needs at least ceil(remainder / max_cand) elements.
        # If this minimum count exceeds the total number of available candidates <= remainder, it is impossible.
        max_cand_idx = bisect.bisect_right(values, remainder, lo=start_idx, hi=n) - 1
        if max_cand_idx < start_idx:
            stats.pruned += 1
            stats.lower_prunes += 1
            stats.oracle_infeasible["arithmetic"] += 1
            stats.oracle_useful_prunes["arithmetic"] += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["arithmetic"] += dur
            return OracleResult(OracleStatus.INFEASIBLE, reason="NO_CANDIDATES_LE_REMAINDER", cost=dur)

        available_count = max_cand_idx - start_idx + 1
        max_val = values[max_cand_idx]
        min_count = (remainder + max_val - 1) // max_val

        stats.bound_checks += 1
        if min_count > available_count:
            stats.pruned += 1
            stats.cardinality_prunes += 1
            stats.oracle_infeasible["arithmetic"] += 1
            stats.oracle_useful_prunes["arithmetic"] += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["arithmetic"] += dur
            return OracleResult(OracleStatus.INFEASIBLE, reason="CARDINALITY_LOWER_BOUND_EXCEEDED", cost=dur)

        # 7. Greedy Candidate Sum Upper Bound Pruning
        # Mathematical Reason: Elements > remainder cannot be included. The sum of only those candidates <= remainder
        # is cand_sum = suffix_sum[start_idx] - suffix_sum[max_cand_idx + 1].
        # If cand_sum < remainder, no combination of feasible candidates can sum to remainder.
        cand_sum = cur_suffix_sum - (suffix_sum[max_cand_idx + 1] if max_cand_idx + 1 < n else 0)
        if cand_sum < remainder:
            stats.pruned += 1
            stats.upper_prunes += 1
            stats.oracle_infeasible["arithmetic"] += 1
            stats.oracle_useful_prunes["arithmetic"] += 1
            dur = time.perf_counter() - t0
            stats.oracle_time["arithmetic"] += dur
            return OracleResult(OracleStatus.INFEASIBLE, reason="CANDIDATE_SUM_TOO_SMALL", cost=dur)

        # Necessary conditions passed -> Undecidable by cheap arithmetic alone
        dur = time.perf_counter() - t0
        stats.oracle_time["arithmetic"] += dur
        stats.oracle_unknown["arithmetic"] += 1
        return OracleResult(OracleStatus.UNKNOWN, reason="SOUND_BOUNDS_PASSED", cost=dur)

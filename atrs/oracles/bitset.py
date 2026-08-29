"""
ATRS - Oracle B: Exact Bitset DP Feasibility Oracle
Uses arbitrary-precision integers for fast word-level bitwise operations.
Strictly guarded against OOM / excessive target sizes.
"""
import time
from typing import List, Tuple, Optional
from .base import BaseFeasibilityOracle
from ..state import OracleResult, OracleStatus, Stats
from ..resource_guard import ResourceGuard


class BitsetOracle(BaseFeasibilityOracle):
    def __init__(self):
        super().__init__("bitset")

    def estimate_cost(
        self,
        values: List[int],
        start_idx: int,
        remainder: int,
        suffix_sum: List[int],
        guard: ResourceGuard
    ) -> Tuple[float, float, bool]:
        if remainder <= 0:
            return (0.0, 0.0, True)

        base_bytes = (remainder + 1) // 8
        is_ok = guard.is_bitset_memory_allowed(remainder, safety_factor=2.5)
        d = len(values) - start_idx
        est_time_units = d * (remainder / (64 * 10000) + 1.0)
        return (est_time_units, float(base_bytes * 2.5), is_ok)

    def query(
        self,
        values: List[int],
        start_idx: int,
        remainder: int,
        suffix_sum: List[int],
        suffix_gcd: List[int],
        stats: Stats,
        guard: ResourceGuard,
        reconstruct_witness: bool = True
    ) -> OracleResult:
        t0 = time.perf_counter()
        stats.oracle_calls["bitset"] += 1

        if remainder == 0:
            dur = time.perf_counter() - t0
            stats.oracle_time["bitset"] += dur
            stats.oracle_feasible["bitset"] += 1
            return OracleResult(OracleStatus.FEASIBLE, witness=[], reason="REMAINDER_ZERO", cost=dur)

        est_time, est_bytes, is_ok = self.estimate_cost(values, start_idx, remainder, suffix_sum, guard)
        if not is_ok:
            dur = time.perf_counter() - t0
            stats.oracle_time["bitset"] += dur
            stats.oracle_unknown["bitset"] += 1
            return OracleResult(
                OracleStatus.UNKNOWN,
                reason=f"BITSET_MEMORY_LIMIT (Est: {est_bytes / (1024*1024):.1f} MB)",
                cost=dur
            )

        n = len(values)
        mask = (1 << (remainder + 1)) - 1
        b = 1

        store_history = reconstruct_witness and (est_bytes * (n - start_idx) <= 32 * 1024 * 1024)
        history = [b] if store_history else None

        for j in range(start_idx, n):
            val = values[j]
            if val > remainder:
                break

            if (j - start_idx) % 20 == 0:
                guard.periodic_check(interval=1)

            b = (b | (b << val)) & mask
            stats.arithmetic += 1
            stats.bitset_bits_processed += remainder

            if store_history:
                history.append(b)

            if not store_history and ((b >> remainder) & 1):
                break

        is_feasible = bool((b >> remainder) & 1)
        dur = time.perf_counter() - t0
        stats.oracle_time["bitset"] += dur

        if is_feasible:
            stats.oracle_feasible["bitset"] += 1
            witness = None
            if store_history and history is not None:
                witness = self._reconstruct_witness(values, start_idx, remainder, history)
            return OracleResult(OracleStatus.FEASIBLE, witness=witness, reason="BITSET_REACHABLE", cost=dur)
        else:
            stats.oracle_infeasible["bitset"] += 1
            stats.oracle_useful_prunes["bitset"] += 1
            stats.pruned += 1
            stats.oracle_prunes += 1
            return OracleResult(OracleStatus.INFEASIBLE, reason="BITSET_UNREACHABLE", cost=dur)

    def _reconstruct_witness(
        self,
        values: List[int],
        start_idx: int,
        remainder: int,
        history: List[int]
    ) -> List[int]:
        witness = []
        curr_r = remainder
        steps = len(history) - 1

        for k in range(steps, 0, -1):
            val = values[start_idx + k - 1]
            prev_b = history[k - 1]

            if curr_r >= val and ((prev_b >> (curr_r - val)) & 1):
                if not ((prev_b >> curr_r) & 1):
                    witness.append(val)
                    curr_r -= val
                else:
                    witness.append(val)
                    curr_r -= val
            if curr_r == 0:
                break

        witness.reverse()
        return witness

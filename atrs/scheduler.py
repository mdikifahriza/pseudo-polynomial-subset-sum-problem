"""
ATRS - Adaptive Oracle Manager & Scheduler
Selects and orders feasibility oracles dynamically based on candidate features,
resource budgets, and live runtime performance feedback.
"""
from typing import List, Tuple, Optional, Dict
from .state import Stats, OracleResult, OracleStatus
from .resource_guard import ResourceGuard
from .oracles import (
    BaseFeasibilityOracle,
    ArithmeticBoundOracle,
    BitsetOracle,
    MITMOracle,
    TargetRemainderDFSOracle,
)


class AdaptiveOracleManager:
    def __init__(
        self,
        max_mitm_depth: int = 38,
        max_bitset_memory_mb: float = 256.0,
        enable_adaptive_learning: bool = True
    ):
        self.max_mitm_depth = max_mitm_depth
        self.max_bitset_memory_mb = max_bitset_memory_mb
        self.enable_adaptive_learning = enable_adaptive_learning

        self.oracle_arithmetic = ArithmeticBoundOracle()
        self.oracle_bitset = BitsetOracle()
        self.oracle_mitm = MITMOracle()
        self.oracle_dfs = TargetRemainderDFSOracle()

        self.priority_weights: Dict[str, float] = {
            "bitset": 1.0,
            "mitm": 1.0,
            "dfs": 1.0,
        }

    def choose_oracle_pipeline(
        self,
        values: List[int],
        start_idx: int,
        remainder: int,
        suffix_sum: List[int],
        stats: Stats,
        guard: ResourceGuard
    ) -> List[BaseFeasibilityOracle]:
        """
        Determines the sequence of feasibility oracles to query for state (start_idx, remainder).
        Always begins with Arithmetic / Bound Oracle.
        """
        pipeline: List[BaseFeasibilityOracle] = [self.oracle_arithmetic]
        n = len(values)
        d = n - start_idx

        if self.enable_adaptive_learning:
            self._update_adaptive_weights(stats)

        secondary: List[Tuple[float, BaseFeasibilityOracle]] = []

        _, bitset_mem, bitset_ok = self.oracle_bitset.estimate_cost(values, start_idx, remainder, suffix_sum, guard)
        if bitset_ok and (bitset_mem / (1024 * 1024)) <= self.max_bitset_memory_mb:
            bitset_cost_factor = (remainder / 64.0) * d
            bitset_score = (bitset_cost_factor / 1000.0) / max(0.01, self.priority_weights["bitset"])
            secondary.append((bitset_score, self.oracle_bitset))

        _, mitm_mem, mitm_ok = self.oracle_mitm.estimate_cost(values, start_idx, remainder, suffix_sum, guard)
        if mitm_ok and d <= self.max_mitm_depth:
            mitm_cost_factor = float(1 << min(d // 2, 22))
            mitm_score = mitm_cost_factor / max(0.01, self.priority_weights["mitm"])
            secondary.append((mitm_score, self.oracle_mitm))

        secondary.sort(key=lambda x: x[0])
        for _, oracle in secondary:
            pipeline.append(oracle)

        pipeline.append(self.oracle_dfs)
        return pipeline

    def _update_adaptive_weights(self, stats: Stats):
        """
        Adjusts priority weights dynamically based on historical utility and compute cost.
        Does NOT alter logical correctness; only optimizes scheduling order.
        """
        for key in ["bitset", "mitm"]:
            calls = stats.oracle_calls.get(key, 0)
            time_spent = stats.oracle_time.get(key, 0.0)
            useful = stats.oracle_useful_prunes.get(key, 0)

            if calls >= 5 and time_spent > 0.05:
                efficiency = useful / calls
                if efficiency < 0.1:
                    self.priority_weights[key] = max(0.1, self.priority_weights[key] * 0.8)
                elif efficiency > 0.6:
                    self.priority_weights[key] = min(3.0, self.priority_weights[key] * 1.2)

    def evaluate_state(
        self,
        values: List[int],
        start_idx: int,
        remainder: int,
        suffix_sum: List[int],
        suffix_gcd: List[int],
        stats: Stats,
        guard: ResourceGuard,
        allow_deep_oracles: bool = True
    ) -> OracleResult:
        """
        Executes oracles along the adaptive pipeline until a decisive answer (FEASIBLE or INFEASIBLE)
        is found, or all return UNKNOWN.
        """
        if not allow_deep_oracles:
            return self.oracle_arithmetic.query(values, start_idx, remainder, suffix_sum, suffix_gcd, stats, guard)

        pipeline = self.choose_oracle_pipeline(values, start_idx, remainder, suffix_sum, stats, guard)

        last_unknown = OracleResult(OracleStatus.UNKNOWN, reason="NO_ORACLE_DECIDED")
        for oracle in pipeline:
            res = oracle.query(values, start_idx, remainder, suffix_sum, suffix_gcd, stats, guard)
            if res.status == OracleStatus.FEASIBLE or res.status == OracleStatus.INFEASIBLE:
                return res
            last_unknown = res

        return last_unknown

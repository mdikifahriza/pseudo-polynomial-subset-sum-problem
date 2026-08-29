"""
ATRS - Oracle D: Direct Target-Remainder DFS Feasibility Oracle
Exact DFS with sound mathematical pruning and bounded memoization.
"""
import time
from typing import List, Tuple, Optional, Set
from .base import BaseFeasibilityOracle
from ..state import OracleResult, OracleStatus, Stats
from ..resource_guard import ResourceGuard

class TargetRemainderDFSOracle(BaseFeasibilityOracle):
    def __init__(self):
        super().__init__("dfs")

    def estimate_cost(
        self,
        values: List[int],
        start_idx: int,
        remainder: int,
        suffix_sum: List[int],
        guard: ResourceGuard
    ) -> Tuple[float, float, bool]:
        d = len(values) - start_idx
        est_nodes = 1 << min(d, 30)
        return (float(est_nodes), 1024.0 * 1024.0, True)

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
        stats.oracle_calls["dfs"] += 1
        n = len(values)

        dead_states: Set[Tuple[int, int]] = set()
        witness_solution: Optional[List[int]] = None

        def dfs(i: int, rem: int, current_path: List[int]) -> bool:
            nonlocal witness_solution
            stats.nodes += 1
            guard.periodic_check(interval=512)

            stats.comparisons += 1
            if rem == 0:
                witness_solution = list(current_path)
                return True

            stats.comparisons += 1
            if rem < 0 or i >= n:
                stats.pruned += 1
                return False

            state = (i, rem)
            if state in dead_states:
                stats.memo_hits += 1
                stats.pruned += 1
                return False

            stats.bound_checks += 1
            stats.comparisons += 1
            if suffix_sum[i] < rem:
                stats.upper_prunes += 1
                stats.pruned += 1
                if len(dead_states) < (guard.max_memo_states or 100_000):
                    dead_states.add(state)
                return False

            stats.comparisons += 1
            g = suffix_gcd[i]
            if g > 1:
                stats.comparisons += 1
                if rem % g != 0:
                    stats.gcd_prunes += 1
                    stats.pruned += 1
                    if len(dead_states) < (guard.max_memo_states or 100_000):
                        dead_states.add(state)
                    return False

            stats.comparisons += 1
            if values[i] > rem:
                stats.pruned += 1
                stats.lower_prunes += 1
                if len(dead_states) < (guard.max_memo_states or 100_000):
                    dead_states.add(state)
                return False

            found = False
            for j in range(i, n):
                val = values[j]
                stats.comparisons += 1
                if val > rem:
                    stats.pruned += (n - j)
                    break

                stats.arithmetic += 1
                current_path.append(val)
                if dfs(j + 1, rem - val, current_path):
                    found = True
                    break
                current_path.pop()

            if not found:
                if len(dead_states) < (guard.max_memo_states or 100_000):
                    dead_states.add(state)
                    stats.dead_states_peak = max(stats.dead_states_peak, len(dead_states))
            return found

        is_feasible = dfs(start_idx, remainder, [])
        dur = time.perf_counter() - t0
        stats.oracle_time["dfs"] += dur

        if is_feasible:
            stats.oracle_feasible["dfs"] += 1
            return OracleResult(OracleStatus.FEASIBLE, witness=witness_solution, reason="DFS_PATH_FOUND", cost=dur)
        else:
            stats.oracle_infeasible["dfs"] += 1
            stats.oracle_useful_prunes["dfs"] += 1
            return OracleResult(OracleStatus.INFEASIBLE, reason="DFS_EXHAUSTED", cost=dur)

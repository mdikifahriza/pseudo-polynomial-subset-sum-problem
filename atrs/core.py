"""
ATRS - Core Solver Engine and Baseline Algorithms
Implements exact, uniform solvers:
1. Brute Force
2. Target-Remainder DFS
3. Target-Remainder + Full Pruning (Without Memoization)
4. Target-Remainder + Memoization
5. Bitset DP
6. Meet-in-the-Middle (MITM)
7. ATRS (Adaptive Target-Remainder Solver)
"""
import time
import os
import bisect
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor
from typing import List, Tuple, Optional, Set, Dict, Any

from .state import (
    Stats,
    SolverResult,
    SolverStatus,
    SearchMode,
    OracleStatus,
    OracleResult,
)
from .resource_guard import ResourceGuard, ResourceLimitExceeded
from .preprocess import build_suffix_sum, build_suffix_gcd
from .scheduler import AdaptiveOracleManager
from .oracles.arithmetic import ArithmeticBoundOracle
from .oracles.trivial import TrivialExactSolver
from .oracles.bitset import BitsetOracle
from .oracles.mitm import MITMOracle


class BaseSubsetSumSolver(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def solve(
        self,
        values: List[int],
        target: int,
        mode: SearchMode = SearchMode.FIRST_SOLUTION,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> SolverResult:
        pass


class BruteForceSolver(BaseSubsetSumSolver):
    def __init__(self):
        super().__init__("Brute Force")

    def solve(
        self,
        values: List[int],
        target: int,
        mode: SearchMode = SearchMode.FIRST_SOLUTION,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> SolverResult:
        if guard is None:
            guard = ResourceGuard(timeout_seconds=30.0)
        guard.start()
        stats = Stats()
        solutions: List[Tuple[int, ...]] = []
        n = len(values)
        t0 = time.perf_counter()

        try:
            def explore(i: int, current_sum: int, path: List[int]) -> bool:
                stats.nodes += 1
                guard.periodic_check(interval=1024)

                stats.comparisons += 1
                if current_sum == target and path:
                    stats.solutions_count += 1
                    solutions.append(tuple(path))
                    return True

                stats.comparisons += 1
                if i >= n or current_sum > target:
                    return False

                found_any = False

                # Include values[i]
                stats.arithmetic += 1
                path.append(values[i])
                if explore(i + 1, current_sum + values[i], path):
                    found_any = True
                    if mode != SearchMode.ALL_SOLUTIONS:
                        path.pop()
                        return True
                path.pop()

                # Exclude values[i]
                if explore(i + 1, current_sum, path):
                    found_any = True
                    if mode != SearchMode.ALL_SOLUTIONS:
                        return True

                return found_any

            explore(0, 0, [])
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            stats.memory_peak_bytes = int(guard.get_peak_memory_mb() * 1024 * 1024)

            status = SolverStatus.EXACT_SOL_FOUND if solutions else SolverStatus.EXACT_NO_SOL
            return SolverResult(
                status=status,
                solutions=solutions,
                stats=stats,
                elapsed=elapsed,
                algorithm_name=self.name,
                is_exact=True,
            )
        except ResourceLimitExceeded as e:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            status = SolverStatus.UNKNOWN_MEMORY if e.resource_type == "MEMORY" else SolverStatus.UNKNOWN_TIMEOUT
            return SolverResult(
                status=status,
                solutions=solutions,
                stats=stats,
                elapsed=elapsed,
                algorithm_name=self.name,
                is_exact=False,
                diagnostic_message=str(e),
            )


class TargetRemainderDFSSolver(BaseSubsetSumSolver):
    def __init__(self):
        super().__init__("Target-Remainder DFS")

    def solve(
        self,
        values: List[int],
        target: int,
        mode: SearchMode = SearchMode.FIRST_SOLUTION,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> SolverResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()
        stats = Stats()
        solutions: List[Tuple[int, ...]] = []
        n = len(values)
        t0 = time.perf_counter()

        suffix_sum = build_suffix_sum(values)

        try:
            def dfs(start: int, remainder: int, path: List[int]) -> bool:
                stats.nodes += 1
                guard.periodic_check(interval=1024)

                stats.comparisons += 1
                if remainder == 0:
                    stats.solutions_count += 1
                    solutions.append(tuple(path))
                    return True

                stats.comparisons += 1
                if remainder < 0 or start >= n:
                    stats.pruned += 1
                    return False

                stats.bound_checks += 1
                stats.comparisons += 1
                if suffix_sum[start] < remainder:
                    stats.upper_prunes += 1
                    stats.pruned += 1
                    return False

                found_any = False
                for j in range(start, n):
                    val = values[j]
                    stats.comparisons += 1
                    if val > remainder:
                        stats.lower_prunes += 1
                        stats.pruned += (n - j)
                        break

                    stats.arithmetic += 1
                    path.append(val)
                    if dfs(j + 1, remainder - val, path):
                        found_any = True
                        if mode != SearchMode.ALL_SOLUTIONS:
                            path.pop()
                            return True
                    path.pop()

                return found_any

            dfs(0, target, [])
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            stats.memory_peak_bytes = int(guard.get_peak_memory_mb() * 1024 * 1024)
            status = SolverStatus.EXACT_SOL_FOUND if solutions else SolverStatus.EXACT_NO_SOL
            return SolverResult(status, solutions, stats, elapsed, self.name, True)
        except ResourceLimitExceeded as e:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            status = SolverStatus.UNKNOWN_MEMORY if e.resource_type == "MEMORY" else SolverStatus.UNKNOWN_TIMEOUT
            return SolverResult(status, solutions, stats, elapsed, self.name, False, str(e))


class TargetRemainderPrunedSolver(BaseSubsetSumSolver):
    def __init__(self):
        super().__init__("Target-Remainder + Full Pruning")

    def solve(
        self,
        values: List[int],
        target: int,
        mode: SearchMode = SearchMode.FIRST_SOLUTION,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> SolverResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()
        stats = Stats()
        solutions: List[Tuple[int, ...]] = []
        n = len(values)
        t0 = time.perf_counter()

        suffix_sum = build_suffix_sum(values)
        suffix_gcd = build_suffix_gcd(values)
        bound_oracle = ArithmeticBoundOracle()
        trivial_solver = TrivialExactSolver()

        try:
            def dfs(start: int, remainder: int, path: List[int]) -> bool:
                stats.nodes += 1
                guard.periodic_check(interval=512)

                # 1. Terminal check
                if remainder == 0:
                    stats.solutions_count += 1
                    solutions.append(tuple(path))
                    return True

                # 2. Sound Necessary Pruning
                prune_res = bound_oracle.query(values, start, remainder, suffix_sum, suffix_gcd, stats, guard)
                if prune_res.status == OracleStatus.INFEASIBLE:
                    return False

                # 3. Trivial Exact Check (for single solution / decision)
                if mode != SearchMode.ALL_SOLUTIONS:
                    triv_res = trivial_solver.query(values, start, remainder, suffix_sum, suffix_gcd, stats, guard)
                    if triv_res.status == OracleStatus.FEASIBLE and triv_res.witness is not None:
                        stats.solutions_count += 1
                        full_sol = path + triv_res.witness
                        solutions.append(tuple(full_sol))
                        return True

                # 4. Branching DFS
                found_any = False
                for j in range(start, n):
                    val = values[j]
                    stats.comparisons += 1
                    if val > remainder:
                        stats.pruned += (n - j)
                        break

                    stats.arithmetic += 1
                    path.append(val)
                    if dfs(j + 1, remainder - val, path):
                        found_any = True
                        if mode != SearchMode.ALL_SOLUTIONS:
                            path.pop()
                            return True
                    path.pop()

                return found_any

            dfs(0, target, [])
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            stats.memory_peak_bytes = int(guard.get_peak_memory_mb() * 1024 * 1024)
            status = SolverStatus.EXACT_SOL_FOUND if solutions else SolverStatus.EXACT_NO_SOL
            return SolverResult(status, solutions, stats, elapsed, self.name, True)
        except ResourceLimitExceeded as e:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            status = SolverStatus.UNKNOWN_MEMORY if e.resource_type == "MEMORY" else SolverStatus.UNKNOWN_TIMEOUT
            return SolverResult(status, solutions, stats, elapsed, self.name, False, str(e))


class TargetRemainderMemoSolver(BaseSubsetSumSolver):
    def __init__(self):
        super().__init__("Target-Remainder + Memoization")

    def solve(
        self,
        values: List[int],
        target: int,
        mode: SearchMode = SearchMode.FIRST_SOLUTION,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> SolverResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()
        stats = Stats()
        solutions: List[Tuple[int, ...]] = []
        n = len(values)
        t0 = time.perf_counter()

        suffix_sum = build_suffix_sum(values)
        suffix_gcd = build_suffix_gcd(values)
        bound_oracle = ArithmeticBoundOracle()
        trivial_solver = TrivialExactSolver()
        dead_states: Set[Tuple[int, int]] = set()

        try:
            def dfs(start: int, remainder: int, path: List[int]) -> bool:
                stats.nodes += 1
                guard.periodic_check(interval=512)

                # 1. Terminal check
                if remainder == 0:
                    stats.solutions_count += 1
                    solutions.append(tuple(path))
                    return True

                state = (start, remainder)
                if state in dead_states:
                    stats.memo_hits += 1
                    stats.pruned += 1
                    return False

                # 2. Sound Necessary Pruning
                prune_res = bound_oracle.query(values, start, remainder, suffix_sum, suffix_gcd, stats, guard)
                if prune_res.status == OracleStatus.INFEASIBLE:
                    if len(dead_states) < (guard.max_memo_states or 100_000):
                        dead_states.add(state)
                    return False

                # 3. Trivial Exact Check (for single solution / decision)
                if mode != SearchMode.ALL_SOLUTIONS:
                    triv_res = trivial_solver.query(values, start, remainder, suffix_sum, suffix_gcd, stats, guard)
                    if triv_res.status == OracleStatus.FEASIBLE and triv_res.witness is not None:
                        stats.solutions_count += 1
                        full_sol = path + triv_res.witness
                        solutions.append(tuple(full_sol))
                        return True

                # 4. Branching DFS
                found_any = False
                for j in range(start, n):
                    val = values[j]
                    stats.comparisons += 1
                    if val > remainder:
                        stats.pruned += (n - j)
                        break

                    stats.arithmetic += 1
                    path.append(val)
                    if dfs(j + 1, remainder - val, path):
                        found_any = True
                        if mode != SearchMode.ALL_SOLUTIONS:
                            path.pop()
                            return True
                    path.pop()

                if not found_any and len(dead_states) < (guard.max_memo_states or 100_000):
                    dead_states.add(state)
                    stats.dead_states_peak = max(stats.dead_states_peak, len(dead_states))

                return found_any

            dfs(0, target, [])
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            stats.memory_peak_bytes = int(guard.get_peak_memory_mb() * 1024 * 1024)
            status = SolverStatus.EXACT_SOL_FOUND if solutions else SolverStatus.EXACT_NO_SOL
            return SolverResult(status, solutions, stats, elapsed, self.name, True)
        except ResourceLimitExceeded as e:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            status = SolverStatus.UNKNOWN_MEMORY if e.resource_type == "MEMORY" else SolverStatus.UNKNOWN_TIMEOUT
            return SolverResult(status, solutions, stats, elapsed, self.name, False, str(e))


class BitsetDPSolver(BaseSubsetSumSolver):
    def __init__(self):
        super().__init__("Bitset DP")

    def solve(
        self,
        values: List[int],
        target: int,
        mode: SearchMode = SearchMode.FIRST_SOLUTION,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> SolverResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()
        stats = Stats()
        t0 = time.perf_counter()
        suffix_sum = build_suffix_sum(values)
        suffix_gcd = build_suffix_gcd(values)

        bitset_oracle = BitsetOracle()
        reconstruct_witness = (mode != SearchMode.DECISION_ONLY)
        res = bitset_oracle.query(
            values, 0, target, suffix_sum, suffix_gcd, stats, guard, reconstruct_witness=reconstruct_witness
        )
        elapsed = time.perf_counter() - t0
        stats.elapsed = elapsed
        stats.memory_peak_bytes = int(guard.get_peak_memory_mb() * 1024 * 1024)

        if res.status == OracleStatus.FEASIBLE:
            sols = [tuple(res.witness)] if res.witness is not None else []
            return SolverResult(SolverStatus.EXACT_SOL_FOUND, sols, stats, elapsed, self.name, True)
        elif res.status == OracleStatus.INFEASIBLE:
            return SolverResult(SolverStatus.EXACT_NO_SOL, [], stats, elapsed, self.name, True)
        else:
            return SolverResult(
                SolverStatus.UNKNOWN_MEMORY, [], stats, elapsed, self.name, False, res.reason
            )


class MITMSolver(BaseSubsetSumSolver):
    def __init__(self):
        super().__init__("Meet-in-the-Middle (MITM)")

    def solve(
        self,
        values: List[int],
        target: int,
        mode: SearchMode = SearchMode.FIRST_SOLUTION,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> SolverResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()
        stats = Stats()
        t0 = time.perf_counter()
        suffix_sum = build_suffix_sum(values)
        suffix_gcd = build_suffix_gcd(values)

        mitm_oracle = MITMOracle()
        res = mitm_oracle.query(values, 0, target, suffix_sum, suffix_gcd, stats, guard)
        elapsed = time.perf_counter() - t0
        stats.elapsed = elapsed
        stats.memory_peak_bytes = int(guard.get_peak_memory_mb() * 1024 * 1024)

        if res.status == OracleStatus.FEASIBLE:
            sols = [tuple(res.witness)] if res.witness is not None else []
            return SolverResult(SolverStatus.EXACT_SOL_FOUND, sols, stats, elapsed, self.name, True)
        elif res.status == OracleStatus.INFEASIBLE:
            return SolverResult(SolverStatus.EXACT_NO_SOL, [], stats, elapsed, self.name, True)
        else:
            return SolverResult(
                SolverStatus.UNKNOWN_RESOURCE, [], stats, elapsed, self.name, False, res.reason
            )


def _atrs_worker_task(args) -> Tuple[Stats, List[Tuple[int, ...]], bool]:
    """
    Worker task executed in parallel process on state frontier.
    Uses bounded local memoization and adaptive feasibility oracles.
    In ALL_SOLUTIONS mode:
      - FEASIBLE from deep oracles does NOT add partial witness; exhaustive branching continues.
      - INFEASIBLE from any oracle safely prunes the subtree.
    """
    (
        values,
        start_idx,
        initial_remainder,
        prefix_chosen,
        mode_val,
        max_memo,
        timeout_sec,
        max_mem_bytes
    ) = args

    mode = SearchMode(mode_val)
    guard = ResourceGuard(
        max_memory_bytes=max_mem_bytes,
        timeout_seconds=timeout_sec,
        max_memo_states=max_memo
    )
    guard.start()

    stats = Stats()
    solutions: List[Tuple[int, ...]] = []
    dead_states: Set[Tuple[int, int]] = set()

    suffix_sum = build_suffix_sum(values)
    suffix_gcd = build_suffix_gcd(values)
    trivial_solver = TrivialExactSolver()
    manager = AdaptiveOracleManager()
    n = len(values)

    try:
        def search(idx: int, rem: int, current_path: List[int]) -> bool:
            stats.nodes += 1
            guard.periodic_check(interval=256)

            # 1. Terminal Check
            if rem == 0:
                stats.solutions_count += 1
                solutions.append(tuple(prefix_chosen + current_path))
                return True

            if rem < 0 or idx >= n:
                stats.pruned += 1
                return False

            state = (idx, rem)
            if state in dead_states:
                stats.memo_hits += 1
                stats.pruned += 1
                return False

            # 2. Trivial Exact Check (for FIRST_SOLUTION and DECISION_ONLY)
            if mode != SearchMode.ALL_SOLUTIONS:
                triv_res = trivial_solver.query(values, idx, rem, suffix_sum, suffix_gcd, stats, guard)
                if triv_res.status == OracleStatus.FEASIBLE and triv_res.witness is not None:
                    stats.solutions_count += 1
                    full_sol = prefix_chosen + current_path + triv_res.witness
                    solutions.append(tuple(full_sol))
                    return True

            # 3. Adaptive Feasibility Oracles Evaluation
            allow_deep = (n - idx <= 32)
            oracle_res = manager.evaluate_state(
                values, idx, rem, suffix_sum, suffix_gcd, stats, guard, allow_deep_oracles=allow_deep
            )

            if oracle_res.status == OracleStatus.INFEASIBLE:
                if len(dead_states) < (guard.max_memo_states or 50_000):
                    dead_states.add(state)
                return False

            if oracle_res.status == OracleStatus.FEASIBLE:
                if mode != SearchMode.ALL_SOLUTIONS:
                    stats.solutions_count += 1
                    full_sol = prefix_chosen + current_path + (oracle_res.witness or [])
                    solutions.append(tuple(full_sol))
                    return True

            # 4. Branching DFS
            found_any = False
            for j in range(idx, n):
                val = values[j]
                stats.comparisons += 1
                if val > rem:
                    stats.pruned += (n - j)
                    break

                stats.arithmetic += 1
                current_path.append(val)
                if search(j + 1, rem - val, current_path):
                    found_any = True
                    if mode != SearchMode.ALL_SOLUTIONS:
                        current_path.pop()
                        return True
                current_path.pop()

            if not found_any and len(dead_states) < (guard.max_memo_states or 50_000):
                dead_states.add(state)
                stats.dead_states_peak = max(stats.dead_states_peak, len(dead_states))

            return found_any

        search(start_idx, initial_remainder, [])
        return stats, solutions, True
    except ResourceLimitExceeded:
        return stats, solutions, False


class ATRSSolver(BaseSubsetSumSolver):
    def __init__(self):
        super().__init__("ATRS (Adaptive Target-Remainder Solver)")

    def solve(
        self,
        values: List[int],
        target: int,
        mode: SearchMode = SearchMode.FIRST_SOLUTION,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = None,
    ) -> SolverResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()

        stats = Stats()
        solutions: List[Tuple[int, ...]] = []
        n = len(values)
        t0 = time.perf_counter()

        if n == 0 or target <= 0:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            return SolverResult(SolverStatus.EXACT_NO_SOL, [], stats, elapsed, self.name, True)

        suffix_sum = build_suffix_sum(values)
        suffix_gcd = build_suffix_gcd(values)
        trivial_solver = TrivialExactSolver()
        manager = AdaptiveOracleManager()

        # 1. Root Trivial Check (for single solution / decision)
        if mode != SearchMode.ALL_SOLUTIONS:
            triv_res = trivial_solver.query(values, 0, target, suffix_sum, suffix_gcd, stats, guard)
            if triv_res.status == OracleStatus.FEASIBLE and triv_res.witness is not None:
                elapsed = time.perf_counter() - t0
                stats.elapsed = elapsed
                stats.solutions_count = 1
                return SolverResult(
                    SolverStatus.EXACT_SOL_FOUND, [tuple(triv_res.witness)], stats, elapsed, self.name, True
                )

        # 2. Root Feasibility Oracle Evaluation
        root_res = manager.evaluate_state(
            values, 0, target, suffix_sum, suffix_gcd, stats, guard, allow_deep_oracles=True
        )

        if root_res.status == OracleStatus.FEASIBLE and mode != SearchMode.ALL_SOLUTIONS:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            stats.solutions_count = 1
            wit = [tuple(root_res.witness)] if root_res.witness is not None else []
            return SolverResult(SolverStatus.EXACT_SOL_FOUND, wit, stats, elapsed, self.name, True)

        if root_res.status == OracleStatus.INFEASIBLE:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            return SolverResult(SolverStatus.EXACT_NO_SOL, [], stats, elapsed, self.name, True)

        # 3. Frontier Subtree Task Generation
        tasks = []
        for j in range(n):
            val = values[j]
            stats.comparisons += 1
            if val > target:
                stats.pruned += (n - j)
                break

            stats.arithmetic += 1
            tasks.append((
                values,
                j + 1,
                target - val,
                [val],
                mode.value,
                guard.max_memo_states,
                guard.timeout_seconds,
                guard.max_memory_bytes,
            ))

        if not tasks:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            return SolverResult(SolverStatus.EXACT_NO_SOL, [], stats, elapsed, self.name, True)

        cpu_total = os.cpu_count() or 1
        if num_workers is None:
            num_workers = min(len(tasks), cpu_total)

        # Partition resource budget per worker
        worker_guard = guard.split_for_workers(num_workers)
        tasks = [
            (
                t[0],
                t[1],
                t[2],
                t[3],
                t[4],
                worker_guard.max_memo_states,
                worker_guard.timeout_seconds,
                worker_guard.max_memory_bytes
            )
            for t in tasks
        ]

        all_ok = True
        try:
            if num_workers <= 1 or len(tasks) <= 1 or n <= 14:
                for t in tasks:
                    sub_stats, sub_sols, ok = _atrs_worker_task(t)
                    stats.add(sub_stats)
                    if not ok:
                        all_ok = False
                    if sub_sols:
                        solutions.extend(sub_sols)
                        if mode != SearchMode.ALL_SOLUTIONS:
                            break
            else:
                with ProcessPoolExecutor(max_workers=num_workers) as executor:
                    results = executor.map(_atrs_worker_task, tasks)
                    for sub_stats, sub_sols, ok in results:
                        stats.add(sub_stats)
                        if not ok:
                            all_ok = False
                        if sub_sols:
                            solutions.extend(sub_sols)
                            if mode != SearchMode.ALL_SOLUTIONS:
                                break

            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            stats.memory_peak_bytes = int(guard.get_peak_memory_mb() * 1024 * 1024)

            if solutions:
                status = SolverStatus.EXACT_SOL_FOUND
            elif not all_ok:
                status = SolverStatus.UNKNOWN_RESOURCE
            else:
                status = SolverStatus.EXACT_NO_SOL

            return SolverResult(
                status=status,
                solutions=solutions,
                stats=stats,
                elapsed=elapsed,
                algorithm_name=self.name,
                is_exact=all_ok,
            )

        except ResourceLimitExceeded as e:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            status = SolverStatus.UNKNOWN_MEMORY if e.resource_type == "MEMORY" else SolverStatus.UNKNOWN_TIMEOUT
            return SolverResult(status, solutions, stats, elapsed, self.name, False, str(e))

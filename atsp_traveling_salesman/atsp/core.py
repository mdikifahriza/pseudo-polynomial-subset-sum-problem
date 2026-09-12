"""
ATSP - Core Solver Engine and Baseline Algorithms
Implements exact, uniform TSP solvers:
1. Brute Force (Permutations, for validation)
2. Nearest Neighbor Heuristic (Greedy Baseline)
3. Pure Held-Karp Dynamic Programming (Exact Baseline)
4. Standard Branch & Bound (Classic Baseline)
5. ATSP (Adaptive Traveling Salesman Problem Solver)
"""
import time
import os
import itertools
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor
from typing import List, Tuple, Optional, Set, Dict, Any

from .state import (
    TSPStats,
    TSPResult,
    SolverStatus,
    SearchMode,
    OracleStatus,
    OracleResult,
)
from .resource_guard import ResourceGuard, ResourceLimitExceeded
from .preprocess import (
    build_adj_matrix,
    build_min_out_edges,
    build_min_in_edges,
    compute_mst_cost,
    build_candidate_lists,
    compute_lagrangian_bound,
)
from .scheduler import AdaptiveTSPOracleManager
from .oracles.nearest_neighbor import NearestNeighborOracle
from .warmstart import SimulatedAnnealingWarmStart, AntColonyWarmStart, calculate_tour_cost


class BaseTSPSolver(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def solve(
        self,
        adj: List[List[float]],
        mode: SearchMode = SearchMode.SHORTEST_TOUR,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> TSPResult:
        pass


class BruteForceTSPSolver(BaseTSPSolver):
    def __init__(self):
        super().__init__("Brute Force")

    def solve(
        self,
        adj: List[List[float]],
        mode: SearchMode = SearchMode.SHORTEST_TOUR,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> TSPResult:
        if guard is None:
            guard = ResourceGuard(timeout_seconds=30.0)
        guard.start()
        stats = TSPStats()
        n = len(adj)
        t0 = time.perf_counter()

        if n < 3:
            return TSPResult(SolverStatus.EXACT_NO_SOL, [], float("inf"), stats, 0.0, self.name, True)

        best_cost = float("inf")
        best_tours: List[List[int]] = []

        try:
            other_cities = list(range(1, n))
            for perm in itertools.permutations(other_cities):
                stats.nodes += 1
                guard.periodic_check(interval=1024)

                cost = adj[0][perm[0]]
                valid = (cost < float("inf"))
                for i in range(len(perm) - 1):
                    if not valid:
                        break
                    d = adj[perm[i]][perm[i + 1]]
                    if d >= float("inf"):
                        valid = False
                        break
                    cost += d

                if valid:
                    d_back = adj[perm[-1]][0]
                    if d_back < float("inf"):
                        cost += d_back
                        stats.comparisons += 1
                        if cost < best_cost:
                            best_cost = cost
                            best_tours = [[0] + list(perm) + [0]]
                            stats.bound_improvements += 1
                            if mode == SearchMode.DECISION_ONLY and best_cost < float("inf"):
                                break
                        elif cost == best_cost and mode == SearchMode.ALL_OPTIMAL_TOURS:
                            best_tours.append([0] + list(perm) + [0])

            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            stats.memory_peak_bytes = int(guard.get_peak_memory_mb() * 1024 * 1024)
            status = SolverStatus.EXACT_SOL_FOUND if best_tours else SolverStatus.EXACT_NO_SOL
            return TSPResult(status, best_tours, best_cost, stats, elapsed, self.name, True)

        except ResourceLimitExceeded as e:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            status = SolverStatus.UNKNOWN_MEMORY if e.resource_type == "MEMORY" else SolverStatus.UNKNOWN_TIMEOUT
            return TSPResult(status, best_tours, best_cost, stats, elapsed, self.name, False, str(e))


class NearestNeighborTSPSolver(BaseTSPSolver):
    def __init__(self):
        super().__init__("Nearest Neighbor (Greedy)")

    def solve(
        self,
        adj: List[List[float]],
        mode: SearchMode = SearchMode.SHORTEST_TOUR,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> TSPResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()
        stats = TSPStats()
        n = len(adj)
        t0 = time.perf_counter()

        cur = 0
        unvisited = set(range(1, n))
        tour = [0]
        total_cost = 0.0
        feasible = True

        while unvisited:
            stats.nodes += 1
            best_next = -1
            best_dist = float("inf")
            for cand in unvisited:
                stats.comparisons += 1
                d = adj[cur][cand]
                if d < best_dist:
                    best_dist = d
                    best_next = cand

            if best_next == -1 or best_dist >= float("inf"):
                feasible = False
                break

            total_cost += best_dist
            tour.append(best_next)
            unvisited.remove(best_next)
            cur = best_next

        if feasible and adj[cur][0] < float("inf"):
            total_cost += adj[cur][0]
            tour.append(0)
            status = SolverStatus.EXACT_SOL_FOUND
            tours = [tour]
        else:
            status = SolverStatus.EXACT_NO_SOL
            tours = []
            total_cost = float("inf")

        elapsed = time.perf_counter() - t0
        stats.elapsed = elapsed
        return TSPResult(status, tours, total_cost, stats, elapsed, self.name, False, "Heuristic: Non-exact")


class HeldKarpTSPSolver(BaseTSPSolver):
    def __init__(self):
        super().__init__("Held-Karp DP")

    def solve(
        self,
        adj: List[List[float]],
        mode: SearchMode = SearchMode.SHORTEST_TOUR,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> TSPResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()
        stats = TSPStats()
        n = len(adj)
        t0 = time.perf_counter()

        if n > 22 and not guard.is_held_karp_allowed(n):
            elapsed = time.perf_counter() - t0
            return TSPResult(
                SolverStatus.UNKNOWN_MEMORY, [], float("inf"), stats, elapsed, self.name, False, "Instance too large for Pure Held-Karp"
            )

        try:
            k = n - 1
            # dp[mask][i]: min cost to start at 0, visit subset of {1..n-1} given by mask, ending at city (i+1)
            dp: List[List[float]] = [[float("inf")] * k for _ in range(1 << k)]
            parent: List[List[int]] = [[-1] * k for _ in range(1 << k)]

            for i in range(k):
                stats.nodes += 1
                d = adj[0][i + 1]
                if d < float("inf"):
                    dp[1 << i][i] = d

            for mask in range(1, 1 << k):
                guard.periodic_check(interval=1024)
                for i in range(k):
                    if not (mask & (1 << i)):
                        continue
                    c_cur = dp[mask][i]
                    if c_cur >= float("inf"):
                        continue

                    for j in range(k):
                        if mask & (1 << j):
                            continue
                        d_ij = adj[i + 1][j + 1]
                        if d_ij >= float("inf"):
                            continue
                        next_mask = mask | (1 << j)
                        new_cost = c_cur + d_ij
                        stats.comparisons += 1
                        if new_cost < dp[next_mask][j]:
                            dp[next_mask][j] = new_cost
                            parent[next_mask][j] = i

            full_mask = (1 << k) - 1
            best_cost = float("inf")
            best_end = -1

            for i in range(k):
                c_end = dp[full_mask][i]
                if c_end < float("inf"):
                    d_orig = adj[i + 1][0]
                    if d_orig < float("inf"):
                        tot = c_end + d_orig
                        stats.comparisons += 1
                        if tot < best_cost:
                            best_cost = tot
                            best_end = i

            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            stats.memory_peak_bytes = int(guard.get_peak_memory_mb() * 1024 * 1024)

            if best_cost < float("inf") and best_end != -1:
                path = []
                curr_mask = full_mask
                curr_node = best_end
                while curr_node != -1:
                    path.append(curr_node + 1)
                    prev_node = parent[curr_mask][curr_node]
                    curr_mask ^= (1 << curr_node)
                    curr_node = prev_node
                path.reverse()
                tour = [0] + path + [0]
                return TSPResult(SolverStatus.EXACT_SOL_FOUND, [tour], best_cost, stats, elapsed, self.name, True)
            else:
                return TSPResult(SolverStatus.EXACT_NO_SOL, [], float("inf"), stats, elapsed, self.name, True)

        except ResourceLimitExceeded as e:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            status = SolverStatus.UNKNOWN_MEMORY if e.resource_type == "MEMORY" else SolverStatus.UNKNOWN_TIMEOUT
            return TSPResult(status, [], float("inf"), stats, elapsed, self.name, False, str(e))


class BranchBoundTSPSolver(BaseTSPSolver):
    def __init__(self):
        super().__init__("Branch and Bound (Classic)")

    def solve(
        self,
        adj: List[List[float]],
        mode: SearchMode = SearchMode.SHORTEST_TOUR,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> TSPResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()
        stats = TSPStats()
        n = len(adj)
        t0 = time.perf_counter()

        min_out = build_min_out_edges(adj)
        best_cost = float("inf")
        best_tours: List[List[int]] = []

        # Get initial upper bound from Nearest Neighbor
        nn_solver = NearestNeighborTSPSolver()
        nn_res = nn_solver.solve(adj, guard=guard)
        if nn_res.has_solution:
            best_cost = nn_res.best_cost
            best_tours = [nn_res.tours[0]]

        try:
            def dfs(current: int, visited_mask: int, count: int, cost_so_far: float, path: List[int]):
                nonlocal best_cost, best_tours
                stats.nodes += 1
                guard.periodic_check(interval=256)

                if count == n:
                    d_back = adj[current][0]
                    if d_back < float("inf"):
                        total = cost_so_far + d_back
                        stats.comparisons += 1
                        if total < best_cost:
                            best_cost = total
                            best_tours = [list(path) + [0]]
                            stats.bound_improvements += 1
                        elif total == best_cost and mode == SearchMode.ALL_OPTIMAL_TOURS:
                            best_tours.append(list(path) + [0])
                    return

                # Simple lower bound: cost_so_far + sum(min_out for remaining)
                lb = cost_so_far + min_out[current]
                for v in range(1, n):
                    if not (visited_mask & (1 << v)):
                        lb += min_out[v]

                stats.bound_checks += 1
                if lb >= best_cost:
                    stats.pruned += 1
                    return

                # Explore candidate branches sorted by edge cost
                branches = []
                for v in range(1, n):
                    if not (visited_mask & (1 << v)):
                        d = adj[current][v]
                        if d < float("inf"):
                            branches.append((d, v))

                branches.sort(key=lambda x: x[0])
                for d, v in branches:
                    if cost_so_far + d < best_cost:
                        dfs(v, visited_mask | (1 << v), count + 1, cost_so_far + d, path + [v])

            dfs(0, 1, 1, 0.0, [0])
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            stats.memory_peak_bytes = int(guard.get_peak_memory_mb() * 1024 * 1024)
            status = SolverStatus.EXACT_SOL_FOUND if best_tours else SolverStatus.EXACT_NO_SOL
            return TSPResult(status, best_tours, best_cost, stats, elapsed, self.name, True)

        except ResourceLimitExceeded as e:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            status = SolverStatus.UNKNOWN_MEMORY if e.resource_type == "MEMORY" else SolverStatus.UNKNOWN_TIMEOUT
            return TSPResult(status, best_tours, best_cost, stats, elapsed, self.name, False, str(e))


def _atsp_worker_task(args) -> Tuple[TSPStats, List[List[int]], float, bool, List[Tuple[List[int], float]]]:
    """
    Worker task executed in parallel process on state frontier.
    Uses dynamic adaptive oracles (Bound, MST 1-Tree, Degree, Held-Karp).
    Priority 3: Candidate Neighbor Lists reduce DFS branching from O(n) to O(k).
    """
    (
        adj,
        first_city,
        initial_cost,
        initial_path,
        initial_visited_mask,
        mode_val,
        initial_best_cost,
        max_memo,
        timeout_sec,
        max_mem_bytes,
        candidates,           # Priority 3: precomputed k-nearest neighbor lists
    ) = args

    mode = SearchMode(mode_val)
    guard = ResourceGuard(
        max_memory_bytes=max_mem_bytes,
        timeout_seconds=timeout_sec,
        max_memo_states=max_memo
    )
    guard.start()

    stats = TSPStats()
    n = len(adj)
    min_out = build_min_out_edges(adj)
    min_in = build_min_in_edges(adj)
    manager = AdaptiveTSPOracleManager()

    best_cost = initial_best_cost
    best_tours: List[List[int]] = []
    discovered_tours: List[Tuple[List[int], float]] = []

    try:
        def search(current: int, visited_mask: int, count: int, cost_so_far: float, path: List[int]):
            nonlocal best_cost, best_tours
            stats.nodes += 1
            guard.periodic_check(interval=256)

            # 1. Terminal Check
            if count == n:
                d_back = adj[current][0]
                if d_back < float("inf"):
                    total = cost_so_far + d_back
                    stats.comparisons += 1
                    discovered_tours.append((list(path) + [0], total))
                    if total < best_cost:
                        best_cost = total
                        best_tours = [list(path) + [0]]
                        stats.bound_improvements += 1
                    elif total == best_cost and mode == SearchMode.ALL_OPTIMAL_TOURS:
                        best_tours.append(list(path) + [0])
                return

            # Compute unvisited tuple
            unvisited_list = [v for v in range(1, n) if not (visited_mask & (1 << v))]
            unvisited = tuple(unvisited_list)

            # 2. Adaptive Oracle Evaluation
            oracle_res = manager.evaluate_state(
                adj,
                current,
                visited_mask,
                unvisited,
                cost_so_far,
                best_cost,
                min_out,
                min_in,
                stats,
                guard
            )

            if oracle_res.status == OracleStatus.INFEASIBLE:
                return

            if oracle_res.status == OracleStatus.FEASIBLE and oracle_res.tour_witness is not None:
                total_cand = oracle_res.cost_witness or (cost_so_far + sum(adj[a][b] for a, b in zip([current] + oracle_res.tour_witness[:-1], oracle_res.tour_witness)))
                stats.comparisons += 1
                discovered_tours.append((list(path) + oracle_res.tour_witness, total_cand))
                if total_cand < best_cost:
                    best_cost = total_cand
                    best_tours = [list(path) + oracle_res.tour_witness]
                    stats.bound_improvements += 1
                elif total_cand == best_cost and mode == SearchMode.ALL_OPTIMAL_TOURS:
                    best_tours.append(list(path) + oracle_res.tour_witness)
                return

            # 3. Branching with Pre-Sorted Candidate Neighbors (Priority 3)
            # Evaluates nearest neighbors first with zero object allocations in DFS.
            for v, d in candidates[current]:
                if not (visited_mask & (1 << v)):
                    if cost_so_far + d < best_cost:
                        search(v, visited_mask | (1 << v), count + 1, cost_so_far + d, path + [v])

        search(first_city, initial_visited_mask, 2, initial_cost, initial_path)
        return stats, best_tours, best_cost, True, discovered_tours

    except ResourceLimitExceeded:
        return stats, best_tours, best_cost, False, discovered_tours



class SimulatedAnnealingTSPSolver(BaseTSPSolver):
    def __init__(self, time_limit_sec: float = 2.0):
        super().__init__("Simulated Annealing")
        self.time_limit_sec = time_limit_sec

    def solve(
        self,
        adj: List[List[float]],
        mode: SearchMode = SearchMode.SHORTEST_TOUR,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> TSPResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()
        stats = TSPStats()
        t0 = time.perf_counter()

        nn_solver = NearestNeighborTSPSolver()
        nn_res = nn_solver.solve(adj, guard=guard)
        init_tour = nn_res.tours[0] if nn_res.has_solution else []
        init_cost = nn_res.best_cost if nn_res.has_solution else float("inf")

        budget = min(self.time_limit_sec, guard.timeout_seconds if guard.timeout_seconds else 2.0)
        sa = SimulatedAnnealingWarmStart()
        best_tour, best_cost = sa.run(adj, init_tour, init_cost, time_budget_sec=budget, guard=guard)

        elapsed = time.perf_counter() - t0
        stats.elapsed = elapsed
        status = SolverStatus.EXACT_SOL_FOUND if (best_tour and best_cost < float("inf")) else SolverStatus.EXACT_NO_SOL
        return TSPResult(status, [best_tour] if best_tour else [], best_cost, stats, elapsed, self.name, False, "Metaheuristic: Non-exact")


class ACOTSPSolver(BaseTSPSolver):
    def __init__(self, time_limit_sec: float = 3.0):
        super().__init__("Ant Colony Optimization")
        self.time_limit_sec = time_limit_sec

    def solve(
        self,
        adj: List[List[float]],
        mode: SearchMode = SearchMode.SHORTEST_TOUR,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = 1,
    ) -> TSPResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()
        stats = TSPStats()
        t0 = time.perf_counter()

        nn_solver = NearestNeighborTSPSolver()
        nn_res = nn_solver.solve(adj, guard=guard)
        init_tour = nn_res.tours[0] if nn_res.has_solution else []
        init_cost = nn_res.best_cost if nn_res.has_solution else float("inf")

        budget = min(self.time_limit_sec, guard.timeout_seconds if guard.timeout_seconds else 3.0)
        aco = AntColonyWarmStart()
        best_tour, best_cost = aco.run(adj, init_tour, init_cost, time_budget_sec=budget, guard=guard)

        elapsed = time.perf_counter() - t0
        stats.elapsed = elapsed
        status = SolverStatus.EXACT_SOL_FOUND if (best_tour and best_cost < float("inf")) else SolverStatus.EXACT_NO_SOL
        return TSPResult(status, [best_tour] if best_tour else [], best_cost, stats, elapsed, self.name, False, "Metaheuristic: Non-exact")


class ATSPSolver(BaseTSPSolver):
    def __init__(
        self,
        enable_sa: bool = True,
        enable_aco: bool = True,
        sa_budget_ratio: float = 0.05,
        aco_budget_ratio: float = 0.10,
    ):
        super().__init__("ATSP (Adaptive TSP Solver)")
        self.enable_sa = enable_sa
        self.enable_aco = enable_aco
        self.sa_budget_ratio = sa_budget_ratio
        self.aco_budget_ratio = aco_budget_ratio

    def solve(
        self,
        adj: List[List[float]],
        mode: SearchMode = SearchMode.SHORTEST_TOUR,
        guard: Optional[ResourceGuard] = None,
        num_workers: Optional[int] = None,
    ) -> TSPResult:
        if guard is None:
            guard = ResourceGuard()
        guard.start()
        stats = TSPStats()
        n = len(adj)
        t0 = time.perf_counter()

        if n < 3:
            return TSPResult(SolverStatus.EXACT_NO_SOL, [], float("inf"), stats, 0.0, self.name, True)

        # -------------------------------------------------------------
        # Phase 0: Multi-Heuristic Warm-Start Pipeline
        # -------------------------------------------------------------
        # 0a. Root Fast Initialization using Nearest Neighbor
        nn_solver = NearestNeighborTSPSolver()
        nn_res = nn_solver.solve(adj, guard=guard)
        best_cost = nn_res.best_cost if nn_res.has_solution else float("inf")
        best_tours: List[List[int]] = [nn_res.tours[0]] if nn_res.has_solution else []

        if best_cost < float("inf"):
            stats.bound_improvements += 1

        # 0b. Simulated Annealing Warm-Start (2-opt, for n >= 6)
        if self.enable_sa and n >= 6 and best_cost < float("inf"):
            timeout = guard.timeout_seconds if guard.timeout_seconds else 30.0
            sa_budget = min(0.6, timeout * self.sa_budget_ratio)
            sa = SimulatedAnnealingWarmStart()
            sa_tour, sa_cost = sa.run(adj, best_tours[0], best_cost, time_budget_sec=sa_budget, guard=guard)
            if sa_cost < best_cost and sa_tour:
                best_cost = sa_cost
                best_tours = [sa_tour]
                stats.bound_improvements += 1

        # 0c. Ant Colony Warm-Start (for n >= 18)
        if self.enable_aco and n >= 18 and best_cost < float("inf"):
            timeout = guard.timeout_seconds if guard.timeout_seconds else 30.0
            aco_budget = min(1.5, timeout * self.aco_budget_ratio)
            aco = AntColonyWarmStart()
            aco_tour, aco_cost = aco.run(adj, best_tours[0], best_cost, time_budget_sec=aco_budget, guard=guard)
            if aco_cost < best_cost and aco_tour:
                best_cost = aco_cost
                best_tours = [aco_tour]
                stats.bound_improvements += 1

        # -------------------------------------------------------------
        # Phase 0d: Lagrangian Subgradient Bound (Priority 2)
        # Run once at root. Tightens global best_cost lower bound so DFS prunes harder.
        # Overhead: O(80 * n^2) — negligible vs DFS savings for n > 20.
        # -------------------------------------------------------------
        if n >= 10:
            lagrangian_lb = compute_lagrangian_bound(adj, best_cost, max_iter=80)
            stats.mst_computations += 1  # record that we ran it
            # If the Lagrangian lower bound already equals (or exceeds) best_known,
            # the current best_known IS the optimal — no DFS needed.
            if lagrangian_lb >= best_cost - 1e-6:
                elapsed = time.perf_counter() - t0
                stats.elapsed = elapsed
                return TSPResult(
                    SolverStatus.EXACT_SOL_FOUND, best_tours, best_cost,
                    stats, elapsed, self.name, True
                )

        # -------------------------------------------------------------
        # Phase 0e: Precompute Candidate Neighbor Lists (Priority 3)
        # O(n^2 log n) once — trivial cost, large DFS savings for n > 15.
        # -------------------------------------------------------------
        candidates = build_candidate_lists(adj)

        # -------------------------------------------------------------
        # Phase 1: Frontier Task Generation (Start city 0 -> valid first cities)
        # -------------------------------------------------------------
        tasks = []
        for first_city in range(1, n):
            d = adj[0][first_city]
            if d < float("inf"):
                stats.comparisons += 1
                if d < best_cost:
                    tasks.append((
                        adj,
                        first_city,
                        d,
                        [0, first_city],
                        1 | (1 << first_city),
                        mode.value,
                        best_cost,
                        guard.max_memo_states,
                        guard.timeout_seconds,
                        guard.max_memory_bytes,
                        candidates,
                    ))

        if not tasks:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            return TSPResult(SolverStatus.EXACT_NO_SOL, [], float("inf"), stats, elapsed, self.name, True)

        cpu_total = os.cpu_count() or 1
        if num_workers is None:
            num_workers = min(len(tasks), cpu_total)

        worker_guard = guard.split_for_workers(num_workers)
        tasks = [
            (
                t[0],   # adj
                t[1],   # first_city
                t[2],   # initial_cost
                t[3],   # initial_path
                t[4],   # initial_visited_mask
                t[5],   # mode_val
                best_cost,
                worker_guard.max_memo_states,
                worker_guard.timeout_seconds,
                worker_guard.max_memory_bytes,
                t[10],  # candidates
            )
            for t in tasks
        ]

        all_ok = True
        all_discovered: List[Tuple[List[int], float]] = []
        try:
            if num_workers <= 1 or len(tasks) <= 1 or n <= 10:
                for t in tasks:
                    t_updated = (t[0], t[1], t[2], t[3], t[4], t[5], best_cost, t[7], t[8], t[9], t[10])
                    sub_stats, sub_tours, sub_cost, ok, sub_disc = _atsp_worker_task(t_updated)
                    stats.add(sub_stats)
                    all_discovered.extend(sub_disc)
                    if not ok:
                        all_ok = False
                    if sub_cost < best_cost and sub_tours:
                        best_cost = sub_cost
                        best_tours = sub_tours
                    elif sub_cost == best_cost and mode == SearchMode.ALL_OPTIMAL_TOURS:
                        best_tours.extend(sub_tours)
            else:
                with ProcessPoolExecutor(max_workers=num_workers) as executor:
                    results = executor.map(_atsp_worker_task, tasks)
                    for sub_stats, sub_tours, sub_cost, ok, sub_disc in results:
                        stats.add(sub_stats)
                        all_discovered.extend(sub_disc)
                        if not ok:
                            all_ok = False
                        if sub_cost < best_cost and sub_tours:
                            best_cost = sub_cost
                            best_tours = sub_tours
                        elif sub_cost == best_cost and mode == SearchMode.ALL_OPTIMAL_TOURS:
                            best_tours.extend(sub_tours)

            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            stats.memory_peak_bytes = int(guard.get_peak_memory_mb() * 1024 * 1024)

            # Collect and rank ALL unique candidate tours without limit
            all_tours_map: Dict[Tuple[int, ...], float] = {}
            for t, c in all_discovered:
                if c < float("inf") and len(t) == n + 1:
                    all_tours_map[tuple(t)] = c

            for t in best_tours:
                c = calculate_tour_cost(adj, t)
                if c < float("inf") and len(t) == n + 1:
                    all_tours_map[tuple(t)] = c

            if nn_res.has_solution and nn_res.tours:
                t = nn_res.tours[0]
                c = calculate_tour_cost(adj, t)
                if c < float("inf") and len(t) == n + 1:
                    all_tours_map[tuple(t)] = c

            if 'sa_tour' in locals() and sa_tour:
                c = calculate_tour_cost(adj, sa_tour)
                if c < float("inf") and len(sa_tour) == n + 1:
                    all_tours_map[tuple(sa_tour)] = c

            if 'aco_tour' in locals() and aco_tour:
                c = calculate_tour_cost(adj, aco_tour)
                if c < float("inf") and len(aco_tour) == n + 1:
                    all_tours_map[tuple(aco_tour)] = c

            # Sort all candidate tours from best (Rank 1) to worst
            ranked = sorted(
                [(list(t), c) for t, c in all_tours_map.items()],
                key=lambda x: x[1]
            )

            if best_tours and best_cost < float("inf"):
                status = SolverStatus.EXACT_SOL_FOUND
            elif not all_ok:
                status = SolverStatus.UNKNOWN_RESOURCE
            else:
                status = SolverStatus.EXACT_NO_SOL

            return TSPResult(
                status=status,
                tours=best_tours,
                best_cost=best_cost,
                stats=stats,
                elapsed=elapsed,
                algorithm_name=self.name,
                is_exact=all_ok,
                ranked_tours=ranked,
            )

        except ResourceLimitExceeded as e:
            elapsed = time.perf_counter() - t0
            stats.elapsed = elapsed
            status = SolverStatus.UNKNOWN_MEMORY if e.resource_type == "MEMORY" else SolverStatus.UNKNOWN_TIMEOUT
            return TSPResult(status, best_tours, best_cost, stats, elapsed, self.name, False, str(e), ranked_tours=[])


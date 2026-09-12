"""
ATSP - Simulated Annealing Warm-Start Solver
Uses 2-opt neighborhood mutations and Metropolis cooling schedule to quickly find
near-optimal upper bounds within strict time limits.
"""
import time
import math
import random
from typing import List, Tuple, Optional

from .base import BaseWarmStart
from ..resource_guard import ResourceGuard, ResourceLimitExceeded


def calculate_tour_cost(adj: List[List[float]], tour: List[int]) -> float:
    """Calculates total Hamiltonian cycle cost of tour."""
    n = len(adj)
    if len(tour) != n + 1 or tour[0] != 0 or tour[-1] != 0:
        return float("inf")
    cost = 0.0
    for i in range(len(tour) - 1):
        d = adj[tour[i]][tour[i + 1]]
        if d >= float("inf"):
            return float("inf")
        cost += d
    return cost


class SimulatedAnnealingWarmStart(BaseWarmStart):
    def __init__(
        self,
        alpha: float = 0.997,
        cooling_steps: int = 50_000,
        seed: Optional[int] = None,
    ):
        super().__init__("Simulated Annealing")
        self.alpha = alpha
        self.cooling_steps = cooling_steps
        self.seed = seed

    def run(
        self,
        adj: List[List[float]],
        initial_tour: List[int],
        initial_cost: float,
        time_budget_sec: float = 0.5,
        guard: Optional[ResourceGuard] = None,
    ) -> Tuple[List[int], float]:
        t0 = time.perf_counter()
        n = len(adj)
        if n < 4 or not initial_tour or initial_cost >= float("inf"):
            return initial_tour, initial_cost

        if self.seed is not None:
            random.seed(self.seed)

        best_tour = list(initial_tour)
        best_cost = initial_cost

        curr_tour = list(initial_tour)
        curr_cost = initial_cost

        # Temperature initialization
        t_init = max(1.0, initial_cost * 0.15)
        t_min = max(1e-5, initial_cost * 1e-4)
        t_curr = t_init

        # Maximum iteration budget based on problem size
        max_iters = min(self.cooling_steps, max(1000, n * n * 200))
        check_interval = 256

        # Check if symmetric matrix
        is_symmetric = True
        for i in range(min(5, n)):
            for j in range(i + 1, min(5, n)):
                if abs(adj[i][j] - adj[j][i]) > 1e-5:
                    is_symmetric = False
                    break

        for iteration in range(max_iters):
            if iteration % check_interval == 0:
                if (time.perf_counter() - t0) >= time_budget_sec:
                    break
                if guard is not None:
                    try:
                        guard.check_time()
                    except ResourceLimitExceeded:
                        break

            # Pick 2-opt inversion endpoints in range [1 .. n-1]
            i = random.randint(1, n - 2)
            j = random.randint(i + 1, n - 1)

            if is_symmetric:
                # Fast delta cost O(1) for symmetric TSP
                u1, v1 = curr_tour[i - 1], curr_tour[i]
                u2, v2 = curr_tour[j], curr_tour[j + 1]

                old_edges = adj[u1][v1] + adj[u2][v2]
                new_edges = adj[u1][u2] + adj[v1][v2]

                if old_edges >= float("inf") or new_edges >= float("inf"):
                    delta = float("inf")
                else:
                    delta = new_edges - old_edges
            else:
                # Full evaluation for asymmetric instances
                cand_tour = curr_tour[:i] + curr_tour[i:j + 1][::-1] + curr_tour[j + 1:]
                cand_cost = calculate_tour_cost(adj, cand_tour)
                delta = cand_cost - curr_cost

            # Acceptance rule
            accept = False
            if delta < -1e-9:
                accept = True
            elif delta < float("inf") and t_curr > 1e-7:
                prob = math.exp(-delta / t_curr)
                if random.random() < prob:
                    accept = True

            if accept:
                if is_symmetric:
                    curr_tour[i:j + 1] = reversed(curr_tour[i:j + 1])
                    curr_cost += delta
                else:
                    curr_tour = cand_tour
                    curr_cost = cand_cost

                if curr_cost < best_cost:
                    # Double check correctness of cost
                    verified_cost = calculate_tour_cost(adj, curr_tour)
                    if verified_cost < best_cost:
                        best_cost = verified_cost
                        best_tour = list(curr_tour)

            # Cool down temperature
            t_curr = max(t_min, t_curr * self.alpha)

        return best_tour, best_cost

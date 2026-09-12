"""
ATSP - Ant Colony Optimization (ACO / MMAS) Warm-Start Solver
Constructs collective pheromone trails to explore promising tour basins for medium-large instances.
"""
import time
import random
from typing import List, Tuple, Optional

from .base import BaseWarmStart
from .sa import calculate_tour_cost
from ..resource_guard import ResourceGuard, ResourceLimitExceeded


class AntColonyWarmStart(BaseWarmStart):
    def __init__(
        self,
        n_ants: int = 15,
        alpha: float = 1.0,
        beta: float = 3.5,
        rho: float = 0.1,
        max_iterations: int = 150,
        seed: Optional[int] = None,
    ):
        super().__init__("Ant Colony Optimization")
        self.n_ants = n_ants
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.max_iterations = max_iterations
        self.seed = seed

    def run(
        self,
        adj: List[List[float]],
        initial_tour: List[int],
        initial_cost: float,
        time_budget_sec: float = 1.5,
        guard: Optional[ResourceGuard] = None,
    ) -> Tuple[List[int], float]:
        t0 = time.perf_counter()
        n = len(adj)
        if n < 5 or not initial_tour or initial_cost >= float("inf"):
            return initial_tour, initial_cost

        if self.seed is not None:
            random.seed(self.seed)

        num_ants = min(self.n_ants, max(5, n))
        best_tour = list(initial_tour)
        best_cost = initial_cost

        # Heuristic visibility matrix: eta[i][j] = 1 / d[i][j]
        eta = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j and adj[i][j] < float("inf"):
                    d = max(1e-4, adj[i][j])
                    eta[i][j] = 1.0 / (d ** self.beta)

        # Initial pheromone levels
        tau_max = 1.0 / (max(1e-4, self.rho * initial_cost))
        tau_min = tau_max / (2.0 * n)
        tau = [[tau_max] * n for _ in range(n)]

        for iteration in range(self.max_iterations):
            if (time.perf_counter() - t0) >= time_budget_sec:
                break
            if guard is not None:
                try:
                    guard.check_time()
                except ResourceLimitExceeded:
                    break

            iter_best_tour = None
            iter_best_cost = float("inf")

            # Ants construct tours
            for ant in range(num_ants):
                tour = [0]
                visited = [False] * n
                visited[0] = True
                curr = 0

                for _ in range(n - 1):
                    # Compute transition probabilities
                    weights = []
                    candidates = []
                    for cand in range(n):
                        if not visited[cand] and adj[curr][cand] < float("inf"):
                            p = (tau[curr][cand] ** self.alpha) * eta[curr][cand]
                            if p > 1e-12:
                                weights.append(p)
                                candidates.append(cand)

                    if not candidates:
                        # Dead end
                        break

                    # Roulette wheel selection
                    total_w = sum(weights)
                    r = random.uniform(0, total_w)
                    cum = 0.0
                    chosen = candidates[-1]
                    for cand, w in zip(candidates, weights):
                        cum += w
                        if cum >= r:
                            chosen = cand
                            break

                    tour.append(chosen)
                    visited[chosen] = True
                    curr = chosen

                if len(tour) == n and adj[curr][0] < float("inf"):
                    tour.append(0)
                    cost = calculate_tour_cost(adj, tour)
                    if cost < iter_best_cost:
                        iter_best_cost = cost
                        iter_best_tour = tour

            # Update best known
            if iter_best_tour and iter_best_cost < best_cost:
                best_cost = iter_best_cost
                best_tour = list(iter_best_tour)

            # Evaporation
            for i in range(n):
                for j in range(n):
                    tau[i][j] = max(tau_min, tau[i][j] * (1.0 - self.rho))

            # Pheromone reinforcement from iteration best (or global best)
            reinforce_tour = iter_best_tour or best_tour
            reinforce_cost = iter_best_cost if iter_best_tour else best_cost
            if reinforce_tour and reinforce_cost < float("inf"):
                deposit = 1.0 / max(1e-4, reinforce_cost)
                for i in range(len(reinforce_tour) - 1):
                    u, v = reinforce_tour[i], reinforce_tour[i + 1]
                    tau[u][v] = min(tau_max, tau[u][v] + deposit)
                    tau[v][u] = min(tau_max, tau[v][u] + deposit)

        return best_tour, best_cost

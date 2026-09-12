"""
ATSP - Validation Engine
Cross-validates ATSP results against exact Brute Force and Held-Karp solvers.
"""
import math
from typing import List, Dict, Any, Optional
from .state import SearchMode, SolverStatus
from .core import BruteForceTSPSolver, HeldKarpTSPSolver, ATSPSolver


def validate_atsp_against_bruteforce(
    adj: List[List[float]],
    mode: SearchMode = SearchMode.SHORTEST_TOUR,
    tolerance: float = 1e-4
) -> Dict[str, Any]:
    """
    Validates ATSP against BruteForce (or Held-Karp) on a given distance matrix.
    """
    n = len(adj)
    if n > 11:
        # Use Held-Karp for n between 11 and 16
        ref_solver = HeldKarpTSPSolver()
        ref_name = "Held-Karp"
    else:
        ref_solver = BruteForceTSPSolver()
        ref_name = "Brute Force"

    ref_res = ref_solver.solve(adj, mode=mode)
    atsp_solver = ATSPSolver()
    atsp_res = atsp_solver.solve(adj, mode=mode, num_workers=1)

    # 1. Status consistency check
    if ref_res.status != atsp_res.status:
        return {
            "passed": False,
            "error_msg": f"Status mismatch: {ref_name}={ref_res.status.value} vs ATSP={atsp_res.status.value}",
            "ref_cost": ref_res.best_cost,
            "atsp_cost": atsp_res.best_cost,
        }

    # 2. If no solution, both agree
    if not ref_res.has_solution:
        return {
            "passed": True,
            "error_msg": None,
            "ref_cost": float("inf"),
            "atsp_cost": float("inf"),
        }

    # 3. Cost equality check
    cost_diff = abs(ref_res.best_cost - atsp_res.best_cost)
    if cost_diff > tolerance:
        return {
            "passed": False,
            "error_msg": f"Cost mismatch: {ref_name}={ref_res.best_cost:.4f} vs ATSP={atsp_res.best_cost:.4f} (diff={cost_diff:.6f})",
            "ref_cost": ref_res.best_cost,
            "atsp_cost": atsp_res.best_cost,
        }

    # 4. Tour validity check: each tour in atsp_res must be a valid Hamiltonian cycle
    for tour in atsp_res.tours:
        if len(tour) != n + 1:
            return {
                "passed": False,
                "error_msg": f"Tour length invalid: expected {n+1}, got {len(tour)}",
                "tour": tour,
            }
        if tour[0] != 0 or tour[-1] != 0:
            return {
                "passed": False,
                "error_msg": f"Tour does not start/end at 0: {tour}",
                "tour": tour,
            }
        visited_cities = set(tour[:-1])
        if len(visited_cities) != n or visited_cities != set(range(n)):
            return {
                "passed": False,
                "error_msg": f"Tour does not visit all vertices exactly once: {tour}",
                "tour": tour,
            }

        # Calculate tour cost explicitly
        calc_cost = 0.0
        for i in range(n):
            d = adj[tour[i]][tour[i + 1]]
            if d >= float("inf"):
                return {
                    "passed": False,
                    "error_msg": f"Tour traverses invalid edge ({tour[i]}, {tour[i+1]})",
                    "tour": tour,
                }
            calc_cost += d

        if abs(calc_cost - atsp_res.best_cost) > tolerance:
            return {
                "passed": False,
                "error_msg": f"Calculated tour cost {calc_cost:.4f} != reported best_cost {atsp_res.best_cost:.4f}",
                "tour": tour,
            }

    return {
        "passed": True,
        "error_msg": None,
        "ref_cost": ref_res.best_cost,
        "atsp_cost": atsp_res.best_cost,
        "ref_name": ref_name,
        "atsp_nodes": atsp_res.stats.nodes,
        "atsp_pruned": atsp_res.stats.pruned,
    }

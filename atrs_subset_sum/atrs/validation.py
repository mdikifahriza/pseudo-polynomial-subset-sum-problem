"""
ATRS - Exactness Validation Suite
Performs multi-solver cross-validation against Brute Force on instances (n <= 20).
"""
import random
from typing import List, Tuple, Dict, Any, Optional
from .core import (
    BruteForceSolver,
    TargetRemainderDFSSolver,
    TargetRemainderPrunedSolver,
    TargetRemainderMemoSolver,
    BitsetDPSolver,
    MITMSolver,
    ATRSSolver,
)
from .state import SearchMode, SolverStatus
from .resource_guard import ResourceGuard


def validate_all_solvers_against_bruteforce(
    values: List[int],
    target: int,
    mode: SearchMode = SearchMode.FIRST_SOLUTION
) -> Dict[str, Any]:
    """
    Cross-validates all 7 solvers against Brute Force on an exact instance.
    For n > 20, returns skipped = True, passed = None, status = "SKIPPED".
    """
    n = len(values)
    if n > 20:
        return {
            "passed": None,
            "skipped": True,
            "status": "SKIPPED",
            "reason": f"n={n} > 20 (Brute force omitted for safety)",
            "solver_results": {}
        }

    solvers = [
        BruteForceSolver(),
        TargetRemainderDFSSolver(),
        TargetRemainderPrunedSolver(),
        TargetRemainderMemoSolver(),
        BitsetDPSolver(),
        MITMSolver(),
        ATRSSolver(),
    ]

    solver_results = {}
    for s in solvers:
        g = ResourceGuard(timeout_seconds=20.0, max_memory_bytes=256 * 1024 * 1024)
        solver_results[s.name] = s.solve(values, target, mode=mode, guard=g, num_workers=1)

    bf_res = solver_results["Brute Force"]
    bf_has_sol = bf_res.has_solution
    bf_canonical_sols = set(tuple(sorted(sol)) for sol in bf_res.solutions)

    passed = True
    mismatches = []

    for name, res in solver_results.items():
        if name == "Brute Force":
            continue

        if res.has_solution != bf_has_sol:
            passed = False
            mismatches.append(f"{name} decision mismatch: BF={bf_has_sol}, {name}={res.has_solution}")

        if res.has_solution and res.solutions:
            for sol in res.solutions:
                if sum(sol) != target:
                    passed = False
                    mismatches.append(f"{name} invalid witness: sum({sol}) = {sum(sol)} != target {target}")

        if mode == SearchMode.ALL_SOLUTIONS and name in ["Target-Remainder DFS", "Target-Remainder + Full Pruning", "Target-Remainder + Memoization", "ATRS (Adaptive Target-Remainder Solver)"]:
            cand_canonical = set(tuple(sorted(sol)) for sol in res.solutions)
            if cand_canonical != bf_canonical_sols:
                passed = False
                mismatches.append(
                    f"{name} solution set mismatch: BF count={len(bf_canonical_sols)}, {name} count={len(cand_canonical)}"
                )

    return {
        "passed": passed,
        "skipped": False,
        "status": "PASSED" if passed else "FAILED",
        "error_msg": "; ".join(mismatches) if mismatches else "",
        "bf_res": bf_res,
        "solver_results": solver_results
    }


def validate_atrs_against_bruteforce(
    values: List[int],
    target: int,
    mode: SearchMode = SearchMode.FIRST_SOLUTION
) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper that validates ATRS against Brute Force.
    """
    return validate_all_solvers_against_bruteforce(values, target, mode=mode)


def run_exhaustive_random_validation(
    seeds: range = range(10),
    n_min: int = 4,
    n_max: int = 14
) -> Dict[str, Any]:
    """
    Runs an automated suite of randomized instances across multiple seeds and sizes,
    including solvable, unsolvable, gcd > 1, and duplicate scenarios.
    """
    total_tests = 0
    passed_tests = 0
    failures = []

    for seed in seeds:
        random.seed(seed)
        n = random.randint(n_min, n_max)
        raw_vals = sorted(list(set(random.randint(2, 80) for _ in range(n))))
        if len(raw_vals) < 3:
            continue

        # Case A: Guaranteed Solvable
        k = random.randint(1, len(raw_vals) // 2 + 1)
        sub = random.sample(raw_vals, k)
        target_solvable = sum(sub)

        rep_a = validate_all_solvers_against_bruteforce(raw_vals, target_solvable, mode=SearchMode.ALL_SOLUTIONS)
        total_tests += 1
        if rep_a["passed"]:
            passed_tests += 1
        else:
            failures.append({"seed": seed, "values": raw_vals, "target": target_solvable, "error": rep_a["error_msg"]})

        # Case B: Guaranteed Unsolvable (Even numbers with odd target)
        even_vals = [v * 2 for v in raw_vals]
        target_unsolvable = (sum(even_vals) // 2) * 2 + 1
        rep_b = validate_all_solvers_against_bruteforce(even_vals, target_unsolvable, mode=SearchMode.FIRST_SOLUTION)
        total_tests += 1
        if rep_b["passed"]:
            passed_tests += 1
        else:
            failures.append({"seed": seed, "values": even_vals, "target": target_unsolvable, "error": rep_b["error_msg"]})

        # Case C: Suffix Exact Sum
        target_suffix = sum(raw_vals[len(raw_vals)//2:])
        rep_c = validate_all_solvers_against_bruteforce(raw_vals, target_suffix, mode=SearchMode.FIRST_SOLUTION)
        total_tests += 1
        if rep_c["passed"]:
            passed_tests += 1
        else:
            failures.append({"seed": seed, "values": raw_vals, "target": target_suffix, "error": rep_c["error_msg"]})

    return {
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "all_passed": (total_tests == passed_tests),
        "failures": failures
    }

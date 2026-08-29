"""
ATRS - Benchmark Runner and Random Instance Generator
Executes comparative benchmarks across all solvers and produces detailed performance records.
"""
import random
import csv
from typing import List, Dict, Any, Optional, Tuple

from .state import SearchMode, SolverResult, SolverStatus
from .resource_guard import ResourceGuard
from .core import (
    BaseSubsetSumSolver,
    BruteForceSolver,
    TargetRemainderDFSSolver,
    TargetRemainderPrunedSolver,
    TargetRemainderMemoSolver,
    BitsetDPSolver,
    MITMSolver,
    ATRSSolver,
)


def generate_instance(
    n: int = 20,
    min_val: int = 10,
    max_val: int = 500,
    target_mode: str = "Random",
    seed: Optional[int] = None
) -> Tuple[List[int], int]:
    """
    Generates a Subset Sum problem instance.
    """
    if seed is not None:
        random.seed(seed)

    values = sorted([random.randint(min_val, max_val) for _ in range(n)])

    if target_mode == "Guaranteed Solvable":
        k = random.randint(1, max(1, n // 2))
        subset = random.sample(values, k)
        target = sum(subset)
    elif target_mode == "Guaranteed Unsolvable":
        values = [v * 2 for v in values]
        target = (sum(values) // 2) * 2 + 1
    else:
        total = sum(values)
        target = random.randint(min_val, max(min_val, total // 2))

    return values, target


class BenchmarkRunner:
    def __init__(self, timeout_per_algo: float = 10.0, max_memory_mb: float = 512.0):
        self.timeout_per_algo = timeout_per_algo
        self.max_memory_mb = max_memory_mb
        self.solvers: List[BaseSubsetSumSolver] = [
            BruteForceSolver(),
            TargetRemainderDFSSolver(),
            TargetRemainderPrunedSolver(),
            TargetRemainderMemoSolver(),
            BitsetDPSolver(),
            MITMSolver(),
            ATRSSolver(),
        ]

    def run_benchmark(
        self,
        values: List[int],
        target: int,
        mode: SearchMode = SearchMode.FIRST_SOLUTION,
        selected_solvers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Runs selected solvers against the instance and returns tabular records.
        """
        results = []
        n = len(values)

        for solver in self.solvers:
            if selected_solvers is not None and solver.name not in selected_solvers:
                continue

            if solver.name == "Brute Force" and n > 22:
                results.append({
                    "algorithm": solver.name,
                    "status": "SKIPPED (n > 22)",
                    "exact": None,
                    "time_sec": 0.0,
                    "memory_mb": 0.0,
                    "nodes": 0,
                    "prunes": 0,
                    "work_units": 0,
                    "oracle_calls": 0,
                    "solutions": 0,
                    "diagnostic": "Omitted for safety"
                })
                continue

            guard = ResourceGuard(
                max_memory_bytes=int(self.max_memory_mb * 1024 * 1024),
                timeout_seconds=self.timeout_per_algo
            )

            res: SolverResult = solver.solve(values, target, mode=mode, guard=guard)
            s = res.stats
            total_oracle_calls = sum(s.oracle_calls.values())

            results.append({
                "algorithm": solver.name,
                "status": res.status.value,
                "exact": res.is_exact,
                "time_sec": res.elapsed,
                "memory_mb": s.memory_peak_bytes / (1024 * 1024),
                "nodes": s.nodes,
                "prunes": s.pruned,
                "work_units": s.work_units,
                "oracle_calls": total_oracle_calls,
                "solutions": len(res.solutions) if res.solutions else (1 if res.status == SolverStatus.EXACT_SOL_FOUND else 0),
                "diagnostic": res.diagnostic_message
            })

        return results

    @staticmethod
    def export_csv(records: List[Dict[str, Any]], filepath: str):
        if not records:
            return
        keys = [
            "algorithm",
            "status",
            "exact",
            "time_sec",
            "memory_mb",
            "nodes",
            "prunes",
            "work_units",
            "oracle_calls",
            "solutions",
            "diagnostic"
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for r in records:
                writer.writerow(r)

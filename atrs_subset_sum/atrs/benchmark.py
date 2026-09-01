"""
ATRS - Benchmark Runner and Research Instance Generator
Executes comparative benchmarks across all solvers and produces detailed performance records,
with LaTeX and CSV export utilities for academic publication.
"""
import math
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
    Generates a Subset Sum problem instance across various difficulty regimes.
    Supported target_mode:
      - 'Random': Uniformly sampled elements and target.
      - 'Guaranteed Solvable': Target is the exact sum of a randomly chosen subset.
      - 'Guaranteed Unsolvable': Parity or bound-constructed unsolvable instance.
      - 'Hard Density': Density alpha = n / log2(max_val) ~ 1.0 (phase transition hardness).
      - 'Large GCD': Elements share gcd g > 1 with target testing divisibility pruner.
    """
    if seed is not None:
        random.seed(seed)

    if target_mode == "Hard Density":
        # max_val chosen such that log2(max_val) ~= n, i.e., alpha = n / log2(max_val) ~= 1.0
        max_val_density = max(10, 2 ** n)
        values = sorted([random.randint(1, max_val_density) for _ in range(n)])
        # Target roughly half sum
        target = random.randint(min(values), max(min(values), sum(values) // 2))
        return values, target

    elif target_mode == "Large GCD":
        g = random.choice([2, 3, 5, 7, 11])
        base_vals = [random.randint(min_val // g + 1, max_val // g + 1) for _ in range(n)]
        values = sorted([v * g for v in base_vals])
        if random.random() < 0.5:
            # Non-divisible target -> tests immediate GCD pruning
            target = random.randint(1, sum(values) // 2) * g + random.randint(1, g - 1)
        else:
            # Divisible target
            target = random.randint(1, sum(values) // (2 * g)) * g
        return values, target

    elif target_mode == "Guaranteed Solvable":
        values = sorted([random.randint(min_val, max_val) for _ in range(n)])
        k = random.randint(1, max(1, n // 2))
        subset = random.sample(values, k)
        target = sum(subset)
        return values, target

    elif target_mode == "Guaranteed Unsolvable":
        values = sorted([random.randint(min_val, max_val) * 2 for _ in range(n)])
        target = (sum(values) // 2) * 2 + 1
        return values, target

    else:  # Standard Random
        values = sorted([random.randint(min_val, max_val) for _ in range(n)])
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
        """
        Exports benchmark records to CSV.
        """
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

    @staticmethod
    def export_latex(records: List[Dict[str, Any]], caption: str = "Comparative Benchmark on Subset Sum Problem", label: str = "tab:ssp_benchmark") -> str:
        """
        Exports benchmark records to a clean LaTeX table using booktabs formatting.
        """
        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{" + caption + r"}",
            r"\label{" + label + r"}",
            r"\begin{tabular}{lrrrrrr}",
            r"\toprule",
            r"\textbf{Algorithm} & \textbf{Status} & \textbf{Time (s)} & \textbf{Nodes} & \textbf{Pruned} & \textbf{RAM (MB)} & \textbf{Solutions} \\",
            r"\midrule",
        ]
        for r in records:
            algo = r["algorithm"]
            if "ATRS" in algo:
                algo = r"\textbf{" + algo + r"}"
            status = r["status"]
            time_str = f"{r['time_sec']:.6f}" if r["time_sec"] > 0 else "-"
            nodes_str = f"{r['nodes']:,}" if r['nodes'] > 0 else "-"
            prunes_str = f"{r['prunes']:,}" if r['prunes'] > 0 else "-"
            mem_str = f"{r['memory_mb']:.2f}"
            sol_str = str(r["solutions"])
            lines.append(f"{algo} & {status} & {time_str} & {nodes_str} & {prunes_str} & {mem_str} & {sol_str} \\\\")

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ])
        return "\n".join(lines)

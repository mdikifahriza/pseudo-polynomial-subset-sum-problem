"""
ATSP - Benchmark Runner and Random Instance Generator
Executes comparative benchmarks across all TSP solvers and produces detailed performance records,
with LaTeX and CSV export utilities for academic publication.
"""
import random
import math
import csv
from typing import List, Dict, Any, Optional, Tuple

from .state import SearchMode, TSPResult, SolverStatus
from .resource_guard import ResourceGuard
from .preprocess import build_adj_matrix
from .core import (
    BaseTSPSolver,
    BruteForceTSPSolver,
    NearestNeighborTSPSolver,
    SimulatedAnnealingTSPSolver,
    ACOTSPSolver,
    HeldKarpTSPSolver,
    BranchBoundTSPSolver,
    ATSPSolver,
)


def generate_instance(
    n: int = 12,
    instance_type: str = "Random",
    coord_range: float = 100.0,
    seed: Optional[int] = None
) -> Tuple[List[Tuple[float, float]], List[List[float]]]:
    """
    Generates a TSP instance with n coordinates and its pairwise Euclidean distance matrix.
    Supported instance_type: 'Random', 'Clustered', 'Circle', 'Grid'.
    """
    if seed is not None:
        random.seed(seed)

    coords: List[Tuple[float, float]] = []

    if instance_type == "Clustered":
        num_clusters = max(2, n // 5)
        centers = [(random.uniform(0.2 * coord_range, 0.8 * coord_range),
                    random.uniform(0.2 * coord_range, 0.8 * coord_range)) for _ in range(num_clusters)]
        for i in range(n):
            c_x, c_y = random.choice(centers)
            coords.append((
                max(0.0, min(coord_range, c_x + random.gauss(0, coord_range * 0.08))),
                max(0.0, min(coord_range, c_y + random.gauss(0, coord_range * 0.08))),
            ))
    elif instance_type == "Circle":
        radius = coord_range * 0.4
        cx, cy = coord_range * 0.5, coord_range * 0.5
        for i in range(n):
            angle = (2 * math.pi * i) / n
            coords.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    elif instance_type == "Grid":
        side = int(math.ceil(math.sqrt(n)))
        step = coord_range / max(1, side)
        for i in range(n):
            r, c = i // side, i % side
            coords.append((c * step, r * step))
    else:  # Random
        coords = [
            (random.uniform(0.0, coord_range), random.uniform(0.0, coord_range))
            for _ in range(n)
        ]

    adj = build_adj_matrix(coords)
    return coords, adj


class BenchmarkRunner:
    def __init__(self, timeout_per_algo: float = 10.0, max_memory_mb: float = 512.0):
        self.timeout_per_algo = timeout_per_algo
        self.max_memory_mb = max_memory_mb
        self.solvers: List[BaseTSPSolver] = [
            BruteForceTSPSolver(),
            NearestNeighborTSPSolver(),
            SimulatedAnnealingTSPSolver(),
            ACOTSPSolver(),
            HeldKarpTSPSolver(),
            BranchBoundTSPSolver(),
            ATSPSolver(),
        ]

    def run_benchmark(
        self,
        adj: List[List[float]],
        mode: SearchMode = SearchMode.SHORTEST_TOUR,
        selected_solvers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Runs selected solvers against the distance matrix and returns tabular records.
        """
        results = []
        n = len(adj)

        for solver in self.solvers:
            if selected_solvers is not None and solver.name not in selected_solvers:
                continue

            if solver.name == "Brute Force" and n > 11:
                results.append({
                    "algorithm": solver.name,
                    "status": "SKIPPED (n > 11)",
                    "exact": None,
                    "time_sec": 0.0,
                    "best_cost": 0.0,
                    "memory_mb": 0.0,
                    "nodes": 0,
                    "prunes": 0,
                    "work_units": 0,
                    "diagnostic": "Omitted for safety"
                })
                continue

            if solver.name == "Held-Karp DP" and n > 22:
                results.append({
                    "algorithm": solver.name,
                    "status": "SKIPPED (n > 22)",
                    "exact": None,
                    "time_sec": 0.0,
                    "best_cost": 0.0,
                    "memory_mb": 0.0,
                    "nodes": 0,
                    "prunes": 0,
                    "work_units": 0,
                    "diagnostic": "Omitted for memory safety"
                })
                continue

            guard = ResourceGuard(
                max_memory_bytes=int(self.max_memory_mb * 1024 * 1024),
                timeout_seconds=self.timeout_per_algo
            )

            res: TSPResult = solver.solve(adj, mode=mode, guard=guard)
            s = res.stats

            results.append({
                "algorithm": solver.name,
                "status": res.status.value,
                "exact": res.is_exact,
                "time_sec": res.elapsed,
                "best_cost": res.best_cost if res.best_cost < float("inf") else 0.0,
                "memory_mb": s.memory_peak_bytes / (1024 * 1024),
                "nodes": s.nodes,
                "prunes": s.pruned,
                "work_units": s.work_units,
                "diagnostic": res.diagnostic_message
            })

        return results

    @staticmethod
    def export_csv(records: List[Dict[str, Any]], filepath: str):
        """
        Exports TSP benchmark records to CSV.
        """
        if not records:
            return
        keys = [
            "algorithm",
            "status",
            "exact",
            "time_sec",
            "best_cost",
            "memory_mb",
            "nodes",
            "prunes",
            "work_units",
            "diagnostic"
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for r in records:
                writer.writerow(r)

    @staticmethod
    def export_latex(records: List[Dict[str, Any]], caption: str = "Comparative Benchmark on Traveling Salesperson Problem", label: str = "tab:tsp_benchmark") -> str:
        """
        Exports TSP benchmark records to a clean LaTeX table using booktabs formatting.
        """
        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{" + caption + r"}",
            r"\label{" + label + r"}",
            r"\begin{tabular}{lrrrrrr}",
            r"\toprule",
            r"\textbf{Algorithm} & \textbf{Status} & \textbf{Best Cost} & \textbf{Time (s)} & \textbf{Nodes} & \textbf{Pruned} & \textbf{Exact?} \\",
            r"\midrule",
        ]
        for r in records:
            algo = r["algorithm"]
            if "ATSP" in algo:
                algo = r"\textbf{" + algo + r"}"
            status = r["status"]
            cost_str = f"{r['best_cost']:.2f}" if r["best_cost"] > 0 else "-"
            time_str = f"{r['time_sec']:.6f}" if r["time_sec"] > 0 else "-"
            nodes_str = f"{r['nodes']:,}" if r['nodes'] > 0 else "-"
            prunes_str = f"{r['prunes']:,}" if r['prunes'] > 0 else "-"
            exact_str = r"\checkmark" if r["exact"] else r"\texttimes"
            lines.append(f"{algo} & {status} & {cost_str} & {time_str} & {nodes_str} & {prunes_str} & {exact_str} \\\\")

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ])
        return "\n".join(lines)

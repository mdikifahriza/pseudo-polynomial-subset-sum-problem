"""
ATSP — Adaptive Traveling Salesman Problem Solver
Entry point script for ATSP research platform.
Can be executed as desktop GUI (default) or high-performance CLI with TSPLIB support and LaTeX/CSV export.
"""
import sys
import argparse
from pathlib import Path
from atsp.gui import ATSPApplication
from atsp.core import ATSPSolver
from atsp.preprocess import (
    parse_coords_input,
    parse_matrix_input,
    parse_edge_list,
    parse_tsplib_content,
    parse_unified_input,
    validate_adj_matrix,
    build_adj_matrix,
)
from atsp.state import SearchMode
from atsp.benchmark import BenchmarkRunner, generate_instance
from atsp.validation import validate_atsp_against_bruteforce


def run_cli(args):
    print("=" * 80)
    print("  ATSP — Adaptive Traveling Salesman Problem Solver (CLI Research Mode)")
    print("=" * 80)

    # 1. Validation against exact ground truth
    if args.validate:
        n = args.n or 8
        print(f"Running automated exact soundness validation for n = {n} cities against Brute Force / Held-Karp...")
        coords, adj = generate_instance(n=n, seed=42)
        val = validate_atsp_against_bruteforce(adj)
        if val["passed"]:
            print("Validation: PASSED! (Exact soundness verified)")
            print(f"  Reference Optimal Cost ({val['ref_name']}) : {val['ref_cost']:.6f}")
            print(f"  ATSP Optimal Cost                   : {val['atsp_cost']:.6f}")
            print(f"  Search Nodes Visited                : {val['atsp_nodes']:,}")
            print(f"  Branches Pruned                     : {val['atsp_pruned']:,}")
        else:
            print(f"Validation: FAILED! {val['error_msg']}")
        return

    coords = None
    meta = {}

    # 2. Load instance from TSPLIB or general file
    if args.tsplib or (args.input_file and args.input_file.endswith(".tsp")):
        file_path = args.tsplib or args.input_file
        print(f"Loading standard TSPLIB instance from: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        adj, coords, meta = parse_tsplib_content(content)
        is_ok, err, warnings = validate_adj_matrix(adj)
        if not is_ok:
            print(f"[Error] Invalid TSPLIB distance matrix: {err}")
            return
        for w in warnings:
            print(f"[Warning] {w}")

    elif args.input_file:
        print(f"Loading instance from file: {args.input_file}")
        with open(args.input_file, "r", encoding="utf-8") as f:
            content = f.read()

        if args.input_type == "matrix":
            adj = parse_matrix_input(content)
        elif args.input_type == "edge":
            adj = parse_edge_list(content)
        elif args.input_type == "coords":
            coords = parse_coords_input(content)
            adj = build_adj_matrix(coords)
        else:
            adj, coords = parse_unified_input(content)

        is_ok, err, warnings = validate_adj_matrix(adj)
        if not is_ok:
            print(f"[Error] Invalid input matrix: {err}")
            return
        for w in warnings:
            print(f"[Warning] {w}")

    elif args.cities:
        adj, coords = parse_unified_input(args.cities)
    elif args.random:
        coords, adj = generate_instance(n=args.random, instance_type=args.pattern, seed=args.seed)
    elif args.benchmark:
        n = args.n or 12
        coords, adj = generate_instance(n=n, instance_type=args.pattern, seed=args.seed)
    else:
        coords, adj = generate_instance(n=10, seed=123)

    n = len(adj)

    # 3. Comparative Benchmark Mode
    if args.benchmark:
        print(f"Running Comparative Benchmark on {n} cities across all solvers...")
        runner = BenchmarkRunner(timeout_per_algo=args.timeout)
        records = runner.run_benchmark(adj)
        print("-" * 80)
        print(f"{'Algorithm':<28} | {'Status':<16} | {'Best Cost':<10} | {'Time (s)':<9} | {'Nodes':<8}")
        print("-" * 80)
        for r in records:
            cost_str = f"{r['best_cost']:.2f}" if r['best_cost'] > 0 else "—"
            time_str = f"{r['time_sec']:.4f}"
            print(f"{r['algorithm']:<28} | {r['status'][:16]:<16} | {cost_str:<10} | {time_str:<9} | {r['nodes']:<8,}")
        print("=" * 80)

        if args.export_csv:
            BenchmarkRunner.export_csv(records, args.export_csv)
            print(f"[Export] CSV benchmark saved to: {args.export_csv}")

        if args.export_latex:
            tex = BenchmarkRunner.export_latex(records, caption=f"Traveling Salesperson Benchmark ($n={n}$)")
            Path(args.export_latex).write_text(tex, encoding="utf-8")
            print(f"[Export] LaTeX table saved to: {args.export_latex}")
        return

    # 4. Standard Single Solver Execution Mode
    print(f"Number of Cities (n)  : {n}")
    if meta.get("NAME"):
        print(f"TSPLIB Name / Type    : {meta.get('NAME')} ({meta.get('TYPE', 'TSP')})")
    if coords:
        print(f"Sample Coordinates    : {coords[:4]}{'...' if n > 4 else ''}")
    print(f"Simulated Annealing   : {'Disabled' if args.no_sa else 'Enabled'}")
    print(f"Ant Colony Warm-Start : {'Disabled' if args.no_aco else 'Enabled'}")
    print(f"Worker Processes      : {args.workers or 'All available'}")
    print("-" * 80)

    solver = ATSPSolver(
        enable_sa=not args.no_sa,
        enable_aco=not args.no_aco,
    )
    mode = SearchMode.ALL_OPTIMAL_TOURS if args.all else SearchMode.SHORTEST_TOUR
    res = solver.solve(adj, mode=mode, num_workers=args.workers)

    print(f"Status               : {res.status.value}")
    print(f"Optimal Tour Cost    : {res.best_cost:.6f}")
    print(f"Elapsed Time         : {res.elapsed:.6f} s")
    print(f"Nodes Explored       : {res.stats.nodes:,}")
    print(f"Branches Pruned      : {res.stats.pruned:,}")
    print(f"MST Bounds Computed  : {res.stats.mst_computations:,}")
    print(f"Held-Karp Calls      : {res.stats.held_karp_calls:,}")

    if res.tours:
        print("\nOptimal Tour(s):")
        for idx, tour in enumerate(res.tours[:5], 1):
            tour_str = " -> ".join(map(str, tour))
            print(f"  {idx:>2}. {tour_str} (Cost = {res.best_cost:.4f})")
        if len(res.tours) > 5:
            print(f"  ... and {len(res.tours) - 5:,} additional optimal tours.")


def main():
    parser = argparse.ArgumentParser(description="ATSP — Adaptive Traveling Salesman Problem Solver")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode instead of Tkinter desktop GUI")
    parser.add_argument("--tsplib", type=str, default=None, help="Path to standard TSPLIB (.tsp) benchmark instance")
    parser.add_argument("--input-file", type=str, default=None, help="Path to text/csv/tsp file containing coordinates, matrix, or edge list")
    parser.add_argument("--input-type", type=str, choices=["coords", "matrix", "edge", "auto"], default="auto", help="Input format type")
    parser.add_argument("--cities", type=str, default=None, help="Inline coordinates, matrix, or edge string")
    parser.add_argument("--random", type=int, default=None, help="Solve a randomly generated instance with N cities")
    parser.add_argument("--pattern", type=str, choices=["Random", "Clustered", "Circle", "Grid"], default="Random", help="Random instance spatial pattern")
    parser.add_argument("--all", action="store_true", help="Enumerate all distinct globally optimal tours")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes")
    parser.add_argument("--benchmark", action="store_true", help="Run comparative benchmark across all solvers")
    parser.add_argument("--validate", action="store_true", help="Run exact soundness validation against Brute Force / Held-Karp")
    parser.add_argument("--n", type=int, default=None, help="Number of cities for validation/benchmark")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout in seconds for benchmark")
    parser.add_argument("--seed", type=int, default=None, help="Random generator seed")
    parser.add_argument("--export-csv", type=str, default=None, help="Filepath to export benchmark results as CSV")
    parser.add_argument("--export-latex", type=str, default=None, help="Filepath to export benchmark results as LaTeX table")
    parser.add_argument("--no-sa", action="store_true", help="Disable Simulated Annealing warm-start")
    parser.add_argument("--no-aco", action="store_true", help="Disable Ant Colony Optimization warm-start")

    args, unknown = parser.parse_known_args()

    if args.cli or args.cities or args.input_file or args.tsplib or args.random or args.benchmark or args.validate or args.export_csv or args.export_latex:
        run_cli(args)
    else:
        app = ATSPApplication()
        app.run()


if __name__ == "__main__":
    main()

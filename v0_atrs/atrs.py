"""
ATRS — Adaptive Target-Remainder Solver for Subset Sum
Entry point script for ATRS research platform.
Can be executed as desktop GUI (default) or high-performance CLI with LaTeX/CSV export.
"""
import sys
import argparse
from pathlib import Path
from atrs.gui import ATRSApplication
from atrs.core import ATRSSolver
from atrs.preprocess import parse_input
from atrs.state import SearchMode
from atrs.benchmark import BenchmarkRunner, generate_instance
from atrs.validation import validate_atrs_against_bruteforce


def run_cli(args):
    print("=" * 80)
    print("  ATRS — Adaptive Target-Remainder Solver (CLI Research Mode)")
    print("=" * 80)

    # 1. Comparative Benchmark Mode
    if args.benchmark:
        n = args.n or 20
        print(f"Running Comparative Benchmark Suite (n={n}, regime='{args.regime}')...")
        values, target = generate_instance(n=n, target_mode=args.regime, seed=args.seed)
        runner = BenchmarkRunner(timeout_per_algo=args.timeout)
        records = runner.run_benchmark(values, target)

        print("-" * 80)
        print(f"{'Algorithm':<32} | {'Status':<16} | {'Time (s)':<10} | {'Nodes':<9} | {'Pruned':<9}")
        print("-" * 80)
        for r in records:
            time_str = f"{r['time_sec']:.6f}" if r["time_sec"] > 0 else "—"
            nodes_str = f"{r['nodes']:,}" if r["nodes"] > 0 else "—"
            prunes_str = f"{r['prunes']:,}" if r["prunes"] > 0 else "—"
            print(f"{r['algorithm']:<32} | {r['status'][:16]:<16} | {time_str:<10} | {nodes_str:<9} | {prunes_str:<9}")
        print("=" * 80)

        if args.export_csv:
            BenchmarkRunner.export_csv(records, args.export_csv)
            print(f"[Export] CSV benchmark saved to: {args.export_csv}")

        if args.export_latex:
            tex = BenchmarkRunner.export_latex(records, caption=f"Subset Sum Benchmark ($n={n}, T={target}$)")
            Path(args.export_latex).write_text(tex, encoding="utf-8")
            print(f"[Export] LaTeX table saved to: {args.export_latex}")
        return

    # 2. Single Problem Solving Mode
    if args.random:
        values, target = generate_instance(n=args.random, target_mode=args.regime, seed=args.seed)
    else:
        try:
            values = parse_input(args.values)
            target = int(args.target)
        except Exception as e:
            print(f"[Error] Input parsing failed: {e}")
            sys.exit(1)

    print(f"Multiset Elements (n={len(values)}): {values[:10]}{'...' if len(values) > 10 else ''}")
    print(f"Target Sum (T) : {target:,}")
    print(f"Workers / Cores: {args.workers or 'All available'}")
    print("-" * 80)

    solver = ATRSSolver()
    mode = SearchMode.ALL_SOLUTIONS if args.all else SearchMode.FIRST_SOLUTION
    res = solver.solve(values, target, mode=mode, num_workers=args.workers)

    print(f"Status          : {res.status.value}")
    print(f"Elapsed Time    : {res.elapsed:.6f} s")
    print(f"Nodes Explored  : {res.stats.nodes:,}")
    print(f"Branches Pruned : {res.stats.pruned:,}")
    print(f"Solutions Found : {len(res.solutions):,}")

    if res.solutions:
        print("\nSatisfying Subsets:")
        for idx, s in enumerate(res.solutions[:10], 1):
            print(f"  {idx:>3}. {' + '.join(map(str, s))} = {target}")
        if len(res.solutions) > 10:
            print(f"  ... and {len(res.solutions) - 10:,} additional solutions.")

    if len(values) <= 20 and not args.skip_validation:
        print("\nValidating soundness against Brute Force...")
        val = validate_atrs_against_bruteforce(values, target, mode=mode)
        if val["passed"]:
            print("Validation: PASSED (Exact sound match with Brute Force)")
        else:
            print(f"Validation: FAILED! {val['error_msg']}")


def main():
    parser = argparse.ArgumentParser(description="ATRS — Adaptive Target-Remainder Solver for Subset Sum")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode instead of Tkinter desktop GUI")
    parser.add_argument("--values", type=str, default="3,7,11,14,18,21,26,29,34,38", help="Comma-separated positive integers")
    parser.add_argument("--target", type=int, default=100, help="Target sum integer")
    parser.add_argument("--random", type=int, default=None, help="Generate and solve a random instance with N elements")
    parser.add_argument("--regime", type=str, choices=["Random", "Guaranteed Solvable", "Guaranteed Unsolvable", "Hard Density", "Large GCD"], default="Random", help="Instance hardness regime")
    parser.add_argument("--all", action="store_true", help="Enumerate all distinct satisfying subsets")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes (default: all CPU cores)")
    parser.add_argument("--benchmark", action="store_true", help="Run comparative benchmark suite against baseline solvers")
    parser.add_argument("--n", type=int, default=None, help="Number of elements for benchmark")
    parser.add_argument("--timeout", type=float, default=15.0, help="Timeout in seconds per algorithm in benchmark")
    parser.add_argument("--seed", type=int, default=None, help="Random generator seed")
    parser.add_argument("--export-csv", type=str, default=None, help="Filepath to export benchmark results as CSV")
    parser.add_argument("--export-latex", type=str, default=None, help="Filepath to export benchmark results as LaTeX table")
    parser.add_argument("--skip-validation", action="store_true", help="Skip brute-force validation for small n")

    args, unknown = parser.parse_known_args()

    if args.cli or args.benchmark or args.random or args.export_csv or args.export_latex:
        run_cli(args)
    else:
        app = ATRSApplication()
        app.run()


if __name__ == "__main__":
    main()

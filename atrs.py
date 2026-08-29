"""
ATRS — Adaptive Target-Remainder Solver
Entry point script for ATRS research prototype.
Can be executed as GUI (default) or CLI.
"""
import sys
import argparse
from atrs.gui import ATRSApplication
from atrs.core import ATRSSolver
from atrs.preprocess import parse_input
from atrs.state import SearchMode
from atrs.benchmark import BenchmarkRunner
from atrs.validation import validate_atrs_against_bruteforce

def run_cli(args):
    try:
        values = parse_input(args.values)
        target = int(args.target)
    except Exception as e:
        print(f"[Error] Input parsing failed: {e}")
        sys.exit(1)

    print("=" * 80)
    print("  ATRS — Adaptive Target-Remainder Solver (CLI Mode)")
    print("=" * 80)
    print(f"Elements (n={len(values)}): {values}")
    print(f"Target: {target}")
    print(f"Workers: {args.workers}")
    print("-" * 80)

    solver = ATRSSolver()
    mode = SearchMode.ALL_SOLUTIONS if args.all else SearchMode.FIRST_SOLUTION
    res = solver.solve(values, target, mode=mode, num_workers=args.workers)

    print(f"Status        : {res.status.value}")
    print(f"Elapsed Time  : {res.elapsed:.6f} s")
    print(f"Nodes Evaluated: {res.stats.nodes:,}")
    print(f"Pruned Branches: {res.stats.pruned:,}")
    print(f"Solutions     : {len(res.solutions)}")

    if res.solutions:
        print("\nSolutions:")
        for idx, s in enumerate(res.solutions[:10], 1):
            print(f"  {idx}. {' + '.join(map(str, s))} = {target}")
        if len(res.solutions) > 10:
            print(f"  ... and {len(res.solutions) - 10} more.")

    if len(values) <= 20 and not args.skip_validation:
        print("\nValidating against Brute Force...")
        val = validate_atrs_against_bruteforce(values, target, mode=mode)
        if val["passed"]:
            print("Validation: PASSED (Exact match with Brute Force)")
        else:
            print(f"Validation: FAILED! {val['error_msg']}")

def main():
    parser = argparse.ArgumentParser(description="ATRS — Adaptive Target-Remainder Solver for Subset Sum")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode instead of Tkinter GUI")
    parser.add_argument("--values", type=str, default="3,7,11,14,18,21,26,29,34,38", help="Comma-separated positive integers")
    parser.add_argument("--target", type=int, default=100, help="Target sum")
    parser.add_argument("--all", action="store_true", help="Find all solutions instead of first")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes")
    parser.add_argument("--skip-validation", action="store_true", help="Skip brute-force validation for small n")

    args, unknown = parser.parse_known_args()

    if args.cli:
        run_cli(args)
    else:
        app = ATRSApplication()
        app.run()

if __name__ == "__main__":
    main()

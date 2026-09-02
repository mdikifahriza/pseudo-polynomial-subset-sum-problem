#!/usr/bin/env python3
"""
Driver for bench_single. Every configuration is executed in its own fresh
process (subprocess.run), specifically so that peak-RAM measurements are
never contaminated across configurations (see bench_single.cpp header).
Each configuration is repeated with several seeds so we can report a range
(min/median/max), not a single potentially-lucky-or-unlucky sample.
"""
import csv
import statistics
import subprocess
import sys
import time

BIN = "./bench_single"
COLS = ["n","bits","card","seed","mode","forced","time_limit_ms","max_solutions",
        "strategy_chosen","runtime_ms","peak_ram_mb","states_evaluated",
        "table_lookups","solution_count","all_solutions_size","status","verified"]

def run_one(n, bits, card_frac_x1000, seed, mode, forced, time_limit_ms, max_solutions):
    args = [BIN, str(n), str(bits), str(card_frac_x1000), str(seed),
             str(mode), str(forced), str(time_limit_ms), str(max_solutions)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=(time_limit_ms/1000.0)+30)
    line = r.stdout.strip()
    if not line:
        raise RuntimeError(f"empty output for {args}, stderr={r.stderr}")
    return dict(zip(COLS, line.split(",")))

def write_summary_rows(path, rows):
    if not rows:
        with open(path, "w") as f:
            f.write("(no rows)\n")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

def write_rows(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for row in rows:
            w.writerow(row)

def summarize(rows, key_fields, metric="runtime_ms"):
    groups = {}
    for row in rows:
        key = tuple(row[k] for k in key_fields)
        groups.setdefault(key, []).append(row)
    out = []
    for key, grp in sorted(groups.items()):
        vals = [float(r[metric]) for r in grp]
        statuses = [r["status"] for r in grp]
        verifieds = [int(r["verified"]) for r in grp]
        out.append({
            **dict(zip(key_fields, key)),
            "reps": len(grp),
            f"{metric}_min": min(vals),
            f"{metric}_median": statistics.median(vals),
            f"{metric}_max": max(vals),
            "n_sat": statuses.count("SAT"),
            "n_unsat": statuses.count("UNSAT"),
            "n_timeout": statuses.count("TIMEOUT"),
            "n_capped": statuses.count("CAPPED"),
            "n_verified_ok": sum(1 for v in verifieds if v == 1),
            "n_verified_na": sum(1 for v in verifieds if v == -1),
        })
    return out

def main():
    t_start = time.time()

    # ---- Suite 1: scalability across N, "trillion-scale" bit-length ----
    print("Running Suite 1 (scalability)...", file=sys.stderr)
    s1_rows = []
    for n in [20, 30, 40, 50, 60, 70, 80]:
        for seed in [1, 2, 3]:
            row = run_one(n=n, bits=44, card_frac_x1000=333, seed=seed,
                           mode=0, forced=0, time_limit_ms=8000, max_solutions=5000)
            s1_rows.append(row)
            print("  ", row, file=sys.stderr)
    write_rows("suite1_raw.csv", s1_rows)
    write_summary_rows("suite1_summary.csv", summarize(s1_rows, ["n"]))

    # ---- Suite 2: density sweep at fixed N=40 ----
    print("Running Suite 2 (density sweep)...", file=sys.stderr)
    s2_rows = []
    for bits in [60, 50, 40, 33, 26, 20]:
        for seed in [11, 12, 13]:
            row = run_one(n=40, bits=bits, card_frac_x1000=500, seed=seed,
                           mode=0, forced=0, time_limit_ms=15000, max_solutions=5000)
            s2_rows.append(row)
            print("  ", row, file=sys.stderr)
    write_rows("suite2_raw.csv", s2_rows)
    write_summary_rows("suite2_summary.csv", summarize(s2_rows, ["bits"]))

    # ---- Suite 3: ablation (forced BitsetDP vs forced HybridTailTable vs Auto) ----
    print("Running Suite 3 (ablation)...", file=sys.stderr)
    s3_rows = []
    for forced in [0, 1, 2]:
        for seed in [21, 22, 23]:
            row = run_one(n=40, bits=15, card_frac_x1000=300, seed=seed,
                           mode=0, forced=forced, time_limit_ms=15000, max_solutions=5000)
            s3_rows.append(row)
            print("  ", row, file=sys.stderr)
    write_rows("suite3_raw.csv", s3_rows)
    write_summary_rows("suite3_summary.csv", summarize(s3_rows, ["forced"]))

    # ---- Suite 4: L8 swap extraction vs requested max_solutions ----
    print("Running Suite 4 (swap extraction)...", file=sys.stderr)
    s4_rows = []
    for k in [10, 50, 200, 1000, 5000]:
        for seed in [31, 32, 33]:
            row = run_one(n=60, bits=16, card_frac_x1000=500, seed=seed,
                           mode=1, forced=0, time_limit_ms=20000, max_solutions=k)
            s4_rows.append(row)
            print("  ", row, file=sys.stderr)
    write_rows("suite4_raw.csv", s4_rows)
    write_summary_rows("suite4_summary.csv", summarize(s4_rows, ["max_solutions"]))

    # ---- Suite 5: statistical robustness across many random small/medium instances ----
    print("Running Suite 5 (robustness)...", file=sys.stderr)
    import random
    rng = random.Random(31337)
    s5_rows = []
    n_trials = 100
    for t in range(n_trials):
        n = rng.randint(12, 35)
        bits = rng.randint(10, 40)
        card_frac_x1000 = rng.randint(50, 950)
        seed = 100000 + t
        row = run_one(n=n, bits=bits, card_frac_x1000=card_frac_x1000, seed=seed,
                      mode=0, forced=0, time_limit_ms=4000, max_solutions=5000)
        s5_rows.append(row)
        if t % 20 == 0:
            print(f"  trial {t}/{n_trials}", file=sys.stderr)
    write_rows("suite5_raw.csv", s5_rows)
    statuses = [r["status"] for r in s5_rows]
    verifieds = [int(r["verified"]) for r in s5_rows]
    n_sat = statuses.count("SAT"); n_unsat = statuses.count("UNSAT"); n_timeout = statuses.count("TIMEOUT")
    n_verify_fail = sum(1 for r in s5_rows if r["status"] == "SAT" and int(r["verified"]) == 0)
    n_unexpected_unsat = n_unsat  # every target was constructed as a real subset sum, so UNSAT here is always a genuine defect
    runtimes = [float(r["runtime_ms"]) for r in s5_rows]
    with open("suite5_summary.txt", "w") as f:
        f.write(f"trials={n_trials}\n")
        f.write(f"SAT={n_sat} ({100.0*n_sat/n_trials:.2f}%)\n")
        f.write(f"UNSAT(should be 0; genuine defect if >0)={n_unsat} ({100.0*n_unsat/n_trials:.2f}%)\n")
        f.write(f"TIMEOUT(inconclusive, not an error)={n_timeout} ({100.0*n_timeout/n_trials:.2f}%)\n")
        f.write(f"verify_fail_among_SAT={n_verify_fail} ({100.0*n_verify_fail/max(1,n_sat):.2f}%)\n")
        f.write(f"runtime_ms mean={statistics.mean(runtimes):.4f} median={statistics.median(runtimes):.4f} "
                f"min={min(runtimes):.4f} max={max(runtimes):.4f}\n")

    print(f"\nTotal wall time: {time.time()-t_start:.1f}s", file=sys.stderr)

if __name__ == "__main__":
    main()

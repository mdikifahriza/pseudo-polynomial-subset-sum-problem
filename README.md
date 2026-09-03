# Dumb SSP Solver

Exact solver for the **Subset Sum Problem (SSP)** — finds a subset of positive integers whose sum exactly equals a target `T`. This solver is *adaptive*: selecting different strategies/algorithms depending on instance characteristics (`N` size, `T` magnitude, data structure), then independently verifying the results (L7 Verifier).

---

## 1. Architecture & File Structure

| File | Role |
|---|---|
| `dumbsspCore.hpp` | Core library — data structures, strategy selector, and all solvers (L1–L8) |
| `dumbsspCli.cpp` → `dumbsspCli.exe` | High-performance CLI harness for terminal |
| `dumbsspGui.cpp` → `dumbsspGui.exe` | Native Win32 desktop application |
| `benchmark.txt` | 20 staged benchmark datasets, N=5 to N=100 |
| `README.md` | This documentation |

---

## 2. v1 vs v2 — What's the Difference?

**v1** and **v2** are two generations of the engine that are both exact (always producing a 100% validated solution or proven UNSAT — never approximate), but v2 adds several layers of adaptive optimization not present in v1.

| Aspect | v1 | v2 |
|---|---|---|
| Superincreasing structure detection | None — all cases go through generic DFS | **Present** — detected & routed to dedicated O(n) solver |
| Heavy DFS strategy (`L4`) | Plain `Hybrid Tail-Table + Pruned DFS` | `Hybrid Tail-Table + Pruned DFS (Block-Bound + Ordered)` — adds *block-bound* memoization and branch ordering heuristics |
| Parallelization | None, always single-threaded | Root-split multi-threading for `findone` mode on large instances |
| RAM limit during active DFS | N/A (not needed, as there are no memo structures) | **Unbounded** — `memory_limit_mb` is only used once initially for tail-table sizing, not checked during search |
| RAM during solve | Flat & predictable (~16–20 MB, almost constant regardless of N) | Can be small & flat (~4–20 MB) **or** spike to hundreds of MB, depending on instance structure |

---

## 3. Speed Differences (Based on Actual Benchmark Results)

Tested on three distinct instance categories:

### a) High-Density (small numbers, N > 32)
Both versions select an identical strategy (**L3: Bitset DP**). The results are **virtually identical** — differences are within noise margin, as the code path in this category did not change between v1 and v2.

### b) Superincreasing (each element > sum of all elements below it)
**v2 wins decisively and unconditionally.** v1 still uses generic DFS (`L4`) even though the instance is actually trivial, whereas v2 detects this structure and directly uses `L1: Greedy Superincreasing (Exact O(n))`.

| N | v1 (generic L4) | v2 (L1 Greedy) | Speedup |
|---|---|---|---|
| 35 | ~140 ms | ~0.03 ms | ~4,000x |
| 45 | ~138 ms | ~0.03 ms | ~4,000x |
| 55 | ~137 ms | ~0.04 ms | ~3,800x |

v2 RAM also drops (~20 MB → ~4 MB) because it does not need to build a tail-table at all.

### c) Heavy-Variation (large 12–13 digit numbers, N=45–85, "flat" structure)
This is where the results are **not consistently one-way**:

| N | v1 | v2 | Winner |
|---|---|---|---|
| 45 | 3.341 ms / 20 MB | 4.641 ms / **193 MB** | **v1** (faster & far more RAM-efficient) |
| 50 | 3.674 ms / 20 MB | 427 ms / 32 MB | v2 (~8.6x faster) |
| 65 | 4.676 ms / 20 MB | 2.468 ms / 99.8 MB | v2 (~1.9x faster, RAM increases 5x) |
| 85 | 12.391 ms / 20 MB | 158 ms / 22 MB | v2 (~78x faster, RAM nearly identical) |

**Speed conclusion:** v2 **does not win universally across the board**. For superincreasing cases, its victory is absolute. For heavy DFS cases, v2 is *often* much faster thanks to more aggressive `Block-Bound` pruning — but there are real-world instances (such as N=45 above) where v2 is actually slower while consuming substantially more memory than v1.

---

## 4. The v2 Tradeoff: RAM Can Balloon

The new `Block-Bound` feature in v2 works by recording DFS states `(depth i, remaining target rem)` that have been proven to yield no solution into an `unordered_set<u64>` per depth, preventing them from being re-explored. The issue:

- **No size limit / eviction** on this memo structure — it grows continuously throughout a single `solve()` execution.
- **No actual RAM checking** while DFS is running — the only periodic guard present is a *time limit* (default 120 seconds), not a *memory limit*.
- Its effectiveness (hit-rate) heavily depends on data structure: for instances with large numbers & wide cardinality windows ("flat/unstructured"), the `rem` value at each DFS node rarely repeats identically, meaning the memo more often **adds new entries** rather than **being reused** to prune the search.

**When this risk is most pronounced** (must satisfy all of the following conditions):
1. Target `T` (after dual-complement) **> 15,000,000** → bypasses `Bitset DP`.
2. Array is **not superincreasing** → bypasses the `Greedy` fast-path.
3. GCD = 1, no parity obstruction → passes `TrivialPreCheck`.
4. Cardinality window `[k_min, k_max]` is **wide** (not narrow) → bypasses `NarrowKWindow` detection, so pruning oracles rarely succeed.
5. `N` is in the medium range (≈40–70 based on the benchmark patterns above) with large & random element magnitudes ("flat").
6. Solve time approaches the default limit (120 seconds) — the longer it runs, the more entries accumulate.

Rough estimate from benchmark data: memo overhead ≈ **21 bytes per DFS state**. If exploration throughput is ~1.7–4 million states/second and the solver runs close to the 120-second time limit, explored states can reach hundreds of millions — enough to push process RAM into several GBs, potentially exceeding the 8 GB RAM capacity of typical machines, **because there is no mechanism in the code that actively limits memory consumption during the search phase.**

> **Practical recommendation:** for instances exhibiting the above characteristics (large target, flat structure, medium N), consider explicitly lowering `time_limit_ms`, or monitoring process RAM externally when running v2 on inputs with unknown characteristics.

---

## 5. Under-the-Hood Algorithms (L0–L8)

The solver selects strategies automatically via `AdaptiveStrategySelector`, checking in the following order:

1. **L2 — Trivial Exact Pre-Reduction**
   Instant case detection: `target=0`, target exceeds total sum, GCD modular obstruction, parity obstruction, or empty cardinality window → immediately SAT/UNSAT without searching.

2. **L1 — Greedy Superincreasing (Exact O(n))** *(v2 only — new)*
   Active if the array is fully proven to be superincreasing (each element > sum of all smaller elements below it). The solution is always unique, decided take/skip per element without any backtracking — O(n), never incorrect because the structural property of superincreasing sequences guarantees no combination of smaller elements can equal a larger element above them.

3. **L3 — Bitset DP (Vectorized Exact)**
   Used when target ≤ 15,000,000 and bitset memory estimate is within budget. Classical subset-sum DP with 64-bit bitsets per word, backtracked through `parent[]` array to reconstruct the solution. Fast & low RAM for small targets.

4. **L4 — Hybrid Tail-Table + Pruned DFS**
   Default strategy for heavy cases (large target, not superincreasing, not small target):
   - Array is split into `prefix` (explored via DFS) and `tail` (last m elements, tabulated via *meet-in-the-middle* with incremental Gray-code for O(2^m) instead of O(m·2^m)).
   - DFS on prefix with pruning: suffix-sum bound, cardinality oracle `is_cardinality_feasible` (binary search O(log n)), and branch ordering heuristic (chooses include/exclude whose rem is closer to half of suffix-sum).
   - Upon reaching `cutoff`, the remaining target is searched via binary search in the tail-table.
   - **v1**: stops here.
   - **v2 adds**: `Block-Bound` memoization per `(i, rem)` (see Section 4) + multi-threaded root-split parallel search for `findone` mode on large instances.

5. **L7 — Independent Verifier**
   After a solution is found (any version), it is independently re-verified: valid indices, no duplicates, values match original array, and sum exactly equals target.

6. **L8 — Zero-Sum Swap Extractor**
   For `findall`/`zero` mode: from a single base solution, searches combinatorial swaps at distance ≤4 with identical delta (elements entering vs leaving) to generate dozens to hundreds of additional solution variations extremely quickly, without a full re-DFS.

---

## 6. Compilation (MinGW-w64 GCC)

Run in PowerShell/Command Prompt in the project folder:

**CLI:**
```
g++ -O3 -std=c++17 dumbsspCli.cpp -o dumbsspCli.exe -lpsapi
```

**GUI (Win32 Desktop):**
```
g++ -O3 -std=c++17 dumbsspGui.cpp -o dumbsspGui.exe -mwindows -lcomctl32 -lcomdlg32 -lpsapi -luser32 -lgdi32
```

---

## 7. CLI Syntax & Usage

```
.\dumbsspCli.exe "<elements_list>" <target> [mode] [max_solutions] [time_limit_ms]
```

| Parameter | Description |
|---|---|
| `<elements_list>` | String of positive integers separated by comma/space, e.g. `"10, 20, 30, 40"` |
| `<target>` | Target sum (T) to find |
| `[mode]` | Search mode (default: `findone`) — see Section 8 |
| `[max_solutions]` | Maximum solution witnesses stored in memory for `findall` (default: 5000) |
| `[time_limit_ms]` | Computation time limit in ms (default: 120000 / 2 minutes). Use `0`/`none`/`unlimited`/`inf`/`infinite` for no time limit |

---

## 8. Mode Descriptions & Examples

### [A] `findone` — Fastest Single Solution
Stops (*early exit*) as soon as one valid witness is found. Ultra fast (microseconds to a few ms even for N ≥ 80).
```
.\dumbsspCli.exe "75872066500, 68562112744, 19339160129, 24156275768, 11525390137" 100000000000 findone
```

### [B] `zero` — Find All via L8 Zero-Sum Swap
Finds a single base witness, then extracts dozens to hundreds of variations via combinatorial swaps at distance ≤4. Extremely fast, avoiding exhaustive search overhead.
```
.\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 zero
```

### [C] `dfs` — Find All via Exhaustive DFS
Traverses the entire search space without early return — guarantees 100% of all valid combinations are found. Scales according to problem density & cardinality.
```
.\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 dfs
```

### [D] `count` — Count All
Counts the exact number of valid combinations without storing individual witnesses — RAM-efficient, uses a 128-bit counter.
```
.\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 count
```

### [E] `decision` — Pure Existence / SAT Check
Answers purely SATISFIABLE vs PROVABLY UNSAT with minimal overhead, via initial modular/cardinality obstruction filters or an early hit.
```
.\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 decision
```

---

## 9. Mode Comparison Matrix

| Mode | Speed | Solution Completeness | Peak RAM (normal cases) |
|---|---|---|---|
| `findone` | Ultra fast | 1 witness | ≤ 20 MB (v1) / variable (v2, see Section 4) |
| `zero` | Very fast | Hundreds of variants | ≤ 20 MB |
| `dfs` | Comprehensive | 100% of all solutions | ≤ 20 MB |
| `count` | Fast–medium | Exact count (integer) | Minimal |
| `decision` | Instant | SAT/UNSAT status | Minimal |

> Note: The RAM column in this table refers to typical behavior. For `findone` mode in v2 on large/flat/high-target instances, see Section 4 — RAM can significantly exceed 20 MB.

---

*This documentation was prepared based on source code analysis of `dumbsspCore.hpp` and actual benchmark results from both solver versions.*

# Dumb SSP Solver — High-Performance Exact Subset Sum Engine

A high-performance **Exact Solver** for the **Subset Sum Problem (SSP)** featuring a multi-layered adaptive pipeline (L1–L8), an L3-cache-conscious asymmetric memoization engine ($m \le 20 \implies 16.00\text{ MB}$), a modular **Residue Cascade Sieve**, and a boundary deviation **r-Swap Solver**.

---

## 1. Executable Binaries Overview

Precompiled 64-bit binaries for Windows x64 are included directly in the repository:

| Binary | Generation | Description & Capabilities |
|---|:---:|---|
| **`dumbsspCliv3.exe`** | **v3 (Recommended)** | Flagship release. Integrates *Residue Cascade Sieve* (L2.5), *Small-K MitM* (L2.6), *Boundary Swap Solver* (L2.7), and *Adaptive Bounded BlockBound Cache*. |
| **`dumbsspCliv2.exe`** | v2 | Second-generation engine featuring superincreasing sequence detection, Gray-code tail tables, and unbounded BlockBound cache. |
| **`dumbsspCliv1.exe`** | v1 Baseline | Baseline engine (plain DFS with basic tail table memoization). Ideal for empirical performance comparisons. |
| **`dumbsspGui.exe`** | Desktop GUI | Native Win32 desktop application providing interactive visualization, search telemetry, and live solution exploration. |

---

## 2. CLI Command Syntax

Run the CLI executable from PowerShell or Command Prompt (CMD):

```powershell
.\dumbsspCliv3.exe "<elements_list>" <target> [mode] [max_solutions] [time_limit_ms]
```

### Arguments:

1. **`<elements_list>`** *(Required)*:
   A comma-separated or space-separated list of positive integers. Must be enclosed in double quotes if spaces are present.
   * *Example*: `"10, 20, 30, 40, 50"` or `"123005401502 811856239314 267469214296"`
2. **`<target>`** *(Required)*:
   The target integer value $T$ (supports values up to 64-bit unsigned integers: $0 \le T < 2^{64}-1$).
3. **`[mode]`** *(Optional, Default: `findone`)*:
   Search strategy and reporting policy:
   * **`findone`** / **`1`**: Find a single exact solution witness and halt immediately (*Fastest / Early Exit*).
   * **`findall-zero`** / **`zero`**: Find the first solution and instantly harvest hundreds of additional distinct witnesses via the polynomial-time *Zero-Sum Swap* manifold ($p \le 4$).
   * **`findall-dfs`** / **`dfs`**: Exhaustive 100% full-tree DFS traversal to find all valid combinations.
   * **`countall`** / **`count`**: Count the total exact number of valid subset combinations without storing all solutions in RAM.
   * **`decision`** / **`decide`**: Pure decision problem test (returns boolean `SATISFIABLE` or `PROVABLY UNSAT`).
4. **`[max_solutions]`** *(Optional, Default: `5000`)*:
   Maximum number of witness solutions retained in memory when running `findall` modes.
5. **`[time_limit_ms]`** *(Optional, Default: `120000.0` ms / 2 minutes)*:
   Execution timeout in milliseconds. Pass `0`, `none`, or `inf` for unlimited execution time (*run until finished*).

---

## 3. Practical CLI Examples

### Example 1: Fast Single Solution Search (`findone`)
```powershell
.\dumbsspCliv3.exe "12, 45, 67, 89, 23, 56, 78, 90, 34" 134 findone
```
**Terminal Output**:
```text
Exact Solution Found (3 elements):
Values : [12, 34, 88] -> Sum Check: 134 == Target 134 (EXACT MATCH 100% VALID)
Indices: [0, 8, 3]
L7 Verifier : [100% INDEPENDENTLY VERIFIED VALID]
```

---

### Example 2: Large Trillion-Scale Target ($N=80$)
```powershell
.\dumbsspCliv3.exe "123005401502, 811856239314, 267469214296, 151282538207, 114832269482, 814655221102" 1082124453480 findone
```

---

### Example 3: Multi-Witness Harvesting via Zero-Sum Swap (`findall-zero`)
Harvests multiple solution witnesses in polynomial time without expensive branch-and-bound backtracking:
```powershell
.\dumbsspCliv3.exe "10, 20, 30, 40, 50, 60, 70, 80" 120 zero 50
```

---

### Example 4: Counting Total Exact Combinations (`countall`)
```powershell
.\dumbsspCliv3.exe "5, 10, 15, 20, 25, 30, 35, 40" 40 count
```

---

### Example 5: Decision Problem & Formal Infeasibility Proof (`decision`)
Mathematically proves that no solution exists without performing full exponential backtracking:
```powershell
.\dumbsspCliv3.exe "26, 52, 78, 104, 130" 105 decision
```
**Terminal Output**:
```text
DECISION RESULT    : NO EXACT SUBSET FOUND (PROVABLY UNSAT)
Strategy Chosen    : L1: Trivial Exact Pre-Reduction
Diagnostic Note    : GCD Obstruction: gcd(A) = 26, but 105 % 26 != 0
```

---

### Example 6: Running Automated Demo (No Arguments)
Running the binary without arguments executes a built-in benchmark test with 32 trillion-scale elements:
```powershell
.\dumbsspCliv3.exe
```

---

## 4. Execution Report Structure

Every execution produces a comprehensive kernel-level diagnostic report upon completion:

```text
================================================================================
             DUMB SSP SOLVER v3 - TERMINAL EXECUTION REPORT                     
================================================================================
Test Label         : CLI Execution Result
Elements Count (N) : 80 raw (80 positive active)
Target Value (T)   : 18641147047913
Total Sum (Sigma)  : 41829471850192
Effective Target   : 18641147047913
Feasible K Range   : [22 .. 62] (41 cardinality window, 51%)
GCD Value          : 1
Density Score      : 1.8741
--------------------------------------------------------------------------------
Strategy Chosen    : L3: Hybrid Tail-Table + Adaptive Pruned DFS
BlockBound Cache   : 7002 prunes | Hits: 12410, Misses: 52140 [ACTIVE]
Solve Mode         : Find One (Early Exit)
Status             : SOLVED (SATISFIABLE)
Total Runtime      : 690.4120 ms (Preprocess: 1.2010 ms, Solve: 689.2110 ms)
States Evaluated   : 1385649
States Pruned      : 7002
Peak RAM Memory    : 42.15 MB
L7 Verifier        : [100% INDEPENDENTLY VERIFIED VALID]
================================================================================
```

---

## 5. Building from Source

To compile the C++ source code on Windows, use the GNU C++ Compiler (`g++` MinGW-w64) with `-O3` optimization:

### Build `dumbsspCliv3.exe`:
```powershell
g++ -O3 -std=c++17 v3/dumbsspCli.cpp -lpsapi -o dumbsspCliv3.exe
```

### Build `dumbsspCliv2.exe`:
```powershell
g++ -O3 -std=c++17 v2/dumbsspCli.cpp -lpsapi -o dumbsspCliv2.exe
```

### Build `dumbsspCliv1.exe`:
```powershell
g++ -O3 -std=c++17 v1/dumbsspCli.cpp -lpsapi -o dumbsspCliv1.exe
```

### Build Desktop GUI (`dumbsspGui.exe`):
```powershell
g++ -O3 -std=c++17 -mwindows dumbsspGui.cpp -lpsapi -lcomctl32 -o dumbsspGui.exe
```

---

## 6. Solver Architecture Taxonomy (L1–L8)

The engine automatically routes instances based on mathematical structure and problem density:

1. **L1: Trivial Exact Pre-Reduction** $\to$ Instant $\mathcal{O}(N)$ pre-checks for GCD modular obstructions, bit parity violations, aggregate sum bounds, or empty cardinality windows.
2. **L1.5: Greedy Superincreasing Solver** $\to$ Exact $\mathcal{O}(N)$ deterministic solver without backtracking for superincreasing sequences (Merkle–Hellman cryptosystems).
3. **L2: Vectorized Bitset DP** $\to$ 64-bit word-level parallel dynamic programming for small effective targets ($T \le 1.5 \times 10^7$).
4. **L2.5: Residue Cascade Sieve** $\to$ Elimination of modularly obstructed elements via multi-prime prefix/suffix DP reachability filters.
5. **L2.6: Small-K Combinatorial MitM Solver** $\to$ Instant $\mathcal{O}(N^2)$ or $\mathcal{O}(N^3)$ meet-in-the-middle resolution for sparse targets ($k \le 5$).
6. **L2.7: Boundary Deviation r-Swap Solver** $\to$ Exact $\mathcal{O}(N^2)$ local correction identifying solutions that deviate from the extreme top-$k$ or bottom-$k$ prefix by $r \le 2$ element swaps.
7. **L3: Hybrid Tail-Table + Adaptive Pruned DFS** $\to$ Core search engine bound to L3 cache ($m \le 20 \implies 16.00\text{ MB}$) with Gray-code precomputation, prefix/suffix bounding oracles, and auto-disabling bounded *BlockBound cache*.
8. **L8: Finite-Degree Zero-Sum Swap Extractor** $\to$ Fast polynomial-time extraction of multiple distinct solutions up to degree $p \le 4$.

# Adaptive Target-Remainder Solver (ATRS) & Subset Sum Research Platform

An advanced, exact research platform and comparative benchmark suite for the **Subset Sum Problem (SSP)**. This repository hosts standalone baseline implementations, formal mathematical pruning proofs, and the adaptive multi-oracle solver: **ATRS (Adaptive Target-Remainder Solver)**.

---

## 1. Problem Formulation

Given a finite multiset of positive integers:
$$A = \{a_1, a_2, \dots, a_n\} \subset \mathbb{Z}^+, \quad \text{with } a_1 \le a_2 \le \dots \le a_n$$
and a target integer $T \in \mathbb{Z}^+$, the **Subset Sum Problem** asks whether there exists a binary selection vector $x = (x_1, \dots, x_n) \in \{0, 1\}^n$ such that:
$$\sum_{j=1}^n x_j a_j = T$$

The platform supports three distinct operational search modes:
1. **`DECISION_ONLY`**: Determine the boolean feasibility ($\exists x \text{ s.t. } \sum x_j a_j = T$).
2. **`FIRST_SOLUTION`**: Find a verifiable certificate / witness subset $S \subseteq A$ satisfying $\sum_{a \in S} a = T$.
3. **`ALL_SOLUTIONS`**: Exhaustively enumerate the complete, canonical set of all distinct satisfying subsets without duplicates.

---

## 2. Comparative Algorithm Taxonomy

The platform provides dedicated, standalone implementations for 6 baseline methods alongside the ATRS architecture:

```
subset sum problem/
├── bruteforce.py                     # Method 1: Multi-Core Brute Force (2^n Binary Search)
├── target sisa.py                    # Method 2: Target-Remainder DFS + Suffix-Sum Pruning
├── target sisa dengan memoization.py # Method 3: Target-Remainder + Memoization + Pruning
├── target sisa full pruning.py       # Method 4: Target-Remainder + Full Sound Pruning (No Memo)
├── bitset.py                         # Method 5: Bitset Dynamic Programming (Guarded RAM)
├── atrs/                             # Modular ATRS Package
│   ├── core.py                       # Unified Core Solver Engines
│   ├── state.py                      # Data Structures & Result Semantics
│   ├── resource_guard.py             # Memory & Timeout Resource Guards
│   ├── scheduler.py                  # Dynamic Cost-Utility Oracle Scheduler
│   ├── validation.py                 # Multi-Solver Cross-Validation Engine
│   ├── benchmark.py                  # Automated Benchmarking Suite
│   ├── gui.py                        # Tkinter Research Interface
│   └── oracles/                      # Feasibility Oracles & Trivial Solvers
│       ├── base.py                   # Base Oracle Interface
│       ├── arithmetic.py             # Sound Necessary-Condition Pruner
│       ├── trivial.py                # Trivial Exact Match Solver
│       ├── bitset.py                 # Word-Level Bitset Feasibility Oracle
│       ├── mitm.py                   # Meet-in-the-Middle Feasibility Oracle
│       └── dfs.py                    # Bounded Subtree DFS Oracle
├── atrs.py                           # ATRS Entry Point (GUI / CLI)
└── tests/test_atrs.py                # Unit & Randomized Validation Test Suite
```

---

## 3. Detailed Algorithmic Descriptions

### Method 1: Brute Force (`bruteforce.py`)
- **Principle**: Explores the full binary decision tree of size $2^n$. At each index $i$, the algorithm branches into:
  - $\text{Include } a_i$: $\text{sum} \leftarrow \text{sum} + a_i$
  - $\text{Exclude } a_i$: $\text{sum} \leftarrow \text{sum}$
- **Parallelization**: Root subtrees are partitioned across physical CPU cores via `ProcessPoolExecutor`.
- **Complexity**: Time $\mathcal{O}(2^n)$, Space $\mathcal{O}(n)$.

---

### Method 2: Target-Remainder DFS (`target sisa.py`)
- **Principle**: Evaluates the state transition $(i, r)$ where $r = T - \sum_{j < i} x_j a_j$ denotes the remaining target value.
- **Suffix-Sum Upper Bound Pruning**: Precomputes suffix sums:
  $$\text{suffix\_sum}[i] = \sum_{j=i}^{n-1} a_j$$
  If $\text{suffix\_sum}[i] < r$, the branch is immediately pruned because even selecting all remaining elements cannot reach $r$.
- **Complexity**: Time $\mathcal{O}(2^n)$ worst-case, Space $\mathcal{O}(n)$.

---

### Method 3: Target-Remainder with Dead-States Memoization (`target sisa dengan memoization.py`)
- **Principle**: Caches proven infeasible states $(i, r)$ in a hash set (`dead_states`).
- **Sound Memoization Invariant**: A state $(i, r)$ is added to `dead_states` **if and only if** all subtrees rooted at $(i, r)$ have been exhaustively evaluated and produced zero valid subsets. If a branch yields a solution, $(i, r)$ is strictly kept out of `dead_states`.
- **Complexity**: Worst-case exponential, space bounded by $\min(2^n, |S_{\text{unique}}|)$.

---

### Method 4: Target-Remainder Full Pruning (`target sisa full pruning.py`)
- **Principle**: Pure depth-first search utilizing 5 sound mathematical pruning rules without maintaining a memoization cache.
- **Benefits**: Zero memory allocation overhead during tree traversal; guarantees 100% deterministic reproducibility across deep recursions.

---

### Method 5: Bitset Dynamic Programming (`bitset.py`)
- **Principle**: Encodes reachable subset sums as a large arbitrary-precision integer bitset $B$, updating states via bitwise shift and bitwise OR:
  $$B' = B \lor (B \ll a_i)$$
  Bit $k$ of $B$ is $1$ if and only if sum $k$ is achievable.
- **Memory Safety Guard**: Computes estimated memory $\approx \frac{T + 1}{8} \times 2.5 \text{ bytes}$ before allocation. If $T$ exceeds the memory quota, the solver returns `UNKNOWN: MEMORY_LIMIT` instead of triggering an Out-Of-Memory (OOM) fatal crash.
- **Witness Reconstruction**: Recovers the witness subset by backward bit testing across recorded transition checkpoints.
- **Complexity**: Time $\mathcal{O}\left(n \cdot \frac{T}{64}\right)$, Space $\mathcal{O}\left(\frac{T}{8}\right)$ (Pseudo-polynomial in $T$).

---

### Method 6: Meet-in-the-Middle (`atrs/oracles/mitm.py`)
- **Principle**: Partitions the candidate elements $C = \{a_j \le r\}$ into two halves $L$ and $R$ of sizes $\lfloor |C|/2 \rfloor$ and $\lceil |C|/2 \rceil$.
- **Search Strategy**: Generates subset sum tables for $L$ and $R$, then queries whether $r \in \text{Sums}(L)$, $r \in \text{Sums}(R)$, or $\exists s \in \text{Sums}(L)$ such that $(r - s) \in \text{Sums}(R)$.
- **Complexity**: Time $\mathcal{O}\left(2^{d/2}\right)$, Space $\mathcal{O}\left(2^{d/2}\right)$, where $d = |\{a_j \le r\}|$.

---

### Method 7: ATRS — Adaptive Target-Remainder Solver (`atrs.py` & `atrs/`)

$$ATRS = \text{Target-Remainder Search} + \text{Adaptive Oracles} + \text{Sound Pruning} + \text{Bounded Memo} + \text{Resource Guards}$$

ATRS coordinates search progression across a dynamic pipeline:

```
                       State (i, r)
                            │
                            ▼
              [ 1. Terminal Check: r == 0 ] ──► Solution Found
                            │
                            ▼
           [ 2. Sound Arithmetic Bound Pruner ] ──► INFEASIBLE: Prune
                            │
                            ▼
         [ 3. Trivial Exact Match Check (First Sol) ] ──► FEASIBLE: Return Witness
                            │
                            ▼
              [ 4. Dead-State Cache Lookup ] ──► Hit: Prune
                            │
                            ▼
            [ 5. Adaptive Oracle Manager ]
             ├── Estimate Bitset Cost & RAM
             ├── Estimate MITM Cost & State Limit
             └── Rank & Query Secondary Oracles ──► INFEASIBLE: Prune
                            │
                            ▼ (UNKNOWN)
          [ 6. Recursive Target-Remainder DFS ]
```

---

## 4. Mathematical Soundness of Pruning Rules

Every pruning condition in ATRS is mathematically sound (i.e., guaranteed to never discard a valid solution):

| Rule | Condition | Mathematical Proof / Soundness Justification |
| :--- | :--- | :--- |
| **1. Negative Remainder** | $r < 0$ | $\forall a_i \in A, a_i > 0 \implies \sum_{x \in S} x \ge 0$. A negative sum is impossible. |
| **2. Suffix Exhaustion** | $i \ge n \land r > 0$ | The set of available candidates is empty ($\emptyset$), but required remainder $r > 0$. |
| **3. Smallest Candidate Bound** | $a_i > r$ | Since $A$ is sorted ascending, $\min_{j \ge i}(a_j) = a_i > r$. Any selection yields a sum $> r$. |
| **4. Suffix-Sum Upper Bound** | $\sum_{j=i}^{n-1} a_j < r$ | The maximum achievable sum by including *all* remaining elements is strictly less than $r$. |
| **5. Suffix-GCD Divisibility** | $\gcd_{j \ge i}(a_j) = g > 1 \land r \not\equiv 0 \pmod g$ | Every linear combination $\sum x_j a_j$ is a multiple of $g$. If $r \pmod g \ne 0$, $r$ cannot be represented. |
| **6. Cardinality Lower Bound** | $\left\lceil \frac{r}{\max_{j \ge i, a_j \le r}(a_j)} \right\rceil > |\{a_j \le r\}|$ | Even choosing the largest available element repeatedly exceeds the total number of candidate elements available. |
| **7. Greedy Candidate Sum** | $\sum_{j \ge i, a_j \le r} a_j < r$ | Elements $> r$ cannot be selected. If the sum of all elements $\le r$ is still $< r$, no subset exists. |

---

## 5. Architectural Separation: Pruner vs Solver

To prevent logical ambiguity and false classifications, ATRS enforces strict separation of concerns:

- **`ArithmeticBoundOracle` (Pruner)**:
  - **Outputs ONLY**: `OracleStatus.INFEASIBLE` or `OracleStatus.UNKNOWN`.
  - **Never outputs**: `OracleStatus.FEASIBLE` and never constructs witnesses.
- **`TrivialExactSolver` (Solver)**:
  - Detects single-element matches ($a_k = r$) and exact full suffix matches ($\sum a_j = r$).
  - Outputs `OracleStatus.FEASIBLE` with verified witness lists only in `FIRST_SOLUTION` / `DECISION_ONLY` modes.
- **`ALL_SOLUTIONS` Mode Integrity**:
  - In `ALL_SOLUTIONS` mode, deep feasibility oracles (Bitset, MITM) are utilized **strictly for pruning** (`INFEASIBLE -> prune`).
  - When an oracle returns `FEASIBLE`, the search controller does **not** prematurely inject a partial witness, but continues exhaustive branching DFS. This guarantees **zero duplicate solutions** and 100% complete enumeration.

---

## 6. Theoretical Complexity Reference

> **Scientific Transparency Notice**: ATRS does **not** claim polynomial-time complexity for general Subset Sum. General Subset Sum is NP-complete. ATRS is an exact adaptive framework that drastically reduces search trees in practice while maintaining exactness.

| Method | Time Complexity (Worst-Case) | Space Complexity | Nature |
| :--- | :--- | :--- | :--- |
| **Brute Force** | $\mathcal{O}(2^n)$ | $\mathcal{O}(n)$ | Exponential |
| **Target-Remainder DFS** | $\mathcal{O}(2^n)$ | $\mathcal{O}(n)$ | Exponential |
| **Full Pruning (No Memo)** | $\mathcal{O}(2^n)$ | $\mathcal{O}(n)$ | Exponential |
| **Target-Remainder Memo** | $\mathcal{O}(2^n)$ | $\mathcal{O}(\min(2^n, \|S\|))$ | Non-polynomial state space |
| **Bitset DP** | $\mathcal{O}\left(n \cdot \frac{T}{64}\right)$ | $\mathcal{O}\left(\frac{T}{8}\right)$ | Pseudo-polynomial in $T$ |
| **Meet-in-the-Middle** | $\mathcal{O}(2^{n/2})$ | $\mathcal{O}(2^{n/2})$ | Sub-exponential in $n$ |
| **ATRS** | $\mathcal{O}(2^n)$ | Bounded by $\text{ResourceGuard}$ | Exact Adaptive Hybrid |

---

## 7. How to Run

### Requirements
- Python 3.9+
- Optional: `matplotlib` (for visual compute metrics and charts)

### Running Standalone Baseline Solvers
```powershell
# Method 1: Brute Force GUI & CLI
python bruteforce.py
python bruteforce.py --cli --values "3,7,11,14,18,21,26,29,34,38" --target 100 --all

# Method 2: Target-Remainder DFS GUI & CLI
python "target sisa.py"
python "target sisa.py" --cli --values "3,7,11,14,18,21,26,29,34,38" --target 100 --all

# Method 3: Target-Remainder + Memoization GUI
python "target sisa dengan memoization.py"

# Method 4: Target-Remainder Full Pruning GUI & CLI
python "target sisa full pruning.py"
python "target sisa full pruning.py" --cli --values "3,7,11,14,18,21,26,29,34,38" --target 100 --all

# Method 5: Bitset DP GUI & CLI
python bitset.py
python bitset.py --cli --values "3,7,11,14,18,21,26,29,34,38" --target 100 --all
```

### Running the ATRS Platform
```powershell
# Interactive GUI
python atrs.py

# Terminal CLI Mode
python atrs.py --cli --values "3,7,11,14,18,21,26,29,34,38" --target 100 --all
```

### Running the Test & Validation Suite
```powershell
# Run all unit tests
python -m unittest discover -s tests -v

# Run 30-instance randomized multi-algorithm cross-validation
python -c "from atrs.validation import run_exhaustive_random_validation; rep = run_exhaustive_random_validation(seeds=range(30), n_min=3, n_max=14); print('Validation Success:', rep['all_passed'])"
```

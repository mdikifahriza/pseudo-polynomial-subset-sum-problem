# Adaptive Exact Solvers Research Platform: ATRS & ATSP

An advanced, exact research platform and comparative benchmark suite for NP-hard combinatorial optimization:
1. **ATRS (Adaptive Target-Remainder Solver)** for the **Subset Sum Problem (SSP)**.
2. **ATSP (Adaptive Traveling Salesperson Solver)** for the **Traveling Salesperson Problem (TSP)**.

Both packages feature multi-core frontier parallelism, exact soundness guarantees, memory/timeout guards, TSPLIB compatibility, and automated LaTeX table / CSV export for academic publications.

---

## 1. Installation & Environment Setup

```bash
# 1. Clone repository
git clone https://github.com/mdikifahriza/pseudo-polynomial-subset-sum-problem.git
cd pseudo-polynomial-subset-sum-problem

# 2. Install dependencies or install in editable mode
pip install -r requirements.txt
pip install -e .
```

---

## 2. ATRS — Adaptive Target-Remainder Solver (Subset Sum)

### Problem Formulation
Given positive integers $A = \{a_1, a_2, \dots, a_n\} \subset \mathbb{Z}^+$ and target $T \in \mathbb{Z}^+$, find $x \in \{0, 1\}^n$ such that $\sum_{j=1}^n x_j a_j = T$.

### Key Features
* **Adaptive Feasibility Oracles**: Dynamic cost-utility scheduler toggling Arithmetic Bounds, Bitset DP, and Meet-in-the-Middle (MITM).
* **7 Sound Pruning Invariants**: Suffix-Sum upper bounds, Suffix-GCD modular divisibility ($r \not\equiv 0 \pmod g$), cardinality lower bounds, and dead-state memoization.
* **Multi-Search Modes**: `DECISION_ONLY`, `FIRST_SOLUTION`, and complete `ALL_SOLUTIONS` enumeration.

### Running ATRS
```bash
# Launch Modern Desktop GUI
python atrs.py

# CLI Single Solving Mode
python atrs.py --cli --values "3,7,11,14,18,21,26,29,34,38" --target 100 --all

# Comparative Benchmark & LaTeX/CSV Export
python atrs.py --cli --benchmark --n 20 --regime "Hard Density" --export-latex table_ssp.tex --export-csv results_ssp.csv
```

---

## 3. ATSP — Adaptive Traveling Salesperson Solver (TSP)

### Problem Formulation
Find the shortest Hamiltonian cycle (visiting each vertex exactly once and returning to origin) given a 2D Euclidean point set, custom distance matrix, or standard TSPLIB graph instance.

### Key Features
* **Multi-Heuristic Warm-Start Pipeline**: Fast Nearest Neighbor $\to$ 2-opt Simulated Annealing $\to$ Ant Colony Optimization (ACO) to establish tight global upper bounds.
* **Held-Karp 1-Tree Lagrangian Lower Bounds**: Subgradient optimization to prune subtrees aggressively or prove zero-DFS root optimality.
* **Standard TSPLIB (.tsp) Support**: Load and benchmark official TSPLIB files (`EUC_2D`, `ATT`, `GEO`, `EXPLICIT`).
* **Candidate Solutions Viewer**: Inspect, sort, and display all candidate tours from Rank 1 (Optimal) downwards.

### Running ATSP
```bash
# Launch Interactive 2D GUI & Matrix Grid
python atsp.py

# Run on Standard TSPLIB Instance
python atsp.py --cli --tsplib sample_tsplib.tsp

# Run Comparative Benchmark with LaTeX/CSV Export
python atsp.py --cli --benchmark --n 12 --pattern "Clustered" --export-latex table_tsp.tex --export-csv results_tsp.csv
```

---

## 4. Automated Exactness Validation

To verify the mathematical soundness of both exact solvers against ground truth (Brute Force and Held-Karp):

```bash
# Validate ATRS on randomized instances
python -c "from atrs.validation import run_exhaustive_random_validation; rep = run_exhaustive_random_validation(seeds=range(20), n_min=4, n_max=12); print('ATRS Soundness Verified:', rep['all_passed'])"

# Validate ATSP on randomized instances
python -c "from atsp.validation import validate_atsp_against_bruteforce; from atsp.benchmark import generate_instance; _, adj = generate_instance(n=8, seed=42); res = validate_atsp_against_bruteforce(adj); print('ATSP Soundness Verified:', res['passed'])"
```

---

## 5. Repository Architecture

```
subset-sum-tsp-research/
├── atrs/                               # Package ATRS (Subset Sum Problem)
│   ├── core.py                         # Unified ATRS & Baseline Solver Engines
│   ├── scheduler.py                    # Cost-Utility Oracle Scheduler
│   ├── benchmark.py                    # Benchmark Runner & LaTeX Exporter
│   ├── gui.py                          # Modern Tkinter Research Interface
│   ├── preprocess.py                   # Input Parsers
│   ├── resource_guard.py               # Memory & Timeout Resource Limiters
│   ├── state.py                        # Search Modes & Result Semantics
│   ├── validation.py                   # Soundness Multi-Engine Cross-Validation
│   └── oracles/                        # Arithmetic, Bitset, MITM, & DFS Oracles
├── atsp/                               # Package ATSP (Traveling Salesperson Problem)
│   ├── core.py                         # Unified ATSP & Baseline TSP Solvers
│   ├── scheduler.py                    # Adaptive TSP Oracle Manager
│   ├── benchmark.py                    # TSP Benchmark Runner & LaTeX Exporter
│   ├── gui.py                          # 2D Canvas & Matrix Grid GUI Interface
│   ├── preprocess.py                   # Coordinates, Matrix, & TSPLIB (.tsp) Parser
│   ├── resource_guard.py               # Worker Resource Guards
│   ├── state.py                        # Result Dataclasses & Search Modes
│   ├── validation.py                   # Exact TSP Cross-Validation Engine
│   ├── oracles/                        # MST, Held-Karp, Bound, & Degree Oracles
│   └── warmstart/                      # Simulated Annealing & Ant Colony Warm Starts
├── atrs.py                             # ATRS Entry Point (GUI / CLI)
├── atsp.py                             # ATSP Entry Point (GUI / CLI)
├── sample_tsplib.tsp                   # Sample TSPLIB Benchmark Instance
├── requirements.txt                    # Minimal Dependencies
└── pyproject.toml                      # Standard PEP 517/621 Package Setup
```

---

## 6. License
MIT License.

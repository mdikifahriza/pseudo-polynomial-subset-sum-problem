# ATRS (Adaptive Target-Remainder Solver) — User Guide & Documentation

## 1. Overview

**ATRS (Adaptive Target-Remainder Solver)** is an exact, research-grade solver for the **Subset Sum Problem (SSP)**. It integrates adaptive feasibility oracles, number-theoretic pruning invariants, and dynamic RAM resource guards to solve exact decision, certificate generation, and complete solution enumeration.

---

## 2. Installation & Quick Start

### Prerequisites
* Python 3.9 or higher
* Optional: `matplotlib` (for visual telemetry and efficiency charts)

### Setup
```bash
pip install -r requirements.txt
```

---

## 3. Running ATRS

### A. Modern Desktop Graphical User Interface (GUI)
To launch the interactive Tkinter research interface:
```bash
python atrs.py
```

#### GUI Capabilities:
* **Multiset & Target Input**: Direct entry of comma-separated positive integers and target sum $T$.
* **Random Dataset Generator**: Generate instances with configurable size ($n$), value range, and difficulty regimes:
  * `Random`: Uniformly distributed elements.
  * `Guaranteed Solvable`: Target constructed from a random subset.
  * `Guaranteed Unsolvable`: Parity/bound constructed infeasible targets.
  * `Hard Density`: Critical phase transition regime where $\alpha = n / \log_2(\max A) \approx 1.0$.
  * `Large GCD`: Elements sharing GCD $g > 1$ to test number-theoretic modular divisibility.
* **Search Modes**:
  * `FIRST_SOLUTION`: Returns the first verifiable witness subset.
  * `ALL_SOLUTIONS`: Canonical, complete enumeration without duplicate solutions.
  * `DECISION_ONLY`: Boolean satisfiability checking ($\text{True} / \text{False}$).
* **Solution Inspector**: Browse, filter, copy, and export discovered subsets to `.txt`.
* **Oracle Telemetry Charts**: Real-time Matplotlib visualization of work units, oracle calls, and pruning contributions with high-resolution export (PDF / PNG 300 DPI).
* **Comparative Benchmark Suite**: One-click evaluation against baseline solvers (Brute Force, Target-Remainder DFS, Memoized DFS, Bitset DP, Meet-in-the-Middle) with **LaTeX (`booktabs`)** and **CSV** export.

---

### B. Command-Line Interface (CLI)

ATRS features a high-throughput CLI mode with automated validation and LaTeX/CSV export.

#### Basic Usage:
```bash
# Solve a custom instance (find first witness)
python atrs.py --cli --values "3,7,11,14,18,21,26,29,34,38" --target 100

# Enumerate ALL valid subsets
python atrs.py --cli --values "3,7,11,14,18,21,26,29,34,38" --target 100 --all

# Solve a random instance with 24 elements in the Hard Density regime
python atrs.py --cli --random 24 --regime "Hard Density"
```

#### Comparative Benchmarking & Research Paper Table Export:
```bash
# Run comparative benchmark across all solvers and export to LaTeX & CSV
python atrs.py --cli --benchmark --n 20 --regime "Hard Density" --export-latex table_ssp.tex --export-csv results_ssp.csv
```

#### CLI Options Reference:
| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--cli` | Flag | `False` | Run in headless CLI mode instead of desktop GUI |
| `--values` | String | `"3,7,..."` | Comma-separated positive integers |
| `--target` | Integer | `100` | Target integer $T$ |
| `--all` | Flag | `False` | Enumerate all distinct satisfying subsets |
| `--random` | Integer | `None` | Generate and solve a random instance with $N$ elements |
| `--regime` | Choice | `Random` | Difficulty regime (`Random`, `Guaranteed Solvable`, `Guaranteed Unsolvable`, `Hard Density`, `Large GCD`) |
| `--workers` | Integer | `All` | Number of CPU worker processes |
| `--benchmark` | Flag | `False` | Run comparative benchmark suite |
| `--timeout` | Float | `15.0` | Timeout in seconds per algorithm in benchmark |
| `--export-latex` | Path | `None` | Save benchmark results as a LaTeX `booktabs` table |
| `--export-csv` | Path | `None` | Save benchmark results to CSV |
| `--skip-validation`| Flag | `False` | Skip automated soundness validation against Brute Force |

---

## 4. Python API Integration

You can easily import ATRS as a Python library in your own research scripts:

```python
from atrs.core import ATRSSolver
from atrs.state import SearchMode
from atrs.resource_guard import ResourceGuard

# Initialize solver
solver = ATRSSolver()

# Input data
multiset = [3, 7, 11, 14, 18, 21, 26, 29, 34, 38]
target = 100

# Set safety memory and timeout limits
guard = ResourceGuard(max_memory_bytes=512 * 1024 * 1024, timeout_seconds=30.0)

# Solve
result = solver.solve(
    values=multiset,
    target=target,
    mode=SearchMode.ALL_SOLUTIONS,
    guard=guard,
    num_workers=4
)

print(f"Status: {result.status.value}")
print(f"Elapsed: {result.elapsed:.6f} s")
print(f"Subsets Found: {len(result.solutions)}")
for s in result.solutions:
    print(f"  {' + '.join(map(str, s))} = {target}")
```

---

## 5. Automated Soundness Validation

Verify that ATRS matches exact ground truth on randomized instances:
```bash
python -c "from atrs.validation import run_exhaustive_random_validation; rep = run_exhaustive_random_validation(seeds=range(20), n_min=4, n_max=12); print('Validation Passed:', rep['all_passed'])"
```

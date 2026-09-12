# ATSP (Adaptive Traveling Salesman Problem Solver) — User Guide & Documentation

## 1. Overview

**ATSP (Adaptive Traveling Salesperson Solver)** is an exact research framework for finding optimal Hamiltonian cycles in symmetric and asymmetric weighted graphs. It integrates a multi-tiered metaheuristic warm-start pipeline (Nearest Neighbor, Simulated Annealing, Ant Colony Optimization), Lagrangian subgradient relaxation (Held-Karp 1-Tree lower bounds), and parallel Branch & Bound.

---

## 2. Installation & Quick Start

### Prerequisites
* Python 3.9 or higher
* Optional: `matplotlib` (for visual telemetry and graphs)

### Setup
```bash
pip install -r requirements.txt
```

---

## 3. Running ATSP

### A. Modern Desktop Graphical User Interface (GUI)
To launch the interactive Tkinter research interface:
```bash
python atsp.py
```

#### GUI Capabilities:
* **Interactive 2D Euclidean Canvas**: Left-click directly on the canvas to place custom city coordinates, with automatic route drawing and edge direction arrows.
* **Interactive NxN Matrix Grid**: Real-time table editor with automatic symmetry mirroring, random distance filling, and zero-resetting.
* **Standard TSPLIB (.tsp) & File Loader**: Direct loading of standard TSPLIB benchmark instances, coordinate files, raw text matrices, and edge lists.
* **Candidate Solutions Viewer**: Inspect, sort, and display all candidate tours discovered during the search, ranked from Rank 1 (Globally Optimal) downwards.
* **Comparative Benchmark Ranking**: Benchmark all baseline solvers (Nearest Neighbor, Simulated Annealing, Ant Colony Optimization, Held-Karp DP, Branch & Bound) with **LaTeX (`booktabs`)** and **CSV** export.

---

### B. Command-Line Interface (CLI)

ATSP features a high-performance CLI mode supporting direct TSPLIB files, benchmark sweeps, and LaTeX table export.

#### Basic Usage:
```bash
# Solve a standard TSPLIB benchmark instance
python atsp.py --cli --tsplib sample_tsplib.tsp

# Solve a random 15-city instance with clustered distribution
python atsp.py --cli --random 15 --pattern "Clustered"

# Enumerate all globally optimal tours for a coordinate string
python atsp.py --cli --cities "0,0; 10,0; 10,10; 0,10" --all
```

#### Comparative Benchmarking & Research Paper Table Export:
```bash
# Run comparative benchmark across all 7 solvers and export to LaTeX & CSV
python atsp.py --cli --benchmark --n 10 --pattern "Random" --export-latex table_tsp.tex --export-csv results_tsp.csv
```

#### CLI Options Reference:
| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--cli` | Flag | `False` | Run in headless CLI mode instead of desktop GUI |
| `--tsplib` | Path | `None` | Path to standard TSPLIB (`.tsp`) file |
| `--input-file` | Path | `None` | Path to text/csv/tsp file containing coordinates or matrix |
| `--random` | Integer | `None` | Solve a randomly generated instance with $N$ cities |
| `--pattern` | Choice | `Random` | Spatial pattern (`Random`, `Clustered`, `Circle`, `Grid`) |
| `--all` | Flag | `False` | Enumerate all distinct globally optimal tours |
| `--workers` | Integer | `All` | Number of parallel worker processes |
| `--benchmark` | Flag | `False` | Run comparative benchmark suite across all solvers |
| `--validate` | Flag | `False` | Run exact soundness validation against Brute Force / Held-Karp |
| `--timeout` | Float | `10.0` | Timeout in seconds per algorithm during benchmark |
| `--no-sa` | Flag | `False` | Disable Simulated Annealing warm-start |
| `--no-aco` | Flag | `False` | Disable Ant Colony Optimization warm-start |
| `--export-latex` | Path | `None` | Save benchmark records as a LaTeX `booktabs` table |
| `--export-csv` | Path | `None` | Save benchmark records to CSV |

---

## 4. Python API Integration

You can easily import ATSP as a Python library in your own research scripts:

```python
from atsp.core import ATSPSolver
from atsp.state import SearchMode
from atsp.preprocess import build_adj_matrix, generate_instance

# Generate or define coordinates / distance matrix
coords, adj = generate_instance(n=12, instance_type="Clustered", seed=42)

# Initialize solver
solver = ATSPSolver(enable_sa=True, enable_aco=True)

# Solve
result = solver.solve(
    adj=adj,
    mode=SearchMode.SHORTEST_TOUR,
    num_workers=4
)

print(f"Status: {result.status.value}")
print(f"Optimal Cost: {result.best_cost:.4f}")
print(f"Optimal Tour: {' -> '.join(map(str, result.tours[0]))}")
print(f"Elapsed Time: {result.elapsed:.6f} s")
print(f"Nodes Explored: {result.stats.nodes:,}")
print(f"Branches Pruned: {result.stats.pruned:,}")
```

---

## 5. Automated Soundness Validation

Verify that ATSP matches exact ground truth (Brute Force / Held-Karp):
```bash
python -c "from atsp.validation import validate_atsp_against_bruteforce; from atsp.benchmark import generate_instance; _, adj = generate_instance(n=8, seed=42); res = validate_atsp_against_bruteforce(adj); print('Validation Passed:', res['passed'])"
```

"""
ATRS - GUI Application (Tkinter + Matplotlib)
Modern Research Interface for Exact Subset Sum with Adaptive Feasibility Oracles.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import time
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from .state import Stats, SolverResult, SolverStatus, SearchMode
from .preprocess import parse_input
from .resource_guard import ResourceGuard
from .core import (
    BaseSubsetSumSolver,
    BruteForceSolver,
    TargetRemainderDFSSolver,
    TargetRemainderPrunedSolver,
    TargetRemainderMemoSolver,
    BitsetDPSolver,
    MITMSolver,
    ATRSSolver,
)
from .validation import validate_atrs_against_bruteforce
from .benchmark import BenchmarkRunner, generate_instance

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class ATRSApplication:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ATRS — Adaptive Target-Remainder Solver for Subset Sum")
        self.root.geometry("1120x800")
        self.root.minsize(940, 660)
        self.root.configure(bg="#f8fafc")

        self.values: List[int] = []
        self.target: int = 0
        self.result: Optional[SolverResult] = None
        self.is_calculating = False
        self.calc_start_time = 0.0
        self.total_cores = os.cpu_count() or 1

        self.sol_window = None
        self.graph_window = None
        self.bench_window = None
        self.rand_window = None

        self.solvers_map: Dict[str, BaseSubsetSumSolver] = {
            "ATRS (Adaptive Solver)": ATRSSolver(),
            "Brute Force": BruteForceSolver(),
            "Target-Remainder DFS": TargetRemainderDFSSolver(),
            "Target-Remainder + Full Pruning": TargetRemainderPrunedSolver(),
            "Target-Remainder + Memoization": TargetRemainderMemoSolver(),
            "Bitset DP": BitsetDPSolver(),
            "Meet-in-the-Middle (MITM)": MITMSolver(),
        }

        self._setup_style()
        self._create_widgets()
        self._center_window(self.root, 1120, 800)

    def run(self):
        self.root.mainloop()

    def _center_window(self, win, w, h):
        win.update_idletasks()
        ws = win.winfo_screenwidth()
        hs = win.winfo_screenheight()
        x = max(0, (ws - w) // 2)
        y = max(0, (hs - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        bg_color = "#f8fafc"
        card_bg = "#ffffff"
        text_color = "#1e293b"

        style.configure(".", background=bg_color, foreground=text_color, font=("Segoe UI", 9))
        style.configure("TFrame", background=bg_color)
        style.configure("TLabelframe", background=card_bg, foreground="#334155")
        style.configure("TLabelframe.Label", background=card_bg, foreground="#0f172a", font=("Segoe UI", 10, "bold"))

        style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), background="#2563eb", foreground="#ffffff", padding=(14, 6))
        style.map("Primary.TButton", background=[("active", "#1d4ed8"), ("disabled", "#94a3b8")], foreground=[("disabled", "#f8fafc")])

        style.configure("Action.TButton", font=("Segoe UI", 9, "bold"), background="#0d9488", foreground="#ffffff", padding=(10, 5))
        style.map("Action.TButton", background=[("active", "#0f766e"), ("disabled", "#cbd5e1")], foreground=[("disabled", "#64748b")])

        style.configure("Graph.TButton", font=("Segoe UI", 9, "bold"), background="#7c3aed", foreground="#ffffff", padding=(10, 5))
        style.map("Graph.TButton", background=[("active", "#6d28d9"), ("disabled", "#cbd5e1")], foreground=[("disabled", "#64748b")])

        style.configure("Bench.TButton", font=("Segoe UI", 9, "bold"), background="#d97706", foreground="#ffffff", padding=(10, 5))
        style.map("Bench.TButton", background=[("active", "#b45309"), ("disabled", "#cbd5e1")], foreground=[("disabled", "#64748b")])

        style.configure("Secondary.TButton", font=("Segoe UI", 9), padding=(8, 5))

    def _create_widgets(self):
        header_frame = tk.Frame(self.root, bg="#0f172a", height=70)
        header_frame.pack(fill=tk.X)

        title_box = tk.Frame(header_frame, bg="#0f172a")
        title_box.pack(side=tk.LEFT, padx=18, pady=10)

        tk.Label(
            title_box,
            text="ATRS — Adaptive Target-Remainder Solver",
            font=("Segoe UI", 13, "bold"),
            bg="#0f172a",
            fg="#f8fafc"
        ).pack(anchor="w")

        tk.Label(
            title_box,
            text="Exact Subset Sum • Adaptive Feasibility Oracles • Multi-Core Frontier Parallelism",
            font=("Segoe UI", 9),
            bg="#0f172a",
            fg="#94a3b8"
        ).pack(anchor="w", pady=(2, 0))

        badge_box = tk.Frame(header_frame, bg="#1e293b", padx=10, pady=4, relief="solid", bd=1)
        badge_box.pack(side=tk.RIGHT, padx=18, pady=12)

        tk.Label(
            badge_box,
            text=f"⚡ {self.total_cores} CPU Cores Ready",
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#38bdf8"
        ).pack()

        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_card = ttk.LabelFrame(main_frame, text=" Input Parameters & Solver Configuration ", padding=12)
        input_card.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(input_card, text="Elements / Multiset:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=3)
        self.entry_values = ttk.Entry(input_card, font=("Consolas", 10))
        self.entry_values.grid(row=0, column=1, columnspan=4, sticky="ew", padx=(8, 8), pady=3)
        self.entry_values.insert(0, "3, 7, 11, 14, 18, 21, 26, 29, 34, 38, 45, 52, 59")

        ttk.Label(input_card, text="Target Sum (T):", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", pady=4)
        self.entry_target = ttk.Entry(input_card, width=12, font=("Consolas", 10))
        self.entry_target.grid(row=1, column=1, sticky="w", padx=(8, 8), pady=4)
        self.entry_target.insert(0, "150")

        ttk.Label(input_card, text="Algorithm:", font=("Segoe UI", 9, "bold")).grid(row=1, column=2, sticky="w", pady=4)
        self.combo_algo = ttk.Combobox(
            input_card,
            values=list(self.solvers_map.keys()),
            state="readonly",
            width=26
        )
        self.combo_algo.grid(row=1, column=3, sticky="w", padx=(6, 8), pady=4)
        self.combo_algo.current(0)

        ttk.Label(input_card, text="Search Mode:", font=("Segoe UI", 9, "bold")).grid(row=1, column=4, sticky="w", pady=4)
        self.combo_mode = ttk.Combobox(
            input_card,
            values=[m.value for m in SearchMode],
            state="readonly",
            width=22
        )
        self.combo_mode.grid(row=1, column=5, sticky="w", padx=(6, 4), pady=4)
        self.combo_mode.current(0)

        ttk.Label(input_card, text="Timeout (s):", font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=4)
        self.entry_timeout = ttk.Entry(input_card, width=8, font=("Consolas", 9))
        self.entry_timeout.grid(row=2, column=1, sticky="w", padx=(8, 8), pady=4)
        self.entry_timeout.insert(0, "30.0")

        ttk.Label(input_card, text="Memory Limit (MB):", font=("Segoe UI", 9)).grid(row=2, column=2, sticky="w", pady=4)
        self.entry_memory = ttk.Entry(input_card, width=8, font=("Consolas", 9))
        self.entry_memory.grid(row=2, column=3, sticky="w", padx=(6, 8), pady=4)
        self.entry_memory.insert(0, "512")

        btn_box = ttk.Frame(input_card)
        btn_box.grid(row=2, column=4, columnspan=2, sticky="e", pady=4)

        ttk.Button(btn_box, text="🎲 Random Dataset", style="Secondary.TButton", command=self._open_random_dialog).pack(side=tk.LEFT, padx=3)
        self.btn_bench = ttk.Button(btn_box, text="🔬 Benchmark", style="Bench.TButton", command=self._open_benchmark_window)
        self.btn_bench.pack(side=tk.LEFT, padx=3)
        self.btn_run = ttk.Button(btn_box, text="▶ Run ATRS", style="Primary.TButton", command=self._start_calculation)
        self.btn_run.pack(side=tk.LEFT, padx=3)

        input_card.columnconfigure(1, weight=1)

        dash_frame = ttk.Frame(main_frame)
        dash_frame.pack(fill=tk.X, pady=(0, 8))

        self.status_card = tk.Frame(dash_frame, bg="#ffffff", relief="solid", bd=1, padx=12, pady=8)
        self.status_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.lbl_status = tk.Label(self.status_card, text="Status: Ready.", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#334155")
        self.lbl_status.pack(anchor="w")

        self.lbl_strategy = tk.Label(
            self.status_card,
            text="Strategy Pipeline: Arithmetic Bound -> Bitset DP (if RAM budget allows) -> MITM -> DFS Fallback",
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg="#64748b"
        )
        self.lbl_strategy.pack(anchor="w", pady=(2, 0))

        self.lbl_validation = tk.Label(
            self.status_card,
            text="Validation: Not executed yet",
            font=("Segoe UI", 9, "italic"),
            bg="#ffffff",
            fg="#475569"
        )
        self.lbl_validation.pack(anchor="w", pady=(2, 0))

        btn_action_box = ttk.Frame(dash_frame)
        btn_action_box.pack(side=tk.RIGHT, padx=(10, 0))

        self.btn_solutions = ttk.Button(btn_action_box, text="📋 Solutions (0)", style="Action.TButton", command=self._open_solutions_window, state="disabled")
        self.btn_solutions.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        self.btn_graph = ttk.Button(btn_action_box, text="📊 Charts", style="Graph.TButton", command=self._open_graph_window, state="disabled")
        self.btn_graph.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        self.btn_save = ttk.Button(btn_action_box, text="💾 Save Report", style="Secondary.TButton", command=self._save_txt, state="disabled")
        self.btn_save.pack(side=tk.TOP, fill=tk.X)

        stat_frame = ttk.LabelFrame(main_frame, text=" Compute Telemetry & Adaptive Oracle Efficiency ", padding=8)
        stat_frame.pack(fill=tk.BOTH, expand=True)

        self.stat_text = tk.Text(
            stat_frame,
            font=("Consolas", 9),
            relief=tk.FLAT,
            bg="#f8fafc",
            fg="#0f172a",
            wrap=tk.NONE
        )

        scroll_y = ttk.Scrollbar(stat_frame, orient=tk.VERTICAL, command=self.stat_text.yview)
        scroll_x = ttk.Scrollbar(stat_frame, orient=tk.HORIZONTAL, command=self.stat_text.xview)
        self.stat_text.configure(xscrollcommand=scroll_x.set, yscrollcommand=scroll_y.set)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.stat_text.pack(fill=tk.BOTH, expand=True)

        self._show_welcome_text()

    def _show_welcome_text(self):
        self.stat_text.config(state=tk.NORMAL)
        self.stat_text.delete("1.0", tk.END)
        self.stat_text.insert(
            tk.END,
            "========================================================================================\n"
            "  ATRS (Adaptive Target-Remainder Solver) — Exact Subset Sum Research Platform\n"
            "========================================================================================\n\n"
            "Core Theoretical Foundations of ATRS:\n"
            "  1. Formal State Space: (i, r) represents searching for remaining target r in suffix [a_i, ..., a_n].\n"
            "  2. Adaptive Feasibility Oracles:\n"
            "     - Oracle A (Arithmetic & Bound) : O(1) Suffix-Sum, Suffix-GCD, Cardinality & Candidate Pruning.\n"
            "     - Oracle B (Bitset DP)         : Exact word-level DP with Guarded Memory Anti-OOM quota.\n"
            "     - Oracle C (Meet-in-the-Middle) : O(2^(d/2)) exact partitioning with state budget guard.\n"
            "     - Oracle D (Target-Remainder DFS): Exact branch & bound with sound dead-state memoization.\n"
            "  3. Strict Soundness Guarantee:\n"
            "     - Feasibility oracles return strictly FEASIBLE, INFEASIBLE, or UNKNOWN.\n"
            "     - UNKNOWN is never treated as NO SOLUTION (prevents false negatives).\n"
            "  4. Anti-OOM & Resource Guard:\n"
            "     - Apriori cost estimation avoids allocating massive bitsets on multi-billion targets.\n"
            "  5. Exactness & Complexity Transparency:\n"
            "     - Worst-case theoretical complexity: Exponential (no P=NP claim).\n"
            "     - Automated cross-validation against ground truth Brute Force for n <= 20.\n"
            "========================================================================================\n"
        )
        self.stat_text.config(state=tk.DISABLED)

    def _start_calculation(self):
        if self.is_calculating:
            return

        try:
            values = parse_input(self.entry_values.get())
            target = int(self.entry_target.get())
            if target <= 0:
                raise ValueError("Target sum must be a positive integer.")

            timeout = float(self.entry_timeout.get())
            mem_mb = float(self.entry_memory.get())
        except Exception as e:
            messagebox.showerror("Input Error", str(e))
            return

        mode_str = self.combo_mode.get()
        mode = next((m for m in SearchMode if m.value == mode_str), SearchMode.FIRST_SOLUTION)
        algo_name = self.combo_algo.get()
        solver = self.solvers_map[algo_name]

        self.is_calculating = True
        self.calc_start_time = time.perf_counter()

        self.btn_run.config(state="disabled")
        self.btn_bench.config(state="disabled")
        self.btn_save.config(state="disabled")
        self.btn_solutions.config(state="disabled")
        self.btn_graph.config(state="disabled")

        self.lbl_status.config(text=f"Status: Executing {algo_name}... ⏳", fg="#d97706")
        self.lbl_strategy.config(text=f"Distributing task across {self.total_cores} CPU cores.")

        thread = threading.Thread(
            target=self._run_thread,
            args=(solver, values, target, mode, timeout, mem_mb),
            daemon=True
        )
        thread.start()

    def _run_thread(self, solver, values, target, mode, timeout, mem_mb):
        guard = ResourceGuard(
            max_memory_bytes=int(mem_mb * 1024 * 1024),
            timeout_seconds=timeout
        )
        try:
            num_workers = self.total_cores if solver.name.startswith("ATRS") else 1
            res = solver.solve(values, target, mode=mode, guard=guard, num_workers=num_workers)

            val_report = None
            if solver.name.startswith("ATRS") and len(values) <= 20:
                val_report = validate_atrs_against_bruteforce(values, target, mode)

            self.root.after(0, self._on_success, values, target, res, val_report)
        except Exception as e:
            self.root.after(0, self._on_error, str(e))

    def _on_success(self, values: List[int], target: int, res: SolverResult, val_report: Optional[Dict[str, Any]]):
        self.is_calculating = False
        self.values = values
        self.target = target
        self.result = res

        if res.status == SolverStatus.EXACT_SOL_FOUND:
            self.lbl_status.config(text="Status: ✅ EXACT — SOLUTION FOUND", fg="#15803d")
        elif res.status == SolverStatus.EXACT_NO_SOL:
            self.lbl_status.config(text="Status: ✅ EXACT — NO SOLUTION EXISTS", fg="#15803d")
        elif res.status == SolverStatus.UNKNOWN_TIMEOUT:
            self.lbl_status.config(text="Status: ⚠️ INCOMPLETE — TIME LIMIT REACHED", fg="#dc2626")
        elif res.status == SolverStatus.UNKNOWN_MEMORY:
            self.lbl_status.config(text="Status: ⚠️ INCOMPLETE — MEMORY LIMIT REACHED", fg="#dc2626")
        else:
            self.lbl_status.config(text=f"Status: ⚠️ {res.status.value}", fg="#dc2626")

        sol_count = len(res.solutions)
        self.lbl_strategy.config(
            text=f"Algorithm: {res.algorithm_name} | Elapsed: {res.elapsed:.4f}s | Nodes: {res.stats.nodes:,} | Peak RAM: {res.stats.memory_peak_bytes / (1024*1024):.2f} MB"
        )

        if val_report:
            if val_report["passed"]:
                self.lbl_validation.config(text="Validation vs Brute Force: ✅ PASSED (Exact Match)", fg="#15803d")
            else:
                self.lbl_validation.config(text=f"Validation vs Brute Force: ❌ FAILED! ({val_report['error_msg']})", fg="#dc2626")
        else:
            self.lbl_validation.config(text="Validation vs Brute Force: (Omitted for n > 20)", fg="#64748b")

        self.btn_run.config(state="normal")
        self.btn_bench.config(state="normal")
        self.btn_save.config(state="normal")
        self.btn_solutions.config(state="normal", text=f"📋 Solutions ({sol_count:,})")
        if HAS_MATPLOTLIB:
            self.btn_graph.config(state="normal")

        self._render_detailed_stats()

    def _on_error(self, err_msg: str):
        self.is_calculating = False
        self.btn_run.config(state="normal")
        self.btn_bench.config(state="normal")
        messagebox.showerror("Error", err_msg)
        self.lbl_status.config(text=f"Status: Failed ({err_msg})", fg="#dc2626")

    def _render_detailed_stats(self):
        if not self.result:
            return

        r = self.result
        s = r.stats
        lines = []

        lines.append("=" * 86)
        lines.append(f"  COMPUTATIONAL RESEARCH REPORT: {r.algorithm_name.upper()}")
        lines.append("=" * 86)
        lines.append(f"Status / Exactness   : {r.status.value}")
        lines.append(f"Multiset (n={len(self.values)}) : {self.values}")
        lines.append(f"Target Sum (T)       : {self.target:,}")
        lines.append(f"Satisfying Subsets   : {len(r.solutions):,}")
        lines.append(f"Elapsed Time         : {r.elapsed:.6f} seconds")
        lines.append(f"Peak Memory (RAM)    : {s.memory_peak_bytes / (1024*1024):.2f} MB")
        lines.append(f"Peak Dead-States     : {s.dead_states_peak:,}")
        lines.append("")

        lines.append("-" * 86)
        lines.append("SEARCH TREE METRICS & WORK UNITS")
        lines.append("-" * 86)
        lines.append(f"  • Nodes Explored            : {s.nodes:>16,}")
        lines.append(f"  • Arithmetic Operations     : {s.arithmetic:>16,}")
        lines.append(f"  • Comparisons               : {s.comparisons:>16,}")
        lines.append(f"  • Bound Checks              : {s.bound_checks:>16,}")
        lines.append(f"  • Branches Pruned           : {s.pruned:>16,}")
        lines.append(f"  • Total Work Units          : {s.work_units:>16,}")
        lines.append("")

        lines.append("-" * 86)
        lines.append("PRUNING & BOUNDING DECOMPOSITION")
        lines.append("-" * 86)
        lines.append(f"  • Memoization Hits          : {s.memo_hits:>16,}")
        lines.append(f"  • Upper Bound Prunes (Sum)  : {s.upper_prunes:>16,}")
        lines.append(f"  • Lower / Candidate Prunes  : {s.lower_prunes:>16,}")
        lines.append(f"  • Suffix GCD Divisibility   : {s.gcd_prunes:>16,}")
        lines.append(f"  • Cardinality Bound Prunes  : {s.cardinality_prunes:>16,}")
        lines.append(f"  • Oracle Feasibility Prunes : {s.oracle_prunes:>16,}")
        lines.append("")

        lines.append("-" * 86)
        lines.append("ADAPTIVE FEASIBILITY ORACLE DASHBOARD")
        lines.append("-" * 86)
        lines.append(f"{'Oracle':<16} {'Calls':>10} {'Feasible':>10} {'Infeasible':>12} {'Unknown':>10} {'Prunes':>10} {'Time (s)':>12}")
        lines.append("-" * 86)

        for name in ["arithmetic", "bitset", "mitm", "dfs"]:
            calls = s.oracle_calls.get(name, 0)
            feas = s.oracle_feasible.get(name, 0)
            infeas = s.oracle_infeasible.get(name, 0)
            unk = s.oracle_unknown.get(name, 0)
            prunes = s.oracle_useful_prunes.get(name, 0)
            otime = s.oracle_time.get(name, 0.0)
            lines.append(f"{name.capitalize():<16} {calls:>10,} {feas:>10,} {infeas:>12,} {unk:>10,} {prunes:>10,} {otime:>12.6f}")

        lines.append("")
        lines.append("=" * 86)
        lines.append("THEORETICAL COMPLEXITY BENCHMARKS")
        lines.append("=" * 86)
        lines.append("  • Theoretical Worst-Case   : Exponential O(2^(n/2)) or O(2^n)")
        lines.append("  • Bitset DP Complexity     : Pseudo-polynomial O(n * Target)")
        lines.append("  • MITM Complexity          : Suffix-bounded sub-exponential O(2^(d/2))")
        lines.append("  • ATRS Adaptive Property   : Dynamic instance-dependent pruning without P=NP claim")

        self.stat_text.config(state=tk.NORMAL)
        self.stat_text.delete("1.0", tk.END)
        self.stat_text.insert(tk.END, "\n".join(lines))
        self.stat_text.config(state=tk.DISABLED)

    def _open_random_dialog(self):
        if self.rand_window and self.rand_window.winfo_exists():
            self.rand_window.lift()
            return

        self.rand_window = tk.Toplevel(self.root)
        self.rand_window.title("Random Dataset Generator")
        self.rand_window.geometry("450x360")
        self.rand_window.configure(bg="#f8fafc")

        hdr = tk.Frame(self.rand_window, bg="#0f172a", padx=14, pady=10)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Generate Subset Sum Instance", font=("Segoe UI", 10, "bold"), bg="#0f172a", fg="#ffffff").pack(anchor="w")

        f = ttk.Frame(self.rand_window, padding=14)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="Number of Elements (n):").grid(row=0, column=0, sticky="w", pady=4)
        e_n = ttk.Entry(f, width=12)
        e_n.grid(row=0, column=1, sticky="w", pady=4)
        e_n.insert(0, "24")

        ttk.Label(f, text="Minimum Element Value:").grid(row=1, column=0, sticky="w", pady=4)
        e_min = ttk.Entry(f, width=12)
        e_min.grid(row=1, column=1, sticky="w", pady=4)
        e_min.insert(0, "10")

        ttk.Label(f, text="Maximum Element Value:").grid(row=2, column=0, sticky="w", pady=4)
        e_max = ttk.Entry(f, width=12)
        e_max.grid(row=2, column=1, sticky="w", pady=4)
        e_max.insert(0, "500")

        ttk.Label(f, text="Instance Regime:").grid(row=3, column=0, sticky="w", pady=4)
        cb_mode = ttk.Combobox(
            f,
            values=["Random", "Guaranteed Solvable", "Guaranteed Unsolvable", "Hard Density", "Large GCD"],
            state="readonly",
            width=22
        )
        cb_mode.grid(row=3, column=1, sticky="w", pady=4)
        cb_mode.current(1)

        def do_generate():
            try:
                n = int(e_n.get())
                mn = int(e_min.get())
                mx = int(e_max.get())
                tmode = cb_mode.get()
                vals, tgt = generate_instance(n, mn, mx, tmode)
                self.entry_values.delete(0, tk.END)
                self.entry_values.insert(0, ", ".join(map(str, vals)))
                self.entry_target.delete(0, tk.END)
                self.entry_target.insert(0, str(tgt))
                self.rand_window.destroy()
            except Exception as ex:
                messagebox.showerror("Error", str(ex))

        ttk.Button(f, text="🎲 Generate Instance", style="Primary.TButton", command=do_generate).grid(row=4, column=0, columnspan=2, pady=(16, 0))
        self._center_window(self.rand_window, 450, 360)

    def _open_benchmark_window(self):
        if self.bench_window and self.bench_window.winfo_exists():
            self.bench_window.lift()
            return

        try:
            values = parse_input(self.entry_values.get())
            target = int(self.entry_target.get())
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        self.bench_window = tk.Toplevel(self.root)
        self.bench_window.title("Subset Sum Algorithm Benchmark Suite")
        self.bench_window.geometry("940x580")
        self.bench_window.minsize(740, 460)
        self.bench_window.configure(bg="#f8fafc")

        hdr = tk.Frame(self.bench_window, bg="#d97706", padx=14, pady=10)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="🔬 ATRS Comparative Research Benchmark Suite", font=("Segoe UI", 11, "bold"), bg="#d97706", fg="#ffffff").pack(anchor="w")
        tk.Label(hdr, text=f"Target: {target:,} | n: {len(values)} elements", font=("Segoe UI", 9), bg="#d97706", fg="#fef3c7").pack(anchor="w")

        tb = tk.Frame(self.bench_window, bg="#f8fafc", padx=12, pady=6)
        tb.pack(fill=tk.X)

        btn_run_b = ttk.Button(tb, text="▶ Run Benchmark", style="Primary.TButton")
        btn_run_b.pack(side=tk.LEFT, padx=(0, 6))

        btn_export_csv = ttk.Button(tb, text="📊 Export CSV", style="Secondary.TButton")
        btn_export_csv.pack(side=tk.LEFT, padx=(0, 6))

        btn_export_latex = ttk.Button(tb, text="📄 Export LaTeX Table", style="Secondary.TButton")
        btn_export_latex.pack(side=tk.LEFT)

        lbl_b_status = tk.Label(tb, text="Click 'Run Benchmark' to evaluate all baseline solvers.", font=("Segoe UI", 9), bg="#f8fafc", fg="#64748b")
        lbl_b_status.pack(side=tk.RIGHT)

        tree_frame = tk.Frame(self.bench_window, padx=12, pady=6, bg="#f8fafc")
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("algorithm", "status", "time_sec", "nodes", "prunes", "memory_mb", "solutions", "exact")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        tree.heading("algorithm", text="Algorithm")
        tree.heading("status", text="Status")
        tree.heading("time_sec", text="Time (s)")
        tree.heading("nodes", text="Nodes")
        tree.heading("prunes", text="Pruned")
        tree.heading("memory_mb", text="RAM (MB)")
        tree.heading("solutions", text="Solutions")
        tree.heading("exact", text="Exact?")

        tree.column("algorithm", width=220)
        tree.column("status", width=160)
        tree.column("time_sec", width=90, anchor="e")
        tree.column("nodes", width=90, anchor="e")
        tree.column("prunes", width=90, anchor="e")
        tree.column("memory_mb", width=80, anchor="e")
        tree.column("solutions", width=70, anchor="e")
        tree.column("exact", width=60, anchor="center")

        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)

        bench_records: List[Dict[str, Any]] = []

        def run_bench():
            btn_run_b.config(state="disabled")
            lbl_b_status.config(text="Executing benchmark suite... ⏳")
            for item in tree.get_children():
                tree.delete(item)

            def task():
                runner = BenchmarkRunner(timeout_per_algo=15.0)
                recs = runner.run_benchmark(values, target)
                bench_records.clear()
                bench_records.extend(recs)

                def on_done():
                    for r in recs:
                        tree.insert("", tk.END, values=(
                            r["algorithm"],
                            r["status"],
                            f"{r['time_sec']:.4f}",
                            f"{r['nodes']:,}",
                            f"{r['prunes']:,}",
                            f"{r['memory_mb']:.2f}",
                            f"{r['solutions']:,}",
                            "✓" if r["exact"] else "✗"
                        ))
                    btn_run_b.config(state="normal")
                    lbl_b_status.config(text=f"Benchmark completed ({len(recs)} algorithms evaluated).")

                self.root.after(0, on_done)

            threading.Thread(target=task, daemon=True).start()

        def do_export_csv():
            if not bench_records:
                messagebox.showinfo("Info", "Please execute the benchmark first.")
                return
            path = filedialog.asksaveasfilename(
                title="Export Benchmark Results to CSV",
                defaultextension=".csv",
                filetypes=[("CSV File", "*.csv")],
                initialfile=f"benchmark_ssp_n{len(values)}_T{target}.csv"
            )
            if path:
                BenchmarkRunner.export_csv(bench_records, path)
                messagebox.showinfo("Export Successful", f"Benchmark CSV saved to:\n{path}")

        def do_export_latex():
            if not bench_records:
                messagebox.showinfo("Info", "Please execute the benchmark first.")
                return
            path = filedialog.asksaveasfilename(
                title="Export Benchmark Results to LaTeX Table",
                defaultextension=".tex",
                filetypes=[("LaTeX File", "*.tex")],
                initialfile=f"table_ssp_benchmark_n{len(values)}.tex"
            )
            if path:
                tex_code = BenchmarkRunner.export_latex(
                    bench_records,
                    caption=f"Comparative Benchmark on Subset Sum ($n={len(values)}, T={target:,}$)",
                    label=f"tab:ssp_bench_n{len(values)}"
                )
                Path(path).write_text(tex_code, encoding="utf-8")
                messagebox.showinfo("Export Successful", f"LaTeX table saved to:\n{path}")

        btn_run_b.config(command=run_bench)
        btn_export_csv.config(command=do_export_csv)
        btn_export_latex.config(command=do_export_latex)
        self._center_window(self.bench_window, 940, 580)

    def _open_solutions_window(self):
        if not self.result:
            return

        if self.sol_window and self.sol_window.winfo_exists():
            self.sol_window.lift()
            return

        self.sol_window = tk.Toplevel(self.root)
        self.sol_window.title("Subset Sum Solution Inspector")
        self.sol_window.geometry("760x580")
        self.sol_window.configure(bg="#f8fafc")

        hdr = tk.Frame(self.sol_window, bg="#0f766e", padx=16, pady=10)
        hdr.pack(fill=tk.X)

        sols = self.result.solutions
        tk.Label(hdr, text=f"Satisfying Subsets Discovered ({len(sols):,} Subsets)", font=("Segoe UI", 11, "bold"), bg="#0f766e", fg="#ffffff").pack(anchor="w")
        tk.Label(hdr, text=f"Target: {self.target:,} | Algorithm: {self.result.algorithm_name}", font=("Segoe UI", 9), bg="#0f766e", fg="#ccfbf1").pack(anchor="w")

        tb = tk.Frame(self.sol_window, bg="#f8fafc", padx=12, pady=6)
        tb.pack(fill=tk.X)

        def copy_sols():
            lines = [f"{i}. {' + '.join(map(str, s))} = {self.target}" for i, s in enumerate(sols, 1)]
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(lines))
            messagebox.showinfo("Copied", "All solutions copied to clipboard.")

        def export_sols_txt():
            path = filedialog.asksaveasfilename(
                title="Export Solutions to TXT",
                defaultextension=".txt",
                filetypes=[("Text File", "*.txt")],
                initialfile=f"solutions_ssp_T{self.target}_n{len(self.values)}.txt"
            )
            if path:
                lines = [f"{i}. {' + '.join(map(str, s))} = {self.target}" for i, s in enumerate(sols, 1)]
                Path(path).write_text("\n".join(lines), encoding="utf-8")
                messagebox.showinfo("Export Successful", f"Solutions saved to:\n{path}")

        ttk.Button(tb, text="📋 Copy to Clipboard", command=copy_sols).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(tb, text="💾 Export TXT", command=export_sols_txt).pack(side=tk.LEFT)
        ttk.Button(tb, text="Close", command=self.sol_window.destroy).pack(side=tk.RIGHT)

        text_f = tk.Frame(self.sol_window, padx=12, pady=6, bg="#f8fafc")
        text_f.pack(fill=tk.BOTH, expand=True)

        txt = tk.Text(text_f, font=("Consolas", 10), wrap=tk.WORD, bg="#ffffff", fg="#0f172a", relief=tk.SOLID, bd=1)
        scr = ttk.Scrollbar(text_f, orient=tk.VERTICAL, command=txt.yview)
        txt.configure(yscrollcommand=scr.set)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        txt.pack(fill=tk.BOTH, expand=True)

        if not sols:
            txt.insert(tk.END, "NO SATISFYING SUBSET EXISTS FOR THE GIVEN TARGET.\n")
        else:
            limit = min(len(sols), 1000)
            for i in range(limit):
                sol = sols[i]
                txt.insert(tk.END, f"{i+1:>5}.  {' + '.join(map(str, sol))} = {self.target}\n")
            if len(sols) > limit:
                txt.insert(tk.END, f"\n... and {len(sols) - limit:,} additional solutions (Use Export TXT for complete list).\n")

        txt.config(state=tk.DISABLED)
        self._center_window(self.sol_window, 760, 580)

    def _open_graph_window(self):
        if not HAS_MATPLOTLIB or not self.result:
            return

        if self.graph_window and self.graph_window.winfo_exists():
            self.graph_window.lift()
            return

        self.graph_window = tk.Toplevel(self.root)
        self.graph_window.title("ATRS Metric & Oracle Telemetry Visualization")
        self.graph_window.geometry("940x660")
        self.graph_window.minsize(760, 520)
        self.graph_window.configure(bg="#f8fafc")

        hdr = tk.Frame(self.graph_window, bg="#6d28d9", padx=16, pady=10)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Computational Telemetry & Oracle Performance Dashboard", font=("Segoe UI", 11, "bold"), bg="#6d28d9", fg="#ffffff").pack(anchor="w")

        tb = tk.Frame(self.graph_window, bg="#f8fafc", padx=12, pady=6)
        tb.pack(fill=tk.X)

        s = self.result.stats
        fig = Figure(figsize=(9, 5.5), dpi=100, facecolor="#ffffff")

        ax1 = fig.add_subplot(221)
        labels1 = ["Nodes", "Arith", "Comp", "Bound", "Pruned"]
        vals1 = [s.nodes, s.arithmetic, s.comparisons, s.bound_checks, s.pruned]
        ax1.bar(labels1, vals1, color=["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444"])
        ax1.set_title("Work Units Distribution", fontsize=9, fontweight="bold")
        ax1.grid(axis="y", linestyle="--", alpha=0.3)

        ax2 = fig.add_subplot(222)
        oracles = ["Arithmetic", "Bitset", "MITM", "DFS"]
        calls = [s.oracle_calls.get(o.lower(), 0) for o in oracles]
        ax2.bar(oracles, calls, color=["#06b6d4", "#3b82f6", "#8b5cf6", "#f97316"])
        ax2.set_title("Feasibility Oracle Invocations", fontsize=9, fontweight="bold")
        ax2.grid(axis="y", linestyle="--", alpha=0.3)

        ax3 = fig.add_subplot(223)
        prune_lbls = ["Upper", "Lower", "GCD", "Card", "Memo"]
        prune_vals = [s.upper_prunes, s.lower_prunes, s.gcd_prunes, s.cardinality_prunes, s.memo_hits]
        ax3.bar(prune_lbls, prune_vals, color=["#ec4899", "#f43f5e", "#eab308", "#6366f1", "#14b8a6"])
        ax3.set_title("Pruning Rule Contribution", fontsize=9, fontweight="bold")
        ax3.grid(axis="y", linestyle="--", alpha=0.3)

        ax4 = fig.add_subplot(224)
        times = [s.oracle_time.get(o.lower(), 0.0) * 1000 for o in oracles]
        ax4.bar(oracles, times, color=["#10b981", "#0284c7", "#7c3aed", "#ea580c"])
        ax4.set_title("Oracle Execution Time (ms)", fontsize=9, fontweight="bold")
        ax4.grid(axis="y", linestyle="--", alpha=0.3)

        fig.tight_layout(pad=2.0)

        def save_plot():
            path = filedialog.asksaveasfilename(
                title="Save High-Resolution Plot",
                defaultextension=".png",
                filetypes=[("PNG Image", "*.png"), ("PDF Document", "*.pdf"), ("SVG Vector", "*.svg")],
                initialfile=f"ATRS_plot_T{self.target}_n{len(self.values)}.png"
            )
            if path:
                fig.savefig(path, dpi=300, bbox_inches="tight")
                messagebox.showinfo("Export Successful", f"High-resolution figure saved to:\n{path}")

        ttk.Button(tb, text="📷 Save Figure (PDF / PNG 300 DPI)", command=save_plot).pack(side=tk.LEFT)

        container = tk.Frame(self.graph_window, bg="#ffffff", padx=8, pady=8)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = FigureCanvasTkAgg(fig, master=container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self._center_window(self.graph_window, 940, 660)

    def _save_txt(self):
        if not self.result:
            return

        r = self.result
        s = r.stats
        lines = []

        lines.append("=" * 86)
        lines.append("ATRS — ADAPTIVE TARGET-REMAINDER SOLVER RESEARCH REPORT")
        lines.append("=" * 86)
        lines.append(f"Algorithm           : {r.algorithm_name}")
        lines.append(f"Status              : {r.status.value}")
        lines.append(f"Multiset (n={len(self.values)}) : {self.values}")
        lines.append(f"Target Sum (T)      : {self.target:,}")
        lines.append(f"Solutions Found     : {len(r.solutions):,}")
        lines.append(f"Elapsed Time        : {r.elapsed:.6f} s")
        lines.append(f"Peak Memory (RAM)   : {s.memory_peak_bytes / (1024*1024):.2f} MB")
        lines.append("")
        lines.append("COMPUTE TELEMETRY")
        lines.append("-" * 86)
        lines.append(f"Nodes Explored      : {s.nodes:,}")
        lines.append(f"Arithmetic Ops      : {s.arithmetic:,}")
        lines.append(f"Comparisons         : {s.comparisons:,}")
        lines.append(f"Bound Checks        : {s.bound_checks:,}")
        lines.append(f"Branches Pruned     : {s.pruned:,}")
        lines.append(f"Total Work Units    : {s.work_units:,}")
        lines.append(f"Upper Bound Prunes  : {s.upper_prunes:,}")
        lines.append(f"Lower Bound Prunes  : {s.lower_prunes:,}")
        lines.append(f"GCD Divisibility    : {s.gcd_prunes:,}")
        lines.append(f"Cardinality Prunes  : {s.cardinality_prunes:,}")
        lines.append(f"Memoization Hits    : {s.memo_hits:,}")
        lines.append("")
        lines.append("ORACLE BREAKDOWN")
        lines.append("-" * 86)
        for name in ["arithmetic", "bitset", "mitm", "dfs"]:
            lines.append(
                f"{name.capitalize():<12} | Calls: {s.oracle_calls.get(name, 0):<6} | "
                f"Feas: {s.oracle_feasible.get(name, 0):<6} | Infeas: {s.oracle_infeasible.get(name, 0):<6} | "
                f"Time: {s.oracle_time.get(name, 0.0):.6f}s"
            )
        lines.append("")
        lines.append("SOLUTIONS LIST")
        lines.append("=" * 86)
        for i, sol in enumerate(r.solutions, 1):
            lines.append(f"{i:>5}. {' + '.join(map(str, sol))} = {self.target}")

        path = filedialog.asksaveasfilename(
            title="Save ATRS Research Report",
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt")],
            initialfile=f"ATRS_report_T{self.target}_n{len(self.values)}.txt"
        )
        if path:
            Path(path).write_text("\n".join(lines), encoding="utf-8")
            messagebox.showinfo("Success", f"Report successfully saved to:\n{path}")

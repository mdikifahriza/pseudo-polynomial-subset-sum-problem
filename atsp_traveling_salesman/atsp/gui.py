"""
ATSP - Tkinter Desktop Research GUI (Research-Ready v6)
Provides interactive 2D Euclidean city placement, interactive NxN grid matrix editor,
TSPLIB standard format loader, tour visualization, complete solutions viewer,
comparative benchmarks with LaTeX/CSV export, and high-res vector figure exports.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
import math
import random
import threading
import os
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any, Callable

from .state import SearchMode, TSPResult, SolverStatus
from .preprocess import (
    build_adj_matrix,
    parse_coords_input,
    parse_matrix_input,
    parse_edge_list,
    parse_tsplib_content,
    parse_unified_input,
    validate_adj_matrix,
)
from .core import ATSPSolver, NearestNeighborTSPSolver, HeldKarpTSPSolver, BranchBoundTSPSolver, BruteForceTSPSolver
from .benchmark import BenchmarkRunner, generate_instance


# ─────────────────────────────────────────────────────────────────────────────
# Constants & Color Palette
# ─────────────────────────────────────────────────────────────────────────────
COLORS = {
    "bg_primary":    "#f8fafc",
    "bg_panel":      "#ffffff",
    "bg_log":        "#f8fafc",
    "border":        "#cbd5e1",
    "text_heading":  "#0f172a",
    "text_sub":      "#64748b",
    "text_body":     "#1e293b",
    "city_origin":   "#dc2626",
    "city_normal":   "#0284c7",
    "tour_edge":     "#2563eb",
    "cost_green":    "#047857",
    "rank1":         "#047857",
    "rank2":         "#1d4ed8",
    "rank3":         "#b45309",
    "rank_other":    "#475569",
    "btn_primary":   "#2563eb",
    "btn_action":    "#0d9488",
    "btn_danger":    "#dc2626",
    "separator":     "#e2e8f0",
    "grid_diag":     "#e2e8f0",
}

FONT_TITLE    = ("Segoe UI", 12, "bold")
FONT_SUBTITLE = ("Segoe UI", 8, "italic")
FONT_LABEL    = ("Segoe UI", 9)
FONT_LABEL_B  = ("Segoe UI", 9, "bold")
FONT_MONO     = ("Consolas", 9)
FONT_COST     = ("Segoe UI", 11, "bold")


# ─────────────────────────────────────────────────────────────────────────────
# Solutions Window (Solutions & Route Inspector)
# ─────────────────────────────────────────────────────────────────────────────
class SolutionsWindow(tk.Toplevel):
    """
    Popup window showing ALL solutions/routes found by ATSP, ranked from Rank 1 (Optimal) downwards.
    """

    def __init__(
        self,
        parent,
        ranked_tours: List[Tuple[List[int], float]],
        adj: List[List[float]],
        on_select_tour: Optional[Callable[[List[int], float], None]] = None,
    ):
        super().__init__(parent)
        self.title("ATSP Solutions & Route Inspector")
        self.geometry("820x620")
        self.minsize(640, 460)
        self.configure(bg=COLORS["bg_primary"])
        self.grab_set()

        self.ranked_tours = ranked_tours
        self.adj = adj
        self.on_select_tour = on_select_tour
        self.n_cities = len(adj) if adj else (len(ranked_tours[0][0]) - 1 if ranked_tours else 0)

        self._build_ui()

    def _format_segments(self, tour: List[int]) -> str:
        if not self.adj or len(tour) < 2:
            return " — "
        segments = []
        for i in range(len(tour) - 1):
            u, v = tour[i], tour[i + 1]
            if u < len(self.adj) and v < len(self.adj):
                d = self.adj[u][v]
                segments.append(f"{u}→{v} ({d:.1f})")
            else:
                segments.append(f"{u}→{v}")
        return " + ".join(segments)

    def _build_ui(self):
        hdr = tk.Frame(self, bg="#0f766e", padx=16, pady=10)
        hdr.pack(fill=tk.X)

        count = len(self.ranked_tours)
        best_cost = self.ranked_tours[0][1] if self.ranked_tours else 0.0

        tk.Label(
            hdr,
            text=f"📋 Candidate Tours Discovered ({count:,} Solutions)",
            font=("Segoe UI", 11, "bold"),
            bg="#0f766e",
            fg="#ffffff"
        ).pack(anchor="w")

        tk.Label(
            hdr,
            text=f"Total Cities: {self.n_cities} | Optimal Tour Cost (Rank #1): {best_cost:.4f}",
            font=("Segoe UI", 9),
            bg="#0f766e",
            fg="#ccfbf1"
        ).pack(anchor="w", pady=(2, 0))

        tb = tk.Frame(self, bg=COLORS["bg_primary"], padx=12, pady=6)
        tb.pack(fill=tk.X)

        ttk.Button(tb, text="📋 Copy All to Clipboard", command=self._copy_solutions_clipboard).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(tb, text="💾 Save Report (.txt)", command=self._on_export_txt).pack(side=tk.LEFT, padx=4)

        if self.on_select_tour:
            ttk.Button(tb, text="👁 Display on Canvas", command=self._on_preview_selected).pack(side=tk.LEFT, padx=4)

        ttk.Button(tb, text="Close", command=self.destroy).pack(side=tk.RIGHT)

        text_frame = tk.Frame(self, padx=12, pady=6, bg=COLORS["bg_primary"])
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_content = tk.Text(
            text_frame,
            font=("Consolas", 9),
            wrap=tk.WORD,
            bg="#ffffff",
            fg="#0f172a",
            relief=tk.SOLID,
            bd=1
        )
        scroll_y = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.txt_content.yview)
        self.txt_content.configure(yscrollcommand=scroll_y.set)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_content.pack(fill=tk.BOTH, expand=True)

        self._populate_text()

    def _populate_text(self):
        self.txt_content.config(state=tk.NORMAL)
        self.txt_content.delete("1.0", tk.END)

        if not self.ranked_tours:
            self.txt_content.insert(tk.END, "NO TOUR SOLUTIONS DISCOVERED.\n")
            self.txt_content.config(state=tk.DISABLED)
            return

        optimal_cost = self.ranked_tours[0][1]
        lines = [
            f"Total {len(self.ranked_tours):,} candidate tours ranked by path efficiency:",
            "=" * 76,
            "  [Rank #1] represents the proven globally optimal / shortest tour.",
            "=" * 76,
            ""
        ]

        for idx, (tour, cost) in enumerate(self.ranked_tours, 1):
            if idx == 1:
                badge = f"Rank #{idx} (OPTIMAL / SHORTEST)"
                gap_text = ""
            else:
                gap = ((cost - optimal_cost) / max(1e-6, optimal_cost)) * 100.0
                badge = f"Rank #{idx}"
                gap_text = f"  (Gap: +{gap:.2f}%)"

            route_str = " -> ".join(map(str, tour))
            segments_str = self._format_segments(tour)

            lines.append(f"{idx:>4}.  [{badge}]{gap_text}")
            lines.append(f"       Total Cost : {cost:.6f}")
            lines.append(f"       Tour Route : {route_str}")
            lines.append(f"       Edge Steps : {segments_str}")
            lines.append("-" * 76)

        self.txt_content.insert(tk.END, "\n".join(lines))
        self.txt_content.config(state=tk.DISABLED)

    def _copy_solutions_clipboard(self):
        if not self.ranked_tours:
            return
        lines = []
        optimal_cost = self.ranked_tours[0][1]
        for idx, (tour, cost) in enumerate(self.ranked_tours, 1):
            route_str = " -> ".join(map(str, tour))
            gap_str = " (Optimal)" if idx == 1 else f" (+{((cost-optimal_cost)/optimal_cost)*100:.2f}%)"
            lines.append(f"{idx}. Cost={cost:.4f}{gap_str} | Route: {route_str}")
            lines.append(f"   Breakdown: {self._format_segments(tour)}")

        content = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Success", f"{len(self.ranked_tours):,} tour solutions copied to clipboard.")

    def _on_export_txt(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt"), ("All Files", "*.*")],
            initialfile=f"atsp_solutions_n{self.n_cities}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            title="Save All Tour Solutions to Text File"
        )
        if not filepath:
            return
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            optimal_cost = self.ranked_tours[0][1] if self.ranked_tours else 0.0

            lines = [
                "=" * 80,
                "  ATSP — Adaptive Traveling Salesman Problem Solver",
                "  Comprehensive Candidate Tour Solutions & Ranking Report",
                "=" * 80,
                f"  Generated Timestamp : {now}",
                f"  Number of Cities (n): {self.n_cities}",
                f"  Total Solutions     : {len(self.ranked_tours):,}",
                f"  Optimal Cost (#1)   : {optimal_cost:.6f}",
                "=" * 80,
                ""
            ]

            for idx, (tour, cost) in enumerate(self.ranked_tours, 1):
                gap = ((cost - optimal_cost) / max(1e-6, optimal_cost)) * 100.0 if idx > 1 else 0.0
                badge = f"Rank #{idx} (Optimal)" if idx == 1 else f"Rank #{idx} (+{gap:.2f}%)"
                route_str = " -> ".join(map(str, tour))
                lines.append(f"{idx:>4}. [{badge}]")
                lines.append(f"      Total Cost  : {cost:.6f}")
                lines.append(f"      Tour Order  : {route_str}")
                lines.append(f"      Edge Steps  : {self._format_segments(tour)}")
                lines.append("-" * 80)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            messagebox.showinfo("Export Successful", f"Full solution report saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _on_preview_selected(self):
        if self.ranked_tours and self.on_select_tour:
            tour, cost = self.ranked_tours[0]
            self.on_select_tour(tour, cost)
            messagebox.showinfo("Info", "Rank #1 Optimal Tour is now displayed on the main canvas.")


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark Algorithms Ranking Window
# ─────────────────────────────────────────────────────────────────────────────
class BenchmarkRankingWindow(tk.Toplevel):
    """
    Popup window showing comparative benchmark results across all 7 algorithms.
    """

    def __init__(self, parent, records: List[Dict[str, Any]], n_cities: int, instance_desc: str):
        super().__init__(parent)
        self.title("Comparative Benchmark & Algorithm Ranking")
        self.geometry("920x560")
        self.minsize(740, 440)
        self.resizable(True, True)
        self.grab_set()

        self.records = records
        self.ranked = self._compute_ranking(records)
        self.n_cities = n_cities
        self.instance_desc = instance_desc

        self._build_ui()

    def _compute_ranking(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        exact     = [r for r in records if r.get("exact") is True and "SKIPPED" not in r["status"]]
        heuristic = [r for r in records if r.get("exact") is False and "SKIPPED" not in r["status"]]
        skipped   = [r for r in records if "SKIPPED" in r["status"]]

        exact.sort(key=lambda r: r["time_sec"])
        heuristic.sort(key=lambda r: (r["best_cost"] if r["best_cost"] > 0 else float("inf"), r["time_sec"]))
        skipped.sort(key=lambda r: r["algorithm"])

        ranked = []
        rank = 1
        for r in exact + heuristic:
            ranked.append({**r, "rank": rank})
            rank += 1
        for r in skipped:
            ranked.append({**r, "rank": "—"})

        return ranked

    def _build_ui(self):
        header = tk.Frame(self, bg=COLORS["text_heading"], pady=10)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="  Comparative Benchmark & Algorithm Efficiency Ranking",
            font=FONT_TITLE, fg="white", bg=COLORS["text_heading"], anchor="w"
        ).pack(side=tk.LEFT, padx=12)

        tk.Label(
            header,
            text=f"n = {self.n_cities} cities  |  {self.instance_desc}",
            font=FONT_SUBTITLE, fg="#93c5fd", bg=COLORS["text_heading"]
        ).pack(side=tk.RIGHT, padx=12)

        tbl_frame = tk.Frame(self, bg=COLORS["bg_primary"])
        tbl_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        cols = ("rank", "algorithm", "exact", "best_cost", "time_sec", "nodes", "prunes", "status")
        col_labels = {
            "rank":      ("Rank",      65,  tk.CENTER),
            "algorithm": ("Algorithm", 210, tk.W),
            "exact":     ("Exact?",    65,  tk.CENTER),
            "best_cost": ("Best Cost", 95,  tk.E),
            "time_sec":  ("Time (s)",  95,  tk.E),
            "nodes":     ("Nodes",     90,  tk.E),
            "prunes":    ("Pruned",    85,  tk.E),
            "status":    ("Status",    150, tk.W),
        }

        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=16)
        scroll_y = ttk.Scrollbar(tbl_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scroll_x = ttk.Scrollbar(tbl_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        for col, (label, width, anchor) in col_labels.items():
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=anchor, stretch=(col == "algorithm"))

        self.tree.tag_configure("rank1",   foreground=COLORS["rank1"], font=("Segoe UI", 9, "bold"))
        self.tree.tag_configure("rank2",   foreground=COLORS["rank2"], font=("Segoe UI", 9, "bold"))
        self.tree.tag_configure("rank3",   foreground=COLORS["rank3"], font=("Segoe UI", 9, "bold"))
        self.tree.tag_configure("exact",   background="#f0fdf4")
        self.tree.tag_configure("heurist", background="#eff6ff")
        self.tree.tag_configure("skipped", background="#f8fafc", foreground="#94a3b8")

        for r in self.ranked:
            rnk = r["rank"]
            cost = f"{r['best_cost']:.4f}" if r.get("best_cost", 0) > 0 else "—"
            t    = f"{r['time_sec']:.5f}" if r.get("time_sec", 0) > 0 else "—"
            nd   = f"{r.get('nodes', 0):,}"
            pr   = f"{r.get('prunes', 0):,}"
            ex   = "✓" if r.get("exact") is True else ("✗" if r.get("exact") is False else "—")
            st   = r["status"][:30]

            if rnk == "—":
                tag = "skipped"
            elif r.get("exact") is True:
                tag = "exact"
            else:
                tag = "heurist"

            rank_badge = f"  #{rnk}" if rnk != "—" else "  —"
            self.tree.insert("", tk.END, values=(rank_badge, r["algorithm"], ex, cost, t, nd, pr, st), tags=(tag,))

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        btn_frame = tk.Frame(self, bg=COLORS["bg_primary"], pady=6)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        ttk.Button(btn_frame, text="📊 Export CSV", command=self._on_export_csv).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="📄 Export LaTeX Table", command=self._on_export_latex).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="💾 Export TXT Report", command=self._on_export_txt).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side=tk.RIGHT, padx=4)

    def _build_txt_report(self) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "=" * 80,
            "  ATSP — Adaptive Traveling Salesman Problem Solver",
            "  Comparative Benchmark Performance & Ranking Report",
            "=" * 80,
            f"  Timestamp         : {now}",
            f"  Number of Cities  : {self.n_cities}",
            f"  Instance Scenario : {self.instance_desc}",
            "=" * 80,
            "",
            f"{'Rank':<8} {'Algorithm':<28} {'Exact':<7} {'Best Cost':<12} {'Time (s)':<12} {'Nodes':<10} {'Pruned':<10} Status",
            "-" * 110,
        ]

        for r in self.ranked:
            rnk  = f"#{r['rank']}" if r["rank"] != "—" else "—"
            cost = f"{r['best_cost']:.4f}" if r.get("best_cost", 0) > 0 else "N/A"
            t    = f"{r['time_sec']:.6f}" if r.get("time_sec", 0) > 0 else "0.000000"
            nd   = f"{r.get('nodes', 0):,}"
            pr   = f"{r.get('prunes', 0):,}"
            ex   = "Yes" if r.get("exact") is True else ("No" if r.get("exact") is False else "—")
            lines.append(
                f"{rnk:<8} {r['algorithm']:<28} {ex:<7} {cost:<12} {t:<12} {nd:<10} {pr:<10} {r['status']}"
            )

        lines += [
            "-" * 110,
            "=" * 80,
        ]
        return "\n".join(lines)

    def _on_export_txt(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt"), ("All Files", "*.*")],
            initialfile=f"atsp_benchmark_ranking_n{self.n_cities}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            title="Save Benchmark Report to Text File"
        )
        if not filepath:
            return
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self._build_txt_report())
            messagebox.showinfo("Export Successful", f"Report saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _on_export_csv(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV File", "*.csv"), ("All Files", "*.*")],
            initialfile=f"atsp_benchmark_n{self.n_cities}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            title="Save Benchmark Records to CSV"
        )
        if not filepath:
            return
        try:
            BenchmarkRunner.export_csv(self.ranked, filepath)
            messagebox.showinfo("Export Successful", f"CSV saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _on_export_latex(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".tex",
            filetypes=[("LaTeX Table", "*.tex"), ("All Files", "*.*")],
            initialfile=f"table_tsp_benchmark_n{self.n_cities}.tex",
            title="Save Benchmark Records to LaTeX Table"
        )
        if not filepath:
            return
        try:
            tex = BenchmarkRunner.export_latex(
                self.ranked,
                caption=f"Comparative Benchmark on TSP ($n={self.n_cities}$)",
                label=f"tab:tsp_bench_n{self.n_cities}"
            )
            Path(filepath).write_text(tex, encoding="utf-8")
            messagebox.showinfo("Export Successful", f"LaTeX table saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Main Application Window
# ─────────────────────────────────────────────────────────────────────────────
class ATSPApplication:
    """
    Main GUI Application for ATSP — Adaptive Traveling Salesman Problem Solver.
    """

    PANEL_LEFT_WIDTH = 450

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ATSP — Adaptive Traveling Salesman Problem Solver")
        self.root.geometry("1200x760")
        self.root.minsize(1000, 640)
        self.root.configure(bg=COLORS["bg_primary"])

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Header.TFrame", background=COLORS["text_heading"])
        style.configure("TLabelframe", background=COLORS["bg_panel"])
        style.configure("TLabelframe.Label", background=COLORS["bg_panel"], font=FONT_LABEL_B)

        self.coords: List[Tuple[float, float]] = []
        self.custom_adj: Optional[List[List[float]]] = None
        self.best_tour: List[int] = []
        self.best_cost: float = float("inf")
        self.last_ranked_tours: List[Tuple[List[int], float]] = []
        self._last_benchmark_records: List[Dict[str, Any]] = []
        self._last_benchmark_n: int = 0
        self._last_benchmark_desc: str = ""
        self._solving: bool = False
        self.sol_window: Optional[SolutionsWindow] = None

        # Grid state variables
        self.grid_entries: List[List[tk.Entry]] = []
        self.grid_n: int = 5
        self._updating_symmetry: bool = False

        self._build_layout()
        self._load_default_instance()

    def _build_layout(self):
        self._build_header()

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        left = ttk.Frame(paned, width=self.PANEL_LEFT_WIDTH)
        paned.add(left, weight=0)
        self._build_left_panel(left)

        right = ttk.Frame(paned)
        paned.add(right, weight=1)
        self._build_right_panel(right)

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=COLORS["text_heading"], pady=8)
        hdr.pack(fill=tk.X)

        tk.Label(
            hdr,
            text="  ATSP  —  Adaptive Traveling Salesman Problem Solver",
            font=FONT_TITLE, fg="white", bg=COLORS["text_heading"], anchor="w"
        ).pack(side=tk.LEFT)

        tk.Label(
            hdr,
            text="Exact Multi-Oracle Solver • TSPLIB Support • Warm-Start • LaTeX Exporter  ",
            font=FONT_SUBTITLE, fg="#93c5fd", bg=COLORS["text_heading"]
        ).pack(side=tk.RIGHT)

    def _build_left_panel(self, parent):
        parent.pack_propagate(False)

        # ── 1. Tabbed Input Section ──
        sec1 = ttk.LabelFrame(parent, text=" 1. Input Specification & Instance Loader ", padding="6")
        sec1.pack(fill=tk.X, padx=6, pady=(6, 3))

        self.notebook = ttk.Notebook(sec1)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab A: Generator & Canvas
        tab_gen = ttk.Frame(self.notebook, padding="6")
        self.notebook.add(tab_gen, text="🎲 Generator")
        self._build_tab_generator(tab_gen)

        # Tab B: Interactive Grid Matrix NxN
        tab_grid = ttk.Frame(self.notebook, padding="6")
        self.notebook.add(tab_grid, text="📊 Matrix Grid")
        self._build_tab_grid(tab_grid)

        # Tab C: Free Text & TSPLIB Loader
        tab_text = ttk.Frame(self.notebook, padding="6")
        self.notebook.add(tab_text, text="📝 TSPLIB & Files")
        self._build_tab_text(tab_text)

        # ── 2. Solver Execution Section ──
        sec2 = ttk.LabelFrame(parent, text=" 2. Solver Execution & Route Inspector ", padding="8")
        sec2.pack(fill=tk.X, padx=6, pady=3)

        row2a = ttk.Frame(sec2)
        row2a.pack(fill=tk.X, pady=(0, 3))

        self.btn_solve = ttk.Button(row2a, text="▶ Solve (Exact ATSP)", command=self._on_solve, width=18)
        self.btn_solve.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.btn_solutions = ttk.Button(
            row2a, text="📋 Solutions (0)",
            command=self._open_solutions_window, state=tk.DISABLED, width=18
        )
        self.btn_solutions.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        row2b = ttk.Frame(sec2)
        row2b.pack(fill=tk.X)

        self.btn_bench = ttk.Button(row2b, text="🔬 Benchmark All", command=self._on_benchmark, width=18)
        self.btn_bench.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        ttk.Button(row2b, text="Clear", command=self._on_clear, width=10).pack(side=tk.RIGHT, padx=2)

        self.lbl_status = ttk.Label(sec2, text="Ready.", font=("Segoe UI", 8, "italic"), foreground=COLORS["text_sub"])
        self.lbl_status.pack(anchor="w", pady=(4, 0))

        # ── 3. Log Output Section ──
        sec3 = ttk.LabelFrame(parent, text=" 3. Execution Log & Telemetry ", padding="8")
        sec3.pack(fill=tk.BOTH, expand=True, padx=6, pady=(3, 3))

        self.txt_log = tk.Text(
            sec3, font=FONT_MONO, wrap=tk.WORD, height=10,
            bg=COLORS["bg_log"], relief=tk.FLAT,
            borderwidth=1, highlightthickness=1,
            highlightbackground=COLORS["border"]
        )
        scroll_log = ttk.Scrollbar(sec3, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll_log.set)
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_log.pack(side=tk.RIGHT, fill=tk.Y)

        sec4 = ttk.Frame(parent)
        sec4.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Button(sec4, text="💾 Save Log (.txt)", command=self._on_export_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(sec4, text="Clear Log", command=lambda: self.txt_log.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=2)

    # ──────────────────────────────────────────────
    # Tab 1: Generator
    # ──────────────────────────────────────────────
    def _build_tab_generator(self, parent):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=2)

        ttk.Label(row, text="Cities (n):").pack(side=tk.LEFT)
        self.n_var = tk.IntVar(value=12)
        ttk.Spinbox(row, from_=3, to=50, width=5, textvariable=self.n_var).pack(side=tk.LEFT, padx=5)

        ttk.Label(row, text="Pattern:").pack(side=tk.LEFT, padx=(6, 2))
        self.pattern_var = tk.StringVar(value="Random")
        ttk.Combobox(
            row, textvariable=self.pattern_var,
            values=["Random", "Clustered", "Circle", "Grid"],
            width=9, state="readonly"
        ).pack(side=tk.LEFT, padx=3)

        ttk.Button(row, text="🎲 Generate", command=self._on_generate).pack(side=tk.RIGHT, padx=2)

        hint = ttk.Label(parent, text="Tip: Left-click anywhere on the canvas to place custom 2D Euclidean city points.",
                         font=("Segoe UI", 8), foreground=COLORS["text_sub"], wraplength=400)
        hint.pack(anchor="w", pady=(4, 0))

    # ──────────────────────────────────────────────
    # Tab 2: Interactive Grid Matrix (NxN)
    # ──────────────────────────────────────────────
    def _build_tab_grid(self, parent):
        top_row = ttk.Frame(parent)
        top_row.pack(fill=tk.X, pady=2)

        ttk.Label(top_row, text="Matrix Dim (n):").pack(side=tk.LEFT)
        self.grid_n_var = tk.IntVar(value=5)
        ttk.Spinbox(top_row, from_=3, to=12, width=4, textvariable=self.grid_n_var).pack(side=tk.LEFT, padx=4)

        ttk.Button(top_row, text="Set Dim", command=self._on_rebuild_grid).pack(side=tk.LEFT, padx=4)

        self.symmetry_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top_row, text="Auto Symmetry", variable=self.symmetry_var).pack(side=tk.RIGHT, padx=2)

        self.grid_canvas_frame = tk.Frame(parent, bg=COLORS["bg_panel"], bd=1, relief=tk.SOLID)
        self.grid_canvas_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        self.grid_canvas = tk.Canvas(self.grid_canvas_frame, bg=COLORS["bg_panel"], height=130, highlightthickness=0)
        self.grid_scroll_y = ttk.Scrollbar(self.grid_canvas_frame, orient=tk.VERTICAL, command=self.grid_canvas.yview)
        self.grid_scroll_x = ttk.Scrollbar(self.grid_canvas_frame, orient=tk.HORIZONTAL, command=self.grid_canvas.xview)
        self.grid_inner = tk.Frame(self.grid_canvas, bg=COLORS["bg_panel"])

        self.grid_inner.bind("<Configure>", lambda e: self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all")))
        self.grid_window_id = self.grid_canvas.create_window((0, 0), window=self.grid_inner, anchor="nw")
        self.grid_canvas.configure(xscrollcommand=self.grid_scroll_x.set, yscrollcommand=self.grid_scroll_y.set)

        self.grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.grid_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.grid_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        btn_grid_row = ttk.Frame(parent)
        btn_grid_row.pack(fill=tk.X, pady=(2, 0))

        ttk.Button(btn_grid_row, text="Apply Matrix", command=self._on_apply_grid).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_grid_row, text="Randomize", command=self._on_randomize_grid).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_grid_row, text="Reset to 0", command=self._on_reset_grid).pack(side=tk.LEFT, padx=2)

        self._on_rebuild_grid()

    def _on_rebuild_grid(self):
        for widget in self.grid_inner.winfo_children():
            widget.destroy()

        n = min(12, max(3, self.grid_n_var.get()))
        self.grid_n = n
        self.grid_entries = []

        tk.Label(self.grid_inner, text="C\\C", font=FONT_LABEL_B, bg="#e2e8f0", width=4).grid(row=0, column=0, padx=1, pady=1)
        for j in range(n):
            tk.Label(self.grid_inner, text=f"C{j}", font=FONT_LABEL_B, bg="#e2e8f0", width=6).grid(row=0, column=j + 1, padx=1, pady=1)

        for i in range(n):
            row_entries = []
            tk.Label(self.grid_inner, text=f"C{i}", font=FONT_LABEL_B, bg="#e2e8f0", width=4).grid(row=i + 1, column=0, padx=1, pady=1)
            for j in range(n):
                ent = tk.Entry(self.grid_inner, width=6, justify="center", font=FONT_MONO)
                ent.grid(row=i + 1, column=j + 1, padx=1, pady=1)

                if i == j:
                    ent.insert(0, "0.0")
                    ent.config(state="disabled", disabledbackground=COLORS["grid_diag"])
                else:
                    ent.insert(0, "10.0")
                    ent.bind("<KeyRelease>", lambda event, r=i, c=j: self._on_grid_cell_edit(r, c))

                row_entries.append(ent)
            self.grid_entries.append(row_entries)

    def _on_grid_cell_edit(self, r: int, c: int):
        if not self.symmetry_var.get() or self._updating_symmetry:
            return
        val = self.grid_entries[r][c].get().strip()
        if r != c:
            self._updating_symmetry = True
            try:
                self.grid_entries[c][r].delete(0, tk.END)
                self.grid_entries[c][r].insert(0, val)
            except Exception:
                pass
            self._updating_symmetry = False

    def _on_randomize_grid(self):
        n = self.grid_n
        is_sym = self.symmetry_var.get()
        for i in range(n):
            for j in range(i + 1, n):
                d = round(random.uniform(5.0, 50.0), 1)
                self.grid_entries[i][j].delete(0, tk.END)
                self.grid_entries[i][j].insert(0, str(d))
                if is_sym:
                    self.grid_entries[j][i].delete(0, tk.END)
                    self.grid_entries[j][i].insert(0, str(d))
                else:
                    d_back = round(random.uniform(5.0, 50.0), 1)
                    self.grid_entries[j][i].delete(0, tk.END)
                    self.grid_entries[j][i].insert(0, str(d_back))

    def _on_reset_grid(self):
        n = self.grid_n
        for i in range(n):
            for j in range(n):
                if i != j:
                    self.grid_entries[i][j].delete(0, tk.END)
                    self.grid_entries[i][j].insert(0, "0.0")

    def _on_apply_grid(self):
        n = self.grid_n
        matrix = [[0.0] * n for _ in range(n)]
        try:
            for i in range(n):
                for j in range(n):
                    if i == j:
                        matrix[i][j] = 0.0
                    else:
                        val_str = self.grid_entries[i][j].get().strip()
                        matrix[i][j] = float(val_str)
        except ValueError:
            messagebox.showerror("Format Error", "Ensure all matrix entries contain valid numeric values.")
            return

        is_ok, err, warnings = validate_adj_matrix(matrix)
        if not is_ok:
            messagebox.showerror("Invalid Matrix", err)
            return

        self._apply_custom_matrix(matrix, desc=f"Grid Input ({n}x{n})")
        for w in warnings:
            self._log(f"Warning: {w}")

    # ──────────────────────────────────────────────
    # Tab 3: Free Text & TSPLIB Loader
    # ──────────────────────────────────────────────
    def _build_tab_text(self, parent):
        self.txt_input = tk.Text(parent, font=FONT_MONO, height=6, wrap=tk.NONE)
        scroll_txt_y = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.txt_input.yview)
        scroll_txt_x = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.txt_input.xview)
        self.txt_input.configure(yscrollcommand=scroll_txt_y.set, xscrollcommand=scroll_txt_x.set)

        self.txt_input.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(2, 0))
        scroll_txt_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_txt_x.pack(side=tk.BOTTOM, fill=tk.X)

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, pady=(4, 0))

        ttk.Button(btn_row, text="Apply Text", command=self._on_apply_text).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="📂 Load File (.tsp / .txt)", command=self._on_load_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="💾 Save Matrix", command=self._on_save_matrix_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="📋 Sample", command=self._on_load_sample_template).pack(side=tk.RIGHT, padx=2)

    def _on_load_sample_template(self):
        sample = (
            "# Sample Distance Matrix Format (5 cities)\n"
            "TYPE: MATRIX\n"
            "0    12   29   22   13\n"
            "12    0   19   24   20\n"
            "29   19    0   15   18\n"
            "22   24   15    0   10\n"
            "13   20   18   10    0\n"
        )
        self.txt_input.delete("1.0", tk.END)
        self.txt_input.insert("1.0", sample)

    def _on_apply_text(self):
        raw = self.txt_input.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning("Empty", "Please paste or type coordinates, TSPLIB data, or matrix rows first.")
            return
        try:
            adj, coords = parse_unified_input(raw)
            if coords:
                self.coords = coords
                self.custom_adj = None
                self._log(f"Successfully applied coordinate data ({len(coords)} cities).")
            else:
                self._apply_custom_matrix(adj, desc=f"Parsed Matrix ({len(adj)}x{len(adj)})")
            self._redraw_canvas()
        except Exception as e:
            messagebox.showerror("Parse Error", str(e))

    def _on_load_file(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("TSPLIB & Matrix Files", "*.tsp *.txt *.csv"), ("All Files", "*.*")],
            title="Open TSPLIB / Matrix / Coordinates File"
        )
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.txt_input.delete("1.0", tk.END)
            self.txt_input.insert("1.0", content)
            self._on_apply_text()
            self._log(f"File loaded from: {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("File Read Error", str(e))

    def _on_save_matrix_file(self):
        adj = self.custom_adj
        if adj is None and self.coords:
            adj = build_adj_matrix(self.coords)
        if not adj:
            messagebox.showwarning("Empty", "No active distance matrix to save.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt"), ("CSV File", "*.csv"), ("All Files", "*.*")],
            initialfile=f"matrix_n{len(adj)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            title="Save Distance Matrix"
        )
        if not filepath:
            return
        try:
            lines = [f"# ATSP Distance Matrix (n={len(adj)})", "TYPE: MATRIX"]
            for row in adj:
                lines.append("  ".join(f"{v:.2f}" for v in row))
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            messagebox.showinfo("Success", f"Matrix saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _apply_custom_matrix(self, matrix: List[List[float]], desc: str):
        n = len(matrix)
        self.custom_adj = matrix
        self.best_tour = []
        self.best_cost = float("inf")
        self.last_ranked_tours = []
        self._last_benchmark_records = []
        self.btn_solutions.config(state=tk.DISABLED, text="📋 Solutions (0)")

        self.root.update_idletasks()
        cw = max(400, self.canvas.winfo_width()) - 80
        ch = max(300, self.canvas.winfo_height()) - 80
        radius = min(cw, ch) * 0.42
        cx, cy = (cw + 80) / 2, (ch + 80) / 2

        self.coords = [
            (
                cx + radius * math.cos(2 * math.pi * i / n - math.pi / 2),
                cy + radius * math.sin(2 * math.pi * i / n - math.pi / 2)
            )
            for i in range(n)
        ]
        self._update_cost_label()
        self._redraw_canvas()
        self._log(f"Custom matrix applied: {desc} — n = {n} cities (Circular Layout).")

    # ──────────────────────────────────────────────
    # Right Panel & Canvas
    # ──────────────────────────────────────────────
    def _build_right_panel(self, parent):
        bar = tk.Frame(parent, bg=COLORS["bg_panel"], pady=4)
        bar.pack(fill=tk.X, padx=4, pady=(4, 0))

        tk.Label(bar, text="Graph & Optimal Tour Visualization", font=FONT_LABEL_B,
                 fg=COLORS["text_heading"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT, padx=6)

        self.lbl_cost = tk.Label(
            bar, text="Best Tour Cost: —",
            font=FONT_COST, fg=COLORS["cost_green"], bg=COLORS["bg_panel"]
        )
        self.lbl_cost.pack(side=tk.RIGHT, padx=8)

        self.lbl_n = tk.Label(
            bar, text="n = 0",
            font=FONT_LABEL, fg=COLORS["text_sub"], bg=COLORS["bg_panel"]
        )
        self.lbl_n.pack(side=tk.RIGHT, padx=4)

        canvas_frame = tk.Frame(parent, bg=COLORS["border"], bd=1, relief=tk.FLAT)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.canvas = tk.Canvas(
            canvas_frame, bg=COLORS["bg_panel"],
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        status_bar = tk.Frame(parent, bg=COLORS["separator"], pady=2)
        status_bar.pack(fill=tk.X, padx=4, pady=(0, 4))

        self.lbl_canvas_hint = tk.Label(
            status_bar,
            text="  Red node = Origin (0). Blue arrows = Optimal Tour. Click canvas to add Euclidean cities.",
            font=("Segoe UI", 8), fg=COLORS["text_sub"], bg=COLORS["separator"], anchor="w"
        )
        self.lbl_canvas_hint.pack(side=tk.LEFT)

    # ──────────────────────────────────────────────
    # Event Handlers & Execution
    # ──────────────────────────────────────────────
    def _on_canvas_click(self, event):
        if self._solving:
            return
        x, y = float(event.x), float(event.y)
        self.custom_adj = None
        self.coords.append((x, y))
        self.best_tour = []
        self.best_cost = float("inf")
        self.last_ranked_tours = []
        self.btn_solutions.config(state=tk.DISABLED, text="📋 Solutions (0)")
        self._update_cost_label()
        self._redraw_canvas()
        self._log(f"+ City {len(self.coords)-1} placed at ({x:.0f}, {y:.0f})  |  Total: {len(self.coords)} cities")

    def _load_default_instance(self):
        self._on_generate()

    def _on_generate(self):
        n = self.n_var.get()
        pattern = self.pattern_var.get()
        self.custom_adj = None
        self.root.update_idletasks()

        cw = max(400, self.canvas.winfo_width()) - 60
        ch = max(300, self.canvas.winfo_height()) - 60

        coords, _ = generate_instance(n=n, instance_type=pattern, coord_range=min(cw, ch))
        self.coords = [(x + 30, y + 30) for x, y in coords]
        self.best_tour = []
        self.best_cost = float("inf")
        self.last_ranked_tours = []
        self._last_benchmark_records = []
        self.btn_solutions.config(state=tk.DISABLED, text="📋 Solutions (0)")
        self._update_cost_label()
        self._redraw_canvas()
        self._log(f"Generated {n} cities with '{pattern}' distribution.")

    def _on_clear(self):
        if self._solving:
            messagebox.showinfo("Solver Busy", "Please wait for current solver execution to complete.")
            return
        self.coords = []
        self.custom_adj = None
        self.best_tour = []
        self.best_cost = float("inf")
        self.last_ranked_tours = []
        self._last_benchmark_records = []
        self.btn_solutions.config(state=tk.DISABLED, text="📋 Solutions (0)")
        self._update_cost_label()
        self.canvas.delete("all")
        self._log("Canvas cleared.")

    def _get_active_adj_matrix(self) -> Tuple[List[List[float]], int]:
        if self.custom_adj is not None:
            return self.custom_adj, len(self.custom_adj)
        if len(self.coords) >= 3:
            return build_adj_matrix(self.coords), len(self.coords)
        return [], 0

    def _on_solve(self):
        adj, n = self._get_active_adj_matrix()
        if n < 3:
            messagebox.showwarning("Insufficient Data", "At least 3 cities required to solve TSP.")
            return
        if self._solving:
            return

        self._solving = True
        self._set_buttons_state(tk.DISABLED)
        self.lbl_status.config(text="Computing optimal Hamiltonian cycle... ⏳", foreground="#b45309")
        self._log("\n" + "─" * 56)
        mode_desc = "Custom Matrix" if self.custom_adj is not None else "2D Euclidean Coordinates"
        self._log(f"Running ATSP Solver — n = {n} cities ({mode_desc})")

        def task():
            solver = ATSPSolver()
            res: TSPResult = solver.solve(adj)
            self.root.after(0, lambda: self._finish_solve(res))

        threading.Thread(target=task, daemon=True).start()

    def _finish_solve(self, res: TSPResult):
        self._solving = False
        self._set_buttons_state(tk.NORMAL)
        self.lbl_status.config(text="Finished.", foreground=COLORS["text_sub"])

        if res.has_solution:
            self.best_tour = res.tours[0]
            self.best_cost = res.best_cost
            self.last_ranked_tours = res.ranked_tours if res.ranked_tours else [(res.tours[0], res.best_cost)]

            self.btn_solutions.config(
                state=tk.NORMAL,
                text=f"📋 Solutions ({len(self.last_ranked_tours):,})"
            )

            self._update_cost_label()
            self._redraw_canvas()
            tour_str = " -> ".join(map(str, self.best_tour))
            self._log(f"Status              : {res.status.value}")
            self._log(f"Optimal Cost (Rank 1): {self.best_cost:.6f}")
            self._log(f"Optimal Tour Route  : {tour_str}")
            self._log(f"Elapsed Time        : {res.elapsed:.5f} s")
            self._log(f"Nodes Explored      : {res.stats.nodes:,}")
            self._log(f"Branches Pruned     : {res.stats.pruned:,}")
            self._log(f"MST Bounds Computed : {res.stats.mst_computations:,}")
            self._log(f"Held-Karp Calls     : {res.stats.held_karp_calls:,}")
            self._log(f"-> Click '📋 Solutions ({len(self.last_ranked_tours):,})' to inspect full candidate rankings.")
        else:
            self._log(f"Status: {res.status.value}")

    def _select_tour_from_ranking(self, tour: List[int], cost: float):
        self.best_tour = list(tour)
        self.best_cost = cost
        self._update_cost_label()
        self._redraw_canvas()
        self._log(f"Canvas preview updated to tour with cost: {cost:.4f}")

    def _open_solutions_window(self):
        if not self.last_ranked_tours:
            messagebox.showinfo("No Solutions", "Please execute 'Solve (Exact ATSP)' first.")
            return

        if self.sol_window and self.sol_window.winfo_exists():
            self.sol_window.lift()
            self.sol_window.focus_force()
            return

        adj, _ = self._get_active_adj_matrix()
        self.sol_window = SolutionsWindow(
            self.root,
            self.last_ranked_tours,
            adj,
            on_select_tour=self._select_tour_from_ranking
        )

    def _on_benchmark(self):
        adj, n = self._get_active_adj_matrix()
        if n < 3:
            messagebox.showwarning("Insufficient Data", "At least 3 cities required.")
            return
        if self._solving:
            return

        self._solving = True
        self._set_buttons_state(tk.DISABLED)
        self.lbl_status.config(text="Running benchmark suite across all solvers... ⏳", foreground="#b45309")
        self._log("\n" + "─" * 56)
        mode_desc = "Custom Matrix" if self.custom_adj is not None else "2D Euclidean Coordinates"
        self._log(f"Comparative Benchmark — n = {n} cities ({mode_desc})")

        def task():
            runner = BenchmarkRunner(timeout_per_algo=10.0)
            records = runner.run_benchmark(adj)
            self.root.after(0, lambda: self._finish_benchmark(records, n))

        threading.Thread(target=task, daemon=True).start()

    def _finish_benchmark(self, records: List[Dict[str, Any]], n: int):
        self._solving = False
        self._set_buttons_state(tk.NORMAL)
        self.lbl_status.config(text="Benchmark completed.", foreground=COLORS["rank1"])

        self._last_benchmark_records = records
        self._last_benchmark_n = n
        self._last_benchmark_desc = "Custom Matrix" if self.custom_adj is not None else f"{self.pattern_var.get()} distribution"

        self._log(f"{'Algorithm':<28} | {'Exact':<6} | {'Cost':<10} | {'Time (s)'}")
        self._log("─" * 65)
        for r in records:
            cost = f"{r['best_cost']:.2f}" if r.get("best_cost", 0) > 0 else "—"
            ex = "Yes" if r.get("exact") is True else "No"
            self._log(f"{r['algorithm']:<28} | {ex:<6} | {cost:<10} | {r['time_sec']:.5f}")
        self._log("─" * 65)

        win = BenchmarkRankingWindow(
            self.root,
            self._last_benchmark_records,
            self._last_benchmark_n,
            self._last_benchmark_desc
        )
        win.wait_window()

    def _on_export_log(self):
        content = self.txt_log.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Empty Log", "No log output available to export.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt"), ("All Files", "*.*")],
            initialfile=f"atsp_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            title="Save ATSP Execution Log"
        )
        if not filepath:
            return
        try:
            header = [
                "=" * 80,
                "  ATSP — Adaptive Traveling Salesman Problem Solver",
                f"  Execution Log Output — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 80, ""
            ]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(header) + "\n" + content)
            messagebox.showinfo("Success", f"Log saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ──────────────────────────────────────────────
    # Canvas Drawing
    # ──────────────────────────────────────────────
    def _redraw_canvas(self):
        self.canvas.delete("all")
        n = len(self.coords)
        self.lbl_n.config(text=f"n = {n}")

        if n == 0:
            return

        # Draw tour edges
        if self.best_tour and len(self.best_tour) > 1:
            for i in range(len(self.best_tour) - 1):
                u, v = self.best_tour[i], self.best_tour[i + 1]
                if u < n and v < n:
                    x1, y1 = self.coords[u]
                    x2, y2 = self.coords[v]
                    self.canvas.create_line(
                        x1, y1, x2, y2,
                        fill=COLORS["tour_edge"], width=2.5,
                        arrow=tk.LAST, arrowshape=(9, 11, 4)
                    )

        # Draw cities
        for idx, (x, y) in enumerate(self.coords):
            is_origin = (idx == 0)
            color = COLORS["city_origin"] if is_origin else COLORS["city_normal"]
            r = 8 if is_origin else 5
            self.canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill=color, outline=COLORS["text_body"], width=1.5
            )
            lbl_x = x + 11
            lbl_y = y - 9
            self.canvas.create_text(
                lbl_x, lbl_y,
                text=str(idx),
                font=("Segoe UI", 8, "bold"),
                fill=COLORS["text_body"]
            )

    def _update_cost_label(self):
        if self.best_cost < float("inf"):
            self.lbl_cost.config(
                text=f"Best Tour Cost: {self.best_cost:.4f}",
                fg=COLORS["cost_green"]
            )
        else:
            self.lbl_cost.config(text="Best Tour Cost: —", fg=COLORS["text_sub"])

    def _log(self, msg: str):
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)

    def _set_buttons_state(self, state):
        self.btn_solve.config(state=state)
        self.btn_bench.config(state=state)
        if state == tk.NORMAL and self.last_ranked_tours:
            self.btn_solutions.config(state=tk.NORMAL)
        elif state == tk.DISABLED:
            self.btn_solutions.config(state=tk.DISABLED)

    def run(self):
        self.root.mainloop()

import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

@dataclass
class Stats:
    nodes: int = 0
    arithmetic: int = 0
    comparisons: int = 0
    bound_checks: int = 0
    pruned: int = 0
    solutions: int = 0
    memo_hits: int = 0
    gcd_prunes: int = 0
    modulo_prunes: int = 0
    lower_prunes: int = 0
    upper_prunes: int = 0
    cardinality_prunes: int = 0

    @property
    def work_units(self):
        return (
            self.nodes
            + self.arithmetic
            + self.comparisons
            + self.bound_checks
            + self.pruned
        )

def parse_input(raw):

    raw = raw.strip()

    if not raw:
        raise ValueError("Input tidak boleh kosong.")

    parts = [x.strip() for x in raw.split(",")]

    if any(x == "" for x in parts):
        raise ValueError("Format input tidak valid.")

    values = []

    for x in parts:

        if not x.isdigit():
            raise ValueError(
                f"'{x}' bukan bilangan bulat positif."
            )

        value = int(x)

        if value <= 0:
            raise ValueError(
                "Semua angka harus positif."
            )

        values.append(value)

    if len(values) != len(set(values)):
        raise ValueError(
            "Himpunan tidak boleh memiliki duplikat."
        )

    return sorted(values)

def brute_force(values, target):

    stats = Stats()
    solutions = []

    n = len(values)

    def dfs(i, current_sum, chosen):

        stats.nodes += 1

        if i == n:

            stats.comparisons += 1

            if current_sum == target and chosen:

                stats.solutions += 1
                solutions.append(tuple(chosen))

            return

        dfs(
            i + 1,
            current_sum,
            chosen
        )

        stats.arithmetic += 1

        chosen.append(values[i])

        dfs(
            i + 1,
            current_sum + values[i],
            chosen
        )

        chosen.pop()

    dfs(0, 0, [])

    return stats, solutions

def build_suffix_gcd(values):

    n = len(values)

    gcd_suffix = [0] * (n + 1)

    for i in range(n - 1, -1, -1):

        import math

        gcd_suffix[i] = math.gcd(
            values[i],
            gcd_suffix[i + 1]
        )

    return gcd_suffix

def advanced_subset_sum(values, target):

    stats = Stats()

    values = sorted(values)

    n = len(values)

    solutions = []

    suffix_sum = [0] * (n + 1)

    for i in range(n - 1, -1, -1):

        suffix_sum[i] = (
            suffix_sum[i + 1]
            + values[i]
        )

        stats.arithmetic += 1

    gcd_suffix = build_suffix_gcd(values)

    import math

    global_gcd = 0

    for x in values:
        global_gcd = math.gcd(global_gcd, x)

    if global_gcd != 0:

        if target % global_gcd != 0:

            return stats, []

    @lru_cache(maxsize=None)
    def feasible(i, r):

        if r == 0:
            return True

        if r < 0:
            return False

        if i >= n:
            return False

        if suffix_sum[i] < r:
            return False

        g = gcd_suffix[i]

        if g != 0 and r % g != 0:
            return False

        for j in range(i, n):

            a = values[j]

            if a > r:
                break

            if feasible(j + 1, r - a):
                return True

        return False

    def minimum_cardinality(start, remainder):

        total = 0
        count = 0

        for j in range(n - 1, start - 1, -1):

            total += values[j]
            count += 1

            if total >= remainder:
                return count

        return float("inf")

    def maximum_cardinality(start):

        return n - start

    def dfs(start, remainder, chosen):

        stats.nodes += 1

        stats.comparisons += 1

        if remainder == 0:

            if chosen:

                stats.solutions += 1

                solutions.append(
                    tuple(chosen)
                )

            return

        stats.comparisons += 1

        if remainder < 0:

            stats.pruned += 1

            return

        stats.comparisons += 1

        if start >= n:

            stats.pruned += 1

            return

        stats.bound_checks += 1
        stats.comparisons += 1

        if suffix_sum[start] < remainder:

            stats.pruned += 1
            stats.upper_prunes += 1

            return

        g = gcd_suffix[start]

        if g != 0:

            stats.bound_checks += 1
            stats.comparisons += 1

            if remainder % g != 0:

                stats.pruned += 1
                stats.gcd_prunes += 1

                return

        min_count = minimum_cardinality(
            start,
            remainder
        )

        max_count = maximum_cardinality(start)

        current_count = len(chosen)

        additional_min = min_count

        additional_max = max_count

        stats.bound_checks += 1

        if additional_min > additional_max:

            stats.pruned += 1
            stats.cardinality_prunes += 1

            return

        for j in range(start, n):

            value = values[j]

            stats.comparisons += 1

            if value > remainder:

                stats.pruned += n - j

                break

            new_remainder = remainder - value

            stats.arithmetic += 1

            next_i = j + 1

            if new_remainder == 0:

                chosen.append(value)

                stats.solutions += 1

                solutions.append(
                    tuple(chosen)
                )

                chosen.pop()

                continue

            if next_i >= n:

                stats.pruned += 1

                continue

            stats.bound_checks += 1

            if suffix_sum[next_i] < new_remainder:

                stats.pruned += 1
                stats.upper_prunes += 1

                continue

            g2 = gcd_suffix[next_i]

            stats.comparisons += 1

            if (
                g2 != 0
                and new_remainder % g2 != 0
            ):

                stats.pruned += 1
                stats.gcd_prunes += 1

                continue

            possible = feasible(
                next_i,
                new_remainder
            )

            if not possible:

                stats.memo_hits += 1
                stats.pruned += 1

                continue

            remaining_min = minimum_cardinality(
                next_i,
                new_remainder
            )

            available = n - next_i

            stats.bound_checks += 1

            if remaining_min > available:

                stats.pruned += 1
                stats.lower_prunes += 1
                stats.cardinality_prunes += 1

                continue

            chosen.append(value)

            dfs(
                next_i,
                new_remainder,
                chosen
            )

            chosen.pop()

    if target > 0:

        if not feasible(0, target):

            return stats, []

        dfs(
            0,
            target,
            []
        )

    return stats, solutions

def reduction_percent(a, b):

    if a == 0:
        return 0

    return (a - b) / a * 100

def factor(a, b):

    if b == 0:
        return float("inf")

    return a / b

def unique_path(filename):

    path = Path(filename)

    if not path.exists():
        return path

    i = 1

    while True:

        p = path.parent / (
            f"{path.stem}_{i}{path.suffix}"
        )

        if not p.exists():
            return p

        i += 1

class App:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title(
            "Subset Sum — Advanced Exact Solver"
        )

        self.root.geometry(
            "1350x900"
        )

        self.values = []
        self.target = 0

        self.bf_stats = None
        self.advanced_stats = None

        self.bf_solutions = []
        self.advanced_solutions = []

        self.records = []

        self.build_ui()

        self.root.mainloop()

    def build_ui(self):

        frame = ttk.LabelFrame(
            self.root,
            text=" Input ",
            padding=10
        )

        frame.pack(
            fill=tk.X,
            padx=10,
            pady=10
        )

        ttk.Label(
            frame,
            text="Himpunan:"
        ).grid(
            row=0,
            column=0,
            padx=5
        )

        self.entry_values = ttk.Entry(
            frame,
            font=("Consolas", 10)
        )

        self.entry_values.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=5
        )

        self.entry_values.insert(
            0,
            "1,2,3,4,5,6,7,8,9,10"
        )

        ttk.Label(
            frame,
            text="Target:"
        ).grid(
            row=0,
            column=2,
            padx=5
        )

        self.entry_target = ttk.Entry(
            frame,
            width=12,
            font=("Consolas", 10)
        )

        self.entry_target.grid(
            row=0,
            column=3,
            padx=5
        )

        self.entry_target.insert(
            0,
            "20"
        )

        self.btn_run = ttk.Button(
            frame,
            text="Jalankan",
            command=self.run
        )

        self.btn_run.grid(
            row=0,
            column=4,
            padx=10
        )

        frame.columnconfigure(
            1,
            weight=1
        )

        table_frame = ttk.LabelFrame(
            self.root,
            text=" Statistik ",
            padding=5
        )

        table_frame.pack(
            fill=tk.X,
            padx=10,
            pady=5
        )

        columns = (
            "method",
            "nodes",
            "arith",
            "comp",
            "bound",
            "pruned",
            "solutions",
            "work"
        )

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=4
        )

        headers = {
            "method": "Metode",
            "nodes": "Nodes",
            "arith": "Arithmetic",
            "comp": "Comparisons",
            "bound": "Bounds",
            "pruned": "Pruned",
            "solutions": "Solutions",
            "work": "Work"
        }

        widths = {
            "method": 260,
            "nodes": 120,
            "arith": 120,
            "comp": 130,
            "bound": 100,
            "pruned": 130,
            "solutions": 120,
            "work": 140
        }

        for c in columns:

            self.tree.heading(
                c,
                text=headers[c]
            )

            self.tree.column(
                c,
                width=widths[c],
                anchor="center"
            )

        self.tree.pack(
            fill=tk.X
        )

        button_frame = ttk.Frame(
            self.root
        )

        button_frame.pack(
            fill=tk.X,
            padx=10,
            pady=5
        )

        ttk.Button(
            button_frame,
            text="Detail Statistik",
            command=self.show_detail
        ).pack(
            side=tk.LEFT,
            padx=3
        )

        ttk.Button(
            button_frame,
            text="Bandingkan Solusi",
            command=self.show_solutions
        ).pack(
            side=tk.LEFT,
            padx=3
        )

        ttk.Button(
            button_frame,
            text="Daftar Semua Solusi",
            command=self.show_all_solutions
        ).pack(
            side=tk.LEFT,
            padx=3
        )

        ttk.Button(
            button_frame,
            text="Ekspor TXT",
            command=self.export_txt
        ).pack(
            side=tk.LEFT,
            padx=3
        )

        output_frame = ttk.LabelFrame(
            self.root,
            text=" Output ",
            padding=5
        )

        output_frame.pack(
            fill=tk.BOTH,
            expand=True,
            padx=10,
            pady=5
        )

        self.output = tk.Text(
            output_frame,
            font=("Consolas", 9),
            wrap=tk.NONE
        )

        self.output.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True
        )

        scrollbar = ttk.Scrollbar(
            output_frame,
            orient=tk.VERTICAL,
            command=self.output.yview
        )

        scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y
        )

        self.output.configure(
            yscrollcommand=scrollbar.set
        )

        if HAS_MATPLOTLIB:

            graph_frame = ttk.LabelFrame(
                self.root,
                text=" Grafik ",
                padding=5
            )

            graph_frame.pack(
                fill=tk.BOTH,
                expand=True,
                padx=10,
                pady=5
            )

            self.fig = Figure(
                figsize=(10, 4),
                dpi=100
            )

            self.ax = self.fig.add_subplot(
                111
            )

            self.canvas = FigureCanvasTkAgg(
                self.fig,
                master=graph_frame
            )

            self.canvas.get_tk_widget().pack(
                fill=tk.BOTH,
                expand=True
            )

    def run(self):

        try:

            values = parse_input(
                self.entry_values.get()
            )

            target = int(
                self.entry_target.get()
            )

            if target <= 0:
                raise ValueError(
                    "Target harus positif."
                )

        except Exception as e:

            messagebox.showerror(
                "Input Error",
                str(e)
            )

            return

        self.values = values
        self.target = target

        self.output.delete(
            "1.0",
            tk.END
        )

        self.tree.delete(
            *self.tree.get_children()
        )

        self.btn_run.config(
            state=tk.DISABLED
        )

        self.root.update()

        try:

            self.bf_stats, self.bf_solutions = (
                brute_force(
                    values,
                    target
                )
            )

            self.advanced_stats, self.advanced_solutions = (
                advanced_subset_sum(
                    values,
                    target
                )
            )

            self.bf_solutions = sorted(
                self.bf_solutions
            )

            self.advanced_solutions = sorted(
                self.advanced_solutions
            )

            identical = (
                self.bf_solutions
                == self.advanced_solutions
            )

            self.print_result(
                identical
            )

            self.update_table()

            self.draw_graph()

        finally:

            self.btn_run.config(
                state=tk.NORMAL
            )

    def print_result(self, identical):

        bf = self.bf_stats
        ad = self.advanced_stats

        lines = []

        lines.append(
            "=" * 78
        )

        lines.append(
            "SUBSET SUM — ADVANCED EXACT SOLVER"
        )

        lines.append(
            "=" * 78
        )

        lines.append(
            f"Himpunan : {self.values}"
        )

        lines.append(
            f"Target   : {self.target}"
        )

        lines.append(
            f"n        : {len(self.values)}"
        )

        lines.append("")

        lines.append(
            "=" * 78
        )

        lines.append(
            "BRUTE FORCE — FULL ENUMERATION"
        )

        lines.append(
            "=" * 78
        )

        lines.append(
            f"Nodes        : {bf.nodes:,}"
        )

        lines.append(
            f"Arithmetic   : {bf.arithmetic:,}"
        )

        lines.append(
            f"Comparisons  : {bf.comparisons:,}"
        )

        lines.append(
            f"Pruned       : {bf.pruned:,}"
        )

        lines.append(
            f"Solutions    : {bf.solutions:,}"
        )

        lines.append(
            f"Work units   : {bf.work_units:,}"
        )

        lines.append("")

        lines.append(
            "=" * 78
        )

        lines.append(
            "ADVANCED TARGET-SISA"
        )

        lines.append(
            "Target-Sisa + Memoization + GCD + Modulo"
        )

        lines.append(
            "+ Lower Bound + Upper Bound + Cardinality"
        )

        lines.append(
            "=" * 78
        )

        lines.append(
            f"Nodes        : {ad.nodes:,}"
        )

        lines.append(
            f"Arithmetic   : {ad.arithmetic:,}"
        )

        lines.append(
            f"Comparisons  : {ad.comparisons:,}"
        )

        lines.append(
            f"Bound checks : {ad.bound_checks:,}"
        )

        lines.append(
            f"Pruned       : {ad.pruned:,}"
        )

        lines.append(
            f"Solutions    : {ad.solutions:,}"
        )

        lines.append(
            f"Memo hits    : {ad.memo_hits:,}"
        )

        lines.append(
            f"GCD prunes   : {ad.gcd_prunes:,}"
        )

        lines.append(
            f"Lower prunes : {ad.lower_prunes:,}"
        )

        lines.append(
            f"Upper prunes : {ad.upper_prunes:,}"
        )

        lines.append(
            f"Cardinality  : {ad.cardinality_prunes:,}"
        )

        lines.append(
            f"Work units   : {ad.work_units:,}"
        )

        lines.append("")

        lines.append(
            "=" * 78
        )

        lines.append(
            "PERBANDINGAN"
        )

        lines.append(
            "=" * 78
        )

        lines.append(
            f"Node reduction : "
            f"{reduction_percent(bf.nodes, ad.nodes):.2f}%"
        )

        lines.append(
            f"Arithmetic red.: "
            f"{reduction_percent(bf.arithmetic, ad.arithmetic):.2f}%"
        )

        lines.append(
            f"Comparison red.: "
            f"{reduction_percent(bf.comparisons, ad.comparisons):.2f}%"
        )

        lines.append(
            f"Work reduction : "
            f"{reduction_percent(bf.work_units, ad.work_units):.2f}%"
        )

        lines.append("")

        lines.append(
            f"Node factor    : "
            f"{factor(bf.nodes, ad.nodes):.2f}x"
        )

        lines.append(
            f"Work factor    : "
            f"{factor(bf.work_units, ad.work_units):.2f}x"
        )

        lines.append("")

        lines.append(
            "=" * 78
        )

        lines.append(
            "VERIFIKASI"
        )

        lines.append(
            "=" * 78
        )

        lines.append(
            f"BF solutions       : {len(self.bf_solutions):,}"
        )

        lines.append(
            f"Advanced solutions : {len(self.advanced_solutions):,}"
        )

        if identical:

            lines.append(
                "✓ IDENTIK"
            )

            lines.append(
                "Semua subset solusi kedua metode sama."
            )

        else:

            lines.append(
                "✗ TIDAK IDENTIK"
            )

            lines.append(
                "Ada solusi yang berbeda."
            )

        self.output.insert(
            tk.END,
            "\n".join(lines)
        )

    def update_table(self):

        bf = self.bf_stats
        ad = self.advanced_stats

        self.tree.insert(
            "",
            tk.END,
            values=(
                "Brute Force",
                f"{bf.nodes:,}",
                f"{bf.arithmetic:,}",
                f"{bf.comparisons:,}",
                f"{bf.bound_checks:,}",
                f"{bf.pruned:,}",
                f"{bf.solutions:,}",
                f"{bf.work_units:,}"
            )
        )

        self.tree.insert(
            "",
            tk.END,
            values=(
                "Advanced",
                f"{ad.nodes:,}",
                f"{ad.arithmetic:,}",
                f"{ad.comparisons:,}",
                f"{ad.bound_checks:,}",
                f"{ad.pruned:,}",
                f"{ad.solutions:,}",
                f"{ad.work_units:,}"
            )
        )

    def draw_graph(self):

        if not HAS_MATPLOTLIB:
            return

        bf = self.bf_stats
        ad = self.advanced_stats

        self.ax.clear()

        labels = [
            "Nodes",
            "Arithmetic",
            "Comparisons",
            "Pruned",
            "Work"
        ]

        bf_values = [
            bf.nodes,
            bf.arithmetic,
            bf.comparisons,
            bf.pruned,
            bf.work_units
        ]

        ad_values = [
            ad.nodes,
            ad.arithmetic,
            ad.comparisons,
            ad.pruned,
            ad.work_units
        ]

        import numpy as np

        x = np.arange(
            len(labels)
        )

        width = 0.35

        self.ax.bar(
            x - width / 2,
            bf_values,
            width,
            label="Brute Force"
        )

        self.ax.bar(
            x + width / 2,
            ad_values,
            width,
            label="Advanced"
        )

        self.ax.set_xticks(
            x
        )

        self.ax.set_xticklabels(
            labels
        )

        self.ax.set_yscale(
            "log"
        )

        self.ax.set_ylabel(
            "Jumlah operasi (log scale)"
        )

        self.ax.set_title(
            "Brute Force vs Advanced Target-Sisa"
        )

        self.ax.legend()

        self.ax.grid(
            axis="y",
            alpha=0.25
        )

        self.fig.tight_layout()

        self.canvas.draw()

    def show_detail(self):

        if self.bf_stats is None:
            return

        bf = self.bf_stats
        ad = self.advanced_stats

        win = tk.Toplevel(
            self.root
        )

        win.title(
            "Detail Statistik"
        )

        win.geometry(
            "650x720"
        )

        text = tk.Text(
            win,
            font=("Consolas", 10),
            wrap=tk.NONE
        )

        text.pack(
            fill=tk.BOTH,
            expand=True
        )

        lines = []

        lines.append(
            "BRUTE FORCE"
        )

        lines.append(
            "-" * 55
        )

        lines.append(
            f"Nodes        : {bf.nodes:,}"
        )

        lines.append(
            f"Arithmetic   : {bf.arithmetic:,}"
        )

        lines.append(
            f"Comparisons  : {bf.comparisons:,}"
        )

        lines.append(
            f"Solutions    : {bf.solutions:,}"
        )

        lines.append(
            f"Work         : {bf.work_units:,}"
        )

        lines.append("")

        lines.append(
            "ADVANCED"
        )

        lines.append(
            "-" * 55
        )

        lines.append(
            f"Nodes        : {ad.nodes:,}"
        )

        lines.append(
            f"Arithmetic   : {ad.arithmetic:,}"
        )

        lines.append(
            f"Comparisons  : {ad.comparisons:,}"
        )

        lines.append(
            f"Bound checks : {ad.bound_checks:,}"
        )

        lines.append(
            f"Pruned       : {ad.pruned:,}"
        )

        lines.append(
            f"Solutions    : {ad.solutions:,}"
        )

        lines.append(
            f"Memo hits    : {ad.memo_hits:,}"
        )

        lines.append(
            f"GCD prunes   : {ad.gcd_prunes:,}"
        )

        lines.append(
            f"Modulo       : menggunakan GCD residue"
        )

        lines.append(
            f"Lower prune  : {ad.lower_prunes:,}"
        )

        lines.append(
            f"Upper prune  : {ad.upper_prunes:,}"
        )

        lines.append(
            f"Cardinality  : {ad.cardinality_prunes:,}"
        )

        lines.append(
            f"Work         : {ad.work_units:,}"
        )

        lines.append("")

        lines.append(
            "PENGHEMATAN"
        )

        lines.append(
            "-" * 55
        )

        lines.append(
            f"Node reduction : "
            f"{reduction_percent(bf.nodes, ad.nodes):.2f}%"
        )

        lines.append(
            f"Work reduction : "
            f"{reduction_percent(bf.work_units, ad.work_units):.2f}%"
        )

        lines.append(
            f"Node factor    : "
            f"{factor(bf.nodes, ad.nodes):.2f}x"
        )

        lines.append(
            f"Work factor    : "
            f"{factor(bf.work_units, ad.work_units):.2f}x"
        )

        text.insert(
            tk.END,
            "\n".join(lines)
        )

        text.config(
            state=tk.DISABLED
        )

    def show_solutions(self):

        if self.bf_stats is None:
            return

        win = tk.Toplevel(
            self.root
        )

        win.title(
            "Perbandingan Solusi"
        )

        win.geometry(
            "850x650"
        )

        text = tk.Text(
            win,
            font=("Consolas", 9),
            wrap=tk.NONE
        )

        text.pack(
            fill=tk.BOTH,
            expand=True
        )

        identical = (
            self.bf_solutions
            == self.advanced_solutions
        )

        lines = []

        lines.append(
            "=" * 90
        )

        lines.append(
            "VERIFIKASI SOLUSI"
        )

        lines.append(
            "=" * 90
        )

        lines.append(
            f"Brute Force : {len(self.bf_solutions):,} solusi"
        )

        lines.append(
            f"Advanced    : {len(self.advanced_solutions):,} solusi"
        )

        lines.append("")

        if identical:

            lines.append(
                "✓ IDENTIK — semua solusi sama."
            )

        else:

            lines.append(
                "✗ TIDAK IDENTIK."
            )

        lines.append("")

        max_show = min(
            100,
            len(self.bf_solutions)
        )

        for i in range(max_show):

            bf = self.bf_solutions[i]

            lines.append(
                f"{i + 1:>5}. "
                + " + ".join(
                    map(str, bf)
                )
                + f" = {self.target}"
            )

        if len(self.bf_solutions) > max_show:

            lines.append("")

            lines.append(
                f"... {len(self.bf_solutions) - max_show:,} "
                "solusi lainnya tidak ditampilkan di jendela."
            )

        text.insert(
            tk.END,
            "\n".join(lines)
        )

        text.config(
            state=tk.DISABLED
        )

    def show_all_solutions(self):

        if not self.advanced_solutions:
            messagebox.showinfo(
                "Solusi",
                "Tidak ada solusi."
            )

            return

        win = tk.Toplevel(
            self.root
        )

        win.title(
            "Semua Solusi Advanced"
        )

        win.geometry(
            "800x700"
        )

        text = tk.Text(
            win,
            font=("Consolas", 9),
            wrap=tk.NONE
        )

        text.pack(
            fill=tk.BOTH,
            expand=True
        )

        lines = []

        lines.append(
            f"TOTAL SOLUSI: "
            f"{len(self.advanced_solutions):,}"
        )

        lines.append(
            "=" * 70
        )

        for i, sol in enumerate(
            self.advanced_solutions,
            1
        ):

            lines.append(
                f"{i:>8}. "
                + " + ".join(
                    map(str, sol)
                )
                + f" = {self.target}"
            )

        text.insert(
            tk.END,
            "\n".join(lines)
        )

        text.config(
            state=tk.DISABLED
        )

    def export_txt(self):

        if self.bf_stats is None:
            return

        bf = self.bf_stats
        ad = self.advanced_stats

        identical = (
            self.bf_solutions
            == self.advanced_solutions
        )

        lines = []

        lines.append(
            "SUBSET SUM — ADVANCED EXACT SOLVER"
        )

        lines.append(
            "=" * 80
        )

        lines.append(
            f"Himpunan : {self.values}"
        )

        lines.append(
            f"Target   : {self.target}"
        )

        lines.append(
            f"n        : {len(self.values)}"
        )

        lines.append("")

        lines.append(
            "BRUTE FORCE"
        )

        lines.append(
            f"Nodes       : {bf.nodes:,}"
        )

        lines.append(
            f"Arithmetic  : {bf.arithmetic:,}"
        )

        lines.append(
            f"Comparisons : {bf.comparisons:,}"
        )

        lines.append(
            f"Solutions   : {bf.solutions:,}"
        )

        lines.append(
            f"Work        : {bf.work_units:,}"
        )

        lines.append("")

        lines.append(
            "ADVANCED"
        )

        lines.append(
            f"Nodes        : {ad.nodes:,}"
        )

        lines.append(
            f"Arithmetic   : {ad.arithmetic:,}"
        )

        lines.append(
            f"Comparisons  : {ad.comparisons:,}"
        )

        lines.append(
            f"Bound checks : {ad.bound_checks:,}"
        )

        lines.append(
            f"Pruned       : {ad.pruned:,}"
        )

        lines.append(
            f"Solutions    : {ad.solutions:,}"
        )

        lines.append(
            f"Memo hits    : {ad.memo_hits:,}"
        )

        lines.append(
            f"GCD prunes   : {ad.gcd_prunes:,}"
        )

        lines.append(
            f"Lower prunes : {ad.lower_prunes:,}"
        )

        lines.append(
            f"Upper prunes : {ad.upper_prunes:,}"
        )

        lines.append(
            f"Cardinality  : {ad.cardinality_prunes:,}"
        )

        lines.append(
            f"Work         : {ad.work_units:,}"
        )

        lines.append("")

        lines.append(
            "PERBANDINGAN"
        )

        lines.append(
            f"Node reduction : "
            f"{reduction_percent(bf.nodes, ad.nodes):.2f}%"
        )

        lines.append(
            f"Work reduction : "
            f"{reduction_percent(bf.work_units, ad.work_units):.2f}%"
        )

        lines.append(
            f"Node factor : "
            f"{factor(bf.nodes, ad.nodes):.2f}x"
        )

        lines.append(
            f"Work factor : "
            f"{factor(bf.work_units, ad.work_units):.2f}x"
        )

        lines.append("")

        lines.append(
            "VERIFIKASI"
        )

        lines.append(
            f"BF solutions       : "
            f"{len(self.bf_solutions):,}"
        )

        lines.append(
            f"Advanced solutions : "
            f"{len(self.advanced_solutions):,}"
        )

        lines.append(
            "IDENTIK : "
            + ("YA" if identical else "TIDAK")
        )

        lines.append("")

        lines.append(
            "SEMUA SOLUSI"
        )

        lines.append(
            "=" * 80
        )

        for i, sol in enumerate(
            self.advanced_solutions,
            1
        ):

            lines.append(
                f"{i:>8}. "
                + " + ".join(
                    map(str, sol)
                )
                + f" = {self.target}"
            )

        path = unique_path(
            f"subset_sum_advanced_T{self.target}_n{len(self.values)}.txt"
        )

        path.write_text(
            "\n".join(lines),
            encoding="utf-8"
        )

        messagebox.showinfo(
            "Tersimpan",
            f"Hasil disimpan:\n{path.resolve()}"
        )

if __name__ == "__main__":
    App()

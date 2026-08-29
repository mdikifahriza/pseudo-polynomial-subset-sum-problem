import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dataclasses import dataclass
from pathlib import Path
import time
import os
import threading
from concurrent.futures import ProcessPoolExecutor

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
    upper_prunes: int = 0
    lower_prunes: int = 0
    elapsed: float = 0.0

    @property
    def work_units(self):
        return (
            self.nodes
            + self.arithmetic
            + self.comparisons
            + self.bound_checks
            + self.pruned
        )

    def add(self, other: "Stats"):
        self.nodes += other.nodes
        self.arithmetic += other.arithmetic
        self.comparisons += other.comparisons
        self.bound_checks += other.bound_checks
        self.pruned += other.pruned
        self.solutions += other.solutions
        self.upper_prunes += other.upper_prunes
        self.lower_prunes += other.lower_prunes

def parse_input(raw):
    raw = raw.strip()
    if not raw:
        raise ValueError("Input tidak boleh kosong.")

    parts = [x.strip() for x in raw.split(",")]
    values = []

    for part in parts:
        if not part.isdigit():
            raise ValueError(f"'{part}' bukan bilangan bulat positif.")
        value = int(part)
        if value <= 0:
            raise ValueError(f"'{value}' harus lebih besar dari 0.")
        values.append(value)

    if not values:
        raise ValueError("Input himpunan kosong.")

    if len(values) != len(set(values)):
        raise ValueError("Himpunan tidak boleh memiliki elemen duplikat.")

    return sorted(values)

def build_suffix_sum(values):
    n = len(values)
    suffix = [0] * (n + 1)
    current = 0
    for i in range(n - 1, -1, -1):
        current += values[i]
        suffix[i] = current
    return suffix

def _solve_target_sisa_worker(args):
    (
        values,
        target,
        start_idx,
        initial_remainder,
        initial_chosen,
        suffix_sum,
        n,
        collect_solutions
    ) = args

    stats = Stats()
    solutions = []

    def dfs(start, remainder, chosen):
        stats.nodes += 1

        stats.comparisons += 1
        if remainder == 0:
            stats.solutions += 1
            if collect_solutions:
                solutions.append(tuple(chosen))
            return True

        stats.comparisons += 1
        if remainder < 0 or start >= n:
            stats.pruned += 1
            return False

        stats.bound_checks += 1
        stats.comparisons += 1
        if suffix_sum[start] < remainder:
            stats.upper_prunes += 1
            stats.pruned += 1
            return False

        found_any = False
        for j in range(start, n):
            val = values[j]
            stats.comparisons += 1
            if val > remainder:
                stats.lower_prunes += 1
                stats.pruned += (n - j)
                break

            stats.arithmetic += 1
            chosen.append(val)
            if dfs(j + 1, remainder - val, chosen):
                found_any = True
            chosen.pop()

        return found_any

    dfs(start_idx, initial_remainder, list(initial_chosen))
    return stats, solutions

def target_remainder_suffix_sum(values, target, collect_solutions=True, num_workers=None):
    start_time = time.perf_counter()
    n = len(values)
    stats = Stats()
    solutions = []

    if n == 0 or target <= 0:
        stats.elapsed = time.perf_counter() - start_time
        return stats, solutions

    suffix_sum = build_suffix_sum(values)

    stats.nodes += 1
    stats.bound_checks += 1
    stats.comparisons += 1
    if suffix_sum[0] < target:
        stats.upper_prunes += 1
        stats.pruned += 1
        stats.elapsed = time.perf_counter() - start_time
        return stats, solutions

    tasks = []
    for j in range(n):
        val = values[j]
        stats.comparisons += 1
        if val > target:
            stats.lower_prunes += 1
            stats.pruned += (n - j)
            break

        stats.arithmetic += 1
        tasks.append((
            values,
            target,
            j + 1,
            target - val,
            [val],
            suffix_sum,
            n,
            collect_solutions
        ))

    if not tasks:
        stats.elapsed = time.perf_counter() - start_time
        return stats, solutions

    cpu_total = os.cpu_count() or 1
    if num_workers is None:
        num_workers = min(len(tasks), cpu_total)

    if num_workers <= 1 or len(tasks) <= 1 or n <= 12:
        for t in tasks:
            sub_stats, sub_sols = _solve_target_sisa_worker(t)
            stats.add(sub_stats)
            if collect_solutions:
                solutions.extend(sub_sols)
    else:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            results = executor.map(_solve_target_sisa_worker, tasks)
            for sub_stats, sub_sols in results:
                stats.add(sub_stats)
                if collect_solutions:
                    solutions.extend(sub_sols)

    stats.elapsed = time.perf_counter() - start_time
    return stats, solutions

class TargetSisaApp:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Subset Sum — Target-Sisa (Method 2)")
        self.root.geometry("1020x720")
        self.root.minsize(860, 600)
        self.root.configure(bg="#f8fafc")

        self.values = []
        self.target = 0
        self.stats = None
        self.solutions = []

        self.is_calculating = False
        self.calc_start_time = 0.0
        self.total_cores = os.cpu_count() or 1

        self.sol_window = None
        self.graph_window = None

        self._setup_style()
        self._create_widgets()
        self._center_window(self.root, 1020, 720)

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
        style.configure("TLabelframe.Label", background=card_bg, foreground="#1e293b", font=("Segoe UI", 10, "bold"))

        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            background="#2563eb",
            foreground="#ffffff",
            padding=(16, 7)
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#1d4ed8"), ("disabled", "#94a3b8")],
            foreground=[("disabled", "#f8fafc")]
        )

        style.configure(
            "Action.TButton",
            font=("Segoe UI", 9, "bold"),
            background="#0d9488",
            foreground="#ffffff",
            padding=(12, 6)
        )
        style.map(
            "Action.TButton",
            background=[("active", "#0f766e"), ("disabled", "#cbd5e1")],
            foreground=[("disabled", "#64748b")]
        )

        style.configure(
            "Graph.TButton",
            font=("Segoe UI", 9, "bold"),
            background="#7c3aed",
            foreground="#ffffff",
            padding=(12, 6)
        )
        style.map(
            "Graph.TButton",
            background=[("active", "#6d28d9"), ("disabled", "#cbd5e1")],
            foreground=[("disabled", "#64748b")]
        )

        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 9),
            padding=(10, 6)
        )

    def _create_widgets(self):
        header_frame = tk.Frame(self.root, bg="#0f172a", height=65)
        header_frame.pack(fill=tk.X)

        title_box = tk.Frame(header_frame, bg="#0f172a")
        title_box.pack(side=tk.LEFT, padx=20, pady=10)

        title_lbl = tk.Label(
            title_box,
            text="SUBSET SUM SOLVER — TARGET-SISA",
            font=("Segoe UI", 13, "bold"),
            bg="#0f172a",
            fg="#f8fafc"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            title_box,
            text="Metode 2: Target-Sisa Suffix Sum Pruning • Pemrosesan Paralel Multi-Core",
            font=("Segoe UI", 9),
            bg="#0f172a",
            fg="#94a3b8"
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        badge_box = tk.Frame(header_frame, bg="#1e293b", padx=10, pady=4, relief="solid", bd=1)
        badge_box.pack(side=tk.RIGHT, padx=20, pady=12)

        cpu_lbl = tk.Label(
            badge_box,
            text=f"⚡ {self.total_cores} CPU Cores Aktif",
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#38bdf8"
        )
        cpu_lbl.pack()

        main_frame = ttk.Frame(self.root, padding=14)
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_card = ttk.LabelFrame(main_frame, text=" Parameter Masukan ", padding=14)
        input_card.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(input_card, text="Himpunan Bilangan:", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w", pady=4
        )

        self.entry_values = ttk.Entry(input_card, font=("Consolas", 10))
        self.entry_values.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(10, 8), pady=4)
        self.entry_values.insert(0, "3,7,11,14,18,21,26,29,34,38")

        ttk.Label(input_card, text="Nilai Target:", font=("Segoe UI", 9, "bold")).grid(
            row=1, column=0, sticky="w", pady=6
        )

        self.entry_target = ttk.Entry(input_card, width=15, font=("Consolas", 10))
        self.entry_target.grid(row=1, column=1, sticky="w", padx=(10, 8), pady=6)
        self.entry_target.insert(0, "100")

        btn_box = ttk.Frame(input_card)
        btn_box.grid(row=1, column=2, columnspan=2, sticky="e", pady=6)

        self.btn_run = ttk.Button(
            btn_box,
            text="▶ Jalankan Algoritma",
            style="Primary.TButton",
            command=self._start_calculation
        )
        self.btn_run.pack(side=tk.LEFT, padx=4)

        self.btn_save = ttk.Button(
            btn_box,
            text="💾 Simpan Laporan TXT",
            style="Secondary.TButton",
            command=self._save_txt,
            state="disabled"
        )
        self.btn_save.pack(side=tk.LEFT, padx=4)

        input_card.columnconfigure(1, weight=1)

        action_bar = ttk.Frame(main_frame)
        action_bar.pack(fill=tk.X, pady=(0, 10))

        self.status_frame = tk.Frame(action_bar, bg="#ffffff", relief="solid", bd=1, padx=14, pady=10)
        self.status_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.status_lbl = tk.Label(
            self.status_frame,
            text="Status: Siap.",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#334155"
        )
        self.status_lbl.pack(anchor="w")

        self.summary_lbl = tk.Label(
            self.status_frame,
            text=f"Siap memproses menggunakan seluruh {self.total_cores} core prosesor secara asynchronous.",
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg="#64748b"
        )
        self.summary_lbl.pack(anchor="w", pady=(3, 0))

        btn_group = ttk.Frame(action_bar)
        btn_group.pack(side=tk.RIGHT, padx=(12, 0))

        self.btn_solutions = ttk.Button(
            btn_group,
            text="📋 Lihat Solusi",
            style="Action.TButton",
            command=self._open_solutions_window,
            state="disabled"
        )
        self.btn_solutions.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        self.btn_graph = ttk.Button(
            btn_group,
            text="📊 Lihat Grafik Komputasi",
            style="Graph.TButton",
            command=self._open_graph_window,
            state="disabled"
        )
        self.btn_graph.pack(side=tk.TOP, fill=tk.X)

        stat_frame = ttk.LabelFrame(main_frame, text=" Rincian Statistik Komputasi ", padding=10)
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

        self._show_initial_help()

    def _show_initial_help(self):
        self.stat_text.config(state=tk.NORMAL)
        self.stat_text.delete("1.0", tk.END)
        self.stat_text.insert(
            tk.END,
            "SELAMAT DATANG DI SUBSET SUM SOLVER — TARGET-SISA (MULTI-CORE & ASYNC)\n"
            "========================================================================\n"
            "Klik tombol '▶ Jalankan Algoritma' untuk memulai pencarian subset sum.\n\n"
            "Karakteristik Metode 2 (Target-Sisa Suffix Sum):\n"
            "  • Evaluasi state (i, r) dengan pemangkasan cabang suffix_sum[i] < r.\n"
            f"  • Pemanfaatan Penuh {self.total_cores} Core CPU untuk pemrosesan paralel.\n"
            "  • Background Threading: GUI tetap 100% lancar & responsif tanpa not responding.\n"
            "  • Solusi tersembunyi rapi di tombol '📋 Lihat Solusi'.\n"
            "  • Grafik performa komputasi di tombol '📊 Lihat Grafik Komputasi'.\n"
        )
        self.stat_text.config(state=tk.DISABLED)

    def _start_calculation(self):
        if self.is_calculating:
            return

        try:
            values = parse_input(self.entry_values.get())
            target = int(self.entry_target.get())
            if target <= 0:
                raise ValueError("Target harus positif.")
        except Exception as e:
            messagebox.showerror("Input Error", str(e))
            return

        self.is_calculating = True
        self.calc_start_time = time.perf_counter()

        self.btn_run.config(state="disabled")
        self.btn_save.config(state="disabled")
        self.btn_solutions.config(state="disabled")
        self.btn_graph.config(state="disabled")

        self.status_lbl.config(
            text=f"Status: Sedang menghitung di {self.total_cores} Core CPU... ⏳",
            fg="#d97706"
        )
        self.summary_lbl.config(
            text="Memproses pohon pencarian Target-Sisa secara paralel. Waktu berjalan: 0.0s"
        )

        self._update_live_timer()

        worker_thread = threading.Thread(
            target=self._run_computation_thread,
            args=(values, target),
            daemon=True
        )
        worker_thread.start()

    def _update_live_timer(self):
        if not self.is_calculating:
            return
        elapsed = time.perf_counter() - self.calc_start_time
        self.summary_lbl.config(
            text=f"Mengevaluasi cabang Target-Sisa di seluruh core CPU. Waktu berjalan: {elapsed:.1f} detik"
        )
        self.root.after(100, self._update_live_timer)

    def _run_computation_thread(self, values, target):
        try:
            stats, solutions = target_remainder_suffix_sum(
                values,
                target,
                collect_solutions=True
            )
            self.root.after(0, self._on_computation_success, values, target, stats, solutions)
        except Exception as e:
            self.root.after(0, self._on_computation_error, str(e))

    def _on_computation_success(self, values, target, stats, solutions):
        self.is_calculating = False
        self.values = values
        self.target = target
        self.stats = stats
        self.solutions = solutions

        self._show_statistics()

        self.status_lbl.config(text="Status: Selesai ✅", fg="#15803d")
        self.summary_lbl.config(
            text=f"Total Solusi: {len(solutions):,}  |  Waktu: {stats.elapsed:.4f}s ({self.total_cores} Core)  |  Work Units: {stats.work_units:,}  |  Nodes: {stats.nodes:,}"
        )

        self.btn_run.config(state="normal")
        self.btn_save.config(state="normal")
        self.btn_solutions.config(
            state="normal",
            text=f"📋 Lihat Solusi ({len(solutions):,})"
        )
        if HAS_MATPLOTLIB:
            self.btn_graph.config(state="normal")

        if self.sol_window and self.sol_window.winfo_exists():
            self._update_solutions_window()
        if self.graph_window and self.graph_window.winfo_exists():
            self._update_graph_window()

    def _on_computation_error(self, err_msg):
        self.is_calculating = False
        self.btn_run.config(state="normal")
        messagebox.showerror("Error Perhitungan", err_msg)
        self.status_lbl.config(text="Status: Gagal ❌", fg="#dc2626")
        self.summary_lbl.config(text=f"Terjadi kesalahan: {err_msg}")

    def _show_statistics(self):
        s = self.stats
        lines = []

        lines.append("=" * 76)
        lines.append("HASIL KOMPUTASI SUBSET SUM — TARGET-SISA SUFFIX SUM (MULTI-CORE)")
        lines.append("=" * 76)
        lines.append(f"Himpunan (n={len(self.values)}) : {self.values}")
        lines.append(f"Nilai Target        : {self.target}")
        lines.append(f"Total Solusi        : {len(self.solutions):,}")
        lines.append(f"Waktu Eksekusi      : {s.elapsed:.6f} detik")
        lines.append(f"Jumlah Core CPU     : {self.total_cores} Core Paralel")
        lines.append("")

        lines.append("-" * 76)
        lines.append("METRIK PENCARIAN DAN OPERASI KOMPUTASI")
        lines.append("-" * 76)
        lines.append(f"  • Nodes Dievaluasi          : {s.nodes:>16,}")
        lines.append(f"  • Operasi Aritmatika        : {s.arithmetic:>16,}")
        lines.append(f"  • Perbandingan (Comparisons): {s.comparisons:>16,}")
        lines.append(f"  • Bound Checks              : {s.bound_checks:>16,}")
        lines.append(f"  • Total Cabang Dipangkas    : {s.pruned:>16,}")
        lines.append(f"    - Suffix Sum Upper Prunes : {s.upper_prunes:>16,}")
        lines.append(f"    - Candidate Lower Prunes  : {s.lower_prunes:>16,}")
        lines.append(f"  • Total Work Units          : {s.work_units:>16,}")
        lines.append("")

        lines.append("=" * 76)
        lines.append("OPTIMASI AKTIF")
        lines.append("=" * 76)
        lines.append("  [✓] Target-Sisa DFS Multi-Core")
        lines.append("  [✓] Suffix Sum Upper Bound Pruning")
        lines.append("  [✓] Candidate Lower Bound Pruning")
        lines.append("  [✗] Tanpa Memoization")

        self.stat_text.config(state=tk.NORMAL)
        self.stat_text.delete("1.0", tk.END)
        self.stat_text.insert(tk.END, "\n".join(lines))
        self.stat_text.config(state=tk.DISABLED)

    def _open_solutions_window(self):
        if not self.solutions and self.stats is None:
            messagebox.showinfo("Info", "Jalankan algoritma terlebih dahulu.")
            return

        if self.sol_window and self.sol_window.winfo_exists():
            self.sol_window.lift()
            self.sol_window.focus_force()
            return

        self.sol_window = tk.Toplevel(self.root)
        self.sol_window.title("Daftar Solusi Subset Sum")
        self.sol_window.geometry("700x550")
        self.sol_window.minsize(550, 400)
        self.sol_window.configure(bg="#f8fafc")

        hdr = tk.Frame(self.sol_window, bg="#0f766e", padx=16, pady=10)
        hdr.pack(fill=tk.X)

        self.sol_win_title = tk.Label(
            hdr,
            text=f"Solusi Ditemukan ({len(self.solutions):,} Solusi)",
            font=("Segoe UI", 11, "bold"),
            bg="#0f766e",
            fg="#ffffff"
        )
        self.sol_win_title.pack(anchor="w")

        self.sol_win_sub = tk.Label(
            hdr,
            text=f"Target: {self.target} | n: {len(self.values)} elemen",
            font=("Segoe UI", 9),
            bg="#0f766e",
            fg="#ccfbf1"
        )
        self.sol_win_sub.pack(anchor="w")

        tb = tk.Frame(self.sol_window, bg="#f8fafc", padx=12, pady=8)
        tb.pack(fill=tk.X)

        btn_copy = ttk.Button(
            tb,
            text="📋 Salin Semua Solusi ke Clipboard",
            command=self._copy_solutions_clipboard
        )
        btn_copy.pack(side=tk.LEFT, padx=(0, 6))

        btn_close = ttk.Button(
            tb,
            text="Tutup",
            command=self.sol_window.destroy
        )
        btn_close.pack(side=tk.RIGHT)

        text_frame = tk.Frame(self.sol_window, padx=12, pady=6, bg="#f8fafc")
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.sol_popup_text = tk.Text(
            text_frame,
            font=("Consolas", 10),
            wrap=tk.WORD,
            bg="#ffffff",
            fg="#0f172a",
            relief=tk.SOLID,
            bd=1
        )
        sol_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.sol_popup_text.yview)
        self.sol_popup_text.configure(yscrollcommand=sol_scroll.set)

        sol_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.sol_popup_text.pack(fill=tk.BOTH, expand=True)

        self._update_solutions_window()
        self._center_window(self.sol_window, 700, 550)

    def _update_solutions_window(self):
        if not (self.sol_window and self.sol_window.winfo_exists()):
            return

        self.sol_win_title.config(text=f"Solusi Ditemukan ({len(self.solutions):,} Solusi)")
        self.sol_win_sub.config(text=f"Target: {self.target} | n: {len(self.values)} elemen")

        self.sol_popup_text.config(state=tk.NORMAL)
        self.sol_popup_text.delete("1.0", tk.END)

        if not self.solutions:
            self.sol_popup_text.insert(tk.END, "TIDAK ADA SOLUSI YANG MEMENUHI TARGET.")
            self.sol_popup_text.config(state=tk.DISABLED)
            return

        self.sol_popup_text.insert(
            tk.END,
            f"Total {len(self.solutions):,} kombinasi subset dengan jumlah = {self.target}:\n"
            f"{'=' * 60}\n\n"
        )

        limit = min(len(self.solutions), 1000)
        for i in range(limit):
            sol = self.solutions[i]
            expression = " + ".join(map(str, sol))
            self.sol_popup_text.insert(
                tk.END,
                f"{i + 1:>5}.  {expression} = {self.target}\n"
            )

        if len(self.solutions) > limit:
            self.sol_popup_text.insert(
                tk.END,
                f"\n... dan {len(self.solutions) - limit:,} solusi lainnya.\n"
                f"(Gunakan tombol 'Simpan Laporan TXT' untuk melihat seluruh solusi lengkap)\n"
            )

        self.sol_popup_text.config(state=tk.DISABLED)

    def _copy_solutions_clipboard(self):
        if not self.solutions:
            return
        lines = []
        for i, sol in enumerate(self.solutions, 1):
            expression = " + ".join(map(str, sol))
            lines.append(f"{i}. {expression} = {self.target}")
        content = "\n".join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("Sukses", f"{len(self.solutions):,} solusi berhasil disalin ke clipboard!")

    def _open_graph_window(self):
        if not HAS_MATPLOTLIB:
            messagebox.showwarning("Peringatan", "Modul matplotlib tidak tersedia.")
            return

        if self.stats is None:
            messagebox.showinfo("Info", "Jalankan algoritma terlebih dahulu.")
            return

        if self.graph_window and self.graph_window.winfo_exists():
            self.graph_window.lift()
            self.graph_force = self.graph_window.focus_force()
            return

        self.graph_window = tk.Toplevel(self.root)
        self.graph_window.title("Grafik Analisis Aktivitas Komputasi")
        self.graph_window.geometry("820x560")
        self.graph_window.minsize(650, 450)
        self.graph_window.configure(bg="#f8fafc")

        hdr = tk.Frame(self.graph_window, bg="#6d28d9", padx=16, pady=10)
        hdr.pack(fill=tk.X)

        tk.Label(
            hdr,
            text="Visualisasi Aktivitas & Beban Komputasi Target-Sisa",
            font=("Segoe UI", 11, "bold"),
            bg="#6d28d9",
            fg="#ffffff"
        ).pack(anchor="w")

        tk.Label(
            hdr,
            text=f"Target: {self.target} | n={len(self.values)} elemen | Waktu: {self.stats.elapsed:.4f}s ({self.total_cores} Core CPU)",
            font=("Segoe UI", 9),
            bg="#6d28d9",
            fg="#ede9fe"
        ).pack(anchor="w")

        self.graph_container = tk.Frame(self.graph_window, bg="#ffffff", padx=8, pady=8)
        self.graph_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        self._update_graph_window()
        self._center_window(self.graph_window, 820, 560)

    def _update_graph_window(self):
        if not (HAS_MATPLOTLIB and self.graph_window and self.graph_window.winfo_exists()):
            return

        for widget in self.graph_container.winfo_children():
            widget.destroy()

        s = self.stats
        labels = [
            "Nodes",
            "Arithmetic",
            "Comparisons",
            "Bound Checks",
            "Total Pruned"
        ]
        values = [
            s.nodes,
            s.arithmetic,
            s.comparisons,
            s.bound_checks,
            s.pruned
        ]
        colors = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444"]

        fig = Figure(figsize=(7.5, 4.2), dpi=100, facecolor="#ffffff")
        ax = fig.add_subplot(111)

        bars = ax.bar(labels, values, color=colors, width=0.55, edgecolor="#334155", linewidth=0.8)

        for bar in bars:
            h = bar.get_height()
            ax.annotate(
                f"{h:,}",
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color="#1e293b"
            )

        ax.set_title(f"Distribusi Operasi Komputasi Target-Sisa ({self.total_cores} Core CPU)", fontsize=11, fontweight="bold", pad=12)
        ax.set_ylabel("Jumlah Operasi", fontsize=10)
        ax.grid(axis="y", linestyle="--", alpha=0.3)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", labelsize=9)
        ax.tick_params(axis="y", labelsize=9)

        fig.tight_layout(pad=2.0)

        canvas = FigureCanvasTkAgg(fig, master=self.graph_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _save_txt(self):
        if self.stats is None:
            messagebox.showinfo("Info", "Jalankan algoritma terlebih dahulu.")
            return

        s = self.stats
        lines = []

        lines.append("=" * 80)
        lines.append("SUBSET SUM — TARGET-SISA SUFFIX SUM (MULTI-CORE)")
        lines.append("=" * 80)
        lines.append(f"Himpunan : {self.values}")
        lines.append(f"Target   : {self.target}")
        lines.append(f"n        : {len(self.values)}")
        lines.append(f"CPU Core : {self.total_cores} Cores")
        lines.append("")
        lines.append("STATISTIK")
        lines.append("-" * 80)
        lines.append(f"Nodes             : {s.nodes:,}")
        lines.append(f"Arithmetic        : {s.arithmetic:,}")
        lines.append(f"Comparisons       : {s.comparisons:,}")
        lines.append(f"Bound checks      : {s.bound_checks:,}")
        lines.append(f"Pruned            : {s.pruned:,}")
        lines.append(f"  - Upper Prunes  : {s.upper_prunes:,}")
        lines.append(f"  - Lower Prunes  : {s.lower_prunes:,}")
        lines.append(f"Solutions         : {s.solutions:,}")
        lines.append(f"Work units        : {s.work_units:,}")
        lines.append(f"Time              : {s.elapsed:.6f} sec")
        lines.append("")
        lines.append("=" * 80)
        lines.append("SOLUSI")
        lines.append("=" * 80)

        for i, sol in enumerate(self.solutions, 1):
            expression = " + ".join(map(str, sol))
            lines.append(f"{i}. {expression} = {self.target}")

        path = filedialog.asksaveasfilename(
            title="Simpan hasil",
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt")],
            initialfile=f"target_sisa_T{self.target}_n{len(self.values)}.txt"
        )

        if not path:
            return

        Path(path).write_text("\n".join(lines), encoding="utf-8")
        messagebox.showinfo("Berhasil", f"Hasil disimpan:\n{path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Subset Sum — Target-Sisa (Method 2)")
    parser.add_argument("--cli", action="store_true", help="Jalankan dalam mode CLI")
    parser.add_argument("--values", type=str, default="3,7,11,14,18,21,26,29,34,38", help="Himpunan bilangan")
    parser.add_argument("--target", type=int, default=100, help="Nilai target")
    parser.add_argument("--all", action="store_true", help="Temukan semua solusi")

    args, unknown = parser.parse_known_args()

    if args.cli:
        vals = parse_input(args.values)
        stats, sols = target_remainder_suffix_sum(vals, args.target, collect_solutions=True)
        print("=" * 76)
        print("  TARGET-SISA (METHOD 2) — CLI")
        print("=" * 76)
        print(f"Himpunan (n={len(vals)}) : {vals}")
        print(f"Target          : {args.target}")
        print(f"Total Solusi    : {len(sols)}")
        print(f"Waktu Eksekusi  : {stats.elapsed:.6f} detik")
        print(f"Nodes           : {stats.nodes:,}")
        print(f"Work Units      : {stats.work_units:,}")
        if sols:
            for i, s in enumerate(sols[:10], 1):
                print(f"  {i}. {' + '.join(map(str, s))} = {args.target}")
    else:
        app = TargetSisaApp()
        app.run()

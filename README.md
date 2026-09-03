# Dumb SSP Solver

Exact solver untuk **Subset Sum Problem (SSP)** — mencari subset dari sekumpulan bilangan bulat positif yang jumlahnya persis sama dengan target `T`. Solver ini bersifat *adaptif*: memilih strategi/algoritma berbeda tergantung karakteristik instance (ukuran `N`, magnitude `T`, struktur data), lalu memverifikasi hasilnya secara independen (L7 Verifier).

---

## 1. Arsitektur & Struktur File

| File | Peran |
|---|---|
| `dumbsspCore.hpp` | Core library — struktur data, strategy selector, dan seluruh solver (L1–L8) |
| `dumbsspCli.cpp` → `dumbsspCli.exe` | CLI harness performa tinggi untuk terminal |
| `dumbsspGui.cpp` → `dumbsspGui.exe` | Aplikasi desktop native Win32 |
| `benchmark.txt` | 20 dataset benchmark bertahap, N=5 s/d N=100 |
| `readme.md` | Dokumentasi ini |

---

## 2. v1 vs v2 — Apa Bedanya?

**v1** dan **v2** adalah dua generasi engine yang sama-sama exact (selalu menghasilkan solusi tervalidasi 100% atau UNSAT terbukti — tidak pernah approximate), tapi v2 menambah beberapa lapisan optimisasi adaptif yang tidak ada di v1.

| Aspek | v1 | v2 |
|---|---|---|
| Deteksi struktur superincreasing | Tidak ada — semua kasus lewat DFS generik | **Ada** — dideteksi & dirutekan ke solver O(n) khusus |
| Strategi DFS berat (`L4`) | `Hybrid Tail-Table + Pruned DFS` polos | `Hybrid Tail-Table + Pruned DFS (Block-Bound + Ordered)` — ditambah memoisasi *block-bound* dan heuristik urutan cabang |
| Paralelisasi | Tidak ada, selalu single-thread | Root-split multi-thread untuk mode `findone` pada instance besar |
| Batas RAM saat DFS berjalan | N/A (tidak butuh, karena tidak ada struktur memo) | **Tidak dibatasi** — `memory_limit_mb` hanya dipakai sekali di awal untuk ukuran tail-table, bukan dicek ulang selama pencarian |
| RAM saat solve | Flat & predictable (~16–20 MB, hampir konstan berapa pun N) | Bisa flat kecil (~4–20 MB) **atau** melonjak ratusan MB, tergantung struktur instance |

---

## 3. Perbedaan Kecepatan (berdasarkan hasil benchmark aktual)

Diuji pada tiga kategori instance berbeda:

### a) High-Density (angka kecil, N > 32)
Kedua versi memilih strategi identik (**L3: Bitset DP**). Hasilnya **nyaris sama** — selisih di bawah margin noise, karena jalur kode di kategori ini tidak berubah antara v1 dan v2.

### b) Superincreasing (tiap elemen > jumlah semua elemen di bawahnya)
**v2 menang mutlak dan tanpa syarat.** v1 tetap memakai DFS generik (`L4`) meski instance-nya sebetulnya trivial, sedangkan v2 mendeteksi struktur ini dan langsung memakai `L1: Greedy Superincreasing (Exact O(n))`.

| N | v1 (L4 generik) | v2 (L1 Greedy) | Speedup |
|---|---|---|---|
| 35 | ~140 ms | ~0,03 ms | ~4.000x |
| 45 | ~138 ms | ~0,03 ms | ~4.000x |
| 55 | ~137 ms | ~0,04 ms | ~3.800x |

RAM v2 juga ikut turun (~20 MB → ~4 MB) karena tidak perlu membangun tail-table sama sekali.

### c) Heavy-Variation (angka besar 12–13 digit, N=45–85, struktur "flat")
Di sinilah hasilnya **tidak konsisten satu arah**:

| N | v1 | v2 | Pemenang |
|---|---|---|---|
| 45 | 3.341 ms / 20 MB | 4.641 ms / **193 MB** | **v1** (lebih cepat & jauh lebih hemat RAM) |
| 50 | 3.674 ms / 20 MB | 427 ms / 32 MB | v2 (~8,6x lebih cepat) |
| 65 | 4.676 ms / 20 MB | 2.468 ms / 99,8 MB | v2 (~1,9x lebih cepat, RAM naik 5x) |
| 85 | 12.391 ms / 20 MB | 158 ms / 22 MB | v2 (~78x lebih cepat, RAM nyaris sama) |

**Kesimpulan kecepatan:** v2 **tidak menang telak secara universal**. Untuk kasus superincreasing, kemenangannya mutlak. Untuk kasus DFS berat, v2 *sering* jauh lebih cepat berkat pruning `Block-Bound` yang lebih agresif — tapi ada instance nyata (N=45 di atas) di mana v2 justru lebih lambat sekaligus jauh lebih boros memori dibanding v1.

---

## 4. Tradeoff v2: RAM Bisa Meledak

Fitur baru `Block-Bound` di v2 bekerja dengan mencatat state DFS `(kedalaman i, sisa target rem)` yang sudah terbukti tidak punya solusi, ke dalam `unordered_set<u64>` per kedalaman, supaya tidak dieksplorasi ulang. Masalahnya:

- **Tidak ada batas ukuran / eviction** pada struktur memo ini — ia tumbuh terus sepanjang satu kali `solve()`.
- **Tidak ada pengecekan RAM aktual** selama DFS berjalan — satu-satunya guard periodik yang ada hanyalah *time limit* (default 120 detik), bukan *memory limit*.
- Efektivitasnya (hit-rate) sangat bergantung struktur data: untuk instance dengan angka besar & window kardinalitas lebar ("flat/unstructured"), nilai `rem` di tiap node DFS jarang berulang persis, sehingga memo lebih sering **menambah entry baru** daripada **dipakai ulang** untuk memangkas pencarian.

**Kapan risiko ini paling nyata muncul** (harus memenuhi semua kondisi berikut):
1. Target `T` (setelah dual-complement) **> 15.000.000** → lolos dari `Bitset DP`.
2. Array **bukan superincreasing** → lolos dari fast-path `Greedy`.
3. GCD = 1, tidak ada obstruksi paritas → lolos `TrivialPreCheck`.
4. Window kardinalitas `[k_min, k_max]` **lebar** (bukan sempit) → lolos deteksi `NarrowKWindow`, sehingga oracle pemangkas jarang berhasil.
5. `N` di kisaran menengah (≈40–70 berdasarkan pola benchmark di atas) dengan elemen bermagnitude besar & acak ("flat").
6. Waktu solve dibiarkan mendekati batas default (120 detik) — makin lama berjalan, makin banyak entry ter-akumulasi.

Estimasi kasar dari data benchmark: biaya memo ≈ **21 byte per DFS state**. Jika throughput eksplorasi ~1,7–4 juta state/detik dan solver berjalan mendekati batas waktu 120 detik, jumlah state yang tereksplorasi bisa mencapai ratusan juta — cukup untuk mendorong RAM proses ke kisaran beberapa GB, berpotensi melebihi kapasitas RAM 8 GB pada mesin biasa, **karena tidak ada mekanisme apa pun di kode yang secara aktif membatasi konsumsi memori selama fase pencarian berlangsung.**

> **Rekomendasi praktis:** untuk instance dengan karakteristik di atas (target besar, struktur flat, N menengah), pertimbangkan menurunkan `time_limit_ms` secara eksplisit, atau memonitor RAM proses secara eksternal saat menjalankan v2 pada input yang tidak dikenal karakteristiknya.

---

## 5. Algoritma di Balik Layar (L0–L8)

Solver memilih strategi secara otomatis lewat `AdaptiveStrategySelector`, urutan pengecekan:

1. **L2 — Trivial Exact Pre-Reduction**
   Deteksi kasus instan: `target=0`, target melebihi total sum, obstruksi modular GCD, obstruksi paritas, atau window kardinalitas kosong → langsung SAT/UNSAT tanpa pencarian.

2. **L1 — Greedy Superincreasing (Exact O(n))** *(v2 saja — baru)*
   Aktif jika array terbukti penuh superincreasing (tiap elemen > jumlah semua elemen lebih kecil di bawahnya). Solusi selalu unik, diputuskan take/skip per elemen tanpa backtrack sama sekali — O(n), tidak pernah salah karena sifat struktural superincreasing menjamin tidak ada kombinasi elemen kecil yang bisa menyamai elemen besar di atasnya.

3. **L3 — Bitset DP (Vectorized Exact)**
   Dipakai kalau target ≤ 15.000.000 dan estimasi memori bitset masih dalam budget. DP klasik subset-sum dengan bitset 64-bit per word, ditelusuri balik lewat array `parent[]` untuk merekonstruksi solusi. Cepat & RAM rendah untuk target kecil.

4. **L4 — Hybrid Tail-Table + Pruned DFS**
   Strategi default untuk kasus berat (target besar, bukan superincreasing, bukan target kecil):
   - Array dipecah jadi `prefix` (di-DFS) dan `tail` (m elemen terakhir, ditabulasi lewat *meet-in-the-middle* dengan Gray-code incremental supaya O(2^m) bukan O(m·2^m)).
   - DFS di prefix dengan pruning: suffix-sum bound, oracle kardinalitas `is_cardinality_feasible` (binary search O(log n)), dan heuristik urutan cabang (pilih include/exclude yang rem-nya lebih dekat ke setengah suffix-sum).
   - Saat mencapai `cutoff`, sisa target dicari lewat binary search di tail-table.
   - **v1**: berhenti di sini.
   - **v2 menambah**: memoisasi `Block-Bound` per `(i, rem)` (lihat Bagian 4) + root-split paralel multi-thread untuk mode `findone` pada instance besar.

5. **L7 — Independent Verifier**
   Setelah solusi ditemukan (versi manapun), diverifikasi ulang secara independen: indeks valid, tidak ada duplikat, nilai cocok dengan array asli, dan jumlah persis sama dengan target.

6. **L8 — Zero-Sum Swap Extractor**
   Untuk mode `findall`/`zero`: dari satu solusi dasar, cari swap kombinatorial jarak ≤4 dengan delta sama (elemen masuk vs keluar) untuk menghasilkan puluhan-ratusan variasi solusi tambahan dengan sangat cepat, tanpa DFS ulang penuh.

---

## 6. Kompilasi (MinGW-w64 GCC)

Jalankan di PowerShell/Command Prompt pada folder proyek:

**CLI:**
```
g++ -O3 -std=c++17 dumbsspCli.cpp -o dumbsspCli.exe -lpsapi
```

**GUI (Win32 Desktop):**
```
g++ -O3 -std=c++17 dumbsspGui.cpp -o dumbsspGui.exe -mwindows -lcomctl32 -lcomdlg32 -lpsapi -luser32 -lgdi32
```

---

## 7. Sintaks & Penggunaan CLI

```
.\dumbsspCli.exe "<elements_list>" <target> [mode] [max_solutions] [time_limit_ms]
```

| Parameter | Keterangan |
|---|---|
| `<elements_list>` | String bilangan bulat positif dipisah koma/spasi, mis. `"10, 20, 30, 40"` |
| `<target>` | Target sum (T) yang dicari |
| `[mode]` | Mode pencarian (default: `findone`) — lihat Bagian 8 |
| `[max_solutions]` | Maksimum witness solusi disimpan di memori untuk `findall` (default: 5000) |
| `[time_limit_ms]` | Batas waktu komputasi dalam ms (default: 120000 / 2 menit). Gunakan `0`/`none`/`unlimited`/`inf`/`infinite` untuk tanpa batas waktu |

---

## 8. Deskripsi & Contoh Tiap Mode

### [A] `findone` — Solusi Tunggal Tercepat
Berhenti (*early exit*) segera setelah satu witness valid ditemukan. Ultra cepat (mikrodetik–beberapa ms bahkan untuk N ≥ 80).
```
.\dumbsspCli.exe "75872066500, 68562112744, 19339160129, 24156275768, 11525390137" 100000000000 findone
```

### [B] `zero` — Find All via L8 Zero-Sum Swap
Cari satu witness dasar, lalu ekstrak puluhan–ratusan variasi lewat swap kombinatorial jarak ≤4. Sangat cepat, tidak melalui overhead exhaustive search.
```
.\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 zero
```

### [C] `dfs` — Find All via Exhaustive DFS
Menelusuri seluruh ruang pencarian tanpa early-return — menjamin 100% seluruh kombinasi valid ditemukan. Skalanya mengikuti densitas & kardinalitas problem.
```
.\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 dfs
```

### [D] `count` — Count All
Menghitung jumlah pasti kombinasi valid tanpa menyimpan witness individual — hemat RAM, pakai counter 128-bit.
```
.\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 count
```

### [E] `decision` — Pure Existence / SAT Check
Menjawab murni SATISFIABLE vs PROVABLY UNSAT dengan overhead paling rendah, lewat filter obstruksi modular/kardinalitas awal atau early hit.
```
.\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 decision
```

---

## 9. Matriks Perbandingan Mode

| Mode | Kecepatan | Kelengkapan Solusi | Peak RAM (kasus normal) |
|---|---|---|---|
| `findone` | Ultra cepat | 1 witness | ≤ 20 MB (v1) / bervariasi (v2, lihat Bagian 4) |
| `zero` | Sangat cepat | Ratusan varian | ≤ 20 MB |
| `dfs` | Komprehensif | 100% seluruh solusi | ≤ 20 MB |
| `count` | Cepat–sedang | Hitungan eksak (integer) | Minimal |
| `decision` | Instan | Status SAT/UNSAT | Minimal |

> Catatan: kolom RAM di tabel ini mengacu ke perilaku umum. Untuk mode `findone` di v2 pada instance besar/flat/target tinggi, lihat Bagian 4 — RAM bisa jauh melebihi 20 MB.

---

*Dokumentasi ini disusun berdasarkan analisis kode sumber `dumbsspCore.hpp` dan hasil benchmark aktual kedua versi solver.*

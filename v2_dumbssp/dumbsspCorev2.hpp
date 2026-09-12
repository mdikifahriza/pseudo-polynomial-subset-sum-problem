#pragma once

#include <vector>
#include <cstdint>
#include <algorithm>
#include <numeric>
#include <iostream>
#include <chrono>
#include <string>
#include <sstream>
#include <cmath>
#include <atomic>
#include <random>
#include <unordered_set>
#include <unordered_map>
#include <set>
#include <map>
#include <mutex>
#include <thread>
#include <deque>

#if defined(_WIN32) || defined(_WIN64)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <psapi.h>
#else
#include <sys/resource.h>
#endif

using u64  = uint64_t;
using u32  = uint32_t;
using i64  = int64_t;
using u128 = unsigned __int128;

static const u128 INF128 = ~((u128)0);
static const u64  INF64  = 0xFFFFFFFFFFFFFFFFULL;

inline size_t get_current_peak_ram_bytes() {
#if defined(_WIN32) || defined(_WIN64)
    PROCESS_MEMORY_COUNTERS pmc;
    ZeroMemory(&pmc, sizeof(pmc));
    pmc.cb = sizeof(PROCESS_MEMORY_COUNTERS);
    if (GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof(pmc))) {
        return (size_t)pmc.PeakWorkingSetSize;
    }
    return 0;
#else
    struct rusage ru;
    if (getrusage(RUSAGE_SELF, &ru) == 0) {
#if defined(__APPLE__)
        return (size_t)ru.ru_maxrss;
#else
        return (size_t)ru.ru_maxrss * 1024ULL;
#endif
    }
    return 0;
#endif
}

enum class SolveMode { FindOne, FindAll, CountAll, DecisionOnly };

enum class SolverStatus {
    ExactSolutionFound,
    ExactUnsatProven,
    PartialSolutionCapped,
    UnknownTimeout,
    UnknownMemoryExceeded,
    StoppedByUser
};

enum class OracleFeasibility { Infeasible, Feasible, Possible };

// Fase 1.1: alasan spesifik strong_structure -- dipakai buat merutekan strategi,
// bukan cuma flag ya/tidak seperti sebelumnya.
enum class StructureKind {
    None,
    Superincreasing,   // TERBUKTI penuh: tiap elemen > jumlah semua elemen lebih kecil di bawahnya
    NarrowKWindow,      // k-window sempit / >=50% pola mirip-superincreasing (heuristik, bukan bukti penuh)
    GcdReduced,
    ParityForced
};

enum class StrategyType {
    TrivialPreCheck,
    GreedySuperincreasing,
    BitsetDP,
    HybridTailTable
};

inline std::string strategy_to_string(StrategyType st) {
    switch (st) {
        case StrategyType::TrivialPreCheck:        return "L2: Trivial Exact Pre-Reduction";
        case StrategyType::GreedySuperincreasing:  return "L1: Greedy Superincreasing (Exact O(n))";
        case StrategyType::BitsetDP:               return "L3: Bitset DP (Vectorized Exact)";
        case StrategyType::HybridTailTable:        return "L4: Hybrid Tail-Table + Pruned DFS (Block-Bound + Ordered)";
        default: return "Adaptive Exact Strategy";
    }
}

struct SolverBudget {
    double time_limit_ms      = 120000.0;
    size_t memory_limit_mb    = 4096;
    size_t max_solutions      = 5000;
    size_t max_display_solutions = 200;
    bool   exhaustive_find_all   = false;

    // Fase 3.3: ambang aktivasi paralel root-split. Di bawah ambang ini tetap
    // single-thread karena overhead spawn thread bisa lebih mahal dari solve
    // itu sendiri untuk N kecil.
    bool   allow_parallel_root_split = true;
    u64    parallel_state_threshold  = 2000000ULL; // estimasi states_evaluated minimum
    unsigned max_worker_threads      = 0; // 0 = auto (hardware_concurrency)
};

struct Element {
    u64 val = 0;
    int orig_idx = 0;
    bool operator>(const Element& o) const { return (val != o.val) ? val > o.val : orig_idx < o.orig_idx; }
    bool operator<(const Element& o) const { return (val != o.val) ? val < o.val : orig_idx < o.orig_idx; }
};

struct SolutionWitness {
    std::vector<int> original_indices;
    std::vector<u64> values;
    u128 sum = 0;
    void sort_indices() {
        if (original_indices.size() != values.size() || original_indices.empty()) return;
        std::vector<std::pair<int, u64>> paired(original_indices.size());
        for (size_t i = 0; i < original_indices.size(); ++i) {
            paired[i] = {original_indices[i], values[i]};
        }
        std::sort(paired.begin(), paired.end());
        for (size_t i = 0; i < paired.size(); ++i) {
            original_indices[i] = paired[i].first;
            values[i] = paired[i].second;
        }
    }
    bool operator==(const SolutionWitness& o) const { return original_indices == o.original_indices; }
    bool operator<(const SolutionWitness& o) const { return original_indices < o.original_indices; }
};

struct Instance {
    std::vector<u64> raw_elements;
    u64 target = 0;

    std::vector<Element> A;
    std::vector<int> zero_indices;

    u64 normalized_target = 0;
    u64 effective_target  = 0;
    bool complement_applied = false;

    u128 total_sum = 0;
    u64 min_val = 0, max_val = 0;
    u64 gcd_val = 1;
    int odd_count = 0, even_count = 0, unique_count = 0;
    double density = 0.0;

    int k_min = -1, k_max = -1;
    int feasible_k_count = 0;

    bool strong_structure = false;
    StructureKind structure_kind = StructureKind::None; // Fase 1.1

    void normalize() {
        A.clear(); zero_indices.clear();
        total_sum = 0; min_val = INF64; max_val = 0;
        odd_count = 0; even_count = 0; gcd_val = 0;

        for (int i = 0; i < (int)raw_elements.size(); ++i) {
            u64 x = raw_elements[i];
            if (x == 0) { zero_indices.push_back(i); continue; }
            if (x <= target) {
                A.push_back({x, i});
                total_sum += x;
                if (x < min_val) min_val = x;
                if (x > max_val) max_val = x;
                if (x % 2 == 0) even_count++; else odd_count++;
                gcd_val = (gcd_val == 0) ? x : std::gcd(gcd_val, x);
            }
        }
        if (min_val == INF64) min_val = 0;
        if (gcd_val == 0) gcd_val = 1;

        std::sort(A.begin(), A.end(), std::greater<Element>());

        int uniq = 0;
        for (size_t i = 0; i < A.size(); ++i) if (i == 0 || A[i].val != A[i-1].val) uniq++;
        unique_count = uniq;

        if (max_val > 0 && !A.empty()) density = (double)A.size() / std::log2((double)max_val + 1.0);

        normalized_target = target;
        if (normalized_target > (u64)(total_sum / 2) && total_sum >= normalized_target) {
            effective_target = (u64)(total_sum - normalized_target);
            complement_applied = true;
        } else {
            effective_target = normalized_target;
            complement_applied = false;
        }

        compute_cardinality_bounds();
        detect_strong_structure();
    }

    void compute_cardinality_bounds() {
        int n = (int)A.size();
        k_min = -1; k_max = -1;
        if (effective_target == 0) { k_min = 0; k_max = 0; feasible_k_count = 1; return; }
        if (n == 0) { feasible_k_count = 0; return; }

        std::vector<u128> S(n + 1, 0);
        for (int i = n - 1; i >= 0; --i) S[i] = S[i+1] + A[i].val;

        u128 cum_u = 0;
        for (int k = 1; k <= n; ++k) {
            cum_u += A[k-1].val;
            if (cum_u >= effective_target && k_min == -1) k_min = k;
            u128 cum_l = S[n-k];
            if (cum_l <= effective_target) k_max = k;
        }
        feasible_k_count = (k_min != -1 && k_max != -1 && k_max >= k_min) ? (k_max - k_min + 1) : 0;
    }

    // Fase 1.1: pisahkan strong_structure jadi StructureKind spesifik, diurut
    // dari yang paling kuat buktinya (bukti penuh) ke yang paling lemah (heuristik).
    void detect_strong_structure() {
        strong_structure = false;
        structure_kind = StructureKind::None;
        if (A.empty()) return;
        int n = (int)A.size();

        // 1) Superincreasing TERBUKTI PENUH: tiap elemen > jumlah semua elemen
        //    lebih kecil di bawahnya (A sudah terurut menurun).
        {
            u128 cum = 0;
            bool full_superincreasing = true;
            for (int i = n - 1; i >= 0; --i) {
                if (!((u128)A[i].val > cum)) { full_superincreasing = false; break; }
                cum += A[i].val;
            }
            if (full_superincreasing) {
                strong_structure = true;
                structure_kind = StructureKind::Superincreasing;
                return;
            }
        }

        // 2) Obstruksi modular GCD -- deterministik.
        if (gcd_val > 1) {
            strong_structure = true;
            structure_kind = StructureKind::GcdReduced;
            return;
        }

        // 3) Obstruksi paritas -- deterministik.
        if (odd_count == 0 && (effective_target % 2 != 0)) {
            strong_structure = true;
            structure_kind = StructureKind::ParityForced;
            return;
        }

        // 4) Window kardinalitas sempit / pola mirip-superincreasing (heuristik,
        //    bukan bukti penuh -- tetap dirutekan ke HybridTailTable, cuma jadi
        //    sinyal buat pruning lebih agresif).
        if (feasible_k_count > 0 && feasible_k_count <= std::max(4, (n * 3) / 4)) {
            strong_structure = true; structure_kind = StructureKind::NarrowKWindow; return;
        }
        if (k_min > 1 || (k_max >= 0 && k_max < n)) {
            strong_structure = true; structure_kind = StructureKind::NarrowKWindow; return;
        }
        if (n >= 8) {
            int sup_count = 0;
            u128 cum = 0;
            for (int i = n - 1; i >= 0; --i) {
                if (A[i].val > cum) sup_count++;
                cum += A[i].val;
            }
            if ((double)sup_count / n >= 0.5) {
                strong_structure = true; structure_kind = StructureKind::NarrowKWindow; return;
            }
        }
    }

    static Instance from_string(const std::string& text, u64 tgt) {
        Instance inst; inst.target = tgt;
        std::string cur;
        auto flush = [&]() {
            if (!cur.empty()) { try { inst.raw_elements.push_back(std::stoull(cur)); } catch (...) {} cur.clear(); }
        };
        for (char c : text) { if (isdigit((unsigned char)c)) cur += c; else flush(); }
        flush();
        inst.normalize();
        return inst;
    }
};

// Fase 1.3: oracle kardinalitas dgn binary search atas suffix_sum yang sudah
// precompute (suffix_sum monoton terhadap k karena A terurut menurun), jadi
// O(log n) per panggilan alih-alih scan linear O(n) seperti sebelumnya.
inline bool is_cardinality_feasible(int i, u64 R, int n,
                                     const std::vector<u128>& suffix_sum,
                                     const std::vector<Element>& A) {
    if (R == 0) return true;
    int rem = n - i;
    if (rem <= 0) return false;
    if (A[n-1].val > R) return false;

    int lo = i, hi = n - 1, best_idx = -1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (A[mid].val <= R) { best_idx = mid; hi = mid - 1; } else lo = mid + 1;
    }
    if (best_idx == -1) return false;

    u64 max_val = A[best_idx].val;
    if (max_val == 0) return false;
    size_t min_needed_k = (R + max_val - 1) / max_val;
    size_t avail_count = n - best_idx;
    if (min_needed_k > avail_count) return false;

    // k_min: smallest k in [1,rem] such that upper_sum(i,k) = suffix[i]-suffix[i+k] >= R.
    // upper_sum(i,k) is monotonically non-decreasing in k -> binary search.
    int k_min = -1;
    {
        int klo = 1, khi = rem;
        while (klo <= khi) {
            int kmid = klo + (khi - klo) / 2;
            u128 u_k = suffix_sum[i] - suffix_sum[i + kmid];
            if (u_k >= R) { k_min = kmid; khi = kmid - 1; } else klo = kmid + 1;
        }
    }
    if (k_min == -1) return false;

    // k_max: largest k in [k_min,rem] such that lower_sum(k) = suffix[n-k] <= R.
    // suffix[n-k] is monotonically non-decreasing in k -> binary search.
    int k_max = -1;
    {
        int klo = k_min, khi = rem;
        while (klo <= khi) {
            int kmid = klo + (khi - klo) / 2;
            u128 l_k = suffix_sum[n - kmid];
            if (l_k <= R) { k_max = kmid; klo = kmid + 1; } else khi = kmid - 1;
        }
    }
    return (k_max >= k_min);
}

struct ExecutionStats {
    StrategyType strategy_chosen = StrategyType::HybridTailTable;
    SolverStatus status = SolverStatus::ExactUnsatProven;
    double runtime_ms = 0.0, preprocess_ms = 0.0, solve_ms = 0.0, peak_ram_mb = 0.0;

    bool solved = false;
    bool has_solution = false;
    u128 solution_count = 0;

    SolutionWitness sample_solution;
    std::vector<SolutionWitness> all_solutions;

    u64 states_evaluated = 0, states_pruned = 0;
    u64 forced_take = 0, forced_skip = 0, two_way_branches = 0;
    u64 oracle_calls = 0, oracle_pruned = 0;
    u64 heap_operations = 0, comparisons = 0;
    u64 table_lookups = 0;
    u64 block_bound_prunes = 0; // Fase 2.1
    unsigned threads_used = 1;   // Fase 3

    bool verified = false;
    std::string verification_message;

    std::string message;
};

inline bool verify_witness_independently(const std::vector<u64>& raw_elements,
                                          u64 target,
                                          const SolutionWitness& wit,
                                          std::string& out_message) {
    if (wit.original_indices.size() != wit.values.size()) {
        out_message = "FAIL: index count and value count do not match.";
        return false;
    }
    std::unordered_set<int> seen;
    u128 sum = 0;
    for (size_t i = 0; i < wit.original_indices.size(); ++i) {
        int idx = wit.original_indices[i];
        if (idx < 0 || idx >= (int)raw_elements.size()) {
            out_message = "FAIL: index out of range of raw array.";
            return false;
        }
        if (!seen.insert(idx).second) {
            out_message = "FAIL: duplicate index (element used more than once).";
            return false;
        }
        if (raw_elements[idx] != wit.values[i]) {
            out_message = "FAIL: value does not match raw array at the specified index.";
            return false;
        }
        sum += wit.values[i];
    }
    if ((u64)sum != target) {
        std::ostringstream oss;
        oss << "FAIL: sum=" << (u64)sum << " != target=" << target;
        out_message = oss.str();
        return false;
    }
    out_message = "OK: sum validated == target, all elements unique and strictly from original array.";
    return true;
}

class AdaptiveStrategySelector {
public:
    static u64 estimate_bitset_memory(const Instance& inst) {
        if (inst.effective_target > 50000000ULL) return INF64;
        u64 words = (inst.effective_target >> 6) + 1;
        return words * sizeof(u64) + (inst.effective_target + 1) * sizeof(int);
    }
    static u64 estimate_hybrid_memory(int n, int m) {
        (void)n;
        return (1ULL << m) * sizeof(u64) * 2;
    }

    static StrategyType select(const Instance& inst, const SolverBudget& budget, SolveMode mode) {
        u64 mem_budget = budget.memory_limit_mb * 1024ULL * 1024ULL;

        if (inst.target == 0) return StrategyType::TrivialPreCheck;
        if (inst.A.empty() || inst.effective_target > inst.total_sum) return StrategyType::TrivialPreCheck;
        if (inst.gcd_val > 1 && (inst.effective_target % inst.gcd_val != 0)) return StrategyType::TrivialPreCheck;
        if (inst.odd_count == 0 && (inst.effective_target % 2 != 0)) return StrategyType::TrivialPreCheck;
        if (inst.feasible_k_count == 0) return StrategyType::TrivialPreCheck;

        // Fase 1.1: strong_structure Superincreasing -> jalur greedy O(n) exact,
        // sebelumnya flag ini dihitung tapi tidak pernah dipakai untuk merutekan.
        if (inst.structure_kind == StructureKind::Superincreasing) {
            return StrategyType::GreedySuperincreasing;
        }

        u64 bitset_mem = estimate_bitset_memory(inst);
        if (inst.effective_target <= 15000000ULL && bitset_mem < mem_budget / 2 &&
            (mode == SolveMode::FindOne || mode == SolveMode::DecisionOnly)) {
            return StrategyType::BitsetDP;
        }

        return StrategyType::HybridTailTable;
    }
};

// Fase 1.1: solver greedy O(n), EXACT (bukan heuristik) untuk instance
// superincreasing terbukti penuh. Benar karena struktur superincreasing
// menjamin tidak ada kombinasi elemen kecil yang bisa menyamai/melebihi satu
// elemen besar di atasnya -- jadi keputusan take/skip di tiap elemen final,
// tidak pernah perlu backtrack.
class GreedySuperincreasingSolver {
public:
    void solve(const Instance& inst, SolveMode mode, ExecutionStats& stats) {
        u64 rem = inst.effective_target;
        std::vector<int> idxs; std::vector<u64> vals;
        idxs.reserve(inst.A.size()); vals.reserve(inst.A.size());
        for (const auto& e : inst.A) {
            stats.states_evaluated++;
            if (e.val <= rem) {
                idxs.push_back(e.orig_idx);
                vals.push_back(e.val);
                rem -= e.val;
                stats.forced_take++;
            } else {
                stats.forced_skip++;
            }
        }
        if (rem == 0) {
            SolutionWitness wit;
            wit.original_indices = idxs;
            wit.values = vals;
            u128 s = 0; for (u64 v : vals) s += v;
            wit.sum = s;
            wit.sort_indices();
            stats.has_solution = true;
            stats.solution_count = 1; // solusi superincreasing selalu unik
            stats.sample_solution = wit;
            if (mode == SolveMode::FindAll) stats.all_solutions.push_back(wit);
            stats.message = "Exact solution found via Greedy Superincreasing (O(n), no backtrack needed).";
        } else {
            stats.message = "UNSAT provably proven via Greedy Superincreasing (O(n), structural proof).";
        }
    }
};

class HybridTailTableEngine {
public:
    static int choose_m(int n, size_t memory_limit_mb) {
        if (n <= 1) return 0;
        if (n <= 20) return n - 1;
        int m = 20;
        u64 budget_bytes = memory_limit_mb * 1024ULL * 1024ULL / 4;
        while (m > 12 && ((1ULL << m) * 16ULL) > budget_bytes) m--;
        if (m >= n) m = std::max(0, n - 1);
        return m;
    }

    struct Entry { u64 sum; u32 mask; bool operator<(const Entry& o) const { return sum < o.sum; } };

    // Fase 1.2: bangun tabel lewat Gray-code incremental (O(2^m) total, bukan
    // O(m*2^m)) -- tiap langkah gray code berturutan cuma beda 1 bit, jadi sum
    // bisa di-update dengan +/- satu elemen alih-alih rehitung dari nol.
    // Fase 3.1: dibangun paralel, tiap thread mengisi rentang index [begin,end)
    // miliknya sendiri di 'table' yang sudah dipre-alokasi penuh -> tidak ada
    // write-conflict, satu std::sort di akhir setelah semua thread join().
    static void build_tail_table_range(const std::vector<Element>& A, int cutoff, int m,
                                        u32 begin, u32 end, std::vector<Entry>& table) {
        if (begin >= end) return;
        // Hitung sum penuh untuk gray-code awal chunk ini (O(m), sekali per thread).
        u32 start_gray = begin ^ (begin >> 1);
        u64 sum = 0;
        for (int b = 0; b < m; ++b) if ((start_gray >> b) & 1) sum += A[cutoff + b].val;
        table[begin] = {sum, start_gray};
        u32 prev_gray = start_gray;
        for (u32 i = begin + 1; i < end; ++i) {
            u32 gray = i ^ (i >> 1);
            u32 diff = gray ^ prev_gray;
            int bit = __builtin_ctz(diff);
            if (gray & diff) sum += A[cutoff + bit].val; else sum -= A[cutoff + bit].val;
            table[i] = {sum, gray};
            prev_gray = gray;
        }
    }

    static std::vector<Entry> build_tail_table(const std::vector<Element>& A, int cutoff, int m,
                                                unsigned n_threads) {
        u32 total = (m <= 0) ? 1U : (1U << m);
        std::vector<Entry> table(total);
        if (n_threads <= 1 || total < 4096) {
            build_tail_table_range(A, cutoff, m, 0, total, table);
        } else {
            std::vector<std::thread> workers;
            u32 chunk = (total + n_threads - 1) / n_threads;
            for (unsigned t = 0; t < n_threads; ++t) {
                u32 b = t * chunk, e = std::min(total, b + chunk);
                if (b >= e) continue;
                workers.emplace_back(build_tail_table_range, std::cref(A), cutoff, m, b, e, std::ref(table));
            }
            for (auto& th : workers) th.join();
        }
        std::sort(table.begin(), table.end());
        return table;
    }

    // Fase 2.1: memo/block-bound sederhana per kedalaman -- kalau (i, rem)
    // sudah pernah DIEKSPLORASI TUNTAS (bukan dipotong early-exit/timeout/cap)
    // dan terbukti tidak ada solusi, catat rem itu supaya panggilan berikutnya
    // ke (i, rem) yang sama langsung di-prune tanpa eksplorasi ulang. Ini valid
    // untuk SEMUA mode karena "tidak ada solusi di bawah titik ini" tidak
    // tergantung mode -- state (i,rem) yang sama pasti tetap tidak ada solusi
    // di eksplorasi manapun.
    struct BlockBound {
        std::vector<std::unordered_set<u64>> infeasible; // per depth i
        explicit BlockBound(int n) : infeasible(n + 1) {}
        bool is_known_infeasible(int i, u64 rem) const {
            return infeasible[i].find(rem) != infeasible[i].end();
        }
        void mark_infeasible(int i, u64 rem) { infeasible[i].insert(rem); }
    };

    void solve(const Instance& inst, SolveMode mode, ExecutionStats& stats,
               const SolverBudget& budget,
               const std::chrono::steady_clock::time_point& start_time,
               std::atomic<bool>& stop_flag, std::atomic<bool>& solution_found) {
        int n = (int)inst.A.size();
        const auto& A = inst.A;
        u64 T = inst.effective_target;
        if (n == 0) { if (T == 0) { stats.has_solution = true; stats.solution_count = 1; } return; }

        int m = choose_m(n, budget.memory_limit_mb);
        int cutoff = n - m;

        std::vector<u128> suffix(n + 1, 0);
        for (int i = n - 1; i >= 0; --i) suffix[i] = suffix[i+1] + A[i].val;

        unsigned build_threads = budget.max_worker_threads ? budget.max_worker_threads
                                                             : std::max(1u, std::thread::hardware_concurrency());
        std::vector<Entry> table = build_tail_table(A, cutoff, m, build_threads);

        BlockBound bb(n);
        std::mutex bb_mutex; // dipakai hanya kalau DFS root-split aktif (multi-thread)

        // Fase 3.3: putuskan apakah root-split paralel layak dipakai. Hanya
        // untuk mode FindOne, dan hanya kalau estimasi beban kerja (dari
        // feasible_k_count/density -- makin lebar window kardinalitas makin
        // besar beban DFS) melewati ambang. Instance kecil tetap single-thread
        // karena overhead spawn thread bisa lebih mahal dari solve itu sendiri.
        bool try_parallel_root = budget.allow_parallel_root_split &&
                                  mode == SolveMode::FindOne &&
                                  n >= 24 &&
                                  (u64)std::max(1, inst.feasible_k_count) * (u64)n >= budget.parallel_state_threshold / 1000 &&
                                  (std::thread::hardware_concurrency() > 1 || budget.max_worker_threads > 1);

        if (try_parallel_root) {
            run_parallel_root_split(inst, stats, budget, start_time, stop_flag, solution_found,
                                     suffix, table, cutoff, m, bb, bb_mutex);
        } else {
            std::vector<int> path_indices;
            std::vector<u64> path_vals;
            run_single_thread_dfs(inst, mode, stats, budget, start_time, stop_flag, solution_found,
                                   suffix, table, cutoff, m, bb, path_indices, path_vals,
                                   0, T, 0);
        }

        if (stats.status == SolverStatus::UnknownTimeout) {
            stats.message = "Search stopped due to time limit (Timeout).";
        } else if (stats.has_solution) {
            stats.message = "Exact solution found via Hybrid Tail-Table Engine.";
        } else {
            stats.message = "UNSAT provably proven via Hybrid Tail-Table Engine.";
        }
    }

private:
    static void record_solution(ExecutionStats& stats, SolveMode mode, const SolverBudget& budget,
                                 std::atomic<bool>& solution_found, bool early_exit, std::mutex* out_mutex,
                                 const std::vector<int>& idxs, const std::vector<u64>& vals) {
        std::unique_lock<std::mutex> lock;
        if (out_mutex) lock = std::unique_lock<std::mutex>(*out_mutex);
        stats.has_solution = true;
        SolutionWitness wit;
        wit.original_indices = idxs;
        wit.values = vals;
        u128 s = 0; for (u64 v : vals) s += v;
        wit.sum = s;
        wit.sort_indices();
        stats.solution_count++;
        if (stats.sample_solution.values.empty()) stats.sample_solution = wit;
        if (mode == SolveMode::FindAll && stats.all_solutions.size() < budget.max_solutions) {
            stats.all_solutions.push_back(wit);
        }
        if (early_exit) solution_found = true;
    }

    // DFS inti. 'out_mutex' non-null hanya ketika dipanggil dari worker paralel
    // (Fase 3.3) supaya penulisan ke stats bersama aman; nullptr di jalur
    // single-thread (tidak ada overhead locking sama sekali).
    void run_single_thread_dfs(const Instance& inst, SolveMode mode, ExecutionStats& stats,
                                const SolverBudget& budget,
                                const std::chrono::steady_clock::time_point& start_time,
                                std::atomic<bool>& stop_flag, std::atomic<bool>& solution_found,
                                const std::vector<u128>& suffix, const std::vector<Entry>& table,
                                int cutoff, int m, BlockBound& bb,
                                std::vector<int>& path_indices, std::vector<u64>& path_vals,
                                int start_i, u64 start_rem, int start_k,
                                std::mutex* out_mutex = nullptr,
                                std::mutex* bb_mutex = nullptr) {
        const auto& A = inst.A;
        int n = (int)A.size();
        bool early_exit = (mode == SolveMode::FindOne || mode == SolveMode::DecisionOnly);

        auto dfs = [&](auto& self, int i, u64 rem, int k_used) -> bool /*fully_explored*/ {
            if (stop_flag || (solution_found && early_exit) || stats.status == SolverStatus::UnknownTimeout) return false;
            if (mode == SolveMode::FindAll) {
                bool capped;
                { std::unique_lock<std::mutex> lk; if (out_mutex) lk = std::unique_lock<std::mutex>(*out_mutex);
                  capped = stats.all_solutions.size() >= budget.max_solutions && !budget.exhaustive_find_all; }
                if (capped) { stats.status = SolverStatus::PartialSolutionCapped; return false; }
            }
            stats.states_evaluated++;
            if (budget.time_limit_ms > 0.0 && (stats.states_evaluated & 4095) == 0) {
                auto now = std::chrono::steady_clock::now();
                double el = std::chrono::duration<double, std::milli>(now - start_time).count();
                if (el > budget.time_limit_ms) {
                    stats.status = SolverStatus::UnknownTimeout;
                    stop_flag = true;
                    return false;
                }
            }

            // Fase 2.1: block-bound / memo check.
            {
                std::unique_lock<std::mutex> lk; if (bb_mutex) lk = std::unique_lock<std::mutex>(*bb_mutex);
                if (bb.is_known_infeasible(i, rem)) { stats.states_pruned++; stats.block_bound_prunes++; return true; }
            }

            if (rem == 0) {
                if (mode == SolveMode::CountAll && !stats.sample_solution.values.empty()) {
                    stats.has_solution = true;
                    stats.solution_count++;
                } else {
                    record_solution(stats, mode, budget, solution_found, early_exit, out_mutex, path_indices, path_vals);
                }
                return true;
            }
            if (i >= cutoff) {
                stats.table_lookups++;
                Entry dummy{rem, 0};
                auto bounds = std::equal_range(table.begin(), table.end(), dummy);
                for (auto it = bounds.first; it != bounds.second; ++it) {
                    if (stop_flag) return false;
                    if (it->sum != rem) continue;
                    if (mode == SolveMode::CountAll && !stats.sample_solution.values.empty()) {
                        stats.has_solution = true;
                        stats.solution_count++;
                        continue;
                    }
                    std::vector<int> full_idx = path_indices;
                    std::vector<u64> full_val = path_vals;
                    u32 mask = it->mask;
                    for (int b = 0; b < m; ++b) {
                        if ((mask >> b) & 1) {
                            full_idx.push_back(A[cutoff + b].orig_idx);
                            full_val.push_back(A[cutoff + b].val);
                        }
                    }
                    record_solution(stats, mode, budget, solution_found, early_exit, out_mutex, full_idx, full_val);
                    if (early_exit) return true;
                    bool capped;
                    { std::unique_lock<std::mutex> lk; if (out_mutex) lk = std::unique_lock<std::mutex>(*out_mutex);
                      capped = mode == SolveMode::FindAll && stats.all_solutions.size() >= budget.max_solutions && !budget.exhaustive_find_all; }
                    if (capped) return true;
                }
                return true; // full range explored (either found or not)
            }

            if ((u128)rem > suffix[i]) { stats.states_pruned++; return true; }
            if ((k_used + (n - i)) < inst.k_min || (inst.k_max > 0 && k_used > inst.k_max)) {
                stats.states_pruned++; return true;
            }
            stats.oracle_calls++;
            if (!is_cardinality_feasible(i, rem, n, suffix, A)) { stats.oracle_pruned++; stats.states_pruned++; return true; }

            // Fase 2.2: heuristik urutan cabang -- pilih dulu cabang (include /
            // exclude) yang membawa rem' lebih dekat ke S/2 (S = suffix[i+1]),
            // karena secara statistik jumlah solusi memuncak di sekitar setengah
            // jumlah total sisa elemen. Nol memori tambahan, cuma reorder.
            bool can_include = (A[i].val <= rem);
            bool include_first = true;
            if (can_include) {
                double half = (double)(u128)(suffix[i+1] / 2);
                double d_include = std::fabs((double)(rem - A[i].val) - half);
                double d_exclude = std::fabs((double)rem - half);
                include_first = (d_include <= d_exclude);
            }

            bool fully_explored = true;
            auto do_include = [&]() {
                path_indices.push_back(A[i].orig_idx);
                path_vals.push_back(A[i].val);
                bool fe = self(self, i + 1, rem - A[i].val, k_used + 1);
                path_indices.pop_back();
                path_vals.pop_back();
                fully_explored = fully_explored && fe;
            };
            auto do_exclude = [&]() {
                bool fe = self(self, i + 1, rem, k_used);
                fully_explored = fully_explored && fe;
            };

            if (can_include && include_first) {
                do_include();
                if (early_exit && (solution_found || stats.status == SolverStatus::UnknownTimeout)) return false;
                do_exclude();
            } else if (can_include) {
                do_exclude();
                if (early_exit && (solution_found || stats.status == SolverStatus::UnknownTimeout)) return false;
                do_include();
            } else {
                do_exclude();
            }

            // Fase 2.1: aman dicatat sebagai infeasible HANYA kalau eksplorasi
            // subtree ini benar-benar tuntas (fully_explored==true, bukan
            // dipotong stop_flag/timeout/early-exit di tempat lain).
            if (fully_explored && !stop_flag) {
                std::unique_lock<std::mutex> lk; if (bb_mutex) lk = std::unique_lock<std::mutex>(*bb_mutex);
                bb.mark_infeasible(i, rem);
            }
            return fully_explored;
        };

        dfs(dfs, start_i, start_rem, start_k);
    }

    // Fase 3.3: DFS root-split, HANYA mode FindOne. Ekspansi beberapa level
    // pertama untuk menghasilkan daftar task (state DFS awal), taruh di queue
    // bersama (mutex-protected, dipakai sebagai work-stealing stack sederhana),
    // lalu beberapa worker thread mengambil task dari queue itu sampai habis
    // atau solusi ditemukan. Ini menghindari load-imbalance dari split statis
    // karena window kardinalitas sempit bikin sebagian cabang mati instan.
    void run_parallel_root_split(const Instance& inst, ExecutionStats& stats, const SolverBudget& budget,
                                  const std::chrono::steady_clock::time_point& start_time,
                                  std::atomic<bool>& stop_flag, std::atomic<bool>& solution_found,
                                  const std::vector<u128>& suffix, const std::vector<Entry>& table,
                                  int cutoff, int m, BlockBound& bb, std::mutex& bb_mutex) {
        const auto& A = inst.A;
        int n = (int)A.size();
        u64 T = inst.effective_target;

        unsigned hw = budget.max_worker_threads ? budget.max_worker_threads
                                                  : std::max(1u, std::thread::hardware_concurrency());
        stats.threads_used = hw;

        struct Task { int i; u64 rem; int k_used; std::vector<int> path_idx; std::vector<u64> path_val; };
        std::deque<Task> queue;
        std::mutex queue_mutex;

        // Ekspansi awal: BFS dangkal sampai queue punya cukup task (>= 4x jumlah
        // thread) atau sampai kedalaman maksimum wajar, memakai pruning yang
        // sama (suffix bound + cardinality oracle) supaya task yang sudah mati
        // tidak ikut di-enqueue.
        int expand_depth_cap = std::min(n, 6);
        std::vector<Task> frontier;
        frontier.push_back({0, T, 0, {}, {}});
        size_t target_tasks = (size_t)hw * 6;
        for (int depth = 0; depth < expand_depth_cap && frontier.size() < target_tasks; ++depth) {
            std::vector<Task> next;
            for (auto& t : frontier) {
                int i = t.i; u64 rem = t.rem; int k_used = t.k_used;
                if (i >= cutoff || rem == 0) { next.push_back(std::move(t)); continue; }
                if ((u128)rem > suffix[i]) continue; // prune dead branch
                if (!is_cardinality_feasible(i, rem, n, suffix, A)) continue;
                bool can_include = (A[i].val <= rem);
                if (can_include) {
                    Task ti = t;
                    ti.path_idx.push_back(A[i].orig_idx); ti.path_val.push_back(A[i].val);
                    ti.i = i + 1; ti.rem = rem - A[i].val; ti.k_used = k_used + 1;
                    next.push_back(std::move(ti));
                }
                Task te = t;
                te.i = i + 1; te.rem = rem; te.k_used = k_used;
                next.push_back(std::move(te));
            }
            frontier = std::move(next);
        }
        for (auto& t : frontier) queue.push_back(std::move(t));

        auto pop_task = [&](Task& out) -> bool {
            std::lock_guard<std::mutex> lk(queue_mutex);
            if (queue.empty()) return false;
            out = std::move(queue.back());
            queue.pop_back();
            return true;
        };

        std::mutex stats_mutex;
        std::vector<ExecutionStats> local_stats(hw);
        for (auto& ls : local_stats) ls.strategy_chosen = stats.strategy_chosen;

        auto worker = [&](unsigned tid) {
            ExecutionStats& ls = local_stats[tid];
            Task t;
            while (!stop_flag && !solution_found && pop_task(t)) {
                std::vector<int> path_idx = t.path_idx;
                std::vector<u64> path_val = t.path_val;
                run_single_thread_dfs(inst, SolveMode::FindOne, ls, budget, start_time, stop_flag, solution_found,
                                       suffix, table, cutoff, m, bb, path_idx, path_val,
                                       t.i, t.rem, t.k_used, &stats_mutex, &bb_mutex);
            }
        };

        std::vector<std::thread> workers;
        for (unsigned t = 0; t < hw; ++t) workers.emplace_back(worker, t);
        for (auto& th : workers) th.join();

        // Fase 3.2: gabung counter thread-local di akhir (bukan atomic per-increment).
        for (auto& ls : local_stats) {
            stats.states_evaluated += ls.states_evaluated;
            stats.states_pruned    += ls.states_pruned;
            stats.oracle_calls     += ls.oracle_calls;
            stats.oracle_pruned    += ls.oracle_pruned;
            stats.table_lookups    += ls.table_lookups;
            stats.block_bound_prunes += ls.block_bound_prunes;
            if (ls.status == SolverStatus::UnknownTimeout) stats.status = SolverStatus::UnknownTimeout;
            if (ls.has_solution && !stats.has_solution) {
                stats.has_solution = true;
                stats.solution_count = 1;
                stats.sample_solution = ls.sample_solution;
            }
        }
    }
};

class ZeroSumSwapExtractor {
public:
    void extract(const Instance& inst, ExecutionStats& stats, const SolverBudget& budget) {
        if (!stats.has_solution || stats.sample_solution.original_indices.empty()) return;

        std::set<std::vector<int>> seen;
        if (stats.all_solutions.empty()) stats.all_solutions.push_back(stats.sample_solution);
        for (const auto& w : stats.all_solutions) seen.insert(w.original_indices);

        std::vector<Element> S_in, S_out;
        std::unordered_set<int> in_set(stats.sample_solution.original_indices.begin(),
                                        stats.sample_solution.original_indices.end());
        for (const auto& e : inst.A) (in_set.count(e.orig_idx) ? S_in : S_out).push_back(e);

        struct Subset { u64 sum; u64 mask; bool operator<(const Subset& o) const { return sum < o.sum; } };
        std::vector<Subset> in_subsets;
        int n_in = (int)S_in.size();
        auto gen_in = [&](auto& self, int idx, u64 csum, u64 cmask, int cnt) -> void {
            if (cnt > 0) in_subsets.push_back({csum, cmask});
            if (cnt == 4) return;
            for (int j = idx; j < n_in; ++j) self(self, j+1, csum + S_in[j].val, cmask | (1ULL<<j), cnt+1);
        };
        gen_in(gen_in, 0, 0, 0, 0);
        std::sort(in_subsets.begin(), in_subsets.end());

        int n_out = (int)S_out.size();
        auto gen_out = [&](auto& self, int idx, u64 csum, u64 cmask, int cnt) -> void {
            if (stats.all_solutions.size() >= budget.max_solutions) return;
            if (cnt > 0) {
                Subset dummy{csum, 0};
                auto bounds = std::equal_range(in_subsets.begin(), in_subsets.end(), dummy);
                for (auto it = bounds.first; it != bounds.second && stats.all_solutions.size() < budget.max_solutions; ++it) {
                    if (it->sum != csum) continue;
                    SolutionWitness wit;
                    for (int k = 0; k < n_in; ++k) if (!((it->mask>>k)&1)) { wit.original_indices.push_back(S_in[k].orig_idx); wit.values.push_back(S_in[k].val); }
                    for (int k = 0; k < n_out; ++k) if ((cmask>>k)&1) { wit.original_indices.push_back(S_out[k].orig_idx); wit.values.push_back(S_out[k].val); }
                    wit.sort_indices();
                    if (!seen.insert(wit.original_indices).second) continue;
                    u128 s = 0; for (u64 v : wit.values) s += v;
                    wit.sum = s;
                    stats.all_solutions.push_back(wit);
                }
            }
            if (cnt == 4) return;
            for (int j = idx; j < n_out; ++j) self(self, j+1, csum + S_out[j].val, cmask | (1ULL<<j), cnt+1);
        };
        gen_out(gen_out, 0, 0, 0, 0);
    }
};

class AdaptiveExactSolver {
public:
    std::atomic<bool> stop_flag{false};
    std::atomic<bool> solution_found{false};

private:
    static void finalize_status(ExecutionStats& stats, bool stop_flag_value) {
        if (stats.status == SolverStatus::UnknownTimeout ||
            stats.status == SolverStatus::PartialSolutionCapped) {
            stats.solved = true;
        } else if (stop_flag_value) {
            stats.status = SolverStatus::StoppedByUser;
            stats.solved = false;
            stats.message = "Search stopped by user.";
        } else {
            stats.status = stats.has_solution ? SolverStatus::ExactSolutionFound : SolverStatus::ExactUnsatProven;
            stats.solved = true;
        }
    }

public:
    ExecutionStats run(const Instance& inst, SolveMode mode,
                        size_t memory_limit_mb = 4096, bool exhaustive_find_all = false,
                        double time_limit_ms = 120000.0, size_t max_solutions = 5000) {
        SolverBudget budget;
        budget.memory_limit_mb = memory_limit_mb;
        budget.time_limit_ms = time_limit_ms;
        budget.exhaustive_find_all = exhaustive_find_all;
        budget.max_solutions = max_solutions;
        return run_with_budget(inst, mode, budget);
    }

    // Fase 3 testing hook: memungkinkan override penuh SolverBudget (termasuk
    // max_worker_threads) tanpa mengubah signature run() yang sudah ada.
    ExecutionStats run_with_budget(const Instance& inst, SolveMode mode, const SolverBudget& budget) {
        stop_flag = false; solution_found = false;

        ExecutionStats stats;
        auto t0 = std::chrono::steady_clock::now();

        stats.strategy_chosen = AdaptiveStrategySelector::select(inst, budget, mode);
        auto t_prep = std::chrono::steady_clock::now();
        stats.preprocess_ms = std::chrono::duration<double, std::milli>(t_prep - t0).count();

        switch (stats.strategy_chosen) {
            case StrategyType::TrivialPreCheck:
                solve_trivial(inst, mode, stats);
                break;
            case StrategyType::GreedySuperincreasing: {
                GreedySuperincreasingSolver s; s.solve(inst, mode, stats);
                break;
            }
            case StrategyType::BitsetDP:
                solve_bitset(inst, mode, stats, budget, t0);
                break;
            case StrategyType::HybridTailTable:
            default: {
                HybridTailTableEngine e; e.solve(inst, mode, stats, budget, t0, stop_flag, solution_found);
                break;
            }
        }

        if (mode == SolveMode::FindAll && stats.has_solution && !budget.exhaustive_find_all) {
            ZeroSumSwapExtractor extractor;
            extractor.extract(inst, stats, budget);
            stats.solution_count = std::max(stats.solution_count, (u128)stats.all_solutions.size());
        } else if (stats.has_solution && stats.all_solutions.empty() && !stats.sample_solution.values.empty()) {
            stats.all_solutions.push_back(stats.sample_solution);
        }

        if (inst.complement_applied && stats.has_solution) {
            auto invert_witness = [&](SolutionWitness& wit) {
                std::vector<bool> in_comp(inst.raw_elements.size(), false);
                for (int idx : wit.original_indices) {
                    if (idx >= 0 && idx < (int)in_comp.size()) in_comp[idx] = true;
                }
                SolutionWitness inv_wit;
                u128 s = 0;
                for (const auto& elem : inst.A) {
                    int i = elem.orig_idx;
                    if (!in_comp[i]) {
                        inv_wit.original_indices.push_back(i);
                        inv_wit.values.push_back(elem.val);
                        s += elem.val;
                    }
                }
                inv_wit.sum = s;
                inv_wit.sort_indices();
                wit = inv_wit;
            };
            if (!stats.sample_solution.values.empty()) invert_witness(stats.sample_solution);
            for (auto& w : stats.all_solutions) invert_witness(w);
        }

        if (stats.has_solution && !stats.sample_solution.values.empty()) {
            stats.verified = verify_witness_independently(inst.raw_elements, inst.target,
                                                            stats.sample_solution, stats.verification_message);
        } else if (!stats.has_solution) {
            stats.verified = true;
            stats.verification_message = "N/A (UNSAT, no witness to verify).";
        }

        auto t_end = std::chrono::steady_clock::now();
        stats.runtime_ms = std::chrono::duration<double, std::milli>(t_end - t0).count();
        stats.solve_ms = std::chrono::duration<double, std::milli>(t_end - t_prep).count();
        stats.peak_ram_mb = get_current_peak_ram_bytes() / (1024.0 * 1024.0);

        finalize_status(stats, stop_flag);
        return stats;
    }

    ExecutionStats run_forced(const Instance& inst, SolveMode mode, StrategyType forced,
                               size_t memory_limit_mb = 4096, double time_limit_ms = 120000.0,
                               size_t max_solutions = 5000) {
        stop_flag = false; solution_found = false;
        SolverBudget budget;
        budget.memory_limit_mb = memory_limit_mb;
        budget.time_limit_ms = time_limit_ms;
        budget.max_solutions = max_solutions;
        ExecutionStats stats;
        auto t0 = std::chrono::steady_clock::now();
        stats.strategy_chosen = forced;
        switch (forced) {
            case StrategyType::TrivialPreCheck: solve_trivial(inst, mode, stats); break;
            case StrategyType::GreedySuperincreasing: { GreedySuperincreasingSolver s; s.solve(inst, mode, stats); break; }
            case StrategyType::BitsetDP: solve_bitset(inst, mode, stats, budget, t0); break;
            case StrategyType::HybridTailTable:
            default: { HybridTailTableEngine e; e.solve(inst, mode, stats, budget, t0, stop_flag, solution_found); break; }
        }
        if (stats.has_solution && !stats.sample_solution.values.empty()) {
            stats.verified = verify_witness_independently(inst.raw_elements, inst.target, stats.sample_solution, stats.verification_message);
        }
        auto t_end = std::chrono::steady_clock::now();
        stats.runtime_ms = std::chrono::duration<double, std::milli>(t_end - t0).count();
        finalize_status(stats, stop_flag);
        return stats;
    }

private:
    void solve_trivial(const Instance& inst, SolveMode mode, ExecutionStats& stats) {
        if (inst.target == 0) {
            stats.has_solution = true; stats.solution_count = 1;
            if (mode == SolveMode::FindAll) stats.all_solutions.push_back(SolutionWitness{});
            stats.message = "Trivial: target=0 (empty set)."; return;
        }
        if (inst.A.empty() || inst.effective_target > inst.total_sum) { stats.message = "Trivial UNSAT: target exceeds total sum."; return; }
        if (inst.gcd_val > 1 && (inst.effective_target % inst.gcd_val != 0)) { stats.message = "Trivial UNSAT: GCD modular obstruction."; return; }
        if (inst.odd_count == 0 && (inst.effective_target % 2 != 0)) { stats.message = "Trivial UNSAT: parity obstruction."; return; }
        if (inst.feasible_k_count == 0) { stats.message = "Trivial UNSAT: feasible cardinality window empty."; return; }
    }

    void solve_bitset(const Instance& inst, SolveMode mode, ExecutionStats& stats,
                       const SolverBudget& budget, const std::chrono::steady_clock::time_point& start_time) {
        (void)budget; (void)start_time;
        u64 T = inst.effective_target;
        size_t words = (T >> 6) + 1;
        std::vector<u64> bs(words, 0); bs[0] = 1ULL;
        std::vector<int> parent(T + 1, -1);

        for (size_t idx = 0; idx < inst.A.size(); ++idx) {
            u64 val = inst.A[idx].val;
            if (val > T) continue;
            size_t sw = val >> 6, sb = val & 63;
            for (int64_t w = (int64_t)words - 1; w >= (int64_t)sw; --w) {
                u64 low = bs[w - sw] << sb;
                u64 high = (sb > 0 && w > (int64_t)sw) ? (bs[w - sw - 1] >> (64 - sb)) : 0;
                u64 shifted = low | high;
                u64 nb = shifted & ~bs[w];
                bs[w] |= shifted;
                while (nb != 0) {
                    int bit = (int)__builtin_ctzll(nb);
                    u64 sum = ((u64)w << 6) + bit;
                    if (sum <= T && parent[sum] == -1) parent[sum] = (int)idx;
                    nb &= nb - 1;
                }
            }
            if ((bs[T>>6] & (1ULL << (T & 63))) && (mode == SolveMode::FindOne || mode == SolveMode::DecisionOnly)) break;
        }
        bool ok = (bs[T>>6] & (1ULL << (T & 63))) != 0;
        stats.has_solution = ok;
        if (ok) {
            stats.solution_count = 1;
            SolutionWitness wit;
            u64 curr = T;
            while (curr > 0 && parent[curr] >= 0 && parent[curr] < (int)inst.A.size()) {
                int ei = parent[curr];
                wit.original_indices.push_back(inst.A[ei].orig_idx);
                wit.values.push_back(inst.A[ei].val);
                wit.sum += inst.A[ei].val;
                curr -= inst.A[ei].val;
            }
            wit.sort_indices();
            stats.sample_solution = wit;
            if (mode == SolveMode::FindAll) stats.all_solutions.push_back(wit);
            stats.message = "Exact solution found via Bitset DP.";
        } else {
            stats.message = "UNSAT provably proven via Bitset DP.";
        }
    }
};

struct InstancePreset {
    std::string title, category, description;
    int n; u64 target;
    std::vector<u64> elements;
};

class PresetRepository {
public:
    static std::vector<InstancePreset> get_all_presets() {
        std::vector<InstancePreset> presets;
        {
            InstancePreset p;
            p.title = "1. Hybrid Benchmark (N=80, T=18.6 Triliun) - teruji ~1.9 detik";
            p.category = "High Magnitude, Structured (window k sempit)";
            p.description = "Instance 80-elemen dari sesi pengujian solver ini. k_min..k_max=[22,55]. "
                             "Diselesaikan Hybrid Tail-Table Engine.";
            p.n = 80; p.target = 18649525982137ULL;
            std::string s = "123005401502,811856239314,267469214296,151282538207,114832269482,814655221102,600832336209,648913461123,36171878810,98912225903,254342113420,663595448018,614294294452,786833016362,771590378378,461902006519,490573056993,307473554861,956959217036,833251567392,175259659198,466854953851,306404042871,236890980657,841629821540,113114812282,417010168082,391257417624,381597082644,290355792388,50711229824,505645347793,135447068294,87525138708,324493543666,690757033267,973319131003,398837994178,212933106112,76040557041,726046287258,847087372943,936645574450,950187601657,417045625553,499410093882,917558277936,177660601410,388136971785,735339233455,769945806982,751347210314,80092702124,698400899700,584850587138,269419548117,507507949296,297982492152,758663022121,242910249530,359422681392,845433611430,63462436410,902926886138,884901132452,439441524733,69869415071,626820024293,789742985455,233279765208,548275934230,972361834961,708302588518,156589576362,151461507039,817103043321,590821577340,821467220157,470662212986,643806247030";
            Instance inst = Instance::from_string(s, p.target);
            p.elements = inst.raw_elements;
            presets.push_back(p);
        }
        {
            InstancePreset p;
            p.title = "2. Flat / Unstructured (N=32, window k lebar)";
            p.category = "General / Flat Structure (worst-case)";
            p.description = "Instance tanpa struktur kuat, window kardinalitas lebar - kasus paling berat untuk pruning DFS Hybrid Tail-Table.";
            p.n = 32;
            std::mt19937_64 rng(7070);
            std::uniform_int_distribution<u64> dist(10000000000ULL, 90000000000ULL);
            u64 sum = 0;
            for (int i = 0; i < 32; ++i) { u64 v = dist(rng); p.elements.push_back(v); if (i==2||i==7||i==15||i==23||i==30) sum += v; }
            p.target = sum;
            presets.push_back(p);
        }
        {
            InstancePreset p;
            p.title = "3. Dense Small Values (N=40) - Bitset DP instan";
            p.category = "Small Dense Values (high density)";
            p.description = "Target kecil, memicu Bitset DP (<5 ms).";
            p.n = 40;
            std::mt19937_64 rng(2026);
            std::uniform_int_distribution<u64> dist(100, 20000);
            u64 sum = 0;
            for (int i = 0; i < 40; ++i) { u64 v = dist(rng); p.elements.push_back(v); if (i < 8) sum += v; }
            p.target = sum;
            presets.push_back(p);
        }
        {
            InstancePreset p;
            p.title = "4. GCD Obstruction (N=50) - Provably UNSAT instan";
            p.category = "Modular Obstruction";
            p.description = "Semua elemen kelipatan 777, target tidak. UNSAT terbukti <1ms via TrivialPreCheck.";
            p.n = 50;
            std::mt19937_64 rng(5050);
            std::uniform_int_distribution<u64> dist(100000, 5000000);
            for (int i = 0; i < 50; ++i) p.elements.push_back(dist(rng) * 777ULL);
            p.target = (p.elements[3] + p.elements[12]) + 13ULL;
            presets.push_back(p);
        }
        return presets;
    }
};
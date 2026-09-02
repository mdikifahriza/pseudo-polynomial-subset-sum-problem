// bench_single.cpp
//
// Runs exactly ONE solver call per process invocation and prints ONE CSV row,
// then exits. This is deliberate: get_current_peak_ram_bytes() on POSIX reads
// getrusage().ru_maxrss, which is monotonic non-decreasing for the LIFETIME of
// the process. Running many configurations in a single long-lived process (as
// the earlier harness did) means later measurements contaminate earlier ones.
// One process per data point sidesteps that entirely.
//
// Usage:
//   bench_single <n> <bits> <card_frac_x1000> <seed> <mode> <forced>
//                <time_limit_ms> <max_solutions>
//
//   n               : number of elements
//   bits            : element values drawn uniformly from [2^(bits-1), 2^bits - 1]
//   card_frac_x1000 : hidden-solution cardinality as (card_frac_x1000/1000)*n,
//                     clamped to [1, n]. Controls how "wide" the search is.
//   seed            : RNG seed (vary this for repetitions at the same config)
//   mode            : 0=FindOne 1=FindAll
//   forced          : 0=Auto(router) 1=ForceBitsetDP 2=ForceHybridTailTable
//   time_limit_ms   : wall-clock budget passed to the solver
//   max_solutions   : only relevant when mode=FindAll
//
// Output columns (CSV, one line, no header -- header is emitted by the driver):
//   n,bits,card,seed,mode,forced,time_limit_ms,max_solutions,strategy_chosen,
//   runtime_ms,peak_ram_mb,states_evaluated,table_lookups,solution_count,
//   all_solutions_size,status,verified

#include "dumbsspCore.hpp"
#include <cstdio>
#include <cstdlib>
#include <random>
#include <string>

int main(int argc, char** argv) {
    if (argc < 9) {
        fprintf(stderr, "usage: %s n bits card_frac_x1000 seed mode forced time_limit_ms max_solutions\n", argv[0]);
        return 2;
    }
    int n                = std::atoi(argv[1]);
    int bits             = std::atoi(argv[2]);
    int card_frac_x1000  = std::atoi(argv[3]);
    unsigned long long seed = std::strtoull(argv[4], nullptr, 10);
    int mode_i           = std::atoi(argv[5]);
    int forced_i         = std::atoi(argv[6]);
    double time_limit_ms = std::atof(argv[7]);
    size_t max_solutions = (size_t)std::strtoull(argv[8], nullptr, 10);

    if (bits < 1) bits = 1;
    if (bits > 62) bits = 62; // keep target sum comfortably inside u64/i64 arithmetic used downstream

    std::mt19937_64 rng(seed);
    u64 hi = (1ULL << bits) - 1ULL;
    u64 lo = (bits >= 2) ? (1ULL << (bits - 1)) : 1ULL;
    std::uniform_int_distribution<u64> dist(lo, hi);

    std::vector<u64> elems((size_t)n);
    for (int i = 0; i < n; ++i) elems[i] = dist(rng);

    int card = (int)std::llround((card_frac_x1000 / 1000.0) * n);
    if (card < 1) card = 1;
    if (card > n) card = n;

    std::vector<int> idx(n);
    for (int i = 0; i < n; ++i) idx[i] = i;
    std::shuffle(idx.begin(), idx.end(), rng);
    u64 target = 0;
    for (int i = 0; i < card; ++i) target += elems[idx[i]];

    Instance inst;
    inst.raw_elements = elems;
    inst.target = target;
    inst.normalize();

    SolveMode mode = (mode_i == 1) ? SolveMode::FindAll : SolveMode::FindOne;

    ExecutionStats stats;
    if (forced_i == 0) {
        AdaptiveExactSolver solver;
        // run(inst, mode, memory_limit_mb, exhaustive_find_all, time_limit_ms, max_solutions)
        // NOTE: current signature has no worker-count parameter - Trivial/Bitset/
        // HybridTailTable are all single-threaded (see dumbsspCore.hpp for why).
        stats = solver.run(inst, mode, 4096, false, time_limit_ms, max_solutions);
    } else {
        StrategyType forced = (forced_i == 1) ? StrategyType::BitsetDP : StrategyType::HybridTailTable;
        AdaptiveExactSolver solver;
        stats = solver.run_forced(inst, mode, forced, 4096, time_limit_ms, max_solutions);
        // NOTE: run_forced() does not invoke the L8 swap extractor at all, so
        // all_solutions will be empty for forced runs even under FindAll. We
        // report that faithfully rather than papering over it.
    }

    // Independent re-check here too (belt-and-braces on top of stats.verified,
    // which is already computed inside run()/run_forced()).
    bool independently_ok = true;
    if (stats.has_solution && !stats.sample_solution.values.empty()) {
        std::string msg;
        independently_ok = verify_witness_independently(inst.raw_elements, inst.target,
                                                          stats.sample_solution, msg);
    }
    for (const auto& w : stats.all_solutions) {
        if (!independently_ok) break;
        std::string msg;
        if (!verify_witness_independently(inst.raw_elements, inst.target, w, msg)) independently_ok = false;
    }

    // "verified" is only a meaningful signal when the solver actually reached a
    // conclusive answer (SAT, with a witness re-checked independently; or a
    // genuinely exhaustive UNSAT). For TIMEOUT/CAPPED, run()/run_forced() still
    // set stats.verified=true vacuously (no witness to check), which would
    // silently count as "verified OK" if we are not careful -- print -1 (N/A)
    // instead so downstream aggregation never mixes "inconclusive" with
    // "confirmed correct".
    int verified_out;
    if (stats.status == SolverStatus::UnknownTimeout || stats.status == SolverStatus::StoppedByUser ||
        stats.status == SolverStatus::PartialSolutionCapped) {
        verified_out = -1;
    } else {
        verified_out = (independently_ok && stats.verified) ? 1 : 0;
    }

    const char* status =
        (stats.status == SolverStatus::UnknownTimeout) ? "TIMEOUT" :
        // NOTE: this harness never issues an external cancellation, so a
        // StoppedByUser observed here would, by elimination, only be possible
        // via some other path setting stop_flag. As of the current
        // dumbsspCore.hpp, run()/run_forced() give UnknownTimeout/
        // PartialSolutionCapped priority over stop_flag when deciding the
        // final status (see AdaptiveExactSolver::finalize_status), so a
        // genuine internal timeout is no longer mislabeled as StoppedByUser.
        // We keep this fallback mapping anyway as defense-in-depth.
        (stats.status == SolverStatus::StoppedByUser) ? "TIMEOUT" :
        (stats.status == SolverStatus::PartialSolutionCapped) ? "CAPPED" :
        (stats.has_solution ? "SAT" : "UNSAT");

    printf("%d,%d,%d,%llu,%d,%d,%.1f,%zu,%s,%.4f,%.4f,%llu,%llu,%llu,%zu,%s,%d\n",
           n, bits, card, seed, mode_i, forced_i, time_limit_ms, max_solutions,
           strategy_to_string(stats.strategy_chosen).c_str(),
           stats.runtime_ms, stats.peak_ram_mb,
           (unsigned long long)stats.states_evaluated,
           (unsigned long long)stats.table_lookups,
           (unsigned long long)stats.solution_count,
           stats.all_solutions.size(),
           status,
           verified_out);
    return 0;
}

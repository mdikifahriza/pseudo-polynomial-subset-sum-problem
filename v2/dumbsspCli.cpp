#include "dumbsspCorev2.hpp"
#include <iostream>
#include <iomanip>
#include <string>
#include <vector>
#include <algorithm>

void print_help_menu(const char* prog_name) {
    std::cout << "========================================================================================================\n";
    std::cout << "                         DUMB SSP SOLVER - COMMAND LINE INTERFACE (CLI)                                 \n";
    std::cout << "========================================================================================================\n\n";
    std::cout << "USAGE:\n";
    std::cout << "  " << prog_name << " \"<elements_list>\" <target> [mode] [max_solutions] [time_limit_ms]\n\n";
    std::cout << "ARGUMENTS:\n";
    std::cout << "  <elements_list>  : Comma or space separated positive integers (e.g. \"10, 20, 30, 40, 50\").\n";
    std::cout << "  <target>         : Target integer value (T).\n";
    std::cout << "  [mode]           : Search mode / strategy policy:\n";
    std::cout << "                     1. findone             : Find single exact solution witness and halt (Default / Fastest).\n";
    std::cout << "                     2. findall-zero / zero : Find solution and extract variations via L8 Zero-Sum Swap.\n";
    std::cout << "                     3. findall-dfs  / dfs  : Exhaustive 100% full-tree DFS search for all solutions.\n";
    std::cout << "                     4. countall     / count: Count total number of valid subset combinations.\n";
    std::cout << "                     5. decision     / decide: Pure decision problem test (SATISFIABLE or PROVABLY UNSAT).\n";
    std::cout << "  [max_solutions]  : Max witness solutions stored in memory for FindAll (Default: 5000).\n";
    std::cout << "  [time_limit_ms]  : Execution time limit in milliseconds (Default: 120000.0 ms / 2 minutes).\n";
    std::cout << "                     Use 0 / none / unlimited / inf for NO time limit (run until solved).\n\n";
    std::cout << "EXAMPLES:\n";
    std::cout << "  1. Find One Mode (Fast Single Witness):\n";
    std::cout << "     " << prog_name << " \"123, 456, 789, 101112\" 579 findone\n\n";
    std::cout << "  2. Find All Mode via Zero-Sum Swap (Fast Multi-Solution):\n";
    std::cout << "     " << prog_name << " \"10, 20, 30, 40, 50, 60\" 60 zero\n\n";
    std::cout << "  3. Find All Mode via Exhaustive DFS (100% Complete):\n";
    std::cout << "     " << prog_name << " \"10, 20, 30, 40, 50, 60\" 60 dfs\n\n";
    std::cout << "  4. Count All Mode (Total Exact Count):\n";
    std::cout << "     " << prog_name << " \"10, 20, 30, 40, 50, 60\" 60 count\n\n";
    std::cout << "  5. Decision Mode (Existence Proof):\n";
    std::cout << "     " << prog_name << " \"10, 20, 30, 40, 50, 60\" 60 decision\n";
    std::cout << "========================================================================================================\n";
}

void print_solution_details(const std::string& label, const Instance& inst, const ExecutionStats& stats, SolveMode mode, bool exhaustive) {
    std::cout << "\n================================================================================" << std::endl;
    std::cout << "               DUMB SSP SOLVER - TERMINAL EXECUTION REPORT                      " << std::endl;
    std::cout << "================================================================================" << std::endl;
    std::cout << "Test Label         : " << label << std::endl;
    std::cout << "Elements Count (N) : " << inst.raw_elements.size() << " raw (" << inst.A.size() << " positive active)" << std::endl;
    std::cout << "Target Value (T)   : " << inst.target << std::endl;
    std::cout << "Total Sum (Sigma)  : " << (u64)inst.total_sum << std::endl;
    std::cout << "Effective Target   : " << inst.effective_target << (inst.complement_applied ? " (Dual Complement Active)" : "") << std::endl;
    std::cout << "Feasible K Range   : [" << inst.k_min << " .. " << inst.k_max << "] (" << inst.feasible_k_count << " cardinality window)" << std::endl;
    std::cout << "GCD Value          : " << inst.gcd_val << std::endl;
    std::cout << "Density Score      : " << std::fixed << std::setprecision(4) << inst.density << std::endl;
    std::cout << "Structure Profile  : " << (inst.strong_structure ? "STRONG STRUCTURE" : "FLAT / NON-STRUCTURAL") << std::endl;
    std::cout << "--------------------------------------------------------------------------------" << std::endl;
    std::cout << "Strategy Chosen    : " << strategy_to_string(stats.strategy_chosen) << std::endl;
    
    std::string mode_str = "Find One (Early Exit)";
    if (mode == SolveMode::FindAll) mode_str = exhaustive ? "Find All (Exhaustive DFS Traversal)" : "Find All (L8 Zero-Sum Swap Fast Expansion)";
    else if (mode == SolveMode::CountAll) mode_str = "Count All (Total Combinations Counter)";
    else if (mode == SolveMode::DecisionOnly) mode_str = "Decision Only (Existence SAT Proof)";
    std::cout << "Solve Mode         : " << mode_str << std::endl;

    std::cout << "Status             : " << (stats.solved ? (stats.has_solution ? "SOLVED (SATISFIABLE)" : "PROVABLY UNSAT") : "FAILED / TIMEOUT") << std::endl;
    std::cout << "Total Runtime      : " << std::fixed << std::setprecision(4) << stats.runtime_ms << " ms (Preprocess: " << stats.preprocess_ms << " ms, Solve: " << stats.solve_ms << " ms)" << std::endl;
    std::cout << "States Evaluated   : " << stats.states_evaluated << std::endl;
    std::cout << "States Pruned      : " << stats.states_pruned << std::endl;
    std::cout << "Oracle Calls/Prune : " << stats.oracle_calls << " / " << stats.oracle_pruned << std::endl;
    std::cout << "Table Lookups      : " << stats.table_lookups << std::endl;
    std::cout << "Peak RAM Memory    : " << std::fixed << std::setprecision(2) << stats.peak_ram_mb << " MB" << std::endl;
    std::cout << "L7 Verifier        : " << (stats.verified ? "[100% INDEPENDENTLY VERIFIED VALID]" : "[VERIFICATION FAILED]") << std::endl;
    std::cout << "L7 Detail Message  : " << stats.verification_message << std::endl;
    std::cout << "Engine Message     : " << stats.message << std::endl;
    std::cout << "--------------------------------------------------------------------------------" << std::endl;

    if (stats.has_solution) {
        if (mode == SolveMode::FindOne) {
            std::cout << "Exact Solution Found (" << stats.sample_solution.values.size() << " elements):" << std::endl;
            std::cout << "Values : [";
            u64 sum = 0;
            for (size_t i = 0; i < stats.sample_solution.values.size(); ++i) {
                std::cout << stats.sample_solution.values[i];
                sum += stats.sample_solution.values[i];
                if (i + 1 < stats.sample_solution.values.size()) std::cout << ", ";
            }
            std::cout << "]" << std::endl;
            std::cout << "Indices: [";
            for (size_t i = 0; i < stats.sample_solution.original_indices.size(); ++i) {
                std::cout << stats.sample_solution.original_indices[i];
                if (i + 1 < stats.sample_solution.original_indices.size()) std::cout << ", ";
            }
            std::cout << "]" << std::endl;
            std::cout << "Sum Check: " << sum << " == Target " << inst.target << " (" << (sum == inst.target ? "EXACT MATCH 100% VALID" : "MISMATCH ERROR") << ")" << std::endl;
        } else if (mode == SolveMode::DecisionOnly) {
            std::cout << "DECISION RESULT    : SATISFIABLE (YES, AT LEAST ONE SOLUTION EXISTS)" << std::endl;
            std::cout << "Witness Solution   : " << stats.sample_solution.values.size() << " elements -> Sum = " << inst.target << std::endl;
        } else if (mode == SolveMode::FindAll) {
            std::cout << "Total Solutions Counted: " << (u64)stats.solution_count << std::endl;
            std::cout << "Total Solutions Stored : " << stats.all_solutions.size() << std::endl;
            size_t disp = std::min(stats.all_solutions.size(), (size_t)30);
            for (size_t idx = 0; idx < disp; ++idx) {
                const auto& sol = stats.all_solutions[idx];
                u64 sum = 0;
                std::cout << "  #" << std::setw(3) << (idx + 1) << " (" << std::setw(2) << sol.values.size() << " elements): [";
                for (size_t i = 0; i < sol.values.size(); ++i) {
                    std::cout << sol.values[i];
                    sum += sol.values[i];
                    if (i + 1 < sol.values.size()) std::cout << ", ";
                }
                std::cout << "] -> Sum = " << sum << std::endl;
            }
            if (stats.all_solutions.size() > disp) {
                std::cout << "  ... (" << (stats.all_solutions.size() - disp) << " more solutions stored in memory)" << std::endl;
            }
        } else if (mode == SolveMode::CountAll) {
            std::cout << "TOTAL EXACT SOLUTION COUNT: " << (u64)stats.solution_count << " valid subset combinations equal to " << inst.target << "." << std::endl;
        }
    } else {
        std::cout << "NO EXACT SUBSET FOUND (PROVABLY UNSAT)" << std::endl;
    }
    std::cout << "================================================================================\n" << std::endl;
}

int main(int argc, char* argv[]) {
    if (argc == 2 && (std::string(argv[1]) == "--help" || std::string(argv[1]) == "-h" || std::string(argv[1]) == "/?")) {
        print_help_menu(argv[0]);
        return 0;
    }

    if (argc < 3) {
        print_help_menu(argv[0]);
        std::cout << "\n[INFO]: Running automated built-in benchmark demo...\n\n";
        
        std::string default_elements = 
            "75872066500, 68562112744, 19339160129, 24156275768, 11525390137, 34580469918, "
            "87752813318, 25906232742, 20636790211, 47170921689, 84559604264, 23643831465, "
            "33227966252, 76687960064, 39654715033, 65528900292, 79579105284, 38705012015, "
            "20401157240, 23386976450, 31066475967, 59591231930, 54278830146, 11050175502, "
            "14436155101, 38734149918, 61482157040, 31440878278, 60036394637, 89364113560, "
            "13381395447, 54381459751";
        u64 default_target = 135205864112ULL;
        Instance inst = Instance::from_string(default_elements, default_target);
        AdaptiveExactSolver solver;
        ExecutionStats stats = solver.run(inst, SolveMode::FindOne, 4096, false, 120000.0, 5000);
        print_solution_details("Demo Default Dataset (32 Elements) [Find One]", inst, stats, SolveMode::FindOne, false);
        return 0;
    }

    std::string elem_arg = argv[1];
    u64 tgt_arg = std::strtoull(argv[2], nullptr, 10);
    Instance inst = Instance::from_string(elem_arg, tgt_arg);

    SolveMode mode = SolveMode::FindOne;
    bool exhaustive = false;

    if (argc >= 4) {
        std::string m = argv[3];
        std::transform(m.begin(), m.end(), m.begin(), ::tolower);

        if (m == "findone" || m == "1" || m == "one") {
            mode = SolveMode::FindOne;
            exhaustive = false;
        } else if (m == "findall-zero" || m == "zero" || m == "findall" || m == "all" || m == "2") {
            mode = SolveMode::FindAll;
            exhaustive = false;
        } else if (m == "findall-dfs" || m == "dfs" || m == "exhaustive" || m == "full" || m == "3") {
            mode = SolveMode::FindAll;
            exhaustive = true;
        } else if (m == "countall" || m == "count" || m == "4") {
            mode = SolveMode::CountAll;
            exhaustive = false;
        } else if (m == "decision" || m == "decide" || m == "5") {
            mode = SolveMode::DecisionOnly;
            exhaustive = false;
        } else {
            std::cerr << "[WARNING]: Mode '" << argv[3] << "' unrecognized, falling back to default 'findone'.\n";
        }
    }

    size_t max_solutions = (argc >= 5) ? (size_t)std::strtoull(argv[4], nullptr, 10) : 5000;
    double time_limit_ms = 120000.0;
    if (argc >= 6) {
        std::string tl = argv[5];
        std::string tl_lower = tl;
        std::transform(tl_lower.begin(), tl_lower.end(), tl_lower.begin(), ::tolower);
        if (tl_lower == "0" || tl_lower == "none" || tl_lower == "unlimited" || tl_lower == "inf" || tl_lower == "infinite") {
            time_limit_ms = 0.0; // <=0 berarti tanpa batas waktu (lihat dumbsspCore.hpp)
        } else {
            time_limit_ms = std::atof(argv[5]);
        }
    }

    AdaptiveExactSolver solver;
    ExecutionStats stats = solver.run(inst, mode, 4096, exhaustive, time_limit_ms, max_solutions);

    print_solution_details("CLI Execution Result", inst, stats, mode, exhaustive);
    return 0;
}
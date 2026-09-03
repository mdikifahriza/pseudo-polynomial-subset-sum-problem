========================================================================================================
                          DUMB SSP SOLVER — USER MANUAL & DOCUMENTATION
========================================================================================================

1. PROJECT ARCHITECTURE & FILE STRUCTURE
--------------------------------------------------------------------------------------------------------
- Core Solver Library    : dumbsspCore.hpp (Data Structures, ATRS L0-L8 Solvers, L7 Independent Verifier)
- Command Line Interface : dumbsspCli.cpp  -> dumbsspCli.exe (High-performance Terminal CLI Harness)
- Graphical User Interface: dumbsspGui.cpp  -> dumbsspGui.exe (Native Win32 Interactive Desktop Application)
- Benchmark Suite        : benchmark.txt   (20 Stepped Benchmark Datasets from N=5 up to N=100)
- Manual & Documentation : readme.txt      (This manual)

========================================================================================================
2. COMPILATION INSTRUCTIONS (MinGW-w64 GCC)
========================================================================================================
Open PowerShell or Command Prompt in the project folder and run:

a) To compile CLI Binary:
   g++ -O3 -std=c++17 dumbsspCli.cpp -o dumbsspCli.exe -lpsapi

b) To compile GUI Desktop Binary:
   g++ -O3 -std=c++17 dumbsspGui.cpp -o dumbsspGui.exe -mwindows -lcomctl32 -lcomdlg32 -lpsapi -luser32 -lgdi32

========================================================================================================
3. CLI COMMAND LINE SYNTAX & USAGE
========================================================================================================
Command Format:
  .\dumbsspCli.exe "<elements_list>" <target> [mode] [max_solutions] [time_limit_ms]

Parameters:
  - <elements_list>  : Comma or space separated string of positive integers (e.g., "10, 20, 30, 40").
  - <target>         : Positive integer target sum (T) to find.
  - [mode]           : Search mode / strategy policy (Optional, Default: findone):
                       * findone             : Single Solution Mode (Early-Exit, Fastest).
                       * findall-zero / zero : Find All via L8 Zero-Sum Swap (Fast, multi-variation).
                       * findall-dfs  / dfs  : Find All via Exhaustive Full DFS (100% Comprehensive).
                       * countall     / count: Count All Mode (Total Number of Valid Combinations).
                       * decision     / decide: Pure Decision Problem Test (SAT vs PROVABLY UNSAT).
  - [max_solutions]  : Max witness solutions stored in memory for FindAll (Optional, Default: 5000).
  - [time_limit_ms]  : Computation time limit in milliseconds (Optional, Default: 120000.0 ms / 2 mins).
                       Use 0 / none / unlimited / inf / infinite for NO time limit (run until solved).

========================================================================================================
4. DETAILED METHOD DESCRIPTIONS & EXAMPLES
========================================================================================================

--------------------------------------------------------------------------------------------------------
[A] MODE FIND ONE (Fast Single Witness)
--------------------------------------------------------------------------------------------------------
- Concept: Halts tree traversal immediately (Early Exit) upon finding the first valid subset witness.
- Complexity & Speed: Ultra-fast (microseconds to few milliseconds even for N >= 80).
- CLI Keyword: findone | 1 | one
- Example:
  .\dumbsspCli.exe "75872066500, 68562112744, 19339160129, 24156275768, 11525390137" 100000000000 findone

--------------------------------------------------------------------------------------------------------
[B] MODE FIND ALL VIA ZERO-SUM SWAP (L8 Fast Extractor)
--------------------------------------------------------------------------------------------------------
- Concept: Locates a base witness, then performs local combinatorial swaps of distance <= 4 with 
  equal deltas (Delta_in == Delta_out) to extract dozens to hundreds of valid solutions in < 1 ms.
- Complexity & Speed: Very fast, bypasses exhaustive search overhead.
- CLI Keyword: zero | findall-zero | findall | all | 2
- Example:
  .\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 zero

--------------------------------------------------------------------------------------------------------
[C] MODE FIND ALL VIA EXHAUSTIVE DFS (100% Full-Tree Search)
--------------------------------------------------------------------------------------------------------
- Concept: Traverses the full state-space search tree without early return, guaranteeing discovery 
  of 100% of all valid subset combinations.
- Complexity & Speed: Comprehensive; scales with total problem density and cardinality.
- CLI Keyword: dfs | findall-dfs | exhaustive | full | 3
- Example:
  .\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 dfs

--------------------------------------------------------------------------------------------------------
[D] MODE COUNT ALL (Total Combinations Counter)
--------------------------------------------------------------------------------------------------------
- Concept: Accurately counts the exact total number of subsets summing to target T without storing 
  individual witness arrays, consuming minimal RAM.
- Complexity & Speed: Fast to medium; uses 128-bit leaf counters.
- CLI Keyword: count | countall | 4
- Example:
  .\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 count

--------------------------------------------------------------------------------------------------------
[E] MODE DECISION (Pure Existence / SAT Check)
--------------------------------------------------------------------------------------------------------
- Concept: Solves the pure Boolean decision problem: SATISFIABLE or PROVABLY UNSAT with lowest overhead.
- Complexity & Speed: Instantaneous via early modular/cardinality obstruction filters or fast first hit.
- CLI Keyword: decision | decide | 5
- Example:
  .\dumbsspCli.exe "12, 18, 24, 6, 30, 36, 42" 60 decision

========================================================================================================
5. METHOD COMPARISON MATRIX
========================================================================================================
| CLI Mode Keyword  | Execution Speed | Solution Completeness | Peak RAM    |
|-------------------|-----------------|-----------------------|-------------|
| findone           | Ultra Fast      | 1 Solution Witness    | <= 20 MB    |
| zero              | Very Fast       | Hundreds of Variants  | <= 20 MB    |
| dfs               | Comprehensive   | 100% All Solutions    | <= 20 MB    |
| count             | Fast - Medium   | Exact Count (Integer) | Minimal     |
| decision          | Instantaneous   | SAT / UNSAT Status    | Minimal     |

========================================================================================================
                                     END OF USER MANUAL
========================================================================================================

================================================================================
ARXIV.ORG SUBMISSION METADATA & INSTRUCTIONS FOR DUMB SVP SOLVER PAPER
================================================================================

1. PAPER METADATA FOR WEB SUBMISSION FORM:
--------------------------------------------------------------------------------
Title:
An Adaptive Multi-Paradigm Exact Solver for the Subset Sum Problem via Memory-Bounded Tail-Table Memoization and Polynomial-Time Neighborhood Swap Extraction

Authors:
M. Diki Fahriza

Primary Category:
cs.DS (Computer Science - Data Structures and Algorithms)

Secondary Categories:
cs.DM (Computer Science - Discrete Mathematics)
math.OC (Mathematics - Optimization and Control)

ACM / MSC Classification (Optional):
G.2.1; F.2.2; 68W01

Comments:
8 pages, 2 figures, 7 tables. Implemented in pure native C++20.

License:
arXiv.org perpetual non-exclusive license (or CC BY 4.0)

Abstract:
The Subset Sum Problem (SSP) is a foundational NP-complete problem with widespread applications in cryptanalysis, integer programming, and algorithmic game theory. Although pseudo-polynomial dynamic programming and exponential Meet-in-the-Middle (MITM) algorithms exist, practical implementations face severe bottlenecks: symmetric MITM requires O(2^(N/2)) memory causing massive CPU cache thrashing when N >= 50, standard dynamic programming suffers from pseudo-polynomial space explosion on trillion-scale targets (T >= 10^12), and extracting thousands of solutions incurs an exponential O(K * 2^N) branch-and-bound penalty. In this paper, we introduce an Adaptive Multi-Paradigm Exact Solver (Dumb SVP Solver) engineered in native C++20. Our framework introduces three core contributions: (1) An Asymmetric Tail-Table Memoization Engine that fixes the precomputed tail depth to m = min(20, floor(N/2)), restricting table size to exactly 16.00 MB (2^20 entries) to achieve 100% CPU Level-3 (L3) cache residence while pruning 20 levels (10^6x) from the depth-first search tree; (2) A 64-bit Word-Parallel Vectorized Bitset Engine with bit-level backpointers that accelerates moderate target regimes (T <= 5 * 10^7) by 64x in sub-millisecond execution times (0.09 ms to 0.81 ms for N <= 80); and (3) A Polynomial-Time Zero-Sum Swap Extractor (L8) operating on local even-Hamming-distance perturbation manifolds, capable of harvesting over 5,000 distinct valid solutions in ~144 ms in O(k(N-k)) time. Across six benchmark suites comprising 10,000 randomized test instances verified by an independent black-box L7 verifier, the solver achieved a 100.00% solve rate, a 0.000% error rate, and an average runtime of 0.0802 ms per instance with a bounded memory footprint (<= 20.5 MB).

--------------------------------------------------------------------------------
2. INCLUDED FILES IN THIS PACKAGE:
--------------------------------------------------------------------------------
- main.tex                  : Complete master LaTeX manuscript (IEEEtran format).
- references.bib            : BibTeX database containing peer-reviewed citations.
- main.bbl                  : Pre-compiled bibliography required for arXiv automated build.
- README_ARXIV_METADATA.txt : Submission metadata and classification guide.
- arxiv_submission.zip      : Ready-to-upload ZIP package for arXiv / Overleaf.

================================================================================

"""
ATRS - Adaptive Target-Remainder Solver Package
"""
from .state import (
    Stats,
    SolverResult,
    SolverStatus,
    SearchMode,
    OracleStatus,
    OracleResult,
)
from .resource_guard import ResourceGuard, ResourceLimitExceeded
from .preprocess import parse_input, build_suffix_sum, build_suffix_gcd
from .scheduler import AdaptiveOracleManager
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
from .gui import ATRSApplication

__all__ = [
    "Stats",
    "SolverResult",
    "SolverStatus",
    "SearchMode",
    "OracleStatus",
    "OracleResult",
    "ResourceGuard",
    "ResourceLimitExceeded",
    "parse_input",
    "build_suffix_sum",
    "build_suffix_gcd",
    "AdaptiveOracleManager",
    "BaseSubsetSumSolver",
    "BruteForceSolver",
    "TargetRemainderDFSSolver",
    "TargetRemainderPrunedSolver",
    "TargetRemainderMemoSolver",
    "BitsetDPSolver",
    "MITMSolver",
    "ATRSSolver",
    "validate_atrs_against_bruteforce",
    "BenchmarkRunner",
    "generate_instance",
    "ATRSApplication",
]

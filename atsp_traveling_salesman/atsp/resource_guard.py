"""
ATSP - Resource Guard for Memory, Time, and State limits
Provides deterministic safety checks against out-of-memory and runaway execution in TSP search.
"""
import time
import tracemalloc
from typing import Optional


class ResourceLimitExceeded(Exception):
    def __init__(self, reason: str, resource_type: str):
        super().__init__(f"{resource_type} limit exceeded: {reason}")
        self.reason = reason
        self.resource_type = resource_type


class ResourceGuard:
    def __init__(
        self,
        max_memory_bytes: Optional[int] = 512 * 1024 * 1024,
        timeout_seconds: Optional[float] = 30.0,
        max_memo_states: Optional[int] = 100_000,
    ):
        self.max_memory_bytes = max_memory_bytes
        self.timeout_seconds = timeout_seconds
        self.max_memo_states = max_memo_states
        self.start_time = time.perf_counter()
        self.peak_memory_bytes = 0
        self._check_counter = 0

    def start(self):
        self.start_time = time.perf_counter()
        if not tracemalloc.is_tracing():
            try:
                tracemalloc.start()
            except Exception:
                pass

    def check_time(self):
        if self.timeout_seconds is not None and self.timeout_seconds > 0:
            elapsed = time.perf_counter() - self.start_time
            if elapsed >= self.timeout_seconds:
                raise ResourceLimitExceeded(
                    f"Timeout after {elapsed:.2f}s (Limit: {self.timeout_seconds}s)",
                    "TIME"
                )

    def check_memory(self):
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            self.peak_memory_bytes = max(self.peak_memory_bytes, peak)
            if self.max_memory_bytes is not None and self.max_memory_bytes > 0:
                if current > self.max_memory_bytes:
                    raise ResourceLimitExceeded(
                        f"Memory usage {current / (1024*1024):.1f}MB exceeded limit {self.max_memory_bytes / (1024*1024):.1f}MB",
                        "MEMORY"
                    )

    def periodic_check(self, interval: int = 256):
        self._check_counter += 1
        if self._check_counter >= interval:
            self._check_counter = 0
            self.check_time()
            self.check_memory()

    def check_memo_size(self, current_size: int):
        if self.max_memo_states is not None and self.max_memo_states > 0:
            if current_size > self.max_memo_states:
                raise ResourceLimitExceeded(
                    f"Memoization state count {current_size:,} exceeded limit {self.max_memo_states:,}",
                    "MEMO_STATES"
                )

    def is_held_karp_allowed(self, n_remaining: int) -> bool:
        """
        Estimates Held-Karp state count: 2^n * n table.
        Safe for up to ~18-20 cities within memory budget.
        """
        if n_remaining > 20:
            return False
        est_states = (1 << n_remaining) * n_remaining
        est_bytes = est_states * 16  # Approx float + dict overhead
        if self.max_memory_bytes is not None and self.max_memory_bytes > 0:
            return est_bytes <= int(self.max_memory_bytes * 0.40)
        return est_states <= 5_000_000

    def split_for_workers(self, num_workers: int) -> "ResourceGuard":
        """
        Partitions global memory budget across multi-core workers to prevent aggregate OOM.
        """
        w = max(1, num_workers)
        per_worker_mem = (self.max_memory_bytes // w) if self.max_memory_bytes else None
        per_worker_memo = (self.max_memo_states // w) if self.max_memo_states else None
        return ResourceGuard(
            max_memory_bytes=per_worker_mem,
            timeout_seconds=self.timeout_seconds,
            max_memo_states=per_worker_memo,
        )

    def get_elapsed(self) -> float:
        return time.perf_counter() - self.start_time

    def get_peak_memory_mb(self) -> float:
        if tracemalloc.is_tracing():
            _, peak = tracemalloc.get_traced_memory()
            self.peak_memory_bytes = max(self.peak_memory_bytes, peak)
        return self.peak_memory_bytes / (1024 * 1024)

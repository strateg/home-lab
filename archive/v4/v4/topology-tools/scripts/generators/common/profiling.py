"""Performance profiling utilities for generators (Phase 6).

Provides timing, memory profiling, and performance analysis tools.
"""

from __future__ import annotations

import functools
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class TimingResult:
    """Result of timing measurement."""

    name: str
    duration_seconds: float
    start_time: float
    end_time: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        return self.duration_seconds * 1000

    def __str__(self) -> str:
        """Format timing result."""
        if self.duration_ms < 1000:
            return f"{self.name}: {self.duration_ms:.2f}ms"
        else:
            return f"{self.name}: {self.duration_seconds:.2f}s"


@dataclass
class PerformanceProfile:
    """Aggregate performance profile."""

    timings: list[TimingResult] = field(default_factory=list)
    total_duration: float = 0.0

    def add_timing(self, result: TimingResult) -> None:
        """Add timing result."""
        self.timings.append(result)
        self.total_duration += result.duration_seconds

    def get_summary(self) -> str:
        """Get performance summary."""
        if not self.timings:
            return "No timings recorded"

        lines = [
            f"Total: {self.total_duration:.2f}s",
            "Breakdown:",
        ]

        # Sort by duration descending
        sorted_timings = sorted(self.timings, key=lambda t: t.duration_seconds, reverse=True)

        for timing in sorted_timings:
            percent = (timing.duration_seconds / self.total_duration * 100) if self.total_duration > 0 else 0
            lines.append(f"  {timing.name}: {timing.duration_seconds:.2f}s ({percent:.1f}%)")

        return "\n".join(lines)

    def save_report(self, output_path: Path) -> None:
        """Save performance report to file."""
        output_path.write_text(self.get_summary(), encoding="utf-8")


class PerformanceProfiler:
    """Performance profiler for generator operations."""

    def __init__(self, enabled: bool = True):
        """Initialize profiler.

        Args:
            enabled: Whether profiling is enabled
        """
        self.enabled = enabled
        self.profile = PerformanceProfile()

    @contextmanager
    def measure(self, operation_name: str, **metadata):
        """Context manager for timing operations.

        Args:
            operation_name: Name of operation being measured
            **metadata: Additional metadata to attach

        Yields:
            None

        Example:
            >>> profiler = PerformanceProfiler()
            >>> with profiler.measure("load_topology"):
            ...     topology = load_topology("topology.yaml")
        """
        if not self.enabled:
            yield
            return

        start = time.perf_counter()
        try:
            yield
        finally:
            end = time.perf_counter()
            duration = end - start

            result = TimingResult(
                name=operation_name,
                duration_seconds=duration,
                start_time=start,
                end_time=end,
                metadata=metadata,
            )

            self.profile.add_timing(result)

    def get_summary(self) -> str:
        """Get performance summary."""
        return self.profile.get_summary()

    def save_report(self, output_path: Path | str) -> None:
        """Save performance report."""
        self.profile.save_report(Path(output_path))


def timed(func: Callable) -> Callable:
    """Decorator to time function execution.

    Args:
        func: Function to time

    Returns:
        Wrapped function that prints timing info

    Example:
        >>> @timed
        ... def generate_docs():
        ...     ...
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        duration = end - start

        print(f"⏱️  {func.__name__}: {duration:.3f}s")

        return result

    return wrapper


@contextmanager
def simple_timer(name: str, verbose: bool = True):
    """Simple timer context manager.

    Args:
        name: Name of operation
        verbose: Whether to print timing

    Yields:
        Dictionary that will contain 'duration' after completion

    Example:
        >>> with simple_timer("Load topology") as timer:
        ...     load_topology()
        >>> print(f"Took {timer['duration']:.2f}s")
    """
    result = {}
    start = time.perf_counter()

    try:
        yield result
    finally:
        end = time.perf_counter()
        duration = end - start
        result["duration"] = duration

        if verbose:
            print(f"⏱️  {name}: {duration:.3f}s")


class MemoryProfiler:
    """Simple memory profiler."""

    def __init__(self, enabled: bool = False):
        """Initialize memory profiler.

        Note: Requires memory_profiler package for detailed profiling.

        Args:
            enabled: Whether to enable memory profiling
        """
        self.enabled = enabled
        self._snapshots = []

    def snapshot(self, label: str = "") -> None:
        """Take memory snapshot.

        Args:
            label: Label for this snapshot
        """
        if not self.enabled:
            return

        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            self._snapshots.append(
                {
                    "label": label,
                    "rss_mb": memory_info.rss / 1024 / 1024,
                    "vms_mb": memory_info.vms / 1024 / 1024,
                }
            )
        except ImportError:
            # psutil not available
            pass

    def get_summary(self) -> str:
        """Get memory usage summary."""
        if not self._snapshots:
            return "No memory snapshots taken"

        lines = ["Memory Usage:"]
        for snapshot in self._snapshots:
            label = snapshot["label"] or "snapshot"
            rss = snapshot["rss_mb"]
            lines.append(f"  {label}: {rss:.1f} MB RSS")

        return "\n".join(lines)

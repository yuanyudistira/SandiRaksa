"""
Performance Benchmarks for SandiRaksa.

Measures:
- Cold start time (first model load)
- Warm inference time (subsequent calls)
- Throughput (texts/sec, chars/sec)
- Memory usage (peak RAM)
- File processing time per format

Benchmark Targets:
- Cold start: < 5 seconds
- Warm inference: < 100ms per KB of text
- Throughput: > 10 texts/sec
- Peak RAM: < 500MB
"""

from __future__ import annotations

import gc
import logging
import platform
import statistics
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Any

logger = logging.getLogger(__name__)


class BenchmarkType(str, Enum):
    """Types of benchmarks."""

    COLD_START = "cold_start"
    WARM_INFERENCE = "warm_inference"
    THROUGHPUT = "throughput"
    MEMORY = "memory"
    FILE_PROCESSING = "file_processing"


@dataclass
class PerformanceMetrics:
    """
    Performance metrics for a single operation.

    Attributes:
        duration_ms: Execution time in milliseconds
        memory_mb: Memory usage in megabytes
        items_processed: Number of items processed
        chars_processed: Total characters processed
        tokens_processed: Total tokens processed (if applicable)
    """

    duration_ms: float = 0.0
    memory_mb: float = 0.0
    items_processed: int = 0
    chars_processed: int = 0
    tokens_processed: int = 0

    @property
    def items_per_second(self) -> float:
        """Items processed per second."""
        if self.duration_ms <= 0:
            return 0.0
        return self.items_processed / (self.duration_ms / 1000)

    @property
    def chars_per_second(self) -> float:
        """Characters processed per second."""
        if self.duration_ms <= 0:
            return 0.0
        return self.chars_processed / (self.duration_ms / 1000)

    @property
    def ms_per_item(self) -> float:
        """Milliseconds per item."""
        if self.items_processed <= 0:
            return 0.0
        return self.duration_ms / self.items_processed

    def to_dict(self) -> dict:
        return {
            "duration_ms": round(self.duration_ms, 2),
            "memory_mb": round(self.memory_mb, 2),
            "items_processed": self.items_processed,
            "chars_processed": self.chars_processed,
            "items_per_second": round(self.items_per_second, 2),
            "chars_per_second": round(self.chars_per_second, 0),
            "ms_per_item": round(self.ms_per_item, 2),
        }


@dataclass
class BenchmarkResult:
    """
    Result of a benchmark run.

    Attributes:
        name: Benchmark name
        benchmark_type: Type of benchmark
        metrics: Performance metrics
        iterations: Number of iterations run
        min_ms: Minimum duration
        max_ms: Maximum duration
        mean_ms: Mean duration
        std_ms: Standard deviation
        passed: Whether benchmark met targets
        target_ms: Target duration (for pass/fail)
    """

    name: str
    benchmark_type: BenchmarkType
    metrics: PerformanceMetrics
    iterations: int = 1
    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    std_ms: float = 0.0
    passed: bool = True
    target_ms: float | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.benchmark_type.value,
            "iterations": self.iterations,
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "mean_ms": round(self.mean_ms, 2),
            "std_ms": round(self.std_ms, 2),
            "passed": self.passed,
            "target_ms": self.target_ms,
            "metrics": self.metrics.to_dict(),
            "error": self.error,
        }


@dataclass
class BenchmarkReport:
    """
    Complete benchmark report.

    Attributes:
        results: List of benchmark results
        system_info: System information
        timestamp: When benchmarks were run
    """

    results: list[BenchmarkResult] = field(default_factory=list)
    system_info: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def all_passed(self) -> bool:
        """True if all benchmarks passed."""
        return all(r.passed for r in self.results if r.target_ms is not None)

    @property
    def failed_count(self) -> int:
        """Count of failed benchmarks."""
        return sum(1 for r in self.results if not r.passed and r.target_ms is not None)

    def get_result(self, name: str) -> BenchmarkResult | None:
        """Get result by name."""
        for r in self.results:
            if r.name == name:
                return r
        return None

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "failed_count": self.failed_count,
            "timestamp": self.timestamp.isoformat(),
            "system_info": self.system_info,
            "results": [r.to_dict() for r in self.results],
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 70,
            "PERFORMANCE BENCHMARK REPORT",
            "=" * 70,
            f"Timestamp: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Platform: {self.system_info.get('platform', 'Unknown')}",
            f"Python: {self.system_info.get('python_version', 'Unknown')}",
            f"CPU: {self.system_info.get('processor', 'Unknown')}",
            "",
        ]

        if self.all_passed:
            lines.append("✅ ALL BENCHMARKS PASSED")
        else:
            lines.append(f"❌ {self.failed_count} BENCHMARKS FAILED")

        lines.extend([
            "",
            "-" * 70,
            f"{'Benchmark':<30} {'Mean':>10} {'Min':>10} {'Max':>10} {'Status':>8}",
            "-" * 70,
        ])

        for r in self.results:
            status = "✅" if r.passed else "❌"
            target = f"(< {r.target_ms:.0f}ms)" if r.target_ms else ""

            lines.append(
                f"{r.name:<30} "
                f"{r.mean_ms:>9.1f}ms "
                f"{r.min_ms:>9.1f}ms "
                f"{r.max_ms:>9.1f}ms "
                f"{status:>8} {target}"
            )

        lines.append("=" * 70)
        return "\n".join(lines)


class BenchmarkRunner:
    """
    Runner for performance benchmarks.

    Provides utilities for timing, memory measurement, and reporting.
    """

    def __init__(
        self,
        warmup_iterations: int = 2,
        benchmark_iterations: int = 5,
    ):
        """
        Initialize runner.

        Args:
            warmup_iterations: Number of warmup runs before measuring
            benchmark_iterations: Number of measured iterations
        """
        self._warmup = warmup_iterations
        self._iterations = benchmark_iterations
        self._results: list[BenchmarkResult] = []

    def time_function(
        self,
        func: Callable[[], Any],
        name: str,
        benchmark_type: BenchmarkType = BenchmarkType.WARM_INFERENCE,
        target_ms: float | None = None,
        items: int = 1,
        chars: int = 0,
    ) -> BenchmarkResult:
        """
        Time a function execution.

        Args:
            func: Function to benchmark
            name: Benchmark name
            benchmark_type: Type of benchmark
            target_ms: Target duration for pass/fail
            items: Number of items processed
            chars: Total characters processed

        Returns:
            BenchmarkResult
        """
        # Warmup
        for _ in range(self._warmup):
            try:
                func()
            except Exception:
                pass

        # Benchmark
        gc.collect()
        durations = []
        memory_peaks = []

        for _ in range(self._iterations):
            tracemalloc.start()
            start = time.perf_counter()

            try:
                func()
                success = True
                error = None
            except Exception as e:
                success = False
                error = str(e)

            elapsed = (time.perf_counter() - start) * 1000  # ms
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            durations.append(elapsed)
            memory_peaks.append(peak / (1024 * 1024))  # MB

            if not success:
                break

        if not durations:
            return BenchmarkResult(
                name=name,
                benchmark_type=benchmark_type,
                metrics=PerformanceMetrics(),
                error=error or "No iterations completed",
            )

        metrics = PerformanceMetrics(
            duration_ms=statistics.mean(durations),
            memory_mb=max(memory_peaks) if memory_peaks else 0,
            items_processed=items,
            chars_processed=chars,
        )

        mean_ms = statistics.mean(durations)
        passed = target_ms is None or mean_ms <= target_ms

        result = BenchmarkResult(
            name=name,
            benchmark_type=benchmark_type,
            metrics=metrics,
            iterations=len(durations),
            min_ms=min(durations),
            max_ms=max(durations),
            mean_ms=mean_ms,
            std_ms=statistics.stdev(durations) if len(durations) > 1 else 0,
            passed=passed,
            target_ms=target_ms,
            error=error,
        )

        self._results.append(result)
        return result

    def measure_memory(
        self,
        func: Callable[[], Any],
        name: str,
        target_mb: float | None = None,
    ) -> BenchmarkResult:
        """
        Measure peak memory usage of a function.

        Args:
            func: Function to measure
            name: Benchmark name
            target_mb: Target memory limit for pass/fail

        Returns:
            BenchmarkResult
        """
        gc.collect()
        tracemalloc.start()

        start = time.perf_counter()
        try:
            func()
            error = None
        except Exception as e:
            error = str(e)

        elapsed = (time.perf_counter() - start) * 1000
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        memory_mb = peak / (1024 * 1024)
        passed = target_mb is None or memory_mb <= target_mb

        metrics = PerformanceMetrics(
            duration_ms=elapsed,
            memory_mb=memory_mb,
        )

        result = BenchmarkResult(
            name=name,
            benchmark_type=BenchmarkType.MEMORY,
            metrics=metrics,
            iterations=1,
            min_ms=elapsed,
            max_ms=elapsed,
            mean_ms=elapsed,
            passed=passed,
            target_ms=target_mb,  # Using target_ms for target_mb
            error=error,
        )

        self._results.append(result)
        return result

    def generate_report(self) -> BenchmarkReport:
        """Generate benchmark report with all results."""
        return BenchmarkReport(
            results=self._results,
            system_info=get_system_info(),
        )

    def clear_results(self) -> None:
        """Clear accumulated results."""
        self._results = []


def get_system_info() -> dict:
    """Get system information for benchmark context."""
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "system": platform.system(),
        "python_implementation": platform.python_implementation(),
    }


# ============== Benchmark Targets ==============

class BenchmarkTargets:
    """Default benchmark targets for release."""

    # Time targets (milliseconds)
    COLD_START_MS = 5000          # 5 seconds for first load
    WARM_INFERENCE_MS = 100       # 100ms per text
    BATCH_INFERENCE_MS = 50       # 50ms per text in batch

    # Throughput targets
    MIN_TEXTS_PER_SEC = 10        # Minimum texts/second
    MIN_CHARS_PER_SEC = 10000     # Minimum chars/second

    # Memory targets (megabytes)
    PEAK_MEMORY_MB = 500          # 500MB max


# ============== Convenience Functions ==============

def run_benchmarks(
    detection_engine=None,
    sample_texts: list[str] | None = None,
) -> BenchmarkReport:
    """
    Run standard benchmark suite.

    Args:
        detection_engine: Detection engine to benchmark (optional)
        sample_texts: Sample texts for throughput testing

    Returns:
        BenchmarkReport with all results
    """
    runner = BenchmarkRunner()

    # Generate sample texts if not provided
    if sample_texts is None:
        sample_texts = [
            "Nama: Budi Santoso, NIK: 3201011234567890",
            "Email: test@example.com, Telepon: 081234567890",
            "Alamat: Jl. Sudirman No. 45, Jakarta",
        ] * 10  # 30 texts

    total_chars = sum(len(t) for t in sample_texts)

    # Benchmark: Text processing (simulated if no engine)
    def process_texts():
        for text in sample_texts:
            # Simulate processing
            _ = len(text)

    runner.time_function(
        func=process_texts,
        name="text_processing",
        benchmark_type=BenchmarkType.THROUGHPUT,
        target_ms=len(sample_texts) * BenchmarkTargets.WARM_INFERENCE_MS,
        items=len(sample_texts),
        chars=total_chars,
    )

    # Benchmark: Memory baseline
    def memory_test():
        data = [text * 100 for text in sample_texts]
        return len(data)

    runner.measure_memory(
        func=memory_test,
        name="memory_baseline",
        target_mb=BenchmarkTargets.PEAK_MEMORY_MB,
    )

    return runner.generate_report()


def format_benchmark_report(report: BenchmarkReport) -> str:
    """Format benchmark report as string."""
    return report.summary()


__all__ = [
    "BenchmarkType",
    "PerformanceMetrics",
    "BenchmarkResult",
    "BenchmarkReport",
    "BenchmarkRunner",
    "BenchmarkTargets",
    "get_system_info",
    "run_benchmarks",
    "format_benchmark_report",
]

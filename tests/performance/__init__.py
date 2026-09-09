"""
Performance Benchmarking module for SandiRaksa.

Provides tools to measure:
- Cold/warm model load times
- Detection throughput (texts/sec, tokens/sec)
- Memory usage (peak RAM)
- File processing performance
"""

from tests.performance.benchmarks import (
    PerformanceMetrics,
    BenchmarkResult,
    BenchmarkRunner,
    run_benchmarks,
    format_benchmark_report,
)

__all__ = [
    "PerformanceMetrics",
    "BenchmarkResult",
    "BenchmarkRunner",
    "run_benchmarks",
    "format_benchmark_report",
]

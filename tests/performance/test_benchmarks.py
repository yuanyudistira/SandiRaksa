"""
Performance Benchmarks for SandiRaksa.

Tests to measure and track performance of critical operations.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Callable

import pytest


class PerformanceResult:
    """Simple performance measurement result."""

    def __init__(self, name: str, duration: float, iterations: int):
        self.name = name
        self.duration = duration
        self.iterations = iterations
        self.avg_time = duration / iterations
        self.ops_per_sec = iterations / duration if duration > 0 else 0


def measure_performance(
    func: Callable,
    iterations: int = 100,
    warmup: int = 5,
) -> PerformanceResult:
    """
    Measure function performance.
    """
    # Warmup
    for _ in range(warmup):
        func()
    
    # Measure
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    end = time.perf_counter()
    
    return PerformanceResult(func.__name__, end - start, iterations)


class TestCSVPerformance:
    """Performance benchmarks for CSV handling."""

    def test_csv_read_small(self):
        """Benchmark: Read small CSV (100 rows)."""
        from sandiraksa.documents.csv_handler import CSVReader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "small.csv"
            content = "col1,col2,col3\n" + "\n".join(
                f"value{i},data{i},info{i}" for i in range(100)
            )
            csv_path.write_text(content, encoding="utf-8")
            
            def read_csv():
                reader = CSVReader(csv_path)
                list(reader.iter_rows())
            
            result = measure_performance(read_csv, iterations=50)
            
            print(f"\nSmall CSV read: {result.avg_time*1000:.2f}ms avg")
            
            # Should read small CSV in < 100ms
            assert result.avg_time < 0.1


class TestCryptoPerformance:
    """Performance benchmarks for cryptographic operations."""

    def test_hmac_performance(self):
        """Benchmark: HMAC computation speed."""
        from sandiraksa.security import compute_hmac
        
        key = b"test-key-32-bytes-for-hmac-func!"
        data = b"test data for hmac computation"
        
        result = measure_performance(
            lambda: compute_hmac(key, data),
            iterations=10000,
        )
        
        print(f"\nHMAC computation: {result.avg_time*1000000:.2f}µs avg, {result.ops_per_sec:.0f} ops/sec")
        
        # HMAC should be very fast (< 0.1ms)
        assert result.avg_time < 0.0001

    def test_key_derivation_performance(self):
        """Benchmark: Key derivation speed."""
        from sandiraksa.security import derive_key
        
        password = "test-password-123"
        
        result = measure_performance(
            lambda: derive_key(password),
            iterations=3,
            warmup=1,
        )
        
        print(f"\nKey derivation: {result.avg_time*1000:.2f}ms avg")
        
        # Key derivation should be slow enough for security (> 50ms)
        # but not too slow for UX (< 2s)
        assert 0.01 < result.avg_time < 2.0


class TestSecurityOperationsPerformance:
    """Performance benchmarks for security operations."""

    def test_xml_parsing_performance(self):
        """Benchmark: Secure XML parsing."""
        from sandiraksa.security import parse_xml_safely
        
        xml = "<root><child>test content</child></root>"
        
        result = measure_performance(
            lambda: parse_xml_safely(xml),
            iterations=1000,
        )
        
        print(f"\nXML parsing: {result.avg_time*1000:.3f}ms avg")
        
        # Should parse quickly
        assert result.avg_time < 0.01

    def test_filename_sanitization_performance(self):
        """Benchmark: Filename sanitization."""
        from sandiraksa.security import sanitize_filename
        
        filename = "test../file<>name.csv"
        
        result = measure_performance(
            lambda: sanitize_filename(filename),
            iterations=10000,
        )
        
        print(f"\nFilename sanitization: {result.avg_time*1000000:.2f}µs avg")
        
        # Should be very fast
        assert result.avg_time < 0.0001

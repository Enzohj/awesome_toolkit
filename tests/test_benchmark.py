"""tests/test_benchmark.py

对 `my_toolkit.benchmark` 的最小可运行测试脚本。
"""

from __future__ import annotations

import contextlib
import io
import time
import unittest

import my_toolkit.benchmark as bench_mod


def inc(x: int) -> int:
    return x + 1


def slow(x: int) -> int:
    time.sleep(0.02)
    return x


class Incrementer:
    def __call__(self, value: int) -> int:
        return value + 1


class TestBenchmark(unittest.TestCase):
    def test_basic_report_structure(self):
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            report = bench_mod.benchmark(
                inc,
                [1, 2, 3],
                concurrency=2,
                repeat=2,
                timeout=None,
                executor_type="thread",
                show_progress=False,
            )

        self.assertEqual(report["total_requests"], 6)
        self.assertEqual(report["data_size"], 3)
        self.assertEqual(report["repeat"], 2)
        self.assertIn("latency_stats", report)
        self.assertEqual(report["infrastructure_error_count"], 0)
        self.assertEqual(report["results"], [2, 3, 4])

    def test_empty_data_fast_path(self):
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            report = bench_mod.benchmark(inc, [], concurrency=1, repeat=1, show_progress=False)
        self.assertEqual(report["total_requests"], 0)
        self.assertEqual(report["infrastructure_error_count"], 0)
        self.assertEqual(report["results"], [])

    def test_callable_without_name_is_supported(self):
        buf_out = io.StringIO()
        with contextlib.redirect_stdout(buf_out):
            report = bench_mod.benchmark(
                Incrementer(),
                [1, 2],
                concurrency=1,
                executor_type="thread",
                show_progress=False,
            )
        self.assertEqual(report["results"], [2, 3])

    def test_invalid_executor_type(self):
        with self.assertRaises(ValueError):
            bench_mod.benchmark(inc, [1], executor_type="bad", show_progress=False)

    def test_timeout_count(self):
        # 注意：这里的 timeout 仅做“标记”，不会中断实际执行
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            report = bench_mod.benchmark(
                slow,
                [1, 2, 3, 4],
                concurrency=4,
                repeat=1,
                timeout=0.001,
                executor_type="thread",
                show_progress=False,
            )
        self.assertEqual(report["timeout_count"], report["total_requests"])
        self.assertEqual(report["success_count"], 0)

    def test_process_serialization_error_is_infrastructure_not_timeout(self):
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            report = bench_mod.benchmark(
                lambda value: value + 1,
                [1],
                concurrency=1,
                repeat=1,
                timeout=None,
                executor_type="process",
                show_progress=False,
            )

        self.assertEqual(report["success_count"], 0)
        self.assertEqual(report["fail_count"], 1)
        self.assertEqual(report["timeout_count"], 0)
        self.assertEqual(report["infrastructure_error_count"], 1)
        self.assertEqual(report["errors"][0]["error_kind"], "infrastructure")
        self.assertIsNone(report["errors"][0]["latency_ms"])
        self.assertEqual(
            report["latency_stats"],
            {
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

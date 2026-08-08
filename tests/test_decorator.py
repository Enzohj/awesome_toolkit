"""tests/test_decorator.py

对 `my_toolkit.decorator` 的最小可运行测试脚本（timer/timeout/retry）。
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
import time
import unittest

import my_toolkit.decorator as decorator_mod


class TestTimer(unittest.TestCase):
    def test_timer_decorator_sync_preserves_name(self):
        @decorator_mod.timer
        def foo(x: int) -> int:
            return x + 1

        self.assertEqual(foo.__name__, "foo")
        self.assertEqual(foo(1), 2)

    def test_timer_context_manager_elapsed(self):
        with decorator_mod.timer("block") as t:
            time.sleep(0.02)
            self.assertGreater(t.elapsed, 0)

    def test_timer_decorator_async(self):
        @decorator_mod.timer
        async def bar(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        self.assertEqual(asyncio.run(bar(3)), 6)


class TestTimeout(unittest.TestCase):
    def test_timeout_invalid_seconds(self):
        with self.assertRaises(ValueError):
            decorator_mod.timeout(0)

    def test_timeout_sync_raises(self):
        @decorator_mod.timeout(0.05)
        def slow():
            time.sleep(0.2)
            return 1

        t0 = time.perf_counter()
        with self.assertRaises(TimeoutError):
            slow()
        self.assertLess(time.perf_counter() - t0, 1.0)

    def test_timeout_sync_is_soft_and_work_can_finish_in_background(self):
        finished = threading.Event()

        @decorator_mod.timeout(0.01)
        def slow_side_effect():
            time.sleep(0.03)
            finished.set()

        with self.assertRaises(TimeoutError):
            slow_side_effect()

        self.assertTrue(finished.wait(0.5))

    def test_timeout_sync_background_work_does_not_block_process_exit(self):
        script = """
import time
from my_toolkit.decorator import timeout

@timeout(0.01)
def never_finishes_during_the_test():
    time.sleep(5)

try:
    never_finishes_during_the_test()
except TimeoutError:
    print("timed out", flush=True)
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "timed out")

    def test_timeout_sync_preserves_business_timeout_error(self):
        business_error = TimeoutError("upstream service timed out")

        @decorator_mod.timeout(1)
        def fail():
            raise business_error

        with self.assertRaises(TimeoutError) as caught:
            fail()
        self.assertIs(caught.exception, business_error)

    def test_timeout_async_raises(self):
        @decorator_mod.timeout(0.05)
        async def slow_async():
            await asyncio.sleep(0.2)
            return 1

        with self.assertRaises(TimeoutError):
            asyncio.run(slow_async())

    def test_timeout_async_preserves_business_timeout_error(self):
        business_error = TimeoutError("database deadline exceeded")

        @decorator_mod.timeout(1)
        async def fail_async():
            raise business_error

        with self.assertRaises(TimeoutError) as caught:
            asyncio.run(fail_async())
        self.assertIs(caught.exception, business_error)

    def test_timeout_async_cancels_a_truly_timed_out_task(self):
        cancelled = threading.Event()

        @decorator_mod.timeout(0.01)
        async def cancellable():
            try:
                await asyncio.sleep(1)
            finally:
                cancelled.set()

        with self.assertRaises(TimeoutError):
            asyncio.run(cancellable())
        self.assertTrue(cancelled.is_set())


class TestRetry(unittest.TestCase):
    def test_retry_eventually_success(self):
        calls = {"n": 0}

        @decorator_mod.retry(max_attempts=3, delay=0.0)
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ValueError("boom")
            return "ok"

        self.assertEqual(flaky(), "ok")
        self.assertEqual(calls["n"], 3)

    def test_retry_fail_return_default_none(self):
        calls = {"n": 0}

        @decorator_mod.retry(max_attempts=2, delay=0.0, raise_on_failure=False)
        def always_fail():
            calls["n"] += 1
            raise RuntimeError("no")

        self.assertIsNone(always_fail())
        self.assertEqual(calls["n"], 2)

    def test_retry_raise_on_failure(self):
        @decorator_mod.retry(max_attempts=2, delay=0.0, raise_on_failure=True)
        def always_fail2():
            raise KeyError("x")

        with self.assertRaises(KeyError):
            always_fail2()

    def test_retry_async_success(self):
        calls = {"n": 0}

        @decorator_mod.retry(max_attempts=3, delay=0.0)
        async def flaky_async():
            calls["n"] += 1
            if calls["n"] < 2:
                raise ValueError("boom")
            return 42

        self.assertEqual(asyncio.run(flaky_async()), 42)


if __name__ == "__main__":
    unittest.main(verbosity=2)

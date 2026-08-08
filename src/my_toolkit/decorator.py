from __future__ import annotations

import asyncio
import inspect
import os
import queue
import random
import threading
import time
from concurrent.futures import Future, wait
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

from .logger import init_logger
logger = init_logger(name=__name__)

P = ParamSpec("P")
R = TypeVar("R")

__all__ = ["timer", "timeout", "retry"]

_UNSET = object()  # 哨兵值，区分 "返回 None" 与 "未设置"

# 同步 timeout 是软超时：只能停止调用方等待，无法强制终止已经运行的线程。
# 自有 daemon worker 不会在解释器退出时 join 后台任务；worker 数和排队数
# 都有上限，避免连续超时造成无界线程/内存增长。
_TIMEOUT_MAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)
_TIMEOUT_QUEUE_SIZE = max(1, _TIMEOUT_MAX_WORKERS * 4)


class _DaemonThreadPool:
    """只供同步 ``timeout`` 使用的有界 daemon worker 池。"""

    def __init__(self, max_workers: int, max_queue_size: int) -> None:
        self._max_workers = max_workers
        self._max_queue_size = max_queue_size
        self._reset_for_current_process()

    def _reset_for_current_process(self) -> None:
        # fork 后父进程的线程与锁状态不可复用；子进程首次 submit 时重建。
        self._pid = os.getpid()
        self._queue: queue.Queue = queue.Queue(maxsize=self._max_queue_size)
        self._threads: list[threading.Thread] = []
        self._pending = 0
        self._lock = threading.Lock()

    def _ensure_current_process(self) -> None:
        if self._pid != os.getpid():
            self._reset_for_current_process()

    def _future_finished(self, _future: Future) -> None:
        with self._lock:
            self._pending = max(0, self._pending - 1)

    def _start_worker(self) -> None:
        worker = threading.Thread(
            target=self._worker,
            name=f"my-toolkit-timeout-{len(self._threads)}",
            daemon=True,
        )
        self._threads.append(worker)
        worker.start()

    def submit(
        self,
        func: Callable,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        enqueue_timeout: float,
    ) -> Future:
        self._ensure_current_process()
        future: Future = Future()
        future.add_done_callback(self._future_finished)

        with self._lock:
            self._pending += 1
            desired_workers = min(self._max_workers, self._pending)
            if len(self._threads) < desired_workers:
                self._start_worker()

        try:
            self._queue.put(
                (future, func, args, kwargs),
                block=True,
                timeout=max(0.0, enqueue_timeout),
            )
        except queue.Full:
            future.cancel()
            raise
        return future

    def _worker(self) -> None:
        while True:
            future, func, args, kwargs = self._queue.get()
            try:
                if not future.set_running_or_notify_cancel():
                    continue
                try:
                    result = func(*args, **kwargs)
                except BaseException as exc:
                    future.set_exception(exc)
                else:
                    future.set_result(result)
            finally:
                self._queue.task_done()


_TIMEOUT_EXECUTOR = _DaemonThreadPool(
    max_workers=_TIMEOUT_MAX_WORKERS,
    max_queue_size=_TIMEOUT_QUEUE_SIZE,
)


# ────────────────────────────── timer ──────────────────────────────

class timer:
    """
    记录函数执行耗时（秒），无论成功或异常均会输出。

    用法:
        # 作为装饰器
        @timer
        def foo(): ...

        @timer
        async def bar(): ...

        # 作为上下文管理器
        with timer("load_data"):
            heavy_io()
    """

    def __new__(cls, func_or_label: Union[Callable[P, R], str, None] = None):
        instance = super().__new__(cls)

        # @timer  —— 直接装饰（无括号）
        if callable(func_or_label):
            return instance._wrap(func_or_label)

        # timer("label") —— 上下文管理器
        instance._label = func_or_label or "block"
        return instance

    def __init__(self, func_or_label: Union[Callable, str, None] = None):
        # 当作为装饰器直接返回 wrapper 时，__init__ 不会被调用到 self 上
        pass

    # ── 装饰器路径 ──
    def _wrap(self, func: Callable[P, R]) -> Callable[P, R]:
        label = func.__name__

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                start = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    logger.info(f"Function '{label}' elapsed: {(time.perf_counter() - start):.4f} s")

            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                logger.info(f"Function '{label}' elapsed: {(time.perf_counter() - start):.4f} s")

        return sync_wrapper  # type: ignore[return-value]

    # ── 上下文管理器路径 ──
    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_info):
        logger.info(f"Block '{self._label}' elapsed: {(time.perf_counter() - self._start):.4f} s")
        return False

    @property
    def elapsed(self) -> float:
        """在上下文管理器内部调用，返回当前已过时间。"""
        if not hasattr(self, "_start"):
            raise RuntimeError("timer.elapsed 只能在上下文管理器内部使用")
        return time.perf_counter() - self._start


# ────────────────────────────── timeout ──────────────────────────────

def timeout(seconds: float) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    限制调用方等待函数执行的时间。超时后抛出 TimeoutError。

    - 同步函数: 使用模块级有界 daemon worker 池。这是软超时；已经开始运行
      的任务不会被强制终止，但不会阻塞解释器退出。解释器退出时仍在运行的
      后台任务可能被直接终止，因此不要依赖其完成关键写入。
    - 异步函数: 超时后取消任务，并等待取消完成。

    被装饰函数主动抛出的 ``TimeoutError`` 会原样传递，不会被误判为装饰器超时。
    """
    if seconds <= 0:
        raise ValueError("timeout seconds must be positive, got %s" % seconds)

    def decorator(func: Callable[P, R]) -> Callable[P, R]:

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                task = asyncio.create_task(func(*args, **kwargs))
                try:
                    done, _ = await asyncio.wait({task}, timeout=seconds)
                except asyncio.CancelledError:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    raise

                if task in done:
                    # 先由 wait 判断是否真的到达截止时间，再读取结果。这样业务代码
                    # 主动抛出的 builtin TimeoutError（Python 3.11 起与
                    # asyncio.TimeoutError 同类）仍会保持原异常与原消息。
                    return await task

                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    # 截止时间已经到达；取消清理阶段的业务异常不应替代超时结果。
                    pass
                raise TimeoutError(
                    "Function '%s' timed out after %ss" % (func.__name__, seconds)
                ) from None

            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            deadline = time.monotonic() + seconds
            try:
                future = _TIMEOUT_EXECUTOR.submit(
                    func,
                    args,
                    kwargs,
                    enqueue_timeout=seconds,
                )
            except queue.Full:
                raise TimeoutError(
                    "Function '%s' timed out after %ss" % (func.__name__, seconds)
                ) from None

            remaining = max(0.0, deadline - time.monotonic())
            done, _ = wait((future,), timeout=remaining)
            if future in done:
                # future.result() 在这里不使用 timeout 参数，业务 TimeoutError
                # 因而不会与等待超时混淆。
                return future.result()

            # 仅能取消尚未开始的任务；运行中的任务会在后台继续完成。
            future.cancel()
            raise TimeoutError(
                "Function '%s' timed out after %ss" % (func.__name__, seconds)
            ) from None

        return sync_wrapper  # type: ignore[return-value]

    return decorator


# ────────────────────────────── retry ──────────────────────────────

def retry(
    max_attempts: int = 3,
    delay: float = 0.1,
    backoff: float = 1,
    jitter: float = 0,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    fail_return: Any = _UNSET,
    raise_on_failure: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    重试装饰器：在指定异常发生时自动重试。支持同步和异步函数。

    参数:
        max_attempts:     最大尝试次数（>= 1）
        delay:            初始延迟时间（秒）
        backoff:          退避因子（1=固定间隔，>1=指数退避）
        jitter:           随机抖动上限（秒），实际睡眠 = sleep_time + random(0, jitter)，
                          用于防止多实例同步重试造成惊群效应
        exceptions:       需要捕获并重试的异常类型元组
        fail_return:      所有尝试失败后的默认返回值（仅 raise_on_failure=False 时生效）；
                          未设置且 raise_on_failure=False 时返回 None
        raise_on_failure:  True 时在最终失败后重新抛出最后一次异常
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1, got %s" % max_attempts)
    if delay < 0:
        raise ValueError("delay must be >= 0, got %s" % delay)
    if backoff < 0:
        raise ValueError("backoff must be >= 0, got %s" % backoff)
    if jitter < 0:
        raise ValueError("jitter must be >= 0, got %s" % jitter)
    if not isinstance(exceptions, tuple) or not exceptions:
        raise ValueError("exceptions must be a non-empty tuple of exception classes")
    if not all(isinstance(exc, type) and issubclass(exc, BaseException) for exc in exceptions):
        raise TypeError("exceptions must contain only exception classes")

    effective_fail_return = None if fail_return is _UNSET else fail_return

    def decorator(func: Callable[P, R]) -> Callable[P, R]:

        def _compute_sleep(attempt: int) -> float:
            base = delay * (backoff ** (attempt - 1))
            return (base + random.uniform(0, jitter)) if jitter > 0 else base

        def _log_retry(attempt: int, exc: BaseException, sleep_time: float) -> None:
            logger.debug(
                f"[retry] '{func.__name__}' attempt {attempt}/{max_attempts} failed: {exc}; "
                f"retrying in {sleep_time:.3f}s …",
            )

        def _log_exhausted(last_exc: BaseException) -> None:
            logger.error(
                f"[retry] '{func.__name__}' exhausted {max_attempts} attempts. "
                f"Last error: {last_exc}",
                exc_info=True,
            )

        # ── 异步版本 ──
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                last_exception: Optional[BaseException] = None

                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as exc:
                        last_exception = exc

                        if attempt < max_attempts:
                            sleep_time = _compute_sleep(attempt)
                            _log_retry(attempt, exc, sleep_time)
                            await asyncio.sleep(sleep_time)
                        else:
                            _log_exhausted(last_exception)
                            logger.debug(f"[retry] call args={args}, kwargs={kwargs}")

                if raise_on_failure:
                    raise last_exception  # type: ignore[misc]
                return effective_fail_return  # type: ignore[return-value]

            return async_wrapper  # type: ignore[return-value]

        # ── 同步版本 ──
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception: Optional[BaseException] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc

                    if attempt < max_attempts:
                        sleep_time = _compute_sleep(attempt)
                        _log_retry(attempt, exc, sleep_time)
                        time.sleep(sleep_time)
                    else:
                        _log_exhausted(last_exception)
                        logger.debug(f"[retry] call args={args}, kwargs={kwargs}")

            if raise_on_failure:
                raise last_exception  # type: ignore[misc]
            return effective_fail_return  # type: ignore[return-value]

        return sync_wrapper  # type: ignore[return-value]

    return decorator

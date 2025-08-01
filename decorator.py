import time
from functools import wraps
from logger import logger
import concurrent.futures as futures
import traceback
from io import StringIO

executor = futures.ThreadPoolExecutor(1)

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()  # 记录开始时间
        result = func(*args, **kwargs)  # 执行原函数
        end_time = time.time()  # 记录结束时间
        elapsed_time = end_time - start_time  # 计算耗时
        logger.debug(f"func '{func.__name__}' latency: {elapsed_time:.4f} s")
        return result
    return wrapper

def timeout(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            future = executor.submit(func, *args, **kwargs)
            return future.result(timeout=seconds)
        return wrapper
    return decorator

def retry(max_attempts=3, delay=1, backoff=1):
    """
    装饰器：最多尝试 max_attempts 次，失败后等待 delay * (backoff ** 尝试次数) 秒

    参数:
        max_attempts (int): 最大尝试次数（至少 1）
        delay (float): 初始延迟时间（秒）
        backoff (float): 退避因子（1 表示固定间隔，>1 表示指数退避）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        sleep_time = delay * (backoff ** (attempt - 1))
                        logger.debug(f"函数 '{func.__name__}' 第 {attempt} 次尝试失败: {e}")
                        logger.debug(f"将在 {sleep_time:.2f} 秒后重试...")
                        time.sleep(sleep_time)
                    else:
                        # 最后一次失败，打印详细 traceback
                        logger.error(f"函数 '{func.__name__}' 在 {max_attempts} 次尝试后仍失败。")
                        logger.error("详细错误信息:")
                        buffer = StringIO()
                        buffer.write(traceback.format_exc())
                        logger.error(f'\n{buffer.getvalue()}')
                        raise last_exception  # 重新抛出最后一次异常
            return None  # 理论上不会执行到这里
        return wrapper
    return decorator

if __name__ == "__main__":
    @retry(max_attempts=3, delay=0.5)  # 指数退避：1s, 2s, 4s
    def unstable_function():
        import random
        if random.random() < 0.8:
            raise ValueError("随机错误发生")
        return "成功！"

    # 调用函数
    try:
        result = unstable_function()
        print(result)
    except ValueError as e:
        print(f"函数最终失败: {e}")

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from tqdm import tqdm

def apply_multi_thread(iterable, func, num_workers=8, show_progess=True, total_num=None):
    """
    使用多线程对 iterable 中的每个元素应用 func，并显示进度条。
    
    参数:
        iterable: 可迭代对象（如 list, tuple 等）
        func: 要应用的函数
        num_workers: 线程数，默认为 4
        show_progess: 是否显示进度条，默认为 True
        total_num: 总任务数，默认为 None
    
    返回:
        list: func 应用于每个元素后的结果列表
    """
    if total_num is None:
        try:
            total_num = len(iterable)
        except:
            show_progess = False

    def wrapper(args):
        if isinstance(args, tuple):
            return func(*args)
        else:
            return func(args)
        
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        if show_progess:
            results = list(tqdm(executor.map(wrapper, iterable), total=total_num))
        else:
            results = list(executor.map(wrapper, iterable))
    return results

def apply_multi_process(iterable, func, num_workers=8, show_progess=True, total_num=None):
    """
    使用多进程对 iterable 中的每个元素应用 func，并显示进度条。
    
    参数:
        iterable: 可迭代对象（如 list, tuple 等）
        func: 要应用的函数
        num_workers: 进程数，默认为 4
        show_progess: 是否显示进度条，默认为 True
        total_num: 总任务数，默认为 None
    
    返回:
        list: func 应用于每个元素后的结果列表
    """
    if total_num is None:
        try:
            total_num = len(iterable)
        except:
            show_progess = False
        
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        if show_progess:
            results = list(tqdm(executor.map(func, iterable), total=total_num))
        else:
            results = list(executor.map(func, iterable))
    return results



if __name__ == '__main__':
    from time import sleep

    def process_item(x):
        sleep(0.1)  # 模拟耗时任务
        return x * 2
    
    def process_item_(x, y):
        sleep(0.1)  # 模拟耗时任务
        return x * y

    def iter_(n=100):
        for i in range(n):
            yield i

    # data = list(range(100))
    data = iter_(100)
    data_ = iter_(100)
    data4 = [(i,i*2) for i in range(100)]
    print("多线程处理结果：")
    res1 = apply_multi_thread(data4, process_item_, total_num=100)
    print(res1)

    print("\n多进程处理结果：")
    res2 = apply_multi_process(data_, process_item, total_num=100)
    print(res2)
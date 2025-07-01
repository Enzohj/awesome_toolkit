from loguru import logger
import csv
import json
import pandas as pd
import os
from tqdm import tqdm


# ========================
# TXT 文件读写
# ========================

def read_txt(file_path, encoding='utf-8', as_lines=True):
    """
    读取 TXT 文件内容。

    参数:
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。
        as_lines (bool): 是否按行读取，默认 True

    返回:
        str 或 list: 文件内容，若 as_lines=True 返回行列表。
    """
    with open(file_path, 'r', encoding=encoding) as f:
        if as_lines:
            content = f.readlines()
            content = [line.strip() for line in content]
            logger.debug(f"Read {len(content)} lines from '{file_path}'")
        else:
            content = f.read()
            logger.debug(f"Read {len(content)} characters from '{file_path}'")
        return content


def write_txt(file_path, content, encoding='utf-8', append=False):
    """
    写入 TXT 文件内容。

    参数:
        file_path (str): 文件路径。
        content (str 或 list): 要写入的内容。
        encoding (str): 文件编码，默认 utf-8。
        append (bool): 是否追加写入，默认 False。
    """
    mode = 'a' if append else 'w'
    with open(file_path, mode, encoding=encoding) as f:
        if isinstance(content, list):
            content = [line + '\n' for line in content]
            f.writelines(content)
            logger.debug(f"Wrote {len(content)} lines to '{file_path}' in {'append' if append else 'write'} mode")
        else:
            f.write(content)
            logger.debug(f"Wrote {len(content)} characters to '{file_path}' in {'append' if append else 'write'} mode")


# ========================
# CSV 文件读写
# ========================

def read_csv(file_path, encoding='utf-8', delimiter=',', engine=None, skip_header=True, **kwargs):
    """
    读取 CSV 文件。

    参数:
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。
        delimiter (str): 分隔符，默认 ','。
        engine (str): 读取引擎，'pandas' 或 'csv'，默认自动判断。
        skip_header (bool): 是否跳过第一行，默认 True。
        **kwargs: 传递给 pandas.read_csv 的额外参数。

    返回:
        pd.DataFrame 或 list: 文件内容。
    """
    if engine is None:
        engine = 'csv'

    if engine == 'pandas':
        df = pd.read_csv(file_path, sep=delimiter, encoding=encoding, **kwargs)
        logger.debug(f"Read CSV file '{file_path}' using pandas. Shape: {df.shape}")
        return df
    else:
        with open(file_path, 'r', encoding=encoding) as f:
            reader = csv.reader(f, delimiter=delimiter)
            if skip_header:
                next(reader)
            data = [row for row in reader]
            logger.debug(f"Read CSV file '{file_path}' using csv module. {len(data)} rows read")
            return data


def write_csv(file_path, data, encoding='utf-8', append=False, delimiter=',', engine=None, header=None, **kwargs):
    """
    写入 CSV 文件。

    参数:
        file_path (str): 文件路径。
        data (list 或 pd.DataFrame): 要写入的数据。
        encoding (str): 文件编码，默认 utf-8。
        append (bool): 是否追加写入，默认 False。
        delimiter (str): 分隔符，默认 ','。
        engine (str): 写入引擎，'pandas' 或 'csv'，默认自动判断。
        header (list): 列名，默认 None。
        **kwargs: 传递给 pandas.to_csv 的额外参数。
    """
    if engine is None:
        if isinstance(data, pd.DataFrame):
            engine = 'pandas'
        else:
            engine = 'csv'

    if engine == 'pandas':
        mode = 'a' if append else 'w'
        data.to_csv(file_path, index=False, sep=delimiter, mode=mode, encoding=encoding, **kwargs)
        logger.debug(f"Wrote DataFrame to '{file_path}' in {'append' if append else 'write'} mode. Shape: {data.shape}")
    else:
        with open(file_path, 'a' if append else 'w', newline='', encoding=encoding) as f:
            writer = csv.writer(f, delimiter=delimiter)
            if header:
                writer.writerow(header)
            writer.writerows(data)
            logger.debug(f"Wrote {len(data)} rows to '{file_path}' in {'append' if append else 'write'} mode")


# ========================
# JSON 文件读写
# ========================

def read_json(file_path, encoding='utf-8'):
    """
    读取 JSON 文件。

    参数:
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。

    返回:
        dict: 文件内容。
    """
    with open(file_path, 'r', encoding=encoding) as f:
        data = json.load(f)
        logger.debug(f"Read JSON file '{file_path}' successfully")
        return data


def write_json(file_path, data, encoding='utf-8', ensure_ascii=False, indent=4):
    """
    写入 JSON 文件。

    参数:
        file_path (str): 文件路径。
        data (dict): 要写入的数据。
        encoding (str): 文件编码，默认 utf-8。
        ensure_ascii (bool): 是否确保 ASCII 编码，默认 False。
        indent (int): 缩进空格数，默认 4。
    """
    with open(file_path, 'w', encoding=encoding) as f:
        json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
        logger.debug(f"Wrote JSON data to '{file_path}'")


# ========================
# JSONL 文件读写
# ========================

def read_jsonl(file_path, encoding='utf-8'):
    """
    读取 JSONL 文件（每行一个 JSON 对象）。

    参数:
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。

    返回:
        list: 每行解析后的对象列表。
    """
    with open(file_path, 'r', encoding=encoding) as f:
        data = [json.loads(line) for line in f if line.strip()]
        logger.debug(f"Read {len(data)} JSON objects from '{file_path}'")
        return data


def write_jsonl(file_path, data, encoding='utf-8'):
    """
    写入 JSONL 文件（每行一个 JSON 对象）。

    参数:
        file_path (str): 文件路径。
        data (list): 要写入的对象列表。
        encoding (str): 文件编码，默认 utf-8。
    """
    with open(file_path, 'w', encoding=encoding) as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
        logger.debug(f"Wrote {len(data)} JSON objects to '{file_path}'")


# ========================
# Parquet 文件读写
# ========================

def read_parquet(file_root):
    """
    读取 Parquet 文件。

    参数:
        file_root (str): 文件路径或目录路径。
        header_name (str): 列名，默认 None。

    返回:
        pd.DataFrame 或 list: 文件内容。
    """
    if os.path.isfile(file_root):
        try:
            data = pd.read_parquet(file_root)
            logger.debug(f"Successfully read Parquet file from '{file_root}'. Shape: {data.shape}")
            return data
        except Exception as e:
            logger.error(f"Error reading {file_root}: {e}")
            return pd.DataFrame()

    elif os.path.isdir(file_root):
        file_names = os.listdir(file_root)
        all_chunks = []
        for file_name in tqdm(file_names, desc="Reading Parquet files"):
            if '_SUCCESS' in file_name:
                continue
            file_path = os.path.join(file_root, file_name)
            try:
                chunks = pd.read_parquet(file_path)
                all_chunks.append(chunks)
                del chunks
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")

        # 将所有块合并成一个 DataFrame
        if all_chunks:
            data = pd.concat(all_chunks, ignore_index=True)
            logger.info(f"Successfully concatenated {len(all_chunks)} Parquet files. Shape: {data.shape}")
            return data
        else:
            logger.error(f"No data found in directory {file_root}")
            return pd.DataFrame()


def write_parquet(file_path, df, **kwargs):
    """
    写入 Parquet 文件。

    参数:
        file_path (str): 文件路径。
        df (pd.DataFrame): 要写入的 DataFrame。
        **kwargs: 传递给 DataFrame.to_parquet 的额外参数。
    """
    df.to_parquet(file_path, **kwargs)
    logger.debug(f"Wrote Parquet file '{file_path}'. Shape: {df.shape}")


if __name__ == '__main__':
    parquet_dir = '/mnt/hdfs/hjx/data/content2poi/online_sample_100w/part-00000-a605e751-2ec0-4768-a95c-0043bd8dd26e-c000.gz.parquet'
    data = read_parquet(parquet_dir)

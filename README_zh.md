# my_toolkit

[![GitHub Repo stars](https://img.shields.io/github/stars/JaxonHu1024/my_toolkit?style=social)](https://github.com/JaxonHu1024/my_toolkit/stargazers)
[![GitHub last commit](https://img.shields.io/github/last-commit/JaxonHu1024/my_toolkit)](https://github.com/JaxonHu1024/my_toolkit/commits/main)
[![GitHub license](https://img.shields.io/github/license/JaxonHu1024/my_toolkit)](https://github.com/JaxonHu1024/my_toolkit/blob/main/LICENSE)

一个简单易用的 Python 工具包，旨在简化日常开发中的常用操作。

---

## 目录

- [✨ 特性亮点](#-特性亮点)
- [💾 安装指南](#-安装指南)
- [🚀 快速开始](#-快速开始)
  - [文件操作](#文件操作)
  - [图像处理](#图像处理)
  - [日志记录](#日志记录)
  - [并行计算](#并行计算)
  - [实用装饰器](#实用装饰器)
  - [文本处理](#文本处理)
- [📜 常用脚本说明](#-常用脚本说明)
- [🤔 常见问题](#-常见问题)
- [📄 许可](#-许可)

## ✨ 特性亮点

- **统一文件接口**: 支持 `TXT`, `CSV`, `TSV`, `JSON`, `JSONL`, `Parquet`, `Pickle` 等多种格式的标准化读写，无需关心底层细节。
- **便捷图像处理**: 轻松实现 `PIL.Image`, `Bytes`, `Base64` 之间的相互转换，支持从本地或 URL 加载图像。
- **实用日志系统**: 基于标准 `logging` 提供彩色控制台日志、可选滚动文件日志、全局等级切换和安全复用。
- **高效并行处理**: 通过统一的 `apply_parallel` 入口简化多线程和多进程任务，并保证结果顺序与输入一致。
- **实用装饰器**: 提供 `@timer` (计时), `@timeout` (超时), `@retry` (重试) 等常用装饰器，提升代码健壮性。
- **轻量文本工具**: 包含文本清洗、`#hashtags#` 提取等常用文本处理功能。

## 💾 安装指南

1.  **克隆仓库**

    ```bash
    git clone https://github.com/JaxonHu1024/my_toolkit.git
    cd my_toolkit
    ```

2.  **安装项目**

    以可编辑模式安装轻量核心：

    ```bash
    python3 -m pip install -e .
    ```

    安装全部可选功能（DataFrame/Parquet、图像、进度条和 Hugging Face）：

    ```bash
    python3 -m pip install -e ".[all]"
    ```

    如需构建并安装非 editable 的 wheel：

    ```bash
    python3 -m pip wheel --no-deps . --wheel-dir dist
    python3 -m pip install dist/my_toolkit-*.whl
    ```

    依赖和最低 Python 版本（`>=3.9`）统一定义在 `pyproject.toml`；
    `setup_env/requirements.txt` 仅作为完整环境的兼容入口。

3.  **运行测试**

    ```bash
    python3 -m unittest discover -s tests -v
    ```

## 🚀 快速开始

### 文件操作

`my_toolkit` 提供了 `read_file` 和 `write_file` 两个高级函数，能够根据文件扩展名自动选择合适的读写方式。

```python
from my_toolkit.file import read_file, write_file

# 读取 JSONL 文件
data_list = read_file('data.jsonl')

# 读取 CSV 文件为 DataFrame
df = read_file('data.csv', format='dataframe')

# 写入 JSON 文件
my_dict = {"name": "my_toolkit", "version": "1.0"}
write_file(my_dict, 'config.json', indent=4)

# 以追加模式写入 TXT 文件
lines_to_append = ["hello", "world"]
write_file(lines_to_append, 'log.txt', append=True)

# 追加模式支持 TXT、CSV、TSV、JSONL。
# 其他后缀传入 append=True 会抛出明确的 ValueError。
```

### 图像处理

`MyImage` 类支持从本地路径、URL、原始 bytes、Base64 字符串或已有 `PIL.Image` 对象加载图像，也提供常用的模块级转换函数。

```python
from my_toolkit.image import MyImage, img_to_base64, base64_to_img

# 从本地路径或 URL 加载图像
image = MyImage(path='path/to/your/image.jpg')
# image = MyImage(url='https://example.com/image.png')

# 获取独立的 PIL.Image 副本；编辑后用 MyImage(img=...) 重新包装
pil_image = image.img

# 图像格式转换
img_base64 = img_to_base64(pil_image, fmt='png')

# 从 Base64 恢复图像
restored_pil_image = base64_to_img(img_base64)

# 转换格式并保存
image.convert('webp').save('converted.webp')

# 支持读取和输出 Base64 data URL
data_url = image.base64_with_prefix
same_image = MyImage(data_url)
```

### 日志记录

创建可复用的标准库 logger，支持彩色控制台输出和可选滚动文件输出。

```python
from my_toolkit.logger import init_logger, set_level

log = init_logger("demo", level="INFO", save_to="logs/app.log")

log.debug("这是一条调试信息。")
log.info("欢迎使用 my_toolkit！")
log.warning("请注意，这个操作可能耗时较长。")
log.error("文件未找到！")

# 切换所有通过 init_logger 创建的 logger
set_level("WARNING")

# 也可以通过环境变量设置日志等级，例如 LOG_LEVEL=DEBUG
```

### 并行计算

通过 `apply_parallel` 轻松执行有序并行任务。I/O 密集型任务使用 `method="thread"`，CPU 密集型任务使用 `method="process"`。

```python
from my_toolkit.mp import apply_parallel
import time

def task(item):
    time.sleep(0.1)
    return item * 2

def main():
    data = range(20)

    # 使用多线程处理 I/O 密集型任务
    results_thread = apply_parallel(data, task, method="thread", num_workers=4)

    # 使用多进程处理 CPU 密集型任务
    results_process = apply_parallel(data, task, method="process", num_workers=4)

    # error_policy："store"（默认）、"raise" 或 "ignore"
    results = apply_parallel(data, task, error_policy="store")


if __name__ == "__main__":
    main()
```

### 实用装饰器

用装饰器简化常用功能。

```python
from my_toolkit.decorator import timer, retry, timeout

@retry(max_attempts=3, delay=1)
@timeout(seconds=5)
@timer
def risky_operation(should_fail):
    if should_fail:
        raise ValueError("操作失败！")
    print("操作成功！")
    return "OK"

# 示例：函数将自动重试，并在计时结束后打印耗时
print("--- 第一次调用 (会失败并重试) ---")
risky_operation(should_fail=True)

print("\n--- 第二次调用 (直接成功) ---")
risky_operation(should_fail=False)
```

`@retry` 会在创建装饰器时校验重试参数。设置 `raise_on_failure=True` 可在所有尝试失败后重新抛出最后一次异常。

同步 `@timeout` 属于软超时：它会停止等待，但无法终止已经在后台运行的
Python 代码。有界 daemon worker 不会阻塞解释器退出，因此关键写入不能依赖
已经超时的后台任务最终完成。

### 文本处理

提供简单快捷的文本工具函数。

```python
from my_toolkit.text import normalize_text, extract_hashtag, remove_emoji_and_hashtag

text = "   欢迎来到 #my_toolkit  , 这是一个 #Python 库!   😊 "

# 标准化文本 (去除多余空格)
normalized = normalize_text(text)
print(f"标准化文本: {normalized}")

# 提取 hashtags
tags = extract_hashtag(text)
print(f"提取的标签: {tags}")

# 移除 emoji 和 hashtags
cleaned_text = remove_emoji_and_hashtag(text)
print(f"清洗后文本: {cleaned_text}")
```

## 📜 常用脚本说明

`scripts` 目录下提供了一些实用脚本，方便日常开发和管理。

-   **`hang.sh`**: 在后台挂起一个长时间运行的命令，并将标准输出和错误重定向到日志文件。

    ```bash
    # 用法: ./scripts/hang.sh <你的命令> [你的参数...]
    # 示例: 在后台运行 Python 脚本
    ./scripts/hang.sh python my_train_script.py --epochs 100
    ```
    日志会保存到唯一文件，例如 `./logs/hang_YYYYMMDD_HHMMSS.XXXXXX`。

-   **`download_hf_ckpt.sh`**: 默认从 Hugging Face 官方 endpoint 下载模型或数据集。

    ```bash
    # 用法: ./scripts/download_hf_ckpt.sh <模型名称> [保存目录]
    # 示例: 下载 Llama-3-8B-Instruct 到指定目录
    ./scripts/download_hf_ckpt.sh meta-llama/Meta-Llama-3-8B-Instruct /path/to/models
    ```
    非官方 endpoint 必须显式设置 `HF_MIRROR_ALLOW=1`；该模式会禁用隐式 token，
    并拒绝显式 `HF_TOKEN`。

-   **`kill.sh` & `cmd.sh`**: 用于进程管理。
    - `kill.sh`: 对当前用户进程只生成一次 PID 快照，确认后先发 `TERM`，任何 `KILL` 都需要再次确认。
      ```bash
      # 用法: ./scripts/kill.sh <关键词>
      # 示例: 查找并杀死所有包含 "python" 的进程
      ./scripts/kill.sh python
      ```
    - `cmd.sh`: 预览 NVIDIA GPU 使用者，需要显式安全参数，并且只发送 `TERM`。
      ```bash
      # 只处理当前用户目标
      ./scripts/cmd.sh --force

      # 跨用户必须增加额外参数
      ./scripts/cmd.sh --force --all-users
      ```

-   **`clean.sh`**: 递归删除 basename 与指定名称完全相同的条目。脚本会记录
    对象身份、排除目标根目录，并基于已打开的目录描述符执行删除而不跟随符号
    链接；确认后会在删除开始前拒绝被替换的目标和挂载边界。

    ```bash
    ./scripts/clean.sh /path/to/search cache
    ```

## 🤔 常见问题

**Q: 为什么在其他目录导入 `my_toolkit` 时会提示 `ModuleNotFoundError`？**

A: 应安装项目，而不是手动修改 `PYTHONPATH`：

```bash
cd /path/to/my_toolkit
python3 -m pip install -e .
```

之后即可在该 Python 环境的任意工作目录导入 `my_toolkit`。

## 📄 许可

本仓库遵循 [MIT License](LICENSE) 许可。

# awesome_toolkit

A comprehensive Python utility toolkit that provides standardized interfaces for common operations including file handling, image processing, logging, and parallel processing.

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [License](#license)
- [Copyright](#copyright)

## Introduction

`awesome_toolkit` is a collection of Python utilities designed to simplify and standardize common programming tasks. It provides a clean, consistent API for file operations, image processing, logging, and multi-processing/multi-threading, allowing developers to focus on their core application logic rather than reimplementing these common functionalities.

## Features

- **File Operations** (`file.py`)
  - Support for multiple file formats: TXT, CSV, JSON, JSONL, Parquet
  - Consistent read/write interfaces with comprehensive logging
  - Flexible options for encoding, appending, and format-specific parameters

- **Image Processing** (`image.py`)
  - Seamless conversion between PIL Images, byte streams, and Base64 strings
  - Support for loading images from local paths or URLs
  - Image manipulation: resizing, visualization, format conversion
  - Comprehensive error handling and logging

- **Logging** (`logger.py`)
  - Unified logging interface that works with both loguru and standard logging
  - Consistent API regardless of the underlying logging library
  - Configurable log levels and output destinations
  - Automatic fallback to standard logging when loguru is not available

- **Multi-Processing/Multi-Threading** (`mp.py`)
  - Simple interfaces for parallel execution using threads or processes
  - Built-in progress tracking with tqdm
  - Flexible worker count configuration
  - Support for both finite collections and generators

## Installation

### Prerequisites

- Python 3.x

### Basic Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Enzohj/awesome_toolkit.git
   cd awesome_toolkit
   ```

2. Install the required dependencies:
   ```bash
   pip install -r setup_env/requirements.txt
   ```

### Additional Dependencies

While only `loguru` is explicitly listed in requirements.txt, the toolkit has implicit dependencies on:

- `Pillow` (PIL) - For image processing
- `pandas` - For data handling and Parquet file operations
- `requests` - For downloading images from URLs
- `tqdm` - For progress bars

Install these dependencies as needed:

```bash
pip install pillow pandas requests tqdm
```

## Usage

### File Operations

```python
from awesome_toolkit.file import read_txt, write_txt, read_json, write_json, read_csv, write_csv, read_jsonl, write_jsonl, read_parquet, write_parquet

# TXT file operations
lines = read_txt('data.txt', encoding='utf-8', as_lines=True)
write_txt(['Line 1', 'Line 2'], 'output.txt', append=False)

# JSON file operations
data = read_json('config.json')
write_json({'key': 'value'}, 'output.json', indent=4)

# JSONL file operations
records = read_jsonl('data.jsonl')
write_jsonl([{'id': 1}, {'id': 2}], 'output.jsonl')

# CSV file operations
rows = read_csv('data.csv', delimiter=',', engine='csv')
write_csv([['id', 'name'], [1, 'John']], 'output.csv', header=None)

# Parquet file operations
df = read_parquet('data.parquet')
write_parquet(df, 'output.parquet')
```

### Image Processing

```python
from awesome_toolkit.image import ImageTool

# Load image from file path
img_tool = ImageTool(img_path='image.jpg')

# Load image from URL
img_tool = ImageTool(img_path='https://example.com/image.jpg')

# Convert between different formats
img_bytes = ImageTool.img_to_bytes(img_tool.img_pil)
img_base64 = ImageTool.bytes_to_base64(img_bytes)
img_pil = ImageTool.base64_to_img(img_base64)

# Resize image
resized_img = img_tool.resize_img(scale=0.5)

# Save image
img_tool.save_img('output.jpg')

# Visualize image
img_tool.visualize_img()
```

### Logging

```python
from awesome_toolkit.logger import logger, setup_logger

# Configure the logger
setup_logger(level="INFO", output_file="app.log")

# Use the logger
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")
```

### Multi-Processing/Multi-Threading

```python
from awesome_toolkit.mp import apply_multi_thread, apply_multi_process

# Define a function to process each item
def process_item(x):
    return x * 2

# Process items using multiple threads
data = list(range(100))
results = apply_multi_thread(data, process_item, num_workers=8)

# Process items using multiple processes
results = apply_multi_process(data, process_item, num_workers=4)

# Process a generator with progress bar
def item_generator():
    for i in range(100):
        yield i

results = apply_multi_thread(item_generator(), process_item, total_num=100)
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Copyright

Copyright (c) 2025 Enzohj

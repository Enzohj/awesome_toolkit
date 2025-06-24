# Python Toolkit

This Python toolkit provides two main utility classes, `FileTool` and `ImageTool`, designed to simplify file operations and image processing tasks.

## Table of Contents
- [Project Overview](#project-overview)
- [Classes and Functions](#classes-and-functions)
  - [FileTool](#filetool)
  - [ImageTool](#imagetool)
- [Usage Examples](#usage-examples)
  - [FileTool Usage](#filetool-usage)
  - [ImageTool Usage](#imagetool-usage)
- [Environment Setup](#environment-setup)
- [Contributing](#contributing)

## Project Overview
This project offers a set of tools for common file operations and image processing. The `FileTool` class handles reading and writing various file formats, while the `ImageTool` class provides functions for image conversion, loading, saving, and resizing.

## Classes and Functions

### FileTool
The `FileTool` class provides methods for reading and writing different file formats, including text, CSV, JSON, and Parquet files.

- `read_txt(file_path, encoding='utf-8')`: Reads the contents of a text file.
- `write_txt(file_path, content, encoding='utf-8', mode='w')`: Writes text content to a file.
- `read_csv(file_path, delimiter=',', header=0, encoding='utf-8')`: Reads a CSV file into a pandas DataFrame.
- `write_csv(file_path, data, delimiter=',', index=False, encoding='utf-8')`: Writes a pandas DataFrame to a CSV file.
- `read_json(file_path, encoding='utf-8')`: Reads the contents of a JSON file.
- `write_json(file_path, data, indent=4, encoding='utf-8')`: Writes data to a JSON file.
- `read_parquet(file_path, engine='pyarrow')`: Reads a Parquet file into a pandas DataFrame.
- `write_parquet(file_path, data, engine='pyarrow')`: Writes a pandas DataFrame to a Parquet file.

### ImageTool
The `ImageTool` class provides methods for image conversion, loading, saving, and resizing.

- `__init__(img_path=None, img_bytes=None, img_base64=None, img_pil=None)`: Initializes the `ImageTool` class with an image source.
- `img_to_base64(img_pil, img_format='JPEG')`: Converts a PIL image object to a Base64 string.
- `load_img(img_path, only_img=True)`: Loads an image from a local path or URL.
- `img_to_bytes(img_pil, img_format='JPEG')`: Converts a PIL image object to bytes.
- `base64_to_bytes(img_base64)`: Converts a Base64 string to bytes.
- `base64_to_img(img_base64, need_bytes=False)`: Converts a Base64 string to a PIL image object.
- `save_img(save_path, img_format=None)`: Saves the PIL image object to a file.
- `visualize_img()`: Visualizes the PIL image object.
- `resize_img(size=None, scale=None)`: Resizes the PIL image object.

## Usage Examples

### FileTool Usage
```python:/mnt/bn/hjx-nas-arnold/python_tool/example.py
from file import FileTool

# Initialize FileTool
file_tool = FileTool()

# Read a text file
text_content = file_tool.read_txt('example.txt')
print(text_content)

# Write a text file
file_tool.write_txt('output.txt', 'Hello, World!')

# Read a CSV file
import pandas as pd
csv_data = file_tool.read_csv('data.csv')
print(csv_data.head())

# Write a CSV file
df = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
file_tool.write_csv('output.csv', df)

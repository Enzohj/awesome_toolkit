#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "用法: $0 <目标目录> <要删除的精确文件/目录名称>" >&2
    echo "示例: $0 /home/user/docs temp_dir" >&2
    exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "错误：安全清理需要 Python 3。" >&2
    exit 127
fi

script_dir=$(cd -P -- "$(dirname -- "$0")" && pwd -P)
exec python3 "$script_dir/_clean_impl.py" "$1" "$2"

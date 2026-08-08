#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "用法: $0 <model_or_dataset_id> [save_dir]" >&2
    exit 2
fi

if ! command -v hf >/dev/null 2>&1; then
    echo "错误：未找到 Hugging Face CLI 'hf'。请先安装 huggingface_hub。" >&2
    exit 127
fi

repo_id=$1
endpoint=${HF_ENDPOINT:-https://huggingface.co}

if [ "$endpoint" != "https://huggingface.co" ]; then
    if [ "${HF_MIRROR_ALLOW:-0}" != "1" ]; then
        echo "错误：非官方 HF_ENDPOINT 需要显式设置 HF_MIRROR_ALLOW=1。" >&2
        exit 2
    fi
    if [ -n "${HF_TOKEN:-}" ]; then
        echo "错误：拒绝把 HF_TOKEN 发送到非官方 endpoint。请取消 token 后仅下载公开仓库。" >&2
        exit 2
    fi
    export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
    echo "警告：正在使用非官方 endpoint；已禁用隐式 token，仅适用于公开仓库。" >&2
fi

export HF_ENDPOINT="$endpoint"

download_args=(download "$repo_id")
if [ -n "${HF_REVISION:-}" ]; then
    download_args+=(--revision "$HF_REVISION")
fi

if [ "$#" -eq 2 ]; then
    save_dir=$2
    mkdir -p -- "$save_dir"
    download_args+=(--local-dir "$save_dir")
fi

hf "${download_args[@]}"

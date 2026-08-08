#!/usr/bin/env bash

set -uo pipefail

usage() {
    echo "用法: $0 --force [--all-users]"
    echo "预览 NVIDIA 设备使用者，并在确认后先发送 TERM；跨用户必须加 --all-users。"
}

force=0
all_users=0
for arg in "$@"; do
    case "$arg" in
        --force) force=1 ;;
        --all-users) all_users=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "未知参数: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

if [ "$force" -ne 1 ]; then
    echo "错误：该命令具有破坏性，必须显式传入 --force。" >&2
    usage >&2
    exit 2
fi

devices=(/dev/nvidia*)
if [ "${devices[0]}" = "/dev/nvidia*" ]; then
    echo "未发现 NVIDIA 设备。"
    exit 0
fi

if ! command -v fuser >/dev/null 2>&1; then
    echo "错误：未找到 fuser。" >&2
    exit 127
fi

collect_gpu_pids() {
    local pid_output token pid seen
    pid_output=$(fuser "${devices[@]}" 2>/dev/null || true)
    seen=" "
    for token in $pid_output; do
        # fuser 可能输出 1234m 之类带访问模式后缀的 token。
        pid=${token%%[!0-9]*}
        case "$pid" in
            *[!0-9]*|'') continue ;;
        esac
        case "$seen" in
            *" $pid "*) ;;
            *)
                printf '%s\n' "$pid"
                seen="${seen}${pid} "
                ;;
        esac
    done
}

pid_output=$(collect_gpu_pids)
pids=()
for pid in $pid_output; do
    pids+=("$pid")
done

if [ "${#pids[@]}" -eq 0 ]; then
    echo "没有进程正在使用 NVIDIA 设备。"
    exit 0
fi

current_uid=$(id -u)
target_pids=()
target_uids=()
target_starts=()
target_commands=()
echo "===== GPU 进程预览 ====="
for pid in "${pids[@]}"; do
    uid=$(ps -ww -p "$pid" -o uid= 2>/dev/null | tr -d '[:space:]')
    started=$(ps -ww -p "$pid" -o lstart= 2>/dev/null | awk '{$1=$1; print}')
    command_line=$(ps -ww -p "$pid" -o command= 2>/dev/null | awk '{$1=$1; print}')
    [ -n "$uid" ] || continue
    [ -n "$started" ] || continue
    printf 'PID=%s UID=%s STARTED=%s COMMAND=%s\n' \
        "$pid" "$uid" "$started" "$command_line"
    if [ "$uid" = "$current_uid" ] || [ "$all_users" -eq 1 ]; then
        target_pids+=("$pid")
        target_uids+=("$uid")
        target_starts+=("$started")
        target_commands+=("$command_line")
    else
        echo "  跳过：属于其他用户；如确需处理必须增加 --all-users。"
    fi
done

if [ "${#target_pids[@]}" -eq 0 ]; then
    echo "没有符合当前权限边界的目标。"
    exit 0
fi

printf "确认向以上筛选后的 %d 个 PID 发送 TERM 吗？(y/N) " "${#target_pids[@]}"
IFS= read -r confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "操作取消。"
    exit 0
fi

failures=0
live_gpu_pids=" "
for live_pid in $(collect_gpu_pids); do
    live_gpu_pids="${live_gpu_pids}${live_pid} "
done

for ((index = 0; index < ${#target_pids[@]}; index++)); do
    pid=${target_pids[$index]}
    expected_uid=${target_uids[$index]}
    expected_started=${target_starts[$index]}
    expected_command=${target_commands[$index]}

    live_uid=$(ps -ww -p "$pid" -o uid= 2>/dev/null | tr -d '[:space:]')
    live_started=$(ps -ww -p "$pid" -o lstart= 2>/dev/null | awk '{$1=$1; print}')
    live_command=$(ps -ww -p "$pid" -o command= 2>/dev/null | awk '{$1=$1; print}')

    if [ "$live_uid" != "$expected_uid" ] \
        || [ "$live_started" != "$expected_started" ] \
        || [ "$live_command" != "$expected_command" ]; then
        echo "跳过 PID ${pid}：确认后进程身份已变化。" >&2
        continue
    fi
    case "$live_gpu_pids" in
        *" $pid "*) ;;
        *)
            echo "跳过 PID ${pid}：确认后已不再占用 NVIDIA 设备。" >&2
            continue
            ;;
    esac

    if ! kill -TERM "$pid" 2>/dev/null; then
        echo "无法向 PID $pid 发送 TERM。" >&2
        failures=$((failures + 1))
    fi
done

if [ "$failures" -ne 0 ]; then
    exit 1
fi

echo "TERM 已发送；本脚本不会自动升级为 KILL。"

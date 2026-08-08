#!/usr/bin/env bash

set -uo pipefail

usage() {
    echo "用法: $0 <进程命令关键词>"
    echo "默认仅匹配当前用户，关键词按普通文本而非正则表达式处理。"
}

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
    usage >&2
    exit 2
fi

keyword=$1
current_uid=$(id -u)
snapshot_file=$(mktemp "${TMPDIR:-/tmp}/my-toolkit-kill.XXXXXX") || exit 1
targets_file=$(mktemp "${TMPDIR:-/tmp}/my-toolkit-kill-targets.XXXXXX") || {
    rm -f -- "$snapshot_file"
    exit 1
}
signaled_file=$(mktemp "${TMPDIR:-/tmp}/my-toolkit-kill-signaled.XXXXXX") || {
    rm -f -- "$snapshot_file" "$targets_file"
    exit 1
}
survivors_file=$(mktemp "${TMPDIR:-/tmp}/my-toolkit-kill-survivors.XXXXXX") || {
    rm -f -- "$snapshot_file" "$targets_file" "$signaled_file"
    exit 1
}

cleanup() {
    rm -f -- "$snapshot_file" "$targets_file" "$signaled_file" "$survivors_file"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# 先生成不包含后续 awk/grep 命令的稳定快照，避免匹配筛选器自身。
if ! ps -axww -o pid=,ppid=,uid=,lstart=,command= >"$snapshot_file"; then
    echo "错误：无法读取进程列表。" >&2
    exit 1
fi

awk \
    -v uid="$current_uid" \
    -v self_pid="$$" \
    -v parent_pid="$PPID" \
    -v needle="$keyword" '
    {
        pid = $1
        ppid = $2
        process_uid = $3
        started = $4 " " $5 " " $6 " " $7 " " $8
        $1 = $2 = $3 = $4 = $5 = $6 = $7 = $8 = ""
        sub(/^[[:space:]]+/, "", $0)
        if (process_uid == uid && pid != self_pid && pid != parent_pid && index($0, needle) > 0) {
            printf "%s\t%s\t%s\t%s\n", pid, process_uid, started, $0
        }
    }
' "$snapshot_file" >"$targets_file"

if [ ! -s "$targets_file" ]; then
    echo "未找到当前用户下命令中包含「${keyword}」的进程。"
    exit 0
fi

echo "===== 将发送 TERM 的进程快照 ====="
printf "PID\tUID\tSTARTED\tCOMMAND\n"
cat "$targets_file"
printf "\n确认只向以上 PID 发送 TERM 吗？(y/N) "
IFS= read -r confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "操作取消。"
    exit 0
fi

term_failures=0
while IFS=$'\t' read -r pid uid started command; do
    # PID 可能在确认期间被系统复用。所有者、启动时间和完整命令必须一致。
    live_uid=$(ps -ww -p "$pid" -o uid= 2>/dev/null | tr -d '[:space:]')
    live_started=$(ps -ww -p "$pid" -o lstart= 2>/dev/null | awk '{$1=$1; print}')
    live_command=$(ps -ww -p "$pid" -o command= 2>/dev/null | awk '{$1=$1; print}')
    if [ "$live_uid" != "$uid" ] || [ "$live_started" != "$started" ] \
        || [ "$live_command" != "$command" ]; then
        echo "跳过 PID ${pid}：进程已退出或身份已变化。" >&2
        continue
    fi
    if kill -TERM "$pid" 2>/dev/null; then
        printf "%s\t%s\t%s\t%s\n" "$pid" "$uid" "$started" "$command" >>"$signaled_file"
    else
        echo "无法向 PID $pid 发送 TERM。" >&2
        term_failures=$((term_failures + 1))
    fi
done <"$targets_file"

if [ -s "$signaled_file" ]; then
    sleep 2
    while IFS=$'\t' read -r pid uid started command; do
        live_uid=$(ps -ww -p "$pid" -o uid= 2>/dev/null | tr -d '[:space:]')
        live_started=$(ps -ww -p "$pid" -o lstart= 2>/dev/null | awk '{$1=$1; print}')
        live_command=$(ps -ww -p "$pid" -o command= 2>/dev/null | awk '{$1=$1; print}')
        if [ "$live_uid" = "$uid" ] && [ "$live_started" = "$started" ] \
            && [ "$live_command" = "$command" ] \
            && kill -0 "$pid" 2>/dev/null; then
            printf "%s\t%s\t%s\t%s\n" "$pid" "$uid" "$started" "$command" >>"$survivors_file"
        fi
    done <"$signaled_file"
fi

kill_failures=0
if [ -s "$survivors_file" ]; then
    echo "以下进程在 TERM 后仍存活："
    cat "$survivors_file"
    printf "是否仅对这些残余 PID 发送 KILL？(y/N) "
    IFS= read -r force_confirm
    if [ "$force_confirm" = "y" ] || [ "$force_confirm" = "Y" ]; then
        while IFS=$'\t' read -r pid uid started command; do
            live_uid=$(ps -ww -p "$pid" -o uid= 2>/dev/null | tr -d '[:space:]')
            live_started=$(ps -ww -p "$pid" -o lstart= 2>/dev/null | awk '{$1=$1; print}')
            live_command=$(ps -ww -p "$pid" -o command= 2>/dev/null | awk '{$1=$1; print}')
            if [ "$live_uid" != "$uid" ] || [ "$live_started" != "$started" ] \
                || [ "$live_command" != "$command" ]; then
                echo "跳过 PID ${pid}：KILL 前进程身份已变化。" >&2
                continue
            fi
            if ! kill -KILL "$pid" 2>/dev/null; then
                echo "无法 KILL PID $pid。" >&2
                kill_failures=$((kill_failures + 1))
            fi
        done <"$survivors_file"
    else
        echo "未发送 KILL。"
    fi
fi

if [ "$term_failures" -ne 0 ] || [ "$kill_failures" -ne 0 ]; then
    exit 1
fi

echo "进程处理完成。"

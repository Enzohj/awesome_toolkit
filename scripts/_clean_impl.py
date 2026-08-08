"""Descriptor-relative implementation for scripts/clean.sh."""

from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn


@dataclass(frozen=True)
class Target:
    relative_parts: tuple[str, ...]
    device: int
    inode: int
    file_type: int
    ctime_ns: int
    mtime_ns: int
    size: int
    birthtime_ns: int | None
    generation: int | None


def _fail(message: str, exit_code: int = 1) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(exit_code)


def _decode_mount_path(value: str) -> str:
    """Decode the octal escapes used by mountinfo/mount output."""
    return re.sub(
        r"\\([0-7]{3})",
        lambda match: chr(int(match.group(1), 8)),
        value,
    )


def _mount_points() -> set[Path]:
    """Return known mount points, including same-device Linux bind mounts."""
    mount_points: set[Path] = set()
    mountinfo = Path("/proc/self/mountinfo")
    if mountinfo.is_file():
        try:
            for line in mountinfo.read_text(encoding="utf-8").splitlines():
                fields = line.split()
                if len(fields) >= 5:
                    mount_points.add(
                        Path(os.path.abspath(_decode_mount_path(fields[4])))
                    )
        except OSError as error:
            _fail(f"错误：无法读取挂载信息：{error}")
        return mount_points

    try:
        result = subprocess.run(
            ["mount"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        _fail(f"错误：无法查询挂载点：{error}")
    if result.returncode != 0:
        _fail(f"错误：mount 查询失败：{result.stderr.strip()}")
    for line in result.stdout.splitlines():
        match = re.match(r"^.* on (.+) \([^)]*\)$", line)
        if match:
            mount_points.add(
                Path(os.path.abspath(_decode_mount_path(match.group(1))))
            )
    return mount_points


def _birthtime_ns(metadata: os.stat_result) -> int | None:
    value = getattr(metadata, "st_birthtime_ns", None)
    if value is not None:
        return int(value)
    seconds = getattr(metadata, "st_birthtime", None)
    return int(seconds * 1_000_000_000) if seconds is not None else None


def _snapshot(
    root: Path,
    delete_name: str,
    mount_points: set[Path],
) -> tuple[list[Target], list[Path]]:
    targets: list[Target] = []
    scan_errors: list[OSError] = []
    pruned_mounts: list[Path] = []
    root_device = root.stat().st_dev

    def record_error(error: OSError) -> None:
        scan_errors.append(error)

    for directory, dirnames, filenames in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=record_error,
    ):
        kept_directories: list[str] = []
        matched_directories: list[str] = []
        for name in dirnames:
            path = Path(directory, name)
            try:
                crosses_device = (
                    not path.is_symlink() and path.stat().st_dev != root_device
                )
            except OSError as error:
                scan_errors.append(error)
                continue
            if path in mount_points or crosses_device or os.path.ismount(path):
                pruned_mounts.append(path)
            elif name == delete_name:
                # A matched parent already contains any nested match, so snapshot it
                # once and do not traverse beneath it.
                matched_directories.append(name)
            else:
                kept_directories.append(name)
        dirnames[:] = kept_directories

        for name in (*matched_directories, *filenames):
            if name != delete_name:
                continue
            path = Path(directory, name)
            try:
                metadata = path.lstat()
            except OSError as error:
                scan_errors.append(error)
                continue
            relative = path.relative_to(root)
            targets.append(
                Target(
                    relative_parts=relative.parts,
                    device=metadata.st_dev,
                    inode=metadata.st_ino,
                    file_type=stat.S_IFMT(metadata.st_mode),
                    ctime_ns=metadata.st_ctime_ns,
                    mtime_ns=metadata.st_mtime_ns,
                    size=metadata.st_size,
                    birthtime_ns=_birthtime_ns(metadata),
                    generation=getattr(metadata, "st_gen", None),
                )
            )

    if scan_errors:
        details = "; ".join(str(error) for error in scan_errors[:3])
        _fail(f"错误：扫描不完整，未执行删除：{details}")

    return (
        sorted(targets, key=lambda item: item.relative_parts),
        sorted(set(pruned_mounts)),
    )


def _same_identity(metadata: os.stat_result, target: Target) -> bool:
    return (
        metadata.st_dev == target.device
        and metadata.st_ino == target.inode
        and stat.S_IFMT(metadata.st_mode) == target.file_type
        and metadata.st_ctime_ns == target.ctime_ns
        and metadata.st_mtime_ns == target.mtime_ns
        and metadata.st_size == target.size
        and _birthtime_ns(metadata) == target.birthtime_ns
        and getattr(metadata, "st_gen", None) == target.generation
    )


def _open_parent(root_fd: int, parts: tuple[str, ...]) -> tuple[int, str]:
    parent_fd = os.dup(root_fd)
    try:
        for component in parts[:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
            os.close(parent_fd)
            parent_fd = next_fd
        return parent_fd, parts[-1]
    except BaseException:
        os.close(parent_fd)
        raise


def _same_object(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
    )


def _remove_entry(
    parent_fd: int,
    name: str,
    absolute_path: Path,
    root_device: int,
    mount_points: set[Path],
    expected: Target | None = None,
) -> None:
    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if expected is not None and not _same_identity(metadata, expected):
        raise RuntimeError("身份已变化")
    if metadata.st_dev != root_device:
        raise RuntimeError("拒绝跨文件系统边界")
    if stat.S_ISDIR(metadata.st_mode):
        if absolute_path in mount_points or os.path.ismount(absolute_path):
            raise RuntimeError("拒绝进入挂载点")
        child_fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        try:
            opened = os.fstat(child_fd)
            if not _same_object(opened, metadata):
                raise RuntimeError("目录在打开期间被替换")
            if opened.st_dev != root_device:
                raise RuntimeError("拒绝跨文件系统边界")
            for child_name in os.listdir(child_fd):
                _remove_entry(
                    child_fd,
                    child_name,
                    absolute_path / child_name,
                    root_device,
                    mount_points,
                )
        finally:
            os.close(child_fd)
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not _same_object(current, metadata):
            raise RuntimeError("目录在删除期间被替换")
        os.rmdir(name, dir_fd=parent_fd)
    else:
        # Includes symlinks: unlink removes the link and never follows its target.
        os.unlink(name, dir_fd=parent_fd)


def _delete_target(
    root_fd: int,
    root: Path,
    root_device: int,
    mount_points: set[Path],
    target: Target,
) -> None:
    parent_fd, name = _open_parent(root_fd, target.relative_parts)
    try:
        _remove_entry(
            parent_fd,
            name,
            root.joinpath(*target.relative_parts),
            root_device,
            mount_points,
            expected=target,
        )
    finally:
        os.close(parent_fd)


def _find_mount_boundary(
    target_path: Path,
    root_device: int,
    mount_points: set[Path],
) -> Path | None:
    """Preflight a target so a later recursive delete cannot be partial."""

    def is_boundary(path: Path) -> bool:
        if path.is_symlink():
            return False
        metadata = path.stat()
        return (
            metadata.st_dev != root_device
            or path in mount_points
            or os.path.ismount(path)
        )

    if is_boundary(target_path):
        return target_path
    if not target_path.is_dir():
        return None

    for directory, dirnames, _filenames in os.walk(
        target_path,
        topdown=True,
        followlinks=False,
    ):
        for name in dirnames:
            path = Path(directory, name)
            if is_boundary(path):
                return path
    return None


def main() -> None:
    if len(sys.argv) != 3:
        _fail("用法: _clean_impl.py <目标目录> <精确名称>", 2)

    target_path, delete_name = sys.argv[1:]
    if (
        not delete_name
        or delete_name in {".", ".."}
        or os.sep in delete_name
        or (os.altsep is not None and os.altsep in delete_name)
    ):
        _fail("错误：删除名称必须是非空的单个文件名，不能包含路径分隔符。", 2)

    try:
        root = Path(target_path).resolve(strict=True)
    except OSError as error:
        _fail(f"错误：无法解析目标目录 {target_path!r}：{error}")
    if not root.is_dir():
        _fail(f"错误：目标路径 {target_path!r} 不是目录。")
    if root == Path(root.anchor):
        _fail("错误：拒绝以文件系统根目录作为清理范围。", 2)

    initial_mount_points = _mount_points()
    targets, pruned_mounts = _snapshot(root, delete_name, initial_mount_points)
    for mount_path in pruned_mounts:
        print(f"跳过挂载边界: {str(mount_path)!r}", file=sys.stderr)
    if not targets:
        print(f"未找到名称精确等于 {delete_name!r} 的文件或目录。")
        return

    print("===== 将删除的路径快照 =====")
    for target in targets:
        print(f"  {str(root.joinpath(*target.relative_parts))!r}")

    try:
        confirmation = input(f"\n确认删除以上 {len(targets)} 项吗？(y/N) ")
    except EOFError:
        confirmation = ""
    if confirmation not in {"y", "Y"}:
        print("删除操作已取消。")
        return

    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    root_device = os.fstat(root_fd).st_dev
    current_mount_points = _mount_points()
    failures = 0
    try:
        # Children first, so nested matches do not disappear behind a parent match.
        for target in sorted(
            targets,
            key=lambda item: (len(item.relative_parts), item.relative_parts),
            reverse=True,
        ):
            display_path = root.joinpath(*target.relative_parts)
            try:
                mount_boundary = _find_mount_boundary(
                    display_path,
                    root_device,
                    current_mount_points,
                )
                if mount_boundary is not None:
                    raise RuntimeError(
                        f"目标内包含挂载边界 {str(mount_boundary)!r}"
                    )
                _delete_target(
                    root_fd,
                    root,
                    root_device,
                    current_mount_points,
                    target,
                )
            except FileNotFoundError:
                print(f"跳过已消失的路径: {display_path!r}", file=sys.stderr)
            except Exception as error:
                failures += 1
                print(
                    f"拒绝删除 {str(display_path)!r}：身份已变化或安全检查失败：{error}",
                    file=sys.stderr,
                )
            else:
                print(f"已删除: {str(display_path)!r}")
    finally:
        os.close(root_fd)

    if failures:
        _fail(f"清理完成，但有 {failures} 项被安全检查拦截。")
    print("删除操作完成。")


if __name__ == "__main__":
    main()

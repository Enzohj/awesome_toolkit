from __future__ import annotations

import os
import runpy
import select
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"


class TestScriptSafety(unittest.TestCase):
    def test_documented_scripts_are_executable_with_shebangs(self):
        for name in (
            "clean.sh",
            "cmd.sh",
            "download_hf_ckpt.sh",
            "hang.sh",
            "kill.sh",
        ):
            path = SCRIPTS / name
            self.assertTrue(os.access(path, os.X_OK), name)
            self.assertTrue(path.read_text(encoding="utf-8").startswith("#!"), name)

    def test_hang_uses_a_unique_log_for_same_second_launches(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_bin = root / "bin"
            log_dir = root / "logs"
            fake_bin.mkdir()
            fake_date = fake_bin / "date"
            fake_date.write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' '20260808_180000'\n",
                encoding="utf-8",
            )
            fake_date.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["HANG_LOG_DIR"] = str(log_dir)

            for message in ("first", "second"):
                result = subprocess.run(
                    [
                        str(SCRIPTS / "hang.sh"),
                        sys.executable,
                        "-c",
                        f"print({message!r})",
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=env,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                logs = list(log_dir.iterdir())
                if len(logs) == 2:
                    break
                time.sleep(0.02)

            self.assertEqual(len(logs), 2)

    def test_clean_does_not_match_the_target_root_itself(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "cache"
            target.mkdir()
            result = subprocess.run(
                [str(SCRIPTS / "clean.sh"), str(target), "cache"],
                input="y\n",
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(target.is_dir())
            self.assertIn("未找到", result.stdout)

    def test_clean_handles_newline_in_filename_without_escaping_target(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            target = base / "target"
            target.mkdir()
            unusual_name = "x\nvictim"
            unusual = target / unusual_name
            unusual.write_text("inside", encoding="utf-8")
            outside = base / "victim"
            outside.write_text("outside", encoding="utf-8")

            result = subprocess.run(
                [str(SCRIPTS / "clean.sh"), str(target), unusual_name],
                input="y\n",
                text=True,
                capture_output=True,
                cwd=base,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(unusual.exists())
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside")

    def test_clean_does_not_delete_an_object_replaced_after_preview(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "target"
            target.mkdir()
            victim = target / "cache"
            victim.write_text("previewed object", encoding="utf-8")

            process = subprocess.Popen(
                [str(SCRIPTS / "clean.sh"), str(target), "cache"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                preview = b""
                deadline = time.monotonic() + 5
                while b"(y/N) " not in preview:
                    remaining = deadline - time.monotonic()
                    self.assertGreater(
                        remaining,
                        0,
                        "clean confirmation prompt timed out",
                    )
                    ready, _, _ = select.select(
                        [process.stdout.fileno()],
                        [],
                        [],
                        remaining,
                    )
                    self.assertTrue(ready, "clean confirmation prompt timed out")
                    chunk = os.read(process.stdout.fileno(), 4096)
                    self.assertNotEqual(chunk, b"", "clean exited before confirmation")
                    preview += chunk

                victim.unlink()
                victim.write_text("replacement object", encoding="utf-8")
                process.stdin.write(b"y\n")
                process.stdin.flush()
                stdout_rest, stderr_bytes = process.communicate(timeout=5)
                stdout = (preview + stdout_rest).decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=2)

            self.assertNotEqual(process.returncode, 0, stdout + stderr)
            self.assertEqual(
                victim.read_text(encoding="utf-8"),
                "replacement object",
            )
            self.assertIn("身份已变化", stderr)

    def test_clean_recurses_without_following_symlinks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "target"
            outside = root / "outside"
            cache = target / "nested" / "cache"
            cache.mkdir(parents=True)
            outside.mkdir()
            (outside / "preserve.txt").write_text("safe", encoding="utf-8")
            (cache / "local.txt").write_text("delete", encoding="utf-8")
            (cache / "outside-link").symlink_to(outside, target_is_directory=True)

            result = subprocess.run(
                [str(SCRIPTS / "clean.sh"), str(target), "cache"],
                input="y\n",
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(cache.exists())
            self.assertEqual(
                (outside / "preserve.txt").read_text(encoding="utf-8"),
                "safe",
            )

    def test_clean_preflight_rejects_a_nested_mount_boundary(self):
        helper = runpy.run_path(str(SCRIPTS / "_clean_impl.py"))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            cache = root / "cache"
            mounted = cache / "mounted-volume"
            mounted.mkdir(parents=True)
            simulated_mounts = {mounted}

            targets, _pruned = helper["_snapshot"](
                root,
                "cache",
                simulated_mounts,
            )
            boundary = helper["_find_mount_boundary"](
                cache,
                root.stat().st_dev,
                simulated_mounts,
            )

            self.assertEqual(len(targets), 1)
            self.assertEqual(boundary, mounted)

    def test_clean_collapses_nested_matches_into_the_parent_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outer = root / "cache"
            inner = outer / "cache"
            inner.mkdir(parents=True)
            (inner / "data.txt").write_text("delete", encoding="utf-8")

            result = subprocess.run(
                [str(SCRIPTS / "clean.sh"), str(root), "cache"],
                input="y\n",
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(outer.exists())
            self.assertEqual(result.stdout.count("已删除:"), 1)

    def test_kill_cancellation_leaves_the_previewed_process_running(self):
        marker = f"my-toolkit-kill-{uuid.uuid4().hex}"
        sleeper = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)", marker]
        )
        try:
            time.sleep(0.05)
            with tempfile.TemporaryDirectory() as td:
                fake_ps = Path(td) / "ps"
                fake_ps.write_text(
                    "#!/usr/bin/env bash\n"
                    f"printf '%s %s %s Sat Aug 08 18:00:00 2026 %s\\n' "
                    f"{sleeper.pid} 1 {os.getuid()} "
                    f"'python sleeper {marker}'\n",
                    encoding="utf-8",
                )
                fake_ps.chmod(0o755)
                env = os.environ.copy()
                env["PATH"] = f"{td}{os.pathsep}{env.get('PATH', '')}"
                result = subprocess.run(
                    [str(SCRIPTS / "kill.sh"), marker],
                    input="n\n",
                    text=True,
                    errors="replace",
                    capture_output=True,
                    check=False,
                    env=env,
                )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(sleeper.pid), result.stdout)
            self.assertIsNone(sleeper.poll())
        finally:
            sleeper.terminate()
            try:
                sleeper.wait(timeout=2)
            except subprocess.TimeoutExpired:
                sleeper.kill()
                sleeper.wait(timeout=2)

    def test_kill_skips_a_pid_when_identity_changes_after_preview(self):
        marker = f"my-toolkit-reused-pid-{uuid.uuid4().hex}"
        sleeper = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)", marker]
        )
        try:
            time.sleep(0.05)
            with tempfile.TemporaryDirectory() as td:
                fake_bin = Path(td)
                fake_ps = fake_bin / "ps"
                fake_ps.write_text(
                    "#!/usr/bin/env bash\n"
                    "case \" $* \" in\n"
                    "  *\" pid=,ppid=,uid=,lstart=,command= \"*)\n"
                    f"    printf '%s %s %s Sat Aug 08 18:00:00 2026 %s\\n' "
                    f"{sleeper.pid} 1 {os.getuid()} "
                    f"'python sleeper {marker}' ;;\n"
                    "  *\" uid= \"*) printf '%s\\n' \"$(id -u)\" ;;\n"
                    "  *\" lstart= \"*) printf '%s\\n' 'Sat Aug 08 18:00:00 2026' ;;\n"
                    "  *\" command= \"*) printf '%s\\n' 'different command' ;;\n"
                    "esac\n",
                    encoding="utf-8",
                )
                fake_ps.chmod(0o755)
                env = os.environ.copy()
                env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
                result = subprocess.run(
                    [str(SCRIPTS / "kill.sh"), marker],
                    input="y\n",
                    text=True,
                    errors="replace",
                    capture_output=True,
                    check=False,
                    env=env,
                )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("身份已变化", result.stderr)
            self.assertIsNone(sleeper.poll())
        finally:
            sleeper.terminate()
            try:
                sleeper.wait(timeout=2)
            except subprocess.TimeoutExpired:
                sleeper.kill()
                sleeper.wait(timeout=2)

    def test_hf_mirror_rejects_explicit_token(self):
        with tempfile.TemporaryDirectory() as td:
            fake_bin = Path(td)
            fake_hf = fake_bin / "hf"
            fake_hf.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
            fake_hf.chmod(0o755)
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
                    "HF_ENDPOINT": "https://mirror.invalid",
                    "HF_MIRROR_ALLOW": "1",
                    "HF_TOKEN": "secret-value",
                }
            )
            result = subprocess.run(
                [str(SCRIPTS / "download_hf_ckpt.sh"), "public/repo"],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("拒绝把 HF_TOKEN", result.stderr)

    def test_gpu_killer_requires_explicit_force_flag(self):
        result = subprocess.run(
            [str(SCRIPTS / "cmd.sh")],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--force", result.stderr)

    def test_setup_guidance_is_documentation_not_extensionless_shell(self):
        setup_dir = REPO_ROOT / "setup_env"
        self.assertTrue((setup_dir / "README.md").is_file())
        for legacy_name in ("init_git", "init_linux", "init_conda"):
            self.assertFalse((setup_dir / legacy_name).exists(), legacy_name)


if __name__ == "__main__":
    unittest.main(verbosity=2)

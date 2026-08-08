"""tests/test_file.py

对 `my_toolkit.file` 的最小可运行测试脚本。

运行方式：
    - `python -m unittest tests.test_file -v`
"""

from __future__ import annotations

import subprocess
import stat
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

try:
    import pandas as pd
except ModuleNotFoundError:  # Core file helpers do not require the data extra.
    pd = None

try:
    import pyarrow  # noqa: F401 - capability check for Parquet tests
except ModuleNotFoundError:
    HAS_PARQUET_ENGINE = False
else:
    HAS_PARQUET_ENGINE = True

from my_toolkit.file import (
    ParquetReadError,
    read_csv,
    read_file,
    read_json,
    read_jsonl,
    read_parquet,
    read_pickle,
    read_txt,
    write_csv,
    write_file,
    write_json,
    write_jsonl,
    write_parquet,
    write_pickle,
    write_txt,
)


class TestOptionalDependencies(unittest.TestCase):
    def test_core_file_apis_work_when_pandas_is_unavailable(self):
        script = textwrap.dedent(
            """
            import builtins
            import tempfile
            from pathlib import Path

            real_import = builtins.__import__

            def import_without_pandas(name, *args, **kwargs):
                if name == "pandas" or name.startswith("pandas."):
                    raise ModuleNotFoundError("blocked pandas", name="pandas")
                return real_import(name, *args, **kwargs)

            builtins.__import__ = import_without_pandas

            from my_toolkit.file import (
                read_csv,
                read_json,
                read_parquet,
                read_txt,
                write_csv,
                write_json,
                write_parquet,
                write_txt,
            )

            def assert_requires_pandas(call):
                try:
                    call()
                except ImportError as error:
                    assert "my-toolkit[data]" in str(error)
                else:
                    raise AssertionError("operation should require pandas")

            with tempfile.TemporaryDirectory() as td:
                root = Path(td)

                txt_path = root / "data.txt"
                write_txt(["alpha", "beta"], txt_path)
                assert read_txt(txt_path) == ["alpha", "beta"]

                json_path = root / "data.json"
                write_json({"ready": True}, json_path)
                assert read_json(json_path) == {"ready": True}

                csv_path = root / "data.csv"
                write_csv([["1", "x"]], csv_path, header=["a", "b"])
                assert read_csv(csv_path, format="list") == [["1", "x"]]

                assert_requires_pandas(
                    lambda: read_csv(csv_path, format="dataframe")
                )
                assert_requires_pandas(
                    lambda: write_csv({"a": [1]}, csv_path)
                )
                assert_requires_pandas(
                    lambda: read_parquet(root / "data.parquet")
                )
                assert_requires_pandas(
                    lambda: write_parquet(object(), root / "data.parquet")
                )
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TestFileTxt(unittest.TestCase):
    def test_txt_roundtrip_lines_and_string(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a" / "b.txt"

            write_txt(["  hello ", "world"], p)
            self.assertEqual(read_txt(p, as_lines=True), ["  hello ", "world"])

            # 覆盖写入字符串
            write_txt("raw\ntext\n", p)
            self.assertEqual(read_txt(p, as_lines=False), "raw\ntext\n")

    def test_txt_append(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "append.txt"
            write_txt(["a"], p)
            write_txt(["b"], p, append=True)
            self.assertEqual(read_txt(p, as_lines=True), ["a", "b"])


class TestFileJson(unittest.TestCase):
    def test_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "obj.json"
            obj = {"a": 1, "b": [1, 2], "c": {"x": "y"}}
            write_json(obj, p)
            self.assertEqual(read_json(p), obj)

    def test_jsonl_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "rows.jsonl"
            rows = [{"i": 0}, {"i": 1}, {"i": 2, "s": "中文"}]
            write_jsonl(rows, p)
            self.assertEqual(read_jsonl(p), rows)

    def test_json_serialization_failure_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            path = directory / "state.json"
            original = b'{"status":"stable"}\n'
            path.write_bytes(original)

            with self.assertRaises(TypeError):
                write_json({"ok": 1, "bad": object()}, path)

            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(directory.iterdir()), [path])

    def test_json_atomic_overwrite_preserves_existing_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shared.json"
            path.write_text('{"old": true}', encoding="utf-8")
            path.chmod(0o640)

            write_json({"new": True}, path)

            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
            self.assertEqual(read_json(path), {"new": True})


class TestFilePickle(unittest.TestCase):
    def test_pickle_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "obj.pkl"
            obj = {"k": (1, 2, 3), "v": {"nested": True}}
            write_pickle(obj, p)
            self.assertEqual(read_pickle(p), obj)


class TestFileCsvParquetDispatcher(unittest.TestCase):
    @unittest.skipIf(pd is None, "pandas is not installed")
    def test_csv_roundtrip_dataframe(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.csv"

            df = pd.DataFrame({"a": [1, 2], "b": ["x", None]})
            write_csv(df, p)
            read_df = read_csv(p, format="dataframe")
            self.assertEqual(read_df.shape, (2, 2))
            # replace_na=True 会把 NaN 替换为 None
            self.assertIsNone(read_df.loc[1, "b"])

    def test_csv_roundtrip_list(self):
        with tempfile.TemporaryDirectory() as td:
            p2 = Path(td) / "rows.tsv"
            rows = [["1", "x"], ["2", "y"]]
            write_csv(rows, p2, sep="\t", header=["a", "b"])
            read_rows = read_csv(p2, sep="\t", format="list", skip_header=True)
            self.assertEqual(read_rows, rows)

    @unittest.skipIf(pd is None, "pandas is not installed")
    def test_csv_append_dataframe_adds_missing_line_break(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "data.csv"
            path.write_text("a,b\n1,2", encoding="utf-8")

            write_csv(pd.DataFrame({"a": [3], "b": [4]}), path, append=True)

            self.assertEqual(path.read_text(encoding="utf-8"), "a,b\n1,2\n3,4\n")

    def test_csv_append_list_adds_missing_line_break(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "data.csv"
            path.write_text("a,b\n1,2", encoding="utf-8")

            write_csv([[3, 4]], path, append=True)

            self.assertEqual(path.read_text(encoding="utf-8"), "a,b\n1,2\n3,4\n")

    @unittest.skipIf(pd is None, "pandas is not installed")
    def test_csv_dataframe_rejects_unknown_keyword_argument(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "data.csv"
            path.write_text("a,b\n1,2\n", encoding="utf-8")

            with self.assertRaises(TypeError):
                read_csv(path, format="dataframe", unknown_option=True)

    def test_csv_list_rejects_unknown_keyword_argument(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "data.csv"
            path.write_text("a,b\n1,2\n", encoding="utf-8")

            with self.assertRaises(TypeError):
                read_csv(path, format="list", unknown_option=True)

    @unittest.skipUnless(
        pd is not None and HAS_PARQUET_ENGINE,
        "pandas and pyarrow are required",
    )
    def test_parquet_roundtrip_if_available(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.parquet"
            df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
            write_parquet(df, p)
            read_df = read_parquet(p)
            self.assertEqual(read_df.shape, df.shape)

    @unittest.skipUnless(
        pd is not None and HAS_PARQUET_ENGINE,
        "pandas and pyarrow are required",
    )
    def test_parquet_directory_raises_structured_error_for_bad_shard(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good_path = root / "part-00000"
            bad_path = root / "part-00001.parquet"
            pd.DataFrame({"a": [1]}).to_parquet(good_path, index=False)
            bad_path.write_bytes(b"not parquet")
            (root / "README.txt").write_text("not a shard", encoding="utf-8")

            with self.assertRaises(ParquetReadError) as raised:
                read_parquet(root)

            error = raised.exception
            self.assertEqual(error.file_root, root)
            self.assertEqual(set(error.failures), {bad_path})
            self.assertIsInstance(error.failures[bad_path], Exception)

    @unittest.skipUnless(
        pd is not None and HAS_PARQUET_ENGINE,
        "pandas and pyarrow are required",
    )
    def test_parquet_directory_allows_explicit_partial_read_with_warning(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good_path = root / "part-00000"
            bad_path = root / "part-00001.parquet"
            pd.DataFrame({"a": [1]}).to_parquet(good_path, index=False)
            bad_path.write_bytes(b"not parquet")
            (root / "README.txt").write_text("not a shard", encoding="utf-8")

            with self.assertLogs("my_toolkit.file", level="WARNING") as captured:
                result = read_parquet(root, allow_partial=True)

            self.assertEqual(result.to_dict(orient="list"), {"a": [1]})
            warning_messages = [
                message for message in captured.output
                if "Returning partial Parquet data" in message
            ]
            self.assertEqual(len(warning_messages), 1)
            self.assertIn(bad_path.name, warning_messages[0])

    def test_dispatcher_read_write(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)

            # txt
            p_txt = base / "a.txt"
            write_file(["x", "y"], p_txt)
            self.assertEqual(read_file(p_txt, as_lines=True), ["x", "y"])

            # json
            p_json = base / "a.json"
            obj = {"x": 1}
            write_file(obj, p_json)
            self.assertEqual(read_file(p_json), obj)

            # pickle
            p_pkl = base / "a.pkl"
            obj2 = [1, 2, 3]
            write_file(obj2, p_pkl)
            self.assertEqual(read_file(p_pkl), obj2)

    def test_dispatcher_unsupported_suffix(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.unsupported"
            with self.assertRaises(ValueError):
                read_file(p)


if __name__ == "__main__":
    unittest.main(verbosity=2)

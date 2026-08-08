# Toolkit Reliability Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use test-first vertical slices and review each subsystem before integration.

**Goal:** Make `my_toolkit` installable and testable, then remove the confirmed data-integrity, concurrency, image-consistency, and destructive-script failures found in the 2026-08-08 audit.

**Architecture:** Move Python modules into a standard `src/my_toolkit` package and tests into `tests/`, preserving public imports. Keep fixes behind existing public interfaces; add strict failure defaults where silent partial results or destructive ambiguity currently exist. Shell tools keep their command names but snapshot targets and require explicit unsafe opt-ins.

**Tech Stack:** Python 3.9+, setuptools/PEP 517, stdlib `unittest`, pandas/pyarrow/Pillow optional extras, Bash.

## Global Constraints

- Preserve the public imports documented as `my_toolkit.<module>`.
- Preserve unrelated user files and existing Git history.
- Do not stage, commit, push, or publish without explicit authorization.
- Every confirmed bug fix starts with a public-interface regression test.
- Optional dependencies may skip only their own capability tests; package import failures must fail tests.
- Destructive scripts must operate on the exact targets shown during confirmation.

---

### Task 1: Package and test foundation

**Files:**
- Create: `pyproject.toml`
- Create: `src/my_toolkit/__init__.py`
- Move: `file.py`, `image.py`, `logger.py`, `mp.py`, `decorator.py`, `benchmark.py`, `text.py` to `src/my_toolkit/`
- Move/rename: `test/*.py` to `tests/test_*.py`
- Create: `.github/workflows/tests.yml`

**Interfaces:**
- Produces: installable imports such as `from my_toolkit.file import read_file`.
- Produces: `python -m unittest discover -s tests -v` collecting at least one test.

- [x] **Step 1: Prove the current package cannot be installed/imported**

```bash
python3 -m pip install --no-deps .
python3 -c "import my_toolkit"
python3 -m unittest discover -s test -v
```

Expected before implementation: install/import failure and zero discovered tests.

- [x] **Step 2: Add package metadata and move modules/tests**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "my-toolkit-jaxon"
version = "0.1.0"
requires-python = ">=3.9"
```

- [x] **Step 3: Remove test `sys.path` mutation and broad import-to-skip wrappers**

```python
from my_toolkit.file import read_json, write_json
```

Import failures must stop the suite; optional libraries are checked inside only the tests that require them.

- [x] **Step 4: Verify the package from outside the repository**

```bash
python3 -m pip install --no-deps -e .
cd /tmp
python3 -c "import my_toolkit; import my_toolkit.text"
python3 -m unittest discover -s tests -v
```

---

### Task 2: File I/O integrity

**Files:**
- Modify: `src/my_toolkit/file.py`
- Test: `tests/test_file.py`

**Interfaces:**
- Consumes/produces: `read_parquet`, `write_csv`, `write_json`, `read_csv`.

- [x] **Step 1: Add a failing CSV append regression test**

```python
def test_csv_append_inserts_missing_newline(self):
    path.write_text("a,b\n1,2", encoding="utf-8")
    write_csv([["3", "4"]], path, append=True)
    self.assertEqual(path.read_text(), "a,b\n1,2\n3,4\n")
```

- [x] **Step 2: Add the missing separator before both DataFrame and list append writes**

Use `_needs_append_newline` and a shared helper so both branches have identical behavior.

- [x] **Step 3: Add a failing atomic JSON overwrite regression test**

```python
path.write_text('{"preserve": true}', encoding="utf-8")
with self.assertRaises(TypeError):
    write_json({"bad": object()}, path)
self.assertEqual(path.read_text(), '{"preserve": true}')
```

- [x] **Step 4: Serialize to a same-directory temporary file and atomically replace**

Use `tempfile.NamedTemporaryFile(delete=False, dir=file_path.parent)`, flush/fsync, `os.replace`, and cleanup on failure.

- [x] **Step 5: Add strict Parquet-directory failure behavior**

```python
with self.assertRaises(ParquetReadError) as ctx:
    read_parquet(directory)
self.assertIn("bad.parquet", str(ctx.exception))
```

Default behavior raises with failed paths. Partial reads require `allow_partial=True` and log a warning.

- [x] **Step 6: Reject unknown CSV keyword arguments**

```python
with self.assertRaises(TypeError):
    read_csv(path, format="list", typo_option=True)
```

---

### Task 3: Timeout, parallelism, and benchmark truthfulness

**Files:**
- Modify: `src/my_toolkit/decorator.py`
- Modify: `src/my_toolkit/mp.py`
- Modify: `src/my_toolkit/benchmark.py`
- Test: `tests/test_decorator.py`
- Test: `tests/test_mp.py`
- Test: `tests/test_benchmark.py`

**Interfaces:**
- Consumes/produces: `timeout`, `apply_parallel`, `benchmark`.

- [x] **Step 1: Specify synchronous timeout as a soft timeout and bound worker growth**

```python
@timeout(0.01)
def slow():
    time.sleep(0.1)

with self.assertRaises(TimeoutError):
    slow()
```

Use one bounded module-level executor rather than a new executor per call; document that running Python code cannot be forcibly cancelled.

- [x] **Step 2: Preserve domain `TimeoutError` exceptions**

```python
@timeout(1)
def domain_failure():
    raise TimeoutError("domain timeout")

with self.assertRaisesRegex(TimeoutError, "domain timeout"):
    domain_failure()
```

- [x] **Step 3: Make Mapping input a supported iterable**

```python
self.assertEqual(
    apply_parallel({"a": 1, "b": 2}, str.upper, show_progress=False),
    ["A", "B"],
)
```

Materialize non-Sequence iterables; never assume `__getitem__` implies slice support.

- [x] **Step 4: Separate benchmark infrastructure errors from timeouts**

```python
self.assertEqual(report["timeout_count"], 0)
self.assertEqual(report["infrastructure_error_count"], 1)
self.assertEqual(report["errors"][0]["error_kind"], "infrastructure")
```

Do not inject synthetic timeout latency into percentiles. Use `getattr(func, "__name__", type(func).__name__)` for callable objects.

---

### Task 4: Image and text consistency

**Files:**
- Modify: `src/my_toolkit/image.py`
- Modify: `src/my_toolkit/text.py`
- Test: `tests/test_image.py`
- Create: `tests/test_text.py`

**Interfaces:**
- Consumes/produces: `MyImage`, `normalize_text`, `extract_hashtag`, `remove_emoji_and_hashtag`.

- [x] **Step 1: Reject conflicting data-URL MIME and payload formats**

```python
with self.assertRaises(ImageFormatError):
    MyImage(base64="data:image/png;base64," + jpeg_payload)
```

- [x] **Step 2: Prevent stale serialized caches after image mutation**

Return a copy from `.img` so callers cannot mutate internal pixels without going through a cache-invalidating operation.

- [x] **Step 3: Preserve alpha for in-memory images without a source format**

Default RGBA/LA/P images to PNG instead of JPEG.

- [x] **Step 4: Add the documented text API and deterministic hashtag order**

```python
self.assertEqual(normalize_text("  a   b "), "a b")
self.assertEqual(extract_hashtag("#alpha #beta #alpha"), ["alpha", "beta"])
```

Keep `normalize` as a compatibility alias.

---

### Task 5: Destructive script safety

**Files:**
- Modify: `scripts/kill.sh`
- Modify: `scripts/clean.sh`
- Modify: `scripts/cmd.sh`
- Modify: `scripts/download_hf_ckpt.sh`
- Replace/document: `setup_env/init_git`, `setup_env/init_linux`, `setup_env/init_conda`
- Create: `tests/test_scripts.py`

**Interfaces:**
- Consumes/produces: existing script command names and positional arguments.

- [x] **Step 1: Snapshot and confirm exact process targets**

`kill.sh` uses one `ps` snapshot, literal matching by default, excludes its PID and parent PID, restricts to current UID, sends TERM first, and uses KILL only after explicit second confirmation.

- [x] **Step 2: Constrain cleanup paths**

`clean.sh` snapshots device/inode/type identity and delegates deletion to a
descriptor-relative Python helper that refuses symlink traversal and replaced
targets. It preflights and rejects mount boundaries before deletion starts,
while reporting every blocked deletion.

- [x] **Step 3: Make GPU-wide killing explicit**

`cmd.sh` previews PID/UID/command and requires `--all-users --force` before crossing the current UID boundary.

- [x] **Step 4: Make Hugging Face mirrors opt-in and token-safe**

Default to `https://huggingface.co`; a non-official endpoint requires `HF_MIRROR_ALLOW=1`, rejects `HF_TOKEN`, and exports `HF_HUB_DISABLE_IMPLICIT_TOKEN=1`.

- [x] **Step 5: Convert dangerous setup snippets into documentation or parameterized fail-fast scripts**

`init_git` becomes Markdown guidance. Linux setup pins an installer version/checksum, resolves paths relative to the script, supports the detected architecture, and updates a managed shell block idempotently.

---

### Task 6: Documentation and final verification

**Files:**
- Modify: `README.md`
- Modify: `README_zh.md`
- Modify: `setup_env/requirements.txt`
- Modify: `.gitignore`

**Interfaces:**
- Produces: installation, testing, multiprocessing, and script examples that run as written.

- [x] **Step 1: Update install and test instructions**

Document `pip install -e '.[all]'` (the suite uses stdlib `unittest`, so no dev
extra is needed), wheel installation, and `python -m unittest discover -s tests -v`.

- [x] **Step 2: Add safe multiprocessing and script examples**

Every process example uses `if __name__ == "__main__":`; shell examples use executable scripts with explicit safety flags.

- [x] **Step 3: Run focused and full verification**

```bash
python3 -m unittest discover -s tests -v
python3 -m pip wheel --no-deps . -w /tmp/my-toolkit-wheel
bash -n scripts/*.sh
git diff --check
git status --short
```

Expected: all mandatory tests pass, optional tests are narrowly skipped only when their extra is absent, a wheel is created, Shell syntax passes, and no unrelated files are changed.

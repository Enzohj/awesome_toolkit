# Environment setup notes

The old extensionless `init_git`, `init_linux`, and `init_conda` files mixed
documentation with executable shell commands. Running them could overwrite Git
identity, remove `origin`, append machine-specific paths repeatedly, or execute
an unverified installer. They have been replaced by these manual, reviewable
instructions.

## Python package

From the repository root:

```bash
python3 -m pip install -e ".[all]"
python3 -m unittest discover -s tests -v
```

Use an isolated virtual environment when possible. Runtime dependencies and
optional feature groups are defined in `pyproject.toml`.

## Git identity and SSH

Inspect the current scope before changing it:

```bash
git config --list --show-origin
git remote -v
```

Set identity only in the intended scope. Replace the example values before
running either command:

```bash
git config --local user.name "YOUR_NAME"
git config --local user.email "YOUR_EMAIL"
```

Generate an SSH key only after choosing an explicit destination that does not
already exist. Do not remove or replace `origin` as part of environment setup.

## Linux and Conda

Install Miniforge from its official release page. Pin a release compatible with
the detected operating system and architecture, download into a fresh temporary
directory, and verify the published SHA-256 checksum before executing it.

After installation, let Conda generate its own shell integration instead of
copying a machine-specific hook:

```bash
conda init bash
conda config --set auto_activate_base false
```

Do not add private cache paths, internal HDFS addresses, Git identity, or API
tokens to a reusable repository setup file. Store secrets in a system keychain
or secret manager and inject them only into the process that needs them.


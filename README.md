# cppboot

Bootstrap a professional-grade C++ project environment so you can start writing code immediately.

## Install

```bash
pip install -e .
# or
python3 -m pip install -e .
```

## Usage

```bash
cppboot --name myproj
cppboot -n myproj --license mit --with-modules
cppboot -n myproj --no-vscode --no-vim --no-github-actions --no-ctags
cppboot -n myproj --github   # opt-in: create remote with gh
```

Every project includes a **version** library API driven by a root **`VERSION`**
file (single source of truth) and CLI **`--version` / `-V`**.

### Options

Requires **Python 3.9+** (including Amazon Linux’s system 3.9).

| Flag | Default | Description |
|------|---------|-------------|
| `-n`, `--name` | (prompt) | Project name |
| `--license` | `apache-2.0` | License id |
| `--build-system` | `cmake` | Only `cmake` for now |
| `--with-modules` | off | C++20 modules scaffold (opt-in) |
| `--shared` | off | Shared library instead of static (opt-in) |
| `--github` | off | Create GitHub remote with `gh` (opt-in) |
| `--output-dir` | `.` | Parent directory for the new project |
| `-v`, `--verbose` | off | Verbose logging |
| `--version` | | Print cppboot version |
| `-h`, `--help` | | Help |

**Opinionated defaults (always on).** Disable only with `--no-*`:

| Opt-out | Skips |
|---------|--------|
| `--no-vim` | Project-local `.vimrc` |
| `--no-ctags` | Universal Ctags `.ctags` + `make tags` |
| `--no-vscode` | VS Code + `CMakePresets.json` |
| `--no-github-actions` | CI / sanitizers / release workflows |
| `--no-codespaces` | Codespaces / Dev Container |
| `--no-community-docs` | CoC / CONTRIBUTING / SECURITY |
| `--no-git` | `git init` + initial commit |
| `--no-fmt` | `make fmt` after scaffolding |

## What you get

- CMake (C++20) + GNU Makefile + Windows **`build.bat`** + `CMakePresets.json`
- Root **`VERSION`** file → CMake / `--version` / release workflow stay in sync
- Default **version** component + app CLI `--version` + tests + benchmark
- Library + app + GoogleTest + Google Benchmark
- Default app deps (FetchContent, ON): **CLI11**, **nlohmann/json**, **spdlog**
- Component-oriented `src/` layout with explicit source lists
- `.clang-format` (**Microsoft** layout); code logic/naming per **Google C++ Style Guide**
- `.clangd`, Doxygen, warnings-as-errors, `compile_commands.json`
- Root convenience binary symlink (`./myproj` after `make`)
- **Default ON:** `.vimrc`, ctags, VS Code (clangd, CMake Tools, CodeLLDB, **C++ TestMate**), GitHub Actions CI, **Codespaces** (`.devcontainer/`)
- **Default OFF:** `--github` remote creation
- After scaffolding: runs **`make fmt`**, then **`git init` + add + initial commit**
- `README.md`, `AGENTS.md`
- Repo-local **CODE_OF_CONDUCT.md** (short, technology-first), **CONTRIBUTING.md**,
  **SECURITY.md** (override GitHub user/org default community files)

## Post-bootstrap state

When `make`/`clang-format` and `git` are available, a new project ends with:

1. Sources formatted to the checked-in Microsoft `.clang-format`
2. A single **Initial commit from cppboot** containing the full tree

Developers can start work with a clean `git status` and predictable formatting.

## Development / tests

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
python3 -m ruff check src tests
python3 -m ruff format --check src tests
python3 -m mypy
python3 -m build && python3 -m twine check dist/*
```

Tests cover CLI parsing, name/license logic, and filesystem generation with
**offline licenses** and **no network / no `gh`**. Optional markers:

- `@pytest.mark.requires_git` — runs only when `git` is on `PATH`

Optional full C++ smoke (local only, not required for CI):

```bash
bash scripts/smoke.sh
```

### Releasing to PyPI (when ready)

Package version lives in **`src/cppboot/_version.py`** (single source; also used by
setuptools dynamic version).

1. Bump `__version__` in `_version.py` and update `CHANGELOG.md`
2. Merge to `main` (CI must be green)
3. Create a **GitHub Release** with tag **`vX.Y.Z`** matching that version  
   (GitHub UI: Releases → Draft a new release, or `gh release create vX.Y.Z`)
4. Workflow **Publish** (`.github/workflows/publish.yml`) runs on
   `release: published`:
   - Verifies tag `vX.Y.Z` == package version
   - Builds sdist + wheel
   - Uploads to **PyPI** via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
     (OIDC; no long-lived API token in the repo)

Manual dry-run target (does **not** publish to real PyPI unless you choose it):

```bash
gh workflow run publish.yml -f target=testpypi
```

**One-time setup before the first real publish** (not automated here):

1. Create the empty project on [PyPI](https://pypi.org/) (or claim `cppboot` on first upload)
2. Add a **Trusted Publisher**: owner `bluesentinelsec`, repo `cppboot`,
   workflow `publish.yml`, environment `pypi`
3. Optionally configure TestPyPI the same way with environment `testpypi`
4. Create GitHub Environments `pypi` / `testpypi` (optional protection rules)

Until that setup is done, the publish job will fail at the upload step — which is
expected and safe while developing.

### Package layout

```text
src/cppboot/
  cli.py              # argparse entrypoint
  names.py            # name validation / identifiers
  licenses.py         # license fetch (online + offline)
  options.py          # ProjectOptions / GenerateResult
  generator.py        # stable facade (re-exports generate_project)
  generate/           # implementation
    project.py        # orchestration
    cmake_files.py
    build_wrappers.py # Makefile + build.bat
    sources.py        # VERSION + C++ templates
    docs.py
    ide.py
    github_actions.py
    tooling.py        # fmt / git / gh
```

Public imports:

```python
from cppboot import ProjectOptions, generate_project
# or
from cppboot.generator import ProjectOptions, generate_project
```

## Smoke check (generated C++ project)

```bash
python3 -m pip install -e .
bash scripts/smoke.sh
# or manually:
rm -rf /tmp/cppboot-smoke && cppboot -n smoke --output-dir /tmp/cppboot-smoke
cd /tmp/cppboot-smoke/smoke
git status --short   # should be empty after bootstrap
make && make test && ./smoke --version
```

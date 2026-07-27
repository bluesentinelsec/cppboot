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

Every project includes a **version** library API (`0.1.0`) and CLI **`--version` / `-V`**.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-n`, `--name` | (prompt) | Project name |
| `--license` | `apache-2.0` | License id |
| `--build-system` | `cmake` | Only `cmake` for now |
| `--with-modules` | off | C++20 modules scaffold |
| `--shared` | off | Shared library instead of static |
| `--vim` / `--no-vim` | **on** | Project-local `.vimrc` |
| `--ctags` / `--no-ctags` | **on** | Universal Ctags `.ctags` + `make tags` |
| `--vscode` / `--no-vscode` | **on** | VS Code + `CMakePresets.json` |
| `--github-actions` / `--no-github-actions` | **on** | Multi-OS CI workflow |
| `--codespaces` / `--no-codespaces` | **on** | GitHub Codespaces / Dev Container (`.devcontainer/`) |
| `--github` | **off** | Create GitHub remote with `gh` (opt-in) |
| `-v`, `--verbose` | off | Verbose logging |
| `--version` | | Print cppboot version |
| `-h`, `--help` | | Help |

## What you get

- CMake (C++20) + GNU Makefile wrappers + `CMakePresets.json`
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

## Post-bootstrap state

When `make`/`clang-format` and `git` are available, a new project ends with:

1. Sources formatted to the checked-in Microsoft `.clang-format`
2. A single **Initial commit from cppboot** containing the full tree

Developers can start work with a clean `git status` and predictable formatting.

## Smoke check

```bash
python3 -m pip install -e .
bash scripts/smoke.sh
# or manually:
rm -rf /tmp/cppboot-smoke && cppboot -n smoke --output-dir /tmp/cppboot-smoke
cd /tmp/cppboot-smoke/smoke
git status --short   # should be empty after bootstrap
make && make test && ./smoke --version
```

# cppboot

Bootstrap a professional-grade C++ project environment so you can start writing code immediately.

## Install

```bash
pip install -e .
```

## Usage

```bash
cppboot --name myproj
cppboot -n myproj --no-sample
cppboot -n myproj --license mit --with-modules
cppboot -n myproj --no-vscode --no-vim --no-github-actions   # minimal extras
cppboot -n myproj --github   # opt-in: create remote with gh
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-n`, `--name` | (prompt) | Project name |
| `--license` | `apache-2.0` | License id |
| `--build-system` | `cmake` | Only `cmake` for now |
| `--with-modules` | off | C++20 modules scaffold |
| `--no-sample` | off | Skip Calc sample |
| `--shared` | off | Shared library instead of static |
| `--vim` / `--no-vim` | **on** | Project-local `.vimrc` |
| `--ctags` / `--no-ctags` | **on** | Universal Ctags `.ctags` + `make tags` |
| `--vscode` / `--no-vscode` | **on** | VS Code + `CMakePresets.json` |
| `--github-actions` / `--no-github-actions` | **on** | Multi-OS CI workflow |
| `--github` | **off** | Create GitHub remote with `gh` (opt-in) |
| `-v`, `--verbose` | off | Verbose logging |
| `--version` | | Print version |
| `-h`, `--help` | | Help |

## What you get

- CMake (C++20) + GNU Makefile wrappers + `CMakePresets.json`
- Library + app + GoogleTest/GoogleMock + Google Benchmark
- Default app deps (FetchContent, CMake options ON): **CLI11**, **nlohmann/json**, **spdlog**
- Optional Calc sample (omit with `--no-sample`)
- Component-oriented `src/` layout with explicit source lists
- `.clang-format` (**Microsoft** layout); code logic/naming per **Google C++ Style Guide**
- `.clangd`, Doxygen, warnings-as-errors, `compile_commands.json`
- **Default ON:** `.vimrc`, ctags (`.ctags` / `make tags`), VS Code, GitHub Actions CI
- **Default OFF:** `--github` remote creation (does not touch the outside world)
- `git init`, `README.md`, `AGENTS.md`

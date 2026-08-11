# cppboot

**cppboot** scaffolds a complete, opinionated C++ project so you can start shipping code instead of wiring build systems.

```bash
pip install cppboot
cppboot -n myproj
cd myproj && make && make test
```

[![CI](https://github.com/bluesentinelsec/cppboot/actions/workflows/ci.yml/badge.svg)](https://github.com/bluesentinelsec/cppboot/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cppboot.svg)](https://pypi.org/project/cppboot/)
[![Python versions](https://img.shields.io/pypi/pyversions/cppboot.svg)](https://pypi.org/project/cppboot/)
[![License](https://img.shields.io/pypi/l/cppboot.svg)](https://github.com/bluesentinelsec/cppboot/blob/main/LICENSE)

**Documentation:** [bluesentinelsec.github.io/cppboot](https://bluesentinelsec.github.io/cppboot/) — including the [Android](https://bluesentinelsec.github.io/cppboot/android.html) (`--with-android-ci`) and [iOS](https://bluesentinelsec.github.io/cppboot/ios.html) (`--with-ios-ci`) package guides.

---

## Requirements

| | |
|--|--|
| **Python** | 3.9 or newer |
| **Generated projects** | CMake 3.20+ (3.28+ with `--with-modules`), a C++20 compiler, Ninja recommended |

Optional tools used when present: `git`, `clang-format`, `make` / `ninja`, `doxygen`, `ctags`, GitHub CLI (`gh`).

---

## Install

```bash
pip install cppboot
```

Upgrade:

```bash
pip install -U cppboot
```

---

## Quick start

```bash
cppboot -n myproj
cd myproj
make          # Debug build
make test
./myproj --version
```

On Windows (Developer Command Prompt or any shell with `cmake` on `PATH`):

```bat
build.bat
build.bat test
```

Create a public GitHub remote in one step (requires authenticated `gh`):

```bash
cppboot -n myproj --github
```

---

## What you get

Each project is ready for multi-platform development and release:

| Area | Included |
|------|----------|
| **Build** | CMake (C++20), GNU `Makefile`, Windows `build.bat`, `CMakePresets.json` |
| **Versioning** | Root `VERSION` file (single source of truth) → CMake, CLI `--version`, release checks |
| **Library + app** | Static library by default (`--shared` optional), thin `src/main.cpp` entrypoint |
| **Sample API** | Version component with unit tests and a microbenchmark |
| **Deps** | FetchContent (on by default): CLI11, nlohmann/json, spdlog, GoogleTest, Google Benchmark |
| **Quality** | Microsoft `.clang-format`, Google C++ style for code, warnings-as-errors, `.clangd` |
| **Docs** | Doxygen `Doxyfile`, `README.md`, `AGENTS.md` for humans and coding agents |
| **IDE** | VS Code (clangd, CMake Tools, CodeLLDB, C++ TestMate), optional Vim + ctags |
| **CI/CD** | GitHub Actions: multi-OS CI, sanitizers, tag/dispatch **Release** with zip assets; optional Android AAR CI (`--with-android-ci`) and iOS XCFramework CI (`--with-ios-ci`) |
| **Community** | `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md` |
| **Bootstrap** | `make fmt` then `git init` + initial commit (when tools are available) |

**C++20 modules:** `cppboot -n myproj --with-modules` scaffolds module interface units (no classic `include/` tree for the sample API). CI installs module-capable toolchains on Linux/macOS.

---

## CLI

```text
cppboot [-n NAME] [options]
```

### Core options

| Flag | Default | Description |
|------|---------|-------------|
| `-n`, `--name` | (prompt) | Project / program name |
| `--license` | `apache-2.0` | `apache-2.0`, `mit`, `bsd-3-clause`, `gpl-3.0`, `lgpl-3.0`, `mpl-2.0`, `unlicense` |
| `--build-system` | `cmake` | Only `cmake` is supported |
| `--with-modules` | off | C++20 modules layout |
| `--with-android-ci` | off | Android Prefab AAR package: `android/` Gradle project, emulator device tests, Android CI + release jobs (not compatible with `--with-modules`) |
| `--with-ios-ci` | off | iOS XCFramework package: build/verify scripts, Simulator package tests, iOS CI + release jobs (not compatible with `--with-modules`) |
| `--shared` | off | Shared library instead of static |
| `--github` | off | Create a public remote with `gh` and push |
| `--output-dir` | `.` | Parent directory for the new project folder |
| `-v`, `--verbose` | off | Verbose logging |
| `--version` | | Print cppboot version |
| `-h`, `--help` | | Help |

### Opt-outs (features are **on** unless disabled)

| Flag | Effect |
|------|--------|
| `--no-vim` | Skip project-local `.vimrc` |
| `--no-ctags` | Skip Universal Ctags config / `make tags` |
| `--no-vscode` | Skip VS Code config and CMake presets |
| `--no-github-actions` | Skip CI, sanitizers, and release workflows |
| `--no-codespaces` | Skip Dev Container / Codespaces config |
| `--no-community-docs` | Skip CoC / CONTRIBUTING / SECURITY |
| `--no-git` | Skip `git init` and the initial commit |
| `--no-fmt` | Skip `make fmt` after scaffolding |

Examples:

```bash
cppboot -n service --license mit
cppboot -n libdemo --shared --no-vscode
cppboot -n moddemo --with-modules
cppboot -n droidlib --with-android-ci
cppboot -n applelib --with-ios-ci
cppboot -n tool --github --output-dir ~/src
```

**Android** (`--with-android-ci`): adds an `android/` Gradle project that packages the library as a [Prefab](https://google.github.io/prefab/) AAR (arm/x86_64 ABIs), a consumer test app with on-device native tests, and GitHub Actions jobs that build the AAR, verify its contents, and run the tests on an emulator. Releases attach `<name>-android-release-<version>.aar`. Local builds need JDK 17 + the Android SDK; Gradle fetches the pinned NDK and CMake automatically.

**iOS** (`--with-ios-ci`): adds scripts that package the library as a static XCFramework (device arm64 + simulator arm64/x86_64, headers included), a Simulator test app consuming the package, and GitHub Actions jobs that build, verify, and test it. Releases attach `<name>-ios-xcframework-release-<version>.zip`. Local builds need macOS with Xcode command line tools.

---

## Generated project workflow

After scaffolding, day-to-day commands (Unix / `make`):

| Command | Purpose |
|---------|---------|
| `make` / `make debug` | Configure and build Debug |
| `make release` | Configure and build Release |
| `make test` | Unit tests (Debug) |
| `make bench` | Microbenchmarks (Release) |
| `make sanitizer` | ASan+UBSan (Linux-oriented) |
| `make fmt` | clang-format |
| `make doc` | Doxygen HTML under `docs/html` |
| `make clean` | Remove build trees |

Windows: the same targets via `build.bat` / `build.bat release` / `build.bat test`, etc.

**Versioning:** edit the root `VERSION` file only (e.g. `1.2.3`). CMake regenerates the version API; the Release workflow requires the Git tag to match.

**Releases (generated repos):** push tag `vX.Y.Z` or run the Release workflow; multi-OS zips attach to the GitHub Release when CI succeeds.

---

## Library usage (Python)

```python
from pathlib import Path
from cppboot import ProjectOptions, generate_project

result = generate_project(
    ProjectOptions(
        name="myproj",
        root=Path.cwd(),
        with_git=True,
        with_fmt=True,
    )
)
print(result.project_dir)
```

---

## Contributing to cppboot

Clone and develop in an editable environment:

```bash
git clone https://github.com/bluesentinelsec/cppboot.git
cd cppboot
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
python3 -m ruff check src tests
python3 -m mypy
```

Package version is defined in `src/cppboot/_version.py`. Releases are cut from `main` with an annotated GitHub tag `vX.Y.Z` (must match that version); CI publishes the wheel/sdist to [PyPI](https://pypi.org/project/cppboot/).

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

## License

Apache License 2.0. See [LICENSE](LICENSE).

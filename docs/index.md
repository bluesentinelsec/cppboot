# cppboot

**cppboot** scaffolds a complete, opinionated C++ project so you can start
shipping code instead of wiring build systems.

```bash
pip install cppboot
cppboot -n myproj
cd myproj && make && make test
```

- Source: [github.com/bluesentinelsec/cppboot](https://github.com/bluesentinelsec/cppboot)
- Package: [pypi.org/project/cppboot](https://pypi.org/project/cppboot/)

## What you get

Every generated project is ready for multi-platform development and release:

| Area | Included |
|------|----------|
| **Build** | CMake (C++20), GNU `Makefile`, Windows `build.bat`, `CMakePresets.json` |
| **Versioning** | Root `VERSION` file (single source of truth) → CMake, CLI `--version`, release checks |
| **Library + app** | Static library by default (`--shared` optional), thin `src/main.cpp` entrypoint |
| **Deps** | FetchContent (on by default): CLI11, nlohmann/json, spdlog, GoogleTest, Google Benchmark |
| **Quality** | clang-format, warnings-as-errors, ASan+UBSan workflow, `.clangd` |
| **Docs** | Doxygen `Doxyfile`, `README.md`, `AGENTS.md` for humans and coding agents |
| **IDE** | VS Code (clangd, CMake Tools, CodeLLDB, C++ TestMate), optional Vim + ctags |
| **CI/CD** | GitHub Actions: multi-OS CI, sanitizers, tag/dispatch Release with zip assets |
| **Android** | Optional Prefab AAR package, device tests, and CI ([guide](android.md)) |

## Platform guides

| Platform | Status | Guide |
|----------|--------|-------|
| Linux / macOS / Windows | default | Generated CI covers all three out of the box |
| **Android** | `--with-android-ci` | [Android package guide](android.md) |
| iOS | planned (`--with-ios-ci`) | — |
| Web / Emscripten | planned (`--with-web-ci`) | — |

## CLI overview

```text
cppboot [-n NAME] [options]
```

Core opt-ins:

| Flag | Default | Description |
|------|---------|-------------|
| `--with-modules` | off | C++20 modules layout |
| `--with-android-ci` | off | Android Prefab AAR package + CI ([guide](android.md)) |
| `--shared` | off | Shared library instead of static |
| `--github` | off | Create a public remote with `gh` and push |
| `--license` | `apache-2.0` | `apache-2.0`, `mit`, `bsd-3-clause`, `gpl-3.0`, `lgpl-3.0`, `mpl-2.0`, `unlicense` |

Opt-outs (features are **on** unless disabled): `--no-vim`, `--no-ctags`,
`--no-vscode`, `--no-github-actions`, `--no-codespaces`, `--no-community-docs`,
`--no-git`, `--no-fmt`.

See the [repository README](https://github.com/bluesentinelsec/cppboot#readme)
for the complete reference.

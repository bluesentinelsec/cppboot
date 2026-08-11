"""README, AGENTS, community docs, and repo hygiene templates."""

from __future__ import annotations

from cppboot.generate.android import (
    AGP_VERSION,
    ANDROID_ABIS,
    ANDROID_CMAKE_VERSION,
    ANDROID_COMPILE_SDK,
    ANDROID_MIN_SDK,
    GRADLE_VERSION,
    NDK_VERSION,
)
from cppboot.generate.context import Context
from cppboot.generate.ios import IOS_DEPLOYMENT_TARGET

_Context = Context


def _readme(ctx: _Context) -> str:
    modules_note = (
        "This project uses **C++20 modules** (`--with-modules`). "
        "Module interface units live under `src/<component>/` as `.cppm` files."
        if ctx.with_modules
        else "This project uses **classic headers**. Public headers live under "
        f"`include/{ctx.namespace}/` (directory tree == namespace)."
    )
    vim_note = (
        "\nA project-local `.vimrc` was generated (default; disable with "
        "`cppboot --no-vim`). Enable `:set exrc` (and ideally `secure`) in your "
        "global Vim config to load it.\n"
        if ctx.with_vim
        else ""
    )
    vscode_note = (
        "\n**VS Code** config is included (default; disable with "
        "`cppboot --no-vscode`): open the folder, install recommended extensions, "
        "select the **debug** CMake preset, then Build / F5 / Test. See "
        "[Open in VS Code](#open-in-vs-code).\n"
        if ctx.with_vscode
        else ""
    )
    ctags_note = (
        "\n**ctags:** `.ctags` is configured for Universal Ctags (default; "
        "`cppboot --no-ctags` to skip). Run `make tags` to build the `tags` index.\n"
        if ctx.with_ctags
        else ""
    )
    sample_note = (
        "\nDefault library surface is the **version** component driven by the "
        "root **`VERSION`** file (single source of truth) with CLI "
        "`--version` / `-V`, unit tests, and a small benchmark. Bump "
        "`VERSION` only — CMake regenerates the version API. Add real "
        "features as new components under `src/<component>/`.\n"
    )
    gha_section = ""
    if ctx.with_github_actions:
        android_row = ""
        android_ci_note = ""
        if ctx.with_android_ci:
            android_row = (
                "\n| **Android** | `.github/workflows/android.yml` | "
                "Prefab AAR build + verification + emulator device tests |"
            )
            android_ci_note = """
**Android** (`--with-android-ci`): builds the Debug and Release Prefab AARs and
the consumer test APK with Gradle, verifies the release AAR contents (ABIs,
headers, version), then runs the native device tests on an Android emulator
(`scripts/run_android_tests.sh`). The Release workflow builds the release AAR
the same way and attaches `<app>-android-release-<version>.aar` to the
GitHub Release alongside the zips.
"""
        web_row = ""
        web_ci_note = ""
        if ctx.with_web_ci:
            web_row = (
                "\n| **Web** | `.github/workflows/web.yml` | "
                "wasm library + canvas demo build + browser tests in headless Chrome |"
            )
            web_ci_note = """
**Web** (`--with-web-ci`): builds the wasm32 static library, the HTML5 canvas
demo, and the browser test page with Emscripten (Debug and Release), runs the
tests in headless Chrome via `emrun`, and packages the installed library with
the demo bundled. The Release workflow attaches
`<app>-web-wasm32-release-<version>.zip` to the GitHub Release.
"""
        ios_row = ""
        ios_ci_note = ""
        if ctx.with_ios_ci:
            ios_row = (
                "\n| **iOS** | `.github/workflows/ios.yml` | "
                "XCFramework build + verification + Simulator package tests |"
            )
            ios_ci_note = """
**iOS** (`--with-ios-ci`): builds the Debug and Release XCFrameworks
(`scripts/build_ios_xcframework.sh`) and the consumer test apps, verifies the
packaged slices/headers/version, then runs the package tests in an iOS
Simulator (`scripts/run_ios_tests.sh`). The Release workflow builds the
release XCFramework the same way and attaches
`<app>-ios-xcframework-release-<version>.zip` to the GitHub Release.
"""
        gha_section = f"""

## Continuous integration

GitHub Actions workflows (default; disable with `cppboot --no-github-actions`):

| Workflow | File | Purpose |
|----------|------|---------|
| **CI** | `.github/workflows/ci.yml` | Ubuntu/macOS/Windows × Debug+Release, tests, benches, artifacts |
| **Sanitizers** | `.github/workflows/sanitizers.yml` | Linux ASan+UBSan build + `ctest` (failures fail the job) |
| **Release** | `.github/workflows/release.yml` | Tag `v*` or manual dispatch → notes + zip assets |{android_row}{ios_row}{web_row}

**CI** (each OS):

1. Configure and build **Debug** (Ninja)
2. Run unit tests (CTest) on Debug
3. Configure and build **Release**
4. Run unit tests on Release
5. Run Google Benchmark binaries under `build/release` (short min time)
6. Package and upload zip artifacts via `actions/upload-artifact` for **Debug**
   and **Release** on each OS

Artifact archive name shape:

```text
<app>-<os>-<cpu-arch>-<debug|release>-<version>.zip
```

Examples: `myproj-linux-x86_64-debug-0.1.0.zip`,
`myproj-macos-arm64-release-0.1.0.zip`,
`myproj-windows-x86_64-release-0.1.0.zip`.

Each zip contains the contents of `build/<config>/bin/` (app, tests, benches).
Version comes from the root **`VERSION`** file (also what `./<app> --version`
prints after configure).

**Sanitizers** (Ubuntu + Clang): configure with
`-D{ctx.macro}_ENABLE_SANITIZERS=ON`, build, run tests with
`ASAN_OPTIONS` / `UBSAN_OPTIONS` set so findings abort (non-zero exit).

Locally on Linux: `make sanitizer` (same flags and env).
{android_ci_note}{ios_ci_note}{web_ci_note}
### Creating a release

The root **`VERSION`** file is the only place to bump the package version.

1. Edit **`VERSION`** (e.g. `1.0.0`), commit, and merge to the default branch.
2. Either:
   - **Tag:** `git tag -a v1.0.0 -m v1.0.0 && git push origin v1.0.0`
     (tag **must** match `VERSION`), or
   - **Actions → Release → Run workflow** — leave the version input empty to
     use `VERSION`, or pass the same semver (mismatch fails the job).
3. The Release workflow builds **Release** on Linux/macOS/Windows, verifies the
   binary `--version` matches `VERSION`/tag, generates notes, and uploads zips
   named `<app>-<os>-<arch>-release-<version>.zip`.

Action pins use current stable majors (`actions/checkout@v7`,
`actions/upload-artifact@v7`, `actions/download-artifact@v7`,
`lukka/get-cmake@latest`, `softprops/action-gh-release@v3`).
"""
    codespaces_section = ""
    if ctx.with_codespaces:
        codespaces_section = f"""

## GitHub Codespaces (VS Code in the browser)

This repo includes a **Dev Container** (`.devcontainer/`) for
[GitHub Codespaces](https://github.com/features/codespaces) and local
VS Code Dev Containers.

### Open in Codespaces

1. Push the repo to GitHub (or use an existing remote).
2. On GitHub: **Code → Codespaces → Create codespace on &lt;branch&gt;**.
3. Wait for the container create hooks:
   - `onCreateCommand`: install Ninja, clang-format, Doxygen, ctags
   - `postCreateCommand`: `cmake --preset debug` + Debug build (FetchContent)
4. In the browser VS Code: **F5** (*Debug {ctx.name}*), Testing view, or terminal
   `make test` / `./build/debug/bin/{ctx.name} --version`.

### Local Dev Container

In desktop VS Code with the Dev Containers extension:
**Dev Containers: Reopen in Container**.

Disable with `cppboot --no-codespaces` when regenerating a project.
"""
    android_section = ""
    if ctx.with_android_ci:
        android_section = f"""

## Android package (Prefab AAR)

The `android/` Gradle project (`cppboot --with-android-ci`) packages the C++
library as an Android [Prefab](https://google.github.io/prefab/) AAR and hosts
the on-device test application.

Build (requires JDK 17; Gradle downloads the NDK {NDK_VERSION} and its CMake
{ANDROID_CMAKE_VERSION} automatically):

```bash
./android/gradlew -p android :{ctx.target}:assembleRelease
```

Output: `android/{ctx.target}/build/outputs/aar/{ctx.target}-release.aar` with
`lib{ctx.target}.so` for {", ".join(f"`{abi}`" for abi in ANDROID_ABIS)}.
Android consumers add the AAR with `buildFeatures {{ prefab true }}` and link
`{ctx.target}::{ctx.target}` via `find_package({ctx.target} REQUIRED CONFIG)`
(see `tests/android/CMakeLists.txt` for a working example).

Device tests build `android/test-app` against the AAR and run
`tests/android/android_test.cpp` on an emulator or attached device:

```bash
./android/gradlew -p android :test-app:assembleRelease
bash scripts/run_android_tests.sh   # needs adb + a running emulator/device
```

Notes:

- The Android application namespace defaults to **`{ctx.android_package}`** —
  rename it in `android/{ctx.target}/build.gradle`,
  `android/test-app/build.gradle`, and the test sources before publishing.
- On Android the core library is always built **static** (even when the
  project was generated with `--shared`) and folded into one
  `lib{ctx.target}.so`.
- Pinned toolchain: Gradle {GRADLE_VERSION}, Android Gradle Plugin
  {AGP_VERSION}, NDK {NDK_VERSION}, compileSdk {ANDROID_COMPILE_SDK},
  minSdk {ANDROID_MIN_SDK}.
"""
    ios_section = ""
    if ctx.with_ios_ci:
        ios_section = f"""

## iOS package (XCFramework)

The iOS scripts (`cppboot --with-ios-ci`) package the C++ library as a static
XCFramework with device (arm64) and simulator (arm64/x86_64) slices, the
public headers, and the generated `version.hpp`.

Build on macOS with Xcode command line tools installed:

```bash
bash scripts/build_ios_xcframework.sh Release
```

Output: `build/ios/release/{ctx.name}.xcframework` and the versioned archive
`build/ios/release/{ctx.name}-ios-xcframework-release-<version>.zip`. The
script verifies the package (`scripts/verify_ios_xcframework.sh`) after
building. Deployment target defaults to iOS {IOS_DEPLOYMENT_TARGET}; override
with `{ctx.macro}_IOS_DEPLOYMENT_TARGET`.

Consume the XCFramework from an application's CMake build by linking the
`.xcframework` directory directly:

```cmake
target_link_libraries(app_native PRIVATE "/path/to/{ctx.name}.xcframework")
```

Package tests live in `tests/ios/` and run inside an iOS Simulator:

```bash
bash scripts/build_ios_test_apps.sh build/ios/release/{ctx.name}.xcframework Release
bash scripts/run_ios_tests.sh   # boots a temporary Simulator, polls os_log
```

Notes:

- The test app bundle identifier defaults to `{ctx.android_package}.test` —
  change it in `tests/ios/CMakeLists.txt` before shipping anything derived
  from it.
- On iOS the core library is always built **static** (even when the project
  was generated with `--shared`).
- Add project-specific package checks to `tests/ios/test_main.mm`; the
  host-side GoogleTest suite does not run on iOS.
"""
    web_section = ""
    if ctx.with_web_ci:
        web_section = f"""

## Web package (Emscripten / WebAssembly)

The web scaffold (`cppboot --with-web-ci`) targets **browser game
development**: `src/web/` holds an HTML5 canvas demo built around
`emscripten_set_main_loop` (the browser drives frame pacing via
requestAnimationFrame), rendering through an `EM_JS` canvas bridge, with a
fullscreen-canvas shell page (`src/web/shell.html`).

Build with the [Emscripten SDK](https://emscripten.org/docs/getting_started/downloads.html)
activated (`emcmake` on PATH):

```bash
emcmake cmake -S . -B build/web-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/web-release --parallel
emrun build/web-release/bin/{ctx.name}.html   # serves + opens the demo
```

Grow it into a game:

- Put per-frame simulation in `Update()` and rendering in the draw call —
  swap the canvas-2D `EM_JS` bridge for WebGL2 (`-sUSE_WEBGL2=1` is already
  linked) or SDL2 (`-sUSE_SDL=2`, see the commented block in
  `src/web/CMakeLists.txt`).
- Bundle assets into the virtual filesystem with `--preload-file
  assets@/assets` (commented in `src/web/CMakeLists.txt`), then read them
  with normal file I/O.
- Never block the main thread; the browser owns the loop.

Browser tests live in `tests/web/` (GoogleTest compiled to wasm) and run in
headless Chrome:

```bash
emrun --browser=google-chrome \\
  --browser_args="--headless=new --no-sandbox --disable-gpu" \\
  --kill_exit --timeout 120 build/web-release/bin/{ctx.target}_web_test.html
```

The release package `{ctx.name}-web-wasm32-release-<version>.zip` contains
the installed wasm32 static library + headers (consumable from any Emscripten
CMake build via `find_package`), the playable demo under `demo/`, and the
`EMSCRIPTEN_VERSION` it was built with. On the web the core library is always
built **static** (even when the project was generated with `--shared`).
"""
    vscode_section = ""
    if ctx.with_vscode:
        vscode_section = f"""

## Open in VS Code

1. Open this folder in VS Code (`code .`).
2. Install the **recommended extensions** when prompted
   (clangd, CMake Tools, CodeLLDB, **C++ TestMate**).
3. Install **Ninja** (`brew install ninja` / `apt install ninja-build`). VS Code
   presets and `make` both prefer Ninja so they share the same `build/debug` tree.
4. **Build once:** `Ctrl/Cmd+Shift+B` (*Build Debug*). This configures CMake,
   builds, and places `compile_commands.json` at the repo root for **clangd**.
5. If red squiggles remain: Command Palette → **clangd: Restart language server**
   (or reload the window). IntelliSense needs that compilation database.
6. **Debug the app:** F5 → *Debug {ctx.name}* (rebuilds Debug first).
7. **Unit tests (per-test ▶):** open the **Testing** view (beaker icon).
   After a Debug build, **C++ TestMate** discovers GoogleTest binaries under
   `build/debug/bin/` and offers run/debug for suites and individual `TEST`s.
8. **Bulk tests:** Task *Test*, CMake Tools CTest, or `make test`.

Presets live in `CMakePresets.json` (`debug` → `build/debug`, `release` → `build/release`).

**Generator mismatch:** If you see *generator : Ninja Does not match ... Unix Makefiles*,
the build tree was configured with a different generator. Fix with:

```bash
make reconfigure-debug
# or: rm -rf build/debug && cmake --preset debug
```

Then F5 again. Prefer always using Ninja (install it; both `make` and VS Code will use it).

**IntelliSense note:** Disable Microsoft C/C++ IntelliSense (already set) and use
**clangd** only. Do not enable both. `std::string` / CLI11 / project headers resolve
from `compile_commands.json` after the first successful configure+build.

**Tests note:** TestMate needs built test executables — Build Debug first.
Individual test debug uses CodeLLDB (`lldb`) on macOS/Linux; on Windows you may
set `testMate.cpp.debug.configTemplate.type` to `cppvsdbg`.

Windows: use the *Debug {ctx.name} (Windows)* launch config (MSVC debugger).
"""
    return f"""\
# {ctx.name}

Developer guide for this **cppboot** environment. This README orients you to
the build, test, and source-onboarding workflows — not product requirements.
{sample_note}

## Prerequisites

- CMake **3.20+** (3.28+ if this project was generated with C++20 modules)
- A **C++20** compiler (GCC, Clang, or MSVC recent enough for C++20)
- GNU Make (or another make that understands this Makefile)
- **Ninja** is required when this project uses C++20 modules (`--with-modules`)
- Optional tools: `clang-format`, `doxygen`, an LSP client with clangd
- Network access on first configure (CMake **FetchContent** downloads pinned deps)
{gha_section}{android_section}{ios_section}{web_section}{codespaces_section}{vscode_section}
## Preferred third-party libraries

These are **imported by default** via FetchContent (see `cmake/Dependencies.cmake`)
and linked into the project library. Prefer them for the jobs below instead of
adding alternate stacks without a strong reason.

| Purpose | Library | CMake option (default **ON**) | CMake target |
|---------|---------|-------------------------------|--------------|
| CLI arguments | [CLI11](https://github.com/CLIUtils/CLI11) | `-D{ctx.macro}_WITH_CLI11=OFF` | `CLI11::CLI11` |
| JSON | [nlohmann/json](https://github.com/nlohmann/json) | `-D{ctx.macro}_WITH_JSON=OFF` | `nlohmann_json::nlohmann_json` |
| Console logging | [spdlog](https://github.com/gabime/spdlog) | `-D{ctx.macro}_WITH_SPDLOG=OFF` | `spdlog::spdlog` |

Example headers:

```cpp
#include <CLI/CLI.hpp>
#include <nlohmann/json.hpp>
#include <spdlog/spdlog.h>
```

Disable any of them at configure time if you do not need them:

```bash
cmake -S . -B build/debug \\
  -D{ctx.macro}_WITH_CLI11=OFF \\
  -D{ctx.macro}_WITH_JSON=OFF \\
  -D{ctx.macro}_WITH_SPDLOG=OFF
```

## Layout

```text
{ctx.name}/
  VERSION              # single source of truth for package version
  src/main.cpp         # THE program entrypoint (always here)
  src/<component>/     # library implementation; each dir has CMakeLists.txt
  include/             # public headers (classic layout only; version.hpp is generated)
  tests/<component>/   # GoogleTest / GoogleMock
  benchmarks/<component>/
  cmake/               # shared CMake modules + version.*.in templates
  CMakeLists.txt
  Makefile             # macOS / Linux day-to-day targets
  build.bat            # Windows day-to-day targets (mirrors Makefile)
```

{modules_note}

**Modules toolchain note:** CMake C++20 modules need **Ninja** (the Makefile
selects it automatically when `ninja` is on `PATH`), **CMake 3.28+**, and a
compiler with module dependency scanning (**Clang 16+**, **GCC 14+**, or
**MSVC 17.4+**). Stock **AppleClang** often cannot scan modules for CMake yet;
use a recent LLVM Clang/GCC/MSVC when building a modules project.
{vim_note}{vscode_note}{ctags_note}
## Versioning

Package version lives in the root **`VERSION`** file (one line, e.g. `0.1.0`).

| Consumer | How it gets the version |
|----------|-------------------------|
| CMake `project(... VERSION ...)` | Reads `VERSION` at configure time |
| `{ctx.namespace}::Version()` / CLI `--version` | Generated from `cmake/version.*.in` |
| GitHub Release workflow | Requires tag / dispatch input to match `VERSION` |
| Doxygen `PROJECT_NUMBER` | Injected from `VERSION` by `make doc` / `build.bat doc` |

**To ship a new version:** edit `VERSION` only, commit, then tag `vX.Y.Z` (or
run the Release workflow). Do not hand-edit generated version sources under the
build tree.

## Using this library from another CMake project

The library target is **`{ctx.name}::lib`** (also **`{ctx.name}::{ctx.target}`**).

When this repo is **not** the top-level CMake project (via `add_subdirectory` or
`FetchContent`), app/tests/benchmarks and optional app deps default **off** so
you only build the library.

### `add_subdirectory`

```cmake
add_subdirectory(path/to/{ctx.name})
target_link_libraries(my_app PRIVATE {ctx.name}::lib)
```

### `FetchContent` (e.g. from GitHub)

```cmake
include(FetchContent)
FetchContent_Declare(
  {ctx.name}
  GIT_REPOSITORY https://github.com/<org>/{ctx.name}.git
  GIT_TAG        v0.1.0   # or main / a commit SHA
  GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable({ctx.name})
target_link_libraries(my_app PRIVATE {ctx.name}::lib)
```

Optional cache variables (prefix `{ctx.macro}_`):

| Option | Default (top-level / embedded) | Meaning |
|--------|----------------------------------|---------|
| `{ctx.macro}_BUILD_APP` | ON / OFF | Demo executable |
| `{ctx.macro}_BUILD_TESTS` | ON / OFF | GoogleTest suite |
| `{ctx.macro}_BUILD_BENCHMARKS` | ON / OFF | Google Benchmark |
| `{ctx.macro}_WITH_CLI11` | ON / OFF | CLI11 |
| `{ctx.macro}_WITH_JSON` | ON / OFF | nlohmann/json |
| `{ctx.macro}_WITH_SPDLOG` | ON / OFF | spdlog |

### `find_package` (after install)

```bash
cmake --install build/release --prefix /path/to/prefix
```

```cmake
find_package({ctx.name} REQUIRED CONFIG)
target_link_libraries(my_app PRIVATE {ctx.name}::lib)
```

## Build

Out-of-source builds only. Artifacts land under `build/`.

| Command (Unix) | Command (Windows) | Meaning |
|----------------|-------------------|---------|
| `make` / `make debug` | `build.bat` / `build.bat debug` | Configure and build **Debug** |
| `make release` | `build.bat release` | Configure and build **Release** |
| `make test` | `build.bat test` | Unit tests (Debug) |
| `make bench` | `build.bat bench` | Microbenchmarks (Release) |
| `make fmt` | `build.bat fmt` | clang-format |
| `make doc` | `build.bat doc` | Doxygen HTML |
| `make clean` | `build.bat clean` | Remove build trees |

Debug tree: `build/debug`
Release tree: `build/release`

The Debug configure step links/copies `compile_commands.json` at the repo root for LSP.

### Windows

Prefer **`build.bat`** (same targets as the Makefile). Open a **Developer
Command Prompt for VS** or ensure `cmake` (and ideally `ninja`) are on `PATH`:

```bat
build.bat
build.bat test
build.bat release
build.bat help
```

WSL / MSYS2 can keep using `make` if you prefer.

## Run the app

The program entrypoint is always **`src/main.cpp`**.
`make` links **`./{ctx.name}`** at the project root to `build/debug/bin/{ctx.name}`.

After `make debug`:

```bash
./{ctx.name}
./{ctx.name} --version
./{ctx.name} -V
```

## Tests

```bash
make test
```

Runs CTest against the Debug build (includes version API tests).

## Benchmarks

```bash
make bench
```

Builds **Release** and runs Google Benchmark binaries (short min time for smoke runs).

## Format

```bash
make fmt
```

Runs **clang-format** with the checked-in `.clang-format` (**Microsoft** style).

**Formatting** uses Microsoft clang-format; **code logic/naming/design** follow
the **Google C++ Style Guide** (see AGENTS.md).

## Documentation

```bash
make doc
```

Runs **Doxygen** using the checked-in `Doxyfile`. HTML output: `docs/html/`.

## Clean

```bash
make clean
```

Removes `build/`, generated docs, and the root `compile_commands.json` link.

## LSP / clangd

- CMake exports a compilation database (`CMAKE_EXPORT_COMPILE_COMMANDS=ON`).
- After `make debug`, `compile_commands.json` is available at the **project root**.
- Open the project root in your editor so clangd picks it up.
- See `.clangd` for the minimal clangd config.

## Compiler warnings

This project compiles with **warnings as errors** (`-Wall -Wextra -Wpedantic -Werror`
on GCC/Clang; `/W4 /WX` on MSVC). Fix warnings instead of silencing them.

## Onboarding new source files

Sources are organized by **logical component**. Each component directory has its
own `CMakeLists.txt` and **lists files explicitly** (no `file(GLOB)`).

### Example: add a `parser` component

1. **Public header** (classic layout):

   `include/{ctx.namespace}/parser.hpp`

2. **Implementation**:

   ```text
   src/parser/
     CMakeLists.txt
     parser.cpp
   ```

3. **`src/parser/CMakeLists.txt`**:

   ```cmake
   target_sources(${{PROJECT_NAME}}_lib
     PRIVATE
       parser.cpp
   )
   ```

4. **Register the component** in `src/CMakeLists.txt`:

   ```cmake
   add_subdirectory(version)
   add_subdirectory(parser)
   ```

5. **Tests** (same pattern):

   ```text
   tests/parser/
     CMakeLists.txt
     parser_test.cpp
   ```

   And `add_subdirectory(parser)` in `tests/CMakeLists.txt`.

### Rules of thumb

- The only program entrypoint is **`src/main.cpp`**. Keep it thin; put logic in library components.
- Library code goes under `src/<component>/`, never into `src/main.cpp` beyond startup wiring.
- List every `.cpp` / `.cppm` in the component `CMakeLists.txt`.
- Mirror component names under `tests/` and `benchmarks/`.
- Do not rely on directory globs for sources — explicit lists keep reviews and CI unambiguous.

## Agent / contributor conventions

See **[AGENTS.md](AGENTS.md)** for coding standards, documentation rules, and
how automated agents (and humans) should work in this repository.

## License

See `LICENSE` ({ctx.license_id}).
"""


def _agents_md(ctx: _Context) -> str:
    layout_api = (
        f"Public module interfaces live under `src/<component>/` as `.cppm` "
        f"(module name `{ctx.namespace}.<component>`)."
        if ctx.with_modules
        else f"Public headers live under `include/{ctx.namespace}/` "
        f"(directory tree matches the C++ namespace)."
    )
    android_bullet = ""
    if ctx.with_android_ci:
        android_bullet = """
- If present, `android/` is the Android Prefab AAR Gradle project (library
  module + on-device test app). `.github/workflows/android.yml` builds it and
  runs `scripts/run_android_tests.sh` on an emulator; keep it green. Android
  device tests live in `tests/android/`, not the GoogleTest tree."""
    ios_bullet = ""
    if ctx.with_ios_ci:
        ios_bullet = """
- If present, `scripts/build_ios_xcframework.sh` packages the iOS XCFramework
  and `.github/workflows/ios.yml` builds + tests it in an iOS Simulator
  (`scripts/run_ios_tests.sh`); keep it green. iOS package tests live in
  `tests/ios/`, not the GoogleTest tree."""
    web_bullet = ""
    if ctx.with_web_ci:
        web_bullet = """
- If present, `src/web/` is the Emscripten canvas demo (game loop) and
  `tests/web/` the browser test page; `.github/workflows/web.yml` builds both
  and runs the tests in headless Chrome via `emrun`. Keep the game loop
  non-blocking — the browser owns frame pacing."""
    return f"""\
# AGENTS.md — working in `{ctx.name}`

This file orients **human contributors and coding agents** to how this
cppboot-generated C++ project is structured and how code should be written.
For day-to-day build commands, see [README.md](README.md).

## Project model

- **Entrypoint:** the program starts in **`src/main.cpp`** — always. No alternate
  app tree; do not invent a second `main`.
- **Library first:** reusable code belongs in the library target under
  `src/<component>/`, not in `main.cpp`.
- **Main is thin:** `src/main.cpp` only wires startup and calls into the library.
- **Components:** group related code under `src/<component>/`, `tests/<component>/`,
  and `benchmarks/<component>/`.
- **Explicit sources:** every translation unit is listed in that directory's
  `CMakeLists.txt`. Never use `file(GLOB)` for project sources.
- **Onboard a component:** add the directory, list files in its `CMakeLists.txt`,
  then `add_subdirectory(...)` from the parent.

{layout_api}

## Preferred libraries

Use these **default** third-party libraries (FetchContent, ON unless turned off
in CMake) instead of inventing a parallel stack:

| Need | Prefer | Notes |
|------|--------|--------|
| Parse CLI args | **CLI11** (`CLI11::CLI11`) | `#include <CLI/CLI.hpp>` |
| Parse / emit JSON | **nlohmann/json** (`nlohmann_json::nlohmann_json`) | `#include <nlohmann/json.hpp>` |
| Console (and file) logging | **spdlog** (`spdlog::spdlog`) | `#include <spdlog/spdlog.h>` |

They are linked `PUBLIC` on the project library when enabled. Options:

- `{ctx.macro}_WITH_CLI11` (default ON)
- `{ctx.macro}_WITH_JSON` (default ON)
- `{ctx.macro}_WITH_SPDLOG` (default ON)

Do not add competing CLI/JSON/logging libraries unless there is a clear,
documented reason. See `cmake/Dependencies.cmake` for pinned tags.

## Tooling workflow

Prefer the Makefile (Unix) or `build.bat` (Windows) wrappers:

| Goal | Unix | Windows |
|------|------|---------|
| Debug build | `make` / `make debug` | `build.bat` / `build.bat debug` |
| Release build | `make release` | `build.bat release` |
| Unit tests | `make test` | `build.bat test` |
| Benchmarks | `make bench` | `build.bat bench` |
| ASan+UBSan (Linux) | `make sanitizer` | n/a (use Linux/CI) |
| Format | `make fmt` | `build.bat fmt` |
| API docs | `make doc` | `build.bat doc` |
| ctags index | `make tags` (if enabled) | `build.bat tags` |
| Clean | `make clean` | `build.bat clean` |

- Builds are **out-of-source** under `build/`.
- After a Debug configure, `compile_commands.json` at the repo root supports clangd/LSP.
- **Warnings are errors.** Fix warnings; do not silence them without strong reason.
- If present, `.ctags` + `make tags` produce a repo-root `tags` file for editors
  (Universal Ctags recommended).
- If present, `.github/workflows/ci.yml` is the multi-OS CI contract (Debug +
  Release, tests, benchmarks on Linux/macOS/Windows). Keep it green.
- If present, `.github/workflows/sanitizers.yml` runs ASan+UBSan on Linux;
  treat sanitizer failures as bugs. Locally: `make sanitizer`.{android_bullet}{ios_bullet}{web_bullet}
- **Version:** edit the root **`VERSION`** file only. CMake generates
  `{ctx.namespace}::Version()` / CLI `--version` from `cmake/version.*.in`.
  Ship releases with annotated tags `vX.Y.Z` matching `VERSION` (or
  workflow_dispatch); the release job fails on mismatch.
- If present, `.devcontainer/` enables **GitHub Codespaces** / Dev Containers
  (browser or local VS Code in a C++ toolchain container).
- Default library API includes **`Version()`** (from `VERSION`) and the app
  exposes **`--version` / `-V`** via CLI11.
- Mechanical formatting is enforced by **clang-format** via the checked-in
  `.clang-format` (**Microsoft** style). Run `make fmt`.
- **Logic, naming, API design, and code organization** follow the
  **Google C++ Style Guide** (see Coding standards below). These are two
  separate concerns: Microsoft for whitespace/braces layout; Google for how
  the C++ is written.

## Coding standards

### Formatting vs. language style (two different layers)

| Layer | Standard | How it is applied |
|-------|----------|-------------------|
| **Formatting** | Microsoft (clang-format) | `.clang-format`, `make fmt` — indentation, braces, wrapping, spacing |
| **Language / design style** | [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html) | Naming, headers, ownership, construct choices, readability norms |

Do not treat clang-format as a substitute for the Google guide, or vice versa.

### Style (Google C++ Style Guide)

Follow the [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html)
for source code logic and structure:

- Clear, consistent naming (`PascalCase` types, Google-style functions/members;
  match existing code in this tree).
- Prefer headers that express a stable API; keep implementation details out of
  public headers when practical.
- Avoid non-portable extensions and clever syntax that hurts readability.
- Keep functions small and focused; prefer early returns over deep nesting.

### Design (SOLID, readability, maintainability)

Write code that a future human can change safely:

- **Single responsibility:** one class/function does one coherent job.
- **Open/closed:** extend behavior via new types or composition, not by growing
  god-objects or switch-on-type forests.
- **Liskov substitution:** derived types honor base contracts; do not surprise
  callers.
- **Interface segregation:** prefer small, purpose-built interfaces over wide ones.
- **Dependency inversion:** depend on abstractions at boundaries; inject
  collaborators rather than hard-wiring concrete types deep in call chains.

Additional habits:

- Optimize for **clarity over cleverness**. The default reader is a teammate,
  not a compiler.
- Prefer **composition** and explicit ownership (`std::unique_ptr`, values,
  spans) over hidden global state.
- Keep APIs **minimal and intentional**. Every public symbol is a long-term
  commitment.
- Fail loudly and locally: validate preconditions at boundaries; use types and
  names that make invalid states hard to represent.
- Tests are part of the product: add or update unit tests (and mocks where they
  clarify collaboration) when behavior changes.

### Documentation and comments

**Public symbols** (public headers / exported module interfaces, public classes,
functions, enums, and type aliases intended for use outside the defining
translation unit):

- Provide **professional Doxygen** documentation: brief description, parameters,
  return values, pre/postconditions, and ownership or lifetime notes when
  relevant.
- Use `/** ... */` with `@brief`, `@param`, `@return`, and related tags so
  `make doc` stays useful.
- Document *what* and *why* at the API boundary, not line-by-line mechanics.

**Internal code** (`.cpp` bodies, private helpers, anonymous namespaces, test
helpers):

- Favor **self-documenting** names and structure over commentary.
- Use comments **sparsely**.
- When you comment, write **long-lived** notes: invariants, non-obvious
  algorithms, protocol constraints, performance tradeoffs, or security
  boundaries that will still matter months later.
- Do **not** write tactical comments: no "increment i", no narrating the next
  line, no TODOs that only make sense during an unfinished edit, no
  change-log commentary that belongs in version control.

### Tests and benchmarks under warnings-as-errors

- Project flags apply to **your** TUs (lib, app, tests, benchmarks), not only
  production code.
- For `[[nodiscard]]` APIs with GoogleTest throws, bind the result:

  ```cpp
  EXPECT_THROW(
      {{
        auto value = ApiThatIsNodiscard();
        static_cast<void>(value);
      }},
      std::runtime_error);
  ```

- For Google Benchmark, pass a **mutable lvalue** to `DoNotOptimize` (const-ref
  overloads are deprecated and fail `-Werror`):

  ```cpp
  auto value = Compute();
  benchmark::DoNotOptimize(value);
  ```

### What to avoid

- Drive-by refactors unrelated to the task.
- Silent warning suppressions and `#pragma` noise without justification.
- New dependencies without a clear need (third-party code is pinned via
  FetchContent in `cmake/Dependencies.cmake`). Prefer the default CLI11 /
  nlohmann/json / spdlog stack for CLI, JSON, and logging.
- Alternate CLI/JSON/logging libraries when the preferred ones are enabled.
- Globs for source lists; dumping library logic into `src/main.cpp` or a single
  catch-all source file.

## Checklist before finishing a change

1. Sources listed explicitly in the right component `CMakeLists.txt`.
2. `make` (or `make release`) succeeds with warnings-as-errors.
3. `make test` passes; add coverage for new behavior.
4. Public API has Doxygen; internal comments (if any) are durable.
5. `make fmt` leaves formatting clean.
6. Logic/naming match Google C++ guidance; formatting matches `.clang-format`.

## Scope of this file

`AGENTS.md` is about **how to work in this repository**. Product requirements
and design docs for the application itself belong elsewhere.
"""


def _code_of_conduct_md() -> str:
    """Short, technology-first code of conduct (not Contributor Covenant)."""
    return """\
# Code of Conduct

This project is a technical collaboration space. The standard is simple:
**be an adult, be respectful, and keep the work about the work.**

## Principles

1. **Treat others as you would want to be treated.** Assume good faith until
   shown otherwise.
2. **Be mature and professional.** Disagreement is fine; contempt is not.
3. **Focus on the technology.** Prefer technical arguments, evidence, and
   clear tradeoffs over personal attacks, tribal signaling, or off-topic
   politics.
4. **Be direct and civil.** Critique ideas and code, not people. Avoid sarcasm
   that exists only to belittle.
5. **Be responsible.** Own mistakes, fix what you break, and do not waste
   others' time with spam, trolling, or bad-faith engagement.
6. **Respect privacy and safety.** Do not share private information without
   consent. Do not threaten, stalk, or harass anyone.

## What this is not

This is not a speech code about identity, ideology, or belief. Contributors of
any background are welcome on equal terms: the bar is competence, honesty, and
conduct.

## Unacceptable behavior

- Harassment, intimidation, or sustained personal attacks
- Doxxing or publishing private information without consent
- Sexual advances or sexualized content in project spaces
- Spam, vandalism, or deliberate disruption
- Using the project primarily as a vehicle for unrelated political agitation

## Scope

These expectations apply in project spaces: issues, pull requests, discussions,
chats tied to the project, and similar venues when acting as a participant in
this project.

## Enforcement

Maintainers may warn, moderate, block, or remove contributions that violate
this standard. Serious or repeated abuse may result in a temporary or permanent
ban from project spaces.

Report problems privately to a maintainer (see the repository owner/maintainers,
or [SECURITY.md](SECURITY.md) for security-sensitive matters). Do not file public
issues solely to air personal grievances.

## In one line

**Be excellent to each other; ship good software.**
"""


def _contributing_md(ctx: _Context) -> str:
    return f"""\
# Contributing to {ctx.name}

Thank you for considering a contribution. This guide is intentionally generic
and works for most open-source C++ projects bootstrapped with cppboot.

## Code of conduct

Be mature, respectful, and technical. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Getting started

1. Fork the repository and clone your fork.
2. Install a C++20 toolchain, CMake 3.20+, Ninja (recommended), and Make.
3. Build and test:

   ```bash
   make
   make test
   ./{ctx.name} --version
   ```

4. Optional: open the folder in VS Code and install recommended extensions
   (see README).

## Development workflow

- Prefer small, focused pull requests.
- Follow [AGENTS.md](AGENTS.md) for layout, style, and documentation rules:
  - **Google C++ Style Guide** for code logic and naming
  - **Microsoft** `.clang-format` for formatting (`make fmt`)
- List new sources explicitly in the component `CMakeLists.txt` (no globs).
- Add or update unit tests for behavior changes.
- Keep `make` and `make test` green. On Linux, `make sanitizer` is encouraged
  for memory/UB issues.

## Reporting bugs and proposing features

- Use GitHub Issues for bugs and feature requests.
- Include OS, compiler, CMake version, and steps to reproduce when filing bugs.
- Search existing issues before opening a new one.

## Security vulnerabilities

Do **not** open a public issue for security problems. See
[SECURITY.md](SECURITY.md).

## Pull request checklist

- [ ] Code builds (`make`)
- [ ] Tests pass (`make test`)
- [ ] Formatted (`make fmt`)
- [ ] Public APIs have Doxygen where appropriate
- [ ] Commit messages are clear; PR description explains *why*

## License

By contributing, you agree that your contributions will be licensed under the
same license as this repository (see [LICENSE](LICENSE)).
"""


def _security_md(ctx: _Context) -> str:
    return f"""\
# Security Policy

## Supported versions and fix policy

**{ctx.name}** treats security seriously, with a simple support model:

- Security fixes are developed on the default branch and **ship in the next
  release** (or sooner via an out-of-band release if warranted).
- **We do not backport security fixes to older releases by default.**
- Exceptions may be made for **compelling reasons** (for example, a widely used
  previous release with a severe issue and a clear maintainer commitment). Any
  such exception is discretionary and will be called out in release notes.

| Line | Security fixes |
|------|----------------|
| Default branch (development) | Yes — fixed here first |
| Next / upcoming release | Yes — normal ship vehicle for fixes |
| Older released versions | **No** (unless an explicit exception) |

Always prefer upgrading to the latest release when a security fix is announced.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Prefer one of these private channels (first that applies):

1. **GitHub Private Vulnerability Reporting** (Security tab → Advisories →
   Report a vulnerability), if enabled on this repository.
2. Contact a repository maintainer privately (see the owner/maintainer profile
   or organization security contact).

Include:

- A description of the issue and its impact
- Steps to reproduce or a proof of concept if available
- Affected versions / commit SHAs if known

We will acknowledge receipt when possible and work with you on a coordinated
disclosure timeline. Please give maintainers reasonable time to investigate and
ship a fix (typically via the next release) before any public discussion.

## Preferred languages

English is preferred for security reports.
"""


def _gitignore() -> str:
    return """\
# Build trees
build/
cmake-build-*/
out/
install/

# Compilation database (regenerated by make debug)
compile_commands.json

# ctags index (regenerated by make tags)
tags
TAGS
.tags

# Doxygen
docs/html/
docs/latex/
docs/xml/
docs/rtf/
docs/man/

# IDE / editor
.idea/
# Keep shared VS Code project files; ignore only local/unshared editor state.
.vscode/*
!.vscode/extensions.json
!.vscode/settings.json
!.vscode/tasks.json
!.vscode/launch.json
*.swp
*.swo
*~
.DS_Store
CMakeUserPresets.json

# Python / tooling
__pycache__/
*.pyc
.venv/
venv/

# Coverage / sanitizers
*.gcda
*.gcno
*.profraw
*.profdata
default.profraw

# Package / install leftovers
*.a
*.so
*.so.*
*.dylib
*.dll
*.lib
*.exe
*.pdb
"""


def _gitattributes() -> str:
    return """\
* text=auto eol=lf
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.pdf binary
"""


def _clang_format() -> str:
    return """\
BasedOnStyle: Microsoft
Language: Cpp
Standard: c++20
ColumnLimit: 100
SortIncludes: true
IncludeBlocks: Regroup
"""


def _clangd() -> str:
    # Prefer the source-root database (symlinked/copied from the build tree).
    # Fallback paths help before the first build finishes linking the root file.
    return """\
CompileFlags:
  CompilationDatabase: .
---
If:
  PathMatch: .*
CompileFlags:
  Add:
    - -std=c++20
    - -Iinclude
"""


def _doxyfile(ctx: _Context) -> str:
    return f"""\
# Doxyfile generated by cppboot — minimal professional defaults.
# PROJECT_NUMBER is overridden from the root VERSION file by `make doc` /
# `build.bat doc`; the value below is only a fallback.
PROJECT_NAME           = "{ctx.name}"
PROJECT_NUMBER         = "0.1.0"
OUTPUT_DIRECTORY       = docs
CREATE_SUBDIRS         = NO
ALLOW_UNICODE_NAMES    = YES
OUTPUT_LANGUAGE        = English
BRIEF_MEMBER_DESC      = YES
REPEAT_BRIEF           = YES
ALWAYS_DETAILED_SEC    = NO
FULL_PATH_NAMES        = YES
STRIP_FROM_PATH        = .
JAVADOC_AUTOBRIEF      = YES
QT_AUTOBRIEF           = YES
MULTILINE_CPP_IS_BRIEF = NO
INHERIT_DOCS           = YES
SEPARATE_MEMBER_PAGES  = NO
TAB_SIZE               = 2
OPTIMIZE_OUTPUT_FOR_C  = NO
BUILTIN_STL_SUPPORT    = YES
EXTRACT_ALL            = YES
EXTRACT_PRIVATE        = NO
EXTRACT_STATIC         = YES
HIDE_UNDOC_MEMBERS     = NO
HIDE_UNDOC_CLASSES     = NO
CASE_SENSE_NAMES       = YES
SHOW_INCLUDE_FILES     = YES
SHOW_FILES             = YES
SHOW_NAMESPACES        = YES
QUIET                  = YES
WARNINGS               = YES
WARN_IF_UNDOCUMENTED   = YES
WARN_IF_DOC_ERROR      = YES
INPUT                  = src include
FILE_PATTERNS          = *.cpp *.hpp *.h *.cc *.cxx *.cppm *.ixx
RECURSIVE              = YES
EXCLUDE_PATTERNS       = */build/* */.git/*
SOURCE_BROWSER         = YES
INLINE_SOURCES         = NO
REFERENCED_BY_RELATION = YES
REFERENCES_RELATION    = YES
GENERATE_HTML          = YES
HTML_OUTPUT            = html
GENERATE_LATEX         = NO
HAVE_DOT               = NO
"""

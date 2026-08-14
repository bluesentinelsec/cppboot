# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Generated root `CMakeLists.txt` now includes its own `cmake/` modules by
  absolute path. Module-name `include(Dependencies)` resolves against
  `CMAKE_MODULE_PATH`, and when a generated project is embedded in another
  (add_subdirectory / FetchContent) the parent's same-named module silently
  shadows the child's — observed in the wild when mog's mbedTLS/miniz
  declarations never ran while embedded.


## [0.3.2] - 2026-08-12

### Fixed

- Generated web demo: the JavaScript body of the `EM_JS` renderer is now
  wrapped in `clang-format off/on` markers. Previously `make fmt`
  (default-on at bootstrap) reformatted it as C++, splitting `!==` into
  invalid `!= =` and breaking Release Emscripten builds in the acorn
  optimizer.

## [0.3.1] - 2026-08-11

### Added

- `--license zlib`: the zlib License (SPDX `Zlib`) is now a supported
  license choice, with a full offline fallback body. `zlib/libpng` is
  accepted as an alias.

## [0.3.0] - 2026-08-11

### Changed

- Generated CI-style workflows (`ci.yml`, `sanitizers.yml`, `android.yml`,
  `ios.yml`, `web.yml`) no longer run every job twice for commits on pull
  request branches: the `push` trigger is now scoped to
  `branches: [main, master]`, so PR branches get exactly one run (the
  `pull_request` event) while direct pushes to the default branch still
  run CI. Pushes to branches without an open PR no longer trigger CI —
  open a PR to get checks.

### Added

- `--with-web-ci` (opt-in): generated projects gain a web/Emscripten
  package aimed at browser game development — an HTML5 canvas demo under
  `src/web/` (an `emscripten_set_main_loop` game loop with delta-time
  updates, an `EM_JS` canvas renderer, and a custom fullscreen-canvas
  shell page; `-sUSE_WEBGL2` and `-sALLOW_MEMORY_GROWTH` linked, with
  commented hooks for `--preload-file` assets and SDL2), browser tests
  under `tests/web/` (GoogleTest compiled to wasm, run in headless
  Chrome via `emrun`), Emscripten-aware CMake guards (deps off, app and
  benchmarks hard-disabled, core forced static, tests switch to the
  browser page, new `<MACRO>_BUILD_WEB_DEMO` option), a GitHub Actions
  `web.yml` workflow, and a `build-web` release job attaching
  `<name>-web-wasm32-release-<version>.zip` (wasm library + headers +
  playable demo + `EMSCRIPTEN_VERSION`). Not compatible with
  `--with-modules`.
- Web package guide on the documentation site (`docs/web.md`).

- `--with-ios-ci` (opt-in): generated projects gain an iOS XCFramework
  package — `scripts/build_ios_xcframework.sh` builds static device
  (arm64) and simulator (arm64/x86_64) slices with the public headers and
  generated `version.hpp`, `scripts/verify_ios_xcframework.sh` checks
  slices/headers/version/symbols, a Simulator test app under `tests/ios/`
  consumes the package (`scripts/run_ios_tests.sh`), and GitHub Actions
  gains an `ios.yml` workflow plus a `build-ios` release job attaching
  `<name>-ios-xcframework-release-<version>.zip`. `if(IOS)` CMake guards
  mirror the Android ones (deps/app/tests/benchmarks off, core forced
  static). Deployment target iOS 13.0. Not compatible with
  `--with-modules` (Xcode generator cannot scan C++20 modules).
- iOS package guide on the documentation site (`docs/ios.md`).

- `--with-android-ci` (opt-in): generated projects gain an Android
  [Prefab](https://google.github.io/prefab/) AAR package — an `android/`
  Gradle project (library module + consumer test app), on-device native
  tests under `tests/android/` driven by `scripts/run_android_tests.sh`,
  `if(ANDROID)` CMake guards, a GitHub Actions `android.yml` workflow
  (AAR build, content verification, emulator tests), and a `build-android`
  release job that attaches `<name>-android-release-<version>.aar`.
  Pinned toolchain: Gradle 8.10.2, AGP 8.7.3, NDK 27.2.12479018,
  compileSdk 35, minSdk 21. Not compatible with `--with-modules` (AGP
  builds with CMake 3.22.1; modules need 3.28+). iOS and web/Emscripten
  scaffolds will follow the same `generate/<platform>.py` pattern.
- Public documentation site under `docs/` (GitHub Pages, Jekyll `/docs`
  folder mode): landing page plus the Android package guide.

### Fixed

- Generated README now renders the sanitizer configure flag
  (`-D<MACRO>_ENABLE_SANITIZERS=ON`) instead of a literal `{ctx.macro}`
  placeholder.

## [0.2.3] - 2026-07-27

### Added

- Generated projects are consumable as CMake dependencies via
  `add_subdirectory`, `FetchContent`, and `find_package` after install.
- Top-level vs embed detection (`*_IS_TOP_LEVEL`): when embedded, app,
  tests, benchmarks, and preferred app deps default off so only the library
  is built.
- Package export (`install(EXPORT)` + `*Config.cmake`) and dual library
  aliases (`::lib` / `::${target}`) for clean consumer linking.
- Generated README documents the three consumption paths.

### Changed

- Preferred third-party deps (CLI11, nlohmann/json, spdlog) link on the demo
  app only, not the static library, so install/export does not require
  FetchContent targets.

## [0.2.2] - 2026-07-27

### Changed

- Production-grade README: PyPI install first, clear quick start and CLI docs;
  remove development-era “when ready” and smoke-check scaffolding notes.

## [0.2.1] - 2026-07-27

### Fixed

- CI: stop hardcoding the package version in layout tests (failed after 0.2.0 bump).

## [0.2.0] - 2026-07-27

### Added

- Official support for **Python 3.9+** (`requires-python = ">=3.9"`).
- CI matrix covers **3.9–3.15** (3.15 via `allow-prereleases` while pre-release).

### Changed

- Opinionated defaults are **opt-out only**: help/CLI expose `--no-vim`,
  `--no-ctags`, `--no-vscode`, etc. Positive mirrors (`--vim`, `--git`, …) removed
  so the CLI matches “always on unless you disable it.”

## [0.1.0] - 2026-07-27

Initial public release on PyPI: CMake C++20 scaffolds, VERSION single source,
Makefile/`build.bat`, VS Code, Codespaces, GitHub Actions for generated projects,
multi-Python CI, GitHub Release → PyPI Trusted Publishing.

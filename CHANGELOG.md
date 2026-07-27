# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

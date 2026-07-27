# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

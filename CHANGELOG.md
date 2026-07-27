# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Publish** workflow: GitHub Release (`vX.Y.Z`) builds sdist/wheel and uploads
  to PyPI via Trusted Publishing (OIDC). Manual `workflow_dispatch` can target
  TestPyPI. Release tag must match `src/cppboot/_version.py`.
- Ruff + mypy in CI; distribution build + `twine check` job.
- Dev extras: `ruff`, `mypy`, `build`, `twine`.
- Opt-out flags for default-on behavior: `--no-git`, `--no-fmt`, `--no-community-docs`
  (alongside existing `--no-vim`, `--no-ctags`, `--no-vscode`, `--no-github-actions`,
  `--no-codespaces`).
- Offline license mode for deterministic tests (`ProjectOptions.offline_license`).
- pytest unit and integration suite with multi-Python CI.

### Changed

- Package version single-sourced from `src/cppboot/_version.py` (setuptools
  dynamic version).
- Split the monolithic generator into a `cppboot.generate` package (templates,
  tooling, orchestration) while keeping `cppboot.generator` as a stable facade.
- Added package `LICENSE`, `CHANGELOG.md`, and `py.typed` for a PyPI-ready layout.

## [0.1.0] - unreleased on PyPI

Initial public development line: CMake C++20 scaffolds, VERSION single source,
Makefile/`build.bat`, VS Code, Codespaces, GitHub Actions for generated projects.

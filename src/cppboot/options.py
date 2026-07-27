"""Public options and results for cppboot project generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cppboot.licenses import DEFAULT_LICENSE


@dataclass(frozen=True)
class ProjectOptions:
    """Options controlling project generation."""

    name: str
    root: Path
    license_id: str = DEFAULT_LICENSE
    build_system: str = "cmake"
    with_modules: bool = False
    shared_library: bool = False
    with_vim: bool = True
    with_ctags: bool = True
    with_vscode: bool = True
    with_codespaces: bool = True
    create_github: bool = False
    with_github_actions: bool = True
    with_git: bool = True
    with_fmt: bool = True
    with_community_docs: bool = True
    verbose: bool = False
    # When True, license text uses offline fallbacks (no network). Prefer for tests.
    offline_license: bool = False


@dataclass
class GenerateResult:
    """Outcome of scaffolding a project."""

    project_dir: Path
    files_written: list[Path]
    git_initialized: bool
    github_created: bool
    license_source: str
    formatted: bool = False

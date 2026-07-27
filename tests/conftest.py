"""Shared pytest fixtures for cppboot tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cppboot.generator import ProjectOptions


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """Parent directory for generated projects."""
    return tmp_path


def minimal_options(
    name: str,
    root: Path,
    **overrides: object,
) -> ProjectOptions:
    """Build ProjectOptions for fast, deterministic CI tests.

    Defaults disable network side effects (offline license), post-scaffold
    tooling (git/fmt), and most optional extras so assertions stay focused.
    Callers pass overrides to re-enable specific features under test.
    """
    kwargs: dict[str, object] = {
        "name": name,
        "root": root,
        "with_vim": False,
        "with_ctags": False,
        "with_vscode": False,
        "with_codespaces": False,
        "with_github_actions": False,
        "with_git": False,
        "with_fmt": False,
        "with_community_docs": False,
        "create_github": False,
        "offline_license": True,
    }
    kwargs.update(overrides)
    return ProjectOptions(**kwargs)  # type: ignore[arg-type]

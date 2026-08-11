"""Internal generation context shared by template modules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Context:
    """Derived identifiers and flags for one scaffold run."""

    name: str
    namespace: str
    target: str
    macro: str
    android_package: str
    project_dir: Path
    license_id: str
    with_modules: bool
    shared_library: bool
    with_android_ci: bool
    with_ios_ci: bool
    with_vim: bool
    with_ctags: bool
    with_vscode: bool
    with_codespaces: bool
    with_github_actions: bool
    year: str

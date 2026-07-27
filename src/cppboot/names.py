"""Project name validation and derived identifiers."""

from __future__ import annotations

import re

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def validate_project_name(name: str) -> str:
    """Validate and return a trimmed project name."""
    name = name.strip()
    if not name:
        raise ValueError("project name must not be empty")
    if not _NAME_RE.match(name):
        raise ValueError(
            "project name must start with a letter and contain only "
            "letters, digits, underscores, and hyphens"
        )
    return name


def to_namespace(name: str) -> str:
    """Convert a project name to a C++ namespace identifier."""
    ns = name.replace("-", "_")
    if ns[0].isdigit():
        ns = f"ns_{ns}"
    return ns


def to_target_name(name: str) -> str:
    """Convert a project name to a CMake/Make-friendly target name."""
    return name.replace("-", "_")


def to_macro_prefix(name: str) -> str:
    """Convert a project name to an uppercase macro prefix."""
    return to_target_name(name).upper()

"""cppboot: bootstrap a professional C++ project environment."""

from __future__ import annotations

from cppboot._version import __version__
from cppboot.generator import GenerateResult, ProjectOptions, generate_project

__all__ = [
    "GenerateResult",
    "ProjectOptions",
    "__version__",
    "generate_project",
]

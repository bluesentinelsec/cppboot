"""cppboot: bootstrap a professional C++ project environment."""

from __future__ import annotations

from cppboot.generator import GenerateResult, ProjectOptions, generate_project

__version__ = "0.1.0"

__all__ = [
    "GenerateResult",
    "ProjectOptions",
    "__version__",
    "generate_project",
]

"""Generate a professional C++ project tree.

This module is the stable import path used by the CLI and tests::

    from cppboot.generator import ProjectOptions, generate_project

Implementation lives under :mod:`cppboot.generate`.
"""

from __future__ import annotations

from cppboot.generate.project import generate_project
from cppboot.options import GenerateResult, ProjectOptions

__all__ = [
    "GenerateResult",
    "ProjectOptions",
    "generate_project",
]

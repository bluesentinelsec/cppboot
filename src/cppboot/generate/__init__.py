"""Project generation package (templates + orchestration)."""

from cppboot.generate.project import generate_project
from cppboot.options import GenerateResult, ProjectOptions

__all__ = ["GenerateResult", "ProjectOptions", "generate_project"]

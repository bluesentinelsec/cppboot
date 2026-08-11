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


_JAVA_KEYWORDS = frozenset(
    {
        "abstract",
        "assert",
        "boolean",
        "break",
        "byte",
        "case",
        "catch",
        "char",
        "class",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extends",
        "final",
        "finally",
        "float",
        "for",
        "goto",
        "if",
        "implements",
        "import",
        "instanceof",
        "int",
        "interface",
        "long",
        "native",
        "new",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "short",
        "static",
        "strictfp",
        "super",
        "switch",
        "synchronized",
        "this",
        "throw",
        "throws",
        "transient",
        "try",
        "void",
        "volatile",
        "while",
        "true",
        "false",
        "null",
    }
)


def to_android_package(name: str) -> str:
    """Convert a project name to an Android application namespace.

    The project segment strips every non-alphanumeric character (not just
    hyphens): underscores in a Java package segment would force JNI name
    mangling (``_`` becomes ``_1``) in the generated native test symbol, so an
    all-alphanumeric segment keeps JNI symbols a plain concatenation.
    """
    segment = re.sub(r"[^a-z0-9]", "", name.lower())
    if segment in _JAVA_KEYWORDS:
        segment += "app"
    return f"com.example.{segment}"

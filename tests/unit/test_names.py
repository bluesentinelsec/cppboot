"""Unit tests for project name helpers."""

from __future__ import annotations

import pytest

from cppboot.names import (
    to_macro_prefix,
    to_namespace,
    to_target_name,
    validate_project_name,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("myproj", "myproj"),
        ("  MyProj  ", "MyProj"),
        ("a", "a"),
        ("foo-bar_baz", "foo-bar_baz"),
        ("App2", "App2"),
    ],
)
def test_validate_project_name_accepts(raw: str, expected: str) -> None:
    assert validate_project_name(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "1bad",
        "has space",
        "bad.name",
        "slash/name",
        "-leading",
        "_leading",
    ],
)
def test_validate_project_name_rejects(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_project_name(raw)


def test_to_namespace_hyphen() -> None:
    assert to_namespace("cppboot-smoke-test-2") == "cppboot_smoke_test_2"


def test_to_target_name_hyphen() -> None:
    assert to_target_name("my-app") == "my_app"


def test_to_macro_prefix_upper() -> None:
    assert to_macro_prefix("my-app") == "MY_APP"

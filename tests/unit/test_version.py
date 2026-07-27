"""Version single-source checks for packaging and releases."""

from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

import cppboot
from cppboot._version import __version__ as version_module_version


def test_public_version_matches_module() -> None:
    assert cppboot.__version__ == version_module_version


def test_version_is_pep440_ish() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+([.-].+)?", version_module_version)


def test_installed_metadata_matches_when_available() -> None:
    """When installed editable/normal, distribution metadata should match."""
    try:
        dist_version = metadata.version("cppboot")
    except metadata.PackageNotFoundError:
        return
    assert dist_version == version_module_version


def test_version_file_is_single_assignment() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "src" / "cppboot" / "_version.py").read_text(encoding="utf-8")
    matches = re.findall(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.M)
    assert matches == [version_module_version]

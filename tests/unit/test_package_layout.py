"""Sanity checks for the public package layout."""

from __future__ import annotations

import importlib

import cppboot
from cppboot.generator import GenerateResult, ProjectOptions, generate_project


def test_version_exported() -> None:
    assert cppboot.__version__ == "0.1.0"


def test_public_api_reexported() -> None:
    assert cppboot.ProjectOptions is ProjectOptions
    assert cppboot.GenerateResult is GenerateResult
    assert cppboot.generate_project is generate_project


def test_generate_submodules_importable() -> None:
    for name in (
        "cppboot.generate",
        "cppboot.generate.project",
        "cppboot.generate.cmake_files",
        "cppboot.generate.build_wrappers",
        "cppboot.generate.docs",
        "cppboot.generate.ide",
        "cppboot.generate.github_actions",
        "cppboot.generate.sources",
        "cppboot.generate.tooling",
        "cppboot.options",
    ):
        importlib.import_module(name)


def test_generator_facade_matches_package() -> None:
    from cppboot import generate as gen_pkg
    from cppboot import generator as gen_mod

    assert gen_mod.generate_project is gen_pkg.generate_project
    assert gen_mod.ProjectOptions is gen_pkg.ProjectOptions

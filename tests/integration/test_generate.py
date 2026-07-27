"""Integration tests: generate project trees without network or gh."""

from __future__ import annotations

from pathlib import Path

import pytest

from cppboot.generator import generate_project
from tests.conftest import minimal_options


def test_minimal_scaffold_files(tmp_root: Path) -> None:
    opts = minimal_options("minapp", tmp_root)
    result = generate_project(opts)
    root = result.project_dir

    assert root.is_dir()
    assert (root / "VERSION").read_text(encoding="utf-8").strip() == "0.1.0"
    assert (root / "CMakeLists.txt").is_file()
    assert (root / "Makefile").is_file()
    assert (root / "build.bat").is_file()
    assert (root / "src" / "main.cpp").is_file()
    assert (root / "cmake" / "version.hpp.in").is_file()
    assert (root / "cmake" / "version.cpp.in").is_file()
    assert (root / "LICENSE").is_file()
    assert "offline" in result.license_source

    # Opted out
    assert not (root / ".vimrc").exists()
    assert not (root / ".ctags").exists()
    assert not (root / ".vscode").exists()
    assert not (root / ".devcontainer").exists()
    assert not (root / ".github").exists()
    assert not (root / "CODE_OF_CONDUCT.md").exists()
    assert not (root / "CONTRIBUTING.md").exists()
    assert not (root / "SECURITY.md").exists()
    assert not (root / ".git").exists()
    assert result.git_initialized is False
    assert result.formatted is False
    assert result.github_created is False


def test_default_extras_written(tmp_root: Path) -> None:
    opts = minimal_options(
        "fullapp",
        tmp_root,
        with_vim=True,
        with_ctags=True,
        with_vscode=True,
        with_codespaces=True,
        with_github_actions=True,
        with_community_docs=True,
    )
    result = generate_project(opts)
    root = result.project_dir

    assert (root / ".vimrc").is_file()
    assert (root / ".ctags").is_file()
    assert (root / ".vscode" / "settings.json").is_file()
    assert (root / "CMakePresets.json").is_file()
    assert (root / ".devcontainer" / "devcontainer.json").is_file()
    assert (root / ".github" / "workflows" / "ci.yml").is_file()
    assert (root / ".github" / "workflows" / "sanitizers.yml").is_file()
    assert (root / ".github" / "workflows" / "release.yml").is_file()
    assert (root / "CODE_OF_CONDUCT.md").is_file()
    assert (root / "CONTRIBUTING.md").is_file()
    assert (root / "SECURITY.md").is_file()
    assert not (root / ".git").exists()


def test_community_docs_opt_out(tmp_root: Path) -> None:
    opts = minimal_options("nodocs", tmp_root, with_community_docs=False)
    generate_project(opts)
    root = tmp_root / "nodocs"
    assert not (root / "CODE_OF_CONDUCT.md").exists()
    assert not (root / "SECURITY.md").exists()


def test_github_actions_release_syncs_version_file(tmp_root: Path) -> None:
    opts = minimal_options("relapp", tmp_root, with_github_actions=True)
    generate_project(opts)
    release = (tmp_root / "relapp" / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "VERSION file" in release or "VERSION" in release
    assert "does not match VERSION file" in release


def test_version_templates_use_placeholders(tmp_root: Path) -> None:
    opts = minimal_options("verapp", tmp_root)
    generate_project(opts)
    header = (tmp_root / "verapp" / "cmake" / "version.hpp.in").read_text(encoding="utf-8")
    source = (tmp_root / "verapp" / "cmake" / "version.cpp.in").read_text(encoding="utf-8")
    cmake = (tmp_root / "verapp" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "@PROJECT_VERSION_MAJOR@" in header
    assert "@PROJECT_VERSION_STRING@" in source
    assert "file(STRINGS" in cmake
    assert "VERSION" in cmake


def test_modules_layout(tmp_root: Path) -> None:
    opts = minimal_options("modapp", tmp_root, with_modules=True)
    generate_project(opts)
    root = tmp_root / "modapp"
    assert (root / "cmake" / "version.cppm.in").is_file()
    assert not (root / "cmake" / "version.hpp.in").exists()
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "3.28" in cmake
    version_cmake = (root / "src" / "version" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "FILE_SET CXX_MODULES" in version_cmake
    assert "BASE_DIRS" in version_cmake
    assert "version.cppm" in version_cmake
    main = (root / "src" / "main.cpp").read_text(encoding="utf-8")
    assert "import " in main
    assert main.find("#include") < main.find("import ")  # classic headers before import
    cppm = (root / "cmake" / "version.cppm.in").read_text(encoding="utf-8")
    assert "const char* Version()" in cppm
    assert "string_view" not in cppm


def test_modules_ci_installs_capable_toolchains(tmp_root: Path) -> None:
    opts = minimal_options(
        "modci",
        tmp_root,
        with_modules=True,
        with_github_actions=True,
    )
    generate_project(opts)
    ci = (tmp_root / "modci" / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "g++-14" in ci
    assert "brew install llvm" in ci


def test_shared_library(tmp_root: Path) -> None:
    opts = minimal_options("shapp", tmp_root, shared_library=True)
    generate_project(opts)
    cmake = (tmp_root / "shapp" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "SHARED" in cmake


def test_nonempty_destination_raises(tmp_root: Path) -> None:
    dest = tmp_root / "exists"
    dest.mkdir()
    (dest / "stale.txt").write_text("x", encoding="utf-8")
    opts = minimal_options("exists", tmp_root)
    with pytest.raises(FileExistsError):
        generate_project(opts)


def test_invalid_name_raises(tmp_root: Path) -> None:
    opts = minimal_options("bad name", tmp_root)
    with pytest.raises(ValueError, match="project name"):
        generate_project(opts)


def test_build_bat_mirrors_makefile_targets(tmp_root: Path) -> None:
    opts = minimal_options("winapp", tmp_root)
    generate_project(opts)
    bat = (tmp_root / "winapp" / "build.bat").read_text(encoding="utf-8")
    for target in (":debug", ":release", ":test", ":bench", ":fmt", ":clean", ":help"):
        assert target in bat


def test_cli_generate_end_to_end(tmp_root: Path) -> None:
    from cppboot.cli import main

    rc = main(
        [
            "-n",
            "cliapp",
            "--output-dir",
            str(tmp_root),
            "--no-git",
            "--no-fmt",
            "--no-vim",
            "--no-ctags",
            "--no-vscode",
            "--no-codespaces",
            "--no-github-actions",
            "--no-community-docs",
            "--license",
            "mit",
        ]
    )
    assert rc == 0
    assert (tmp_root / "cliapp" / "VERSION").is_file()
    # CLI does not set offline_license; may use network or fallback.
    # Ensure LICENSE exists either way.
    assert (tmp_root / "cliapp" / "LICENSE").is_file()


@pytest.mark.requires_git
def test_git_opt_in_creates_repo(tmp_root: Path) -> None:
    import shutil

    if shutil.which("git") is None:
        pytest.skip("git not available")
    opts = minimal_options("gitapp", tmp_root, with_git=True)
    result = generate_project(opts)
    assert result.git_initialized is True
    assert (result.project_dir / ".git").is_dir()


def test_git_opt_out_skips_repo(tmp_root: Path) -> None:
    opts = minimal_options("nogit", tmp_root, with_git=False)
    result = generate_project(opts)
    assert result.git_initialized is False
    assert not (result.project_dir / ".git").exists()

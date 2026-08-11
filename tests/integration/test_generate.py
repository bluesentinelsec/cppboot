"""Integration tests: generate project trees without network or gh."""

from __future__ import annotations

import os
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


def test_cmake_is_consumable_as_dependency(tmp_root: Path) -> None:
    """Generated projects support add_subdirectory / FetchContent / find_package."""
    opts = minimal_options("pkgdemo", tmp_root)
    generate_project(opts)
    root = tmp_root / "pkgdemo"
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "IS_TOP_LEVEL" in cmake
    assert "BUILD_APP" in cmake
    assert f"{opts.name.upper().replace('-', '_')}_IS_TOP_LEVEL" in cmake or "IS_TOP_LEVEL" in cmake
    assert "add_library(${PROJECT_NAME}::lib ALIAS" in cmake
    assert "configure_package_config_file" in cmake
    assert "install(EXPORT" in cmake
    config_in = root / "cmake" / "pkgdemoConfig.cmake.in"
    assert config_in.is_file()
    assert "pkgdemoTargets.cmake" in config_in.read_text(encoding="utf-8")
    deps = (root / "cmake" / "Dependencies.cmake").read_text(encoding="utf-8")
    assert "if(PKGDEMO_BUILD_TESTS)" in deps or "BUILD_TESTS)" in deps
    assert "if(PKGDEMO_BUILD_BENCHMARKS)" in deps or "BUILD_BENCHMARKS)" in deps
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "FetchContent" in readme
    assert "add_subdirectory" in readme
    assert "find_package" in readme
    src_cmake = (root / "src" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "BUILD_APP" in src_cmake


def test_android_scaffold_files(tmp_root: Path) -> None:
    opts = minimal_options("droid", tmp_root, with_android_ci=True)
    result = generate_project(opts)
    root = result.project_dir

    gradlew = root / "android" / "gradlew"
    assert gradlew.is_file()
    if os.name != "nt":  # Windows has no POSIX executable bit
        assert gradlew.stat().st_mode & 0o111, "gradlew must be executable"
    jar = root / "android" / "gradle" / "wrapper" / "gradle-wrapper.jar"
    assert jar.is_file()
    assert jar.stat().st_size > 0
    wrapper_props = (
        root / "android" / "gradle" / "wrapper" / "gradle-wrapper.properties"
    ).read_text(encoding="utf-8")
    assert "distributionSha256Sum=" in wrapper_props

    settings = (root / "android" / "settings.gradle").read_text(encoding="utf-8")
    assert 'include(":droid")' in settings
    assert 'include(":test-app")' in settings

    lib_gradle = (root / "android" / "droid" / "build.gradle").read_text(encoding="utf-8")
    assert 'namespace "com.example.droid"' in lib_gradle
    assert "-DDROID_BUILD_APP=OFF" in lib_gradle
    assert "-DDROID_BUILD_TESTS=OFF" in lib_gradle
    assert "prefabPublishing true" in lib_gradle
    assert "ndkVersion" in lib_gradle
    assert (root / "android" / "droid" / "src" / "main" / "AndroidManifest.xml").is_file()
    assert (root / "android" / "test-app" / "build.gradle").is_file()
    activity = root / ("android/test-app/src/main/java/com/example/droid/test/TestActivity.java")
    assert activity.is_file()
    assert "DROID_ANDROID_TESTS" in activity.read_text(encoding="utf-8")

    assert (root / "src" / "android" / "CMakeLists.txt").is_file()
    assert (root / "src" / "android" / "android_library.cpp").is_file()
    test_cpp = (root / "tests" / "android" / "android_test.cpp").read_text(encoding="utf-8")
    assert "Java_com_example_droid_test_TestActivity_runNativeTests" in test_cpp
    assert "<droid/version.hpp>" in test_cpp
    runner = root / "scripts" / "run_android_tests.sh"
    assert runner.is_file()
    if os.name != "nt":
        assert runner.stat().st_mode & 0o111, "run_android_tests.sh must be executable"

    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "if(ANDROID)" in cmake
    assert "CMAKE_POSITION_INDEPENDENT_CODE" in cmake
    src_cmake = (root / "src" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "add_subdirectory(android)" in src_cmake
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert "android/.gradle/" in gitignore

    # Workflows are off in minimal_options; the scaffold must not force them on.
    assert not (root / ".github").exists()


def test_android_with_github_actions(tmp_root: Path) -> None:
    opts = minimal_options("droidci", tmp_root, with_android_ci=True, with_github_actions=True)
    generate_project(opts)
    root = tmp_root / "droidci"
    android_yml = (root / ".github" / "workflows" / "android.yml").read_text(encoding="utf-8")
    assert ":droidci:assembleRelease" in android_yml
    assert "reactivecircus/android-emulator-runner" in android_yml
    release = (root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "build-android:" in release
    assert "needs: [prepare, build, build-android]" in release
    assert "release-assets/**/*.aar" in release


def test_android_absent_by_default(tmp_root: Path) -> None:
    opts = minimal_options("plainapp", tmp_root, with_github_actions=True)
    generate_project(opts)
    root = tmp_root / "plainapp"
    assert not (root / "android").exists()
    assert not (root / "src" / "android").exists()
    assert not (root / "tests" / "android").exists()
    assert not (root / ".github" / "workflows" / "android.yml").exists()
    release = (root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "build-android" not in release
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "if(ANDROID)" not in cmake
    assert "CORE_LIB_TYPE" not in cmake
    assert "DEFAULT_WITH_OPTIONAL_DEPS" not in cmake


def test_android_rejects_modules(tmp_root: Path) -> None:
    opts = minimal_options("droidmod", tmp_root, with_android_ci=True, with_modules=True)
    with pytest.raises(ValueError, match="with-modules"):
        generate_project(opts)
    assert not (tmp_root / "droidmod").exists()


def test_android_with_shared_forces_static_core(tmp_root: Path) -> None:
    opts = minimal_options("droidsh", tmp_root, with_android_ci=True, shared_library=True)
    generate_project(opts)
    cmake = (tmp_root / "droidsh" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "set(DROIDSH_CORE_LIB_TYPE SHARED)" in cmake
    assert "set(DROIDSH_CORE_LIB_TYPE STATIC)" in cmake


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

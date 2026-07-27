"""Orchestrate writing a complete cppboot-generated project tree."""

from __future__ import annotations

import datetime as _dt
import logging
from pathlib import Path

from cppboot.generate.build_wrappers import _build_bat, _makefile
from cppboot.generate.cmake_files import (
    _benchmarks_cmake,
    _dependencies_cmake,
    _package_config_cmake_in,
    _root_cmake,
    _sanitizers_cmake,
    _src_cmake,
    _tests_cmake,
    _version_bench_cmake,
    _version_src_cmake,
    _version_tests_cmake,
    _warnings_cmake,
)
from cppboot.generate.context import Context
from cppboot.generate.docs import (
    _agents_md,
    _clang_format,
    _clangd,
    _code_of_conduct_md,
    _contributing_md,
    _doxyfile,
    _gitattributes,
    _gitignore,
    _readme,
    _security_md,
)
from cppboot.generate.github_actions import (
    _github_actions_release_workflow,
    _github_actions_sanitizers_workflow,
    _github_actions_workflow,
)
from cppboot.generate.ide import (
    _cmake_presets,
    _ctags_config,
    _devcontainer_json,
    _devcontainer_setup_sh,
    _vimrc,
    _vscode_extensions,
    _vscode_launch,
    _vscode_settings,
    _vscode_tasks,
)
from cppboot.generate.sources import (
    _main_cpp,
    _version_bench,
    _version_file,
    _version_header_in,
    _version_module_in,
    _version_source_in,
    _version_test,
)
from cppboot.generate.tooling import _create_github_repo, _git_init, _run_make_fmt
from cppboot.licenses import fetch_license_text, normalize_license_id
from cppboot.names import (
    to_macro_prefix,
    to_namespace,
    to_target_name,
    validate_project_name,
)
from cppboot.options import GenerateResult, ProjectOptions

logger = logging.getLogger(__name__)


def generate_project(options: ProjectOptions) -> GenerateResult:
    """Create the project directory and write all scaffold files."""
    name = validate_project_name(options.name)
    if options.build_system != "cmake":
        raise ValueError(
            f"unsupported build system {options.build_system!r}; only 'cmake' is available"
        )

    license_id = normalize_license_id(options.license_id)
    project_dir = (options.root / name).resolve()
    if project_dir.exists():
        if any(project_dir.iterdir()):
            raise FileExistsError(
                f"project directory already exists and is not empty: {project_dir}"
            )
    else:
        project_dir.mkdir(parents=True)

    ctx = Context(
        name=name,
        namespace=to_namespace(name),
        target=to_target_name(name),
        macro=to_macro_prefix(name),
        project_dir=project_dir,
        license_id=license_id,
        with_modules=options.with_modules,
        shared_library=options.shared_library,
        with_vim=options.with_vim,
        with_ctags=options.with_ctags,
        with_vscode=options.with_vscode,
        with_codespaces=options.with_codespaces,
        with_github_actions=options.with_github_actions,
        year=str(_dt.date.today().year),
    )

    if options.with_modules:
        logger.info(
            "C++20 modules scaffold enabled: requires CMake 3.28+, Ninja, and a "
            "compiler with module dependency scanning (Clang 16+, GCC 14+, or "
            "MSVC 17.4+). AppleClang often lacks CMake module scanning support."
        )
    written: list[Path] = []

    def write(relpath: str, content: str) -> None:
        path = project_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
        logger.debug("wrote %s", path)

    # Root files
    write("VERSION", _version_file())
    write("CMakeLists.txt", _root_cmake(ctx))
    write("Makefile", _makefile(ctx))
    write("build.bat", _build_bat(ctx))
    write("README.md", _readme(ctx))
    write("AGENTS.md", _agents_md(ctx))
    # Repo-local community health files override GitHub user/org defaults
    # (e.g. a personal .github repo with company-specific templates).
    if options.with_community_docs:
        write("CODE_OF_CONDUCT.md", _code_of_conduct_md())
        write("CONTRIBUTING.md", _contributing_md(ctx))
        write("SECURITY.md", _security_md(ctx))
    write(".gitignore", _gitignore())
    write(".gitattributes", _gitattributes())
    write(".clang-format", _clang_format())
    write(".clangd", _clangd())
    write("Doxyfile", _doxyfile(ctx))
    write("cmake/Dependencies.cmake", _dependencies_cmake(ctx))
    write("cmake/CompilerWarnings.cmake", _warnings_cmake())
    write("cmake/Sanitizers.cmake", _sanitizers_cmake())
    write(f"cmake/{ctx.name}Config.cmake.in", _package_config_cmake_in(ctx))
    # Version API is generated from VERSION via configure_file (single source).
    if ctx.with_modules:
        write("cmake/version.cppm.in", _version_module_in(ctx))
    else:
        write("cmake/version.hpp.in", _version_header_in(ctx))
        write("cmake/version.cpp.in", _version_source_in(ctx))
        # Keep the public include tree present for new components (version.hpp
        # is generated into the build tree, not checked into include/).
        write(f"include/{ctx.namespace}/.gitkeep", "")

    # Default library surface: version API + thin CLI with --version.
    write("src/CMakeLists.txt", _src_cmake(ctx))
    write("src/main.cpp", _main_cpp(ctx))
    write("src/version/CMakeLists.txt", _version_src_cmake(ctx))

    # Tests
    write("tests/CMakeLists.txt", _tests_cmake(ctx))
    write("tests/version/CMakeLists.txt", _version_tests_cmake(ctx))
    write("tests/version/version_test.cpp", _version_test(ctx))

    # Benchmarks
    write("benchmarks/CMakeLists.txt", _benchmarks_cmake(ctx))
    write("benchmarks/version/CMakeLists.txt", _version_bench_cmake(ctx))
    write("benchmarks/version/version_bench.cpp", _version_bench(ctx))

    if ctx.with_vim:
        write(".vimrc", _vimrc(ctx))

    if ctx.with_ctags:
        write(".ctags", _ctags_config())
        logger.info("wrote Universal Ctags config (.ctags); run: make tags")

    # CMakePresets are shared by local VS Code and GitHub Codespaces.
    if ctx.with_vscode or ctx.with_codespaces:
        write("CMakePresets.json", _cmake_presets(ctx))

    if ctx.with_vscode:
        write(".vscode/extensions.json", _vscode_extensions())
        write(".vscode/settings.json", _vscode_settings(ctx))
        write(".vscode/tasks.json", _vscode_tasks(ctx))
        write(".vscode/launch.json", _vscode_launch(ctx))
        logger.info("wrote VS Code config under .vscode/ and CMakePresets.json")

    if ctx.with_codespaces:
        write(".devcontainer/devcontainer.json", _devcontainer_json(ctx))
        write(".devcontainer/setup.sh", _devcontainer_setup_sh(ctx))
        setup_sh = project_dir / ".devcontainer" / "setup.sh"
        setup_sh.chmod(setup_sh.stat().st_mode | 0o111)
        logger.info("wrote GitHub Codespaces / Dev Container config under .devcontainer/")

    if ctx.with_github_actions:
        write(".github/workflows/ci.yml", _github_actions_workflow(ctx))
        write(".github/workflows/sanitizers.yml", _github_actions_sanitizers_workflow(ctx))
        write(".github/workflows/release.yml", _github_actions_release_workflow(ctx))
        logger.info("wrote GitHub Actions workflows under .github/workflows/")

    year = ctx.year
    holder = name
    license_result = fetch_license_text(
        license_id,
        year=year,
        holder=holder,
        offline=options.offline_license,
    )
    write("LICENSE", license_result.text)
    logger.info(
        "license %s written from %s",
        license_result.license_id,
        license_result.source,
    )

    # Format before the initial commit so the tree is in a predictable state.
    formatted = False
    if options.with_fmt:
        formatted = _run_make_fmt(project_dir)
    git_ok = False
    if options.with_git:
        git_ok = _git_init(project_dir)
    github_ok = False
    if options.create_github:
        github_ok = _create_github_repo(project_dir, name)

    return GenerateResult(
        project_dir=project_dir,
        files_written=written,
        git_initialized=git_ok,
        github_created=github_ok,
        license_source=license_result.source,
        formatted=formatted,
    )

"""Generate a professional C++ project tree."""

from __future__ import annotations

import datetime as _dt
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cppboot.licenses import DEFAULT_LICENSE, fetch_license_text, normalize_license_id
from cppboot.names import (
    to_macro_prefix,
    to_namespace,
    to_target_name,
    validate_project_name,
)

logger = logging.getLogger(__name__)

# Pinned to latest stable releases as of implementation time.
GOOGLETEST_TAG = "v1.17.0"
BENCHMARK_TAG = "v1.9.5"
CLI11_TAG = "v2.6.2"
NLOHMANN_JSON_TAG = "v3.12.0"
SPDLOG_TAG = "v1.17.0"


@dataclass(frozen=True)
class ProjectOptions:
    """Options controlling project generation."""

    name: str
    root: Path
    license_id: str = DEFAULT_LICENSE
    build_system: str = "cmake"
    with_modules: bool = False
    shared_library: bool = False
    with_vim: bool = True
    with_ctags: bool = True
    with_vscode: bool = True
    with_codespaces: bool = True
    create_github: bool = False
    with_github_actions: bool = True
    with_git: bool = True
    with_fmt: bool = True
    with_community_docs: bool = True
    verbose: bool = False
    # When True, license text uses offline fallbacks (no network). Prefer for tests.
    offline_license: bool = False


@dataclass
class GenerateResult:
    """Outcome of scaffolding a project."""

    project_dir: Path
    files_written: list[Path]
    git_initialized: bool
    github_created: bool
    license_source: str
    formatted: bool = False


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

    ctx = _Context(
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
        logger.info(
            "wrote GitHub Codespaces / Dev Container config under .devcontainer/"
        )

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


@dataclass
class _Context:
    name: str
    namespace: str
    target: str
    macro: str
    project_dir: Path
    license_id: str
    with_modules: bool
    shared_library: bool
    with_vim: bool
    with_ctags: bool
    with_vscode: bool
    with_codespaces: bool
    with_github_actions: bool
    year: str


def _run_make_fmt(project_dir: Path) -> bool:
    """Run ``make fmt`` so generated sources match .clang-format."""
    make = shutil.which("make")
    if make is None:
        logger.warning("make not found; skipped source formatting")
        return False
    if shutil.which("clang-format") is None:
        logger.warning("clang-format not found; skipped source formatting")
        return False
    try:
        completed = subprocess.run(
            [make, "fmt"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        if completed.stdout.strip():
            logger.debug("make fmt: %s", completed.stdout.strip())
        logger.info("formatted sources with make fmt")
        return True
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "make fmt failed (continuing with unformatted sources): %s",
            (exc.stderr or exc.stdout or str(exc)).strip(),
        )
        return False


def _git_init(project_dir: Path) -> bool:
    """Initialize git and create a single initial commit of the scaffold."""
    git = shutil.which("git")
    if git is None:
        logger.warning("git not found; skipped git init")
        return False
    try:
        subprocess.run(
            [git, "init"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [git, "add", "-A"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        # Avoid empty commits if nothing is staged (should not happen).
        status = subprocess.run(
            [git, "status", "--porcelain"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        if not status.stdout.strip():
            logger.warning("git: nothing to commit after scaffold")
            return True
        subprocess.run(
            [
                git,
                "-c",
                "user.email=cppboot@localhost",
                "-c",
                "user.name=cppboot",
                "commit",
                "-m",
                "Initial commit from cppboot",
            ],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(
            "initialized git repository with initial commit in %s",
            project_dir,
        )
        return True
    except subprocess.CalledProcessError as exc:
        logger.warning("git init failed: %s", exc.stderr or exc)
        return False


def _create_github_repo(project_dir: Path, name: str) -> bool:
    gh = shutil.which("gh")
    if gh is None:
        logger.error("gh client not found; cannot create GitHub repository")
        return False
    try:
        subprocess.run(
            [
                gh,
                "repo",
                "create",
                name,
                "--source=.",
                "--public",
                "--remote=origin",
                "--push",
            ],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("created GitHub repository for %s", name)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("gh repo create failed: %s", exc.stderr or exc)
        return False


# ---------------------------------------------------------------------------
# File templates
# ---------------------------------------------------------------------------


def _root_cmake(ctx: _Context) -> str:
    lib_type = "SHARED" if ctx.shared_library else "STATIC"
    modules_block = ""
    if ctx.with_modules:
        modules_block = """
# C++20 modules require a recent CMake and toolchain.
set(CMAKE_CXX_SCAN_FOR_MODULES ON)
"""
    if ctx.with_modules:
        version_generate = f"""\
# Generate the version module from cmake/version.cppm.in (values from VERSION).
set({ctx.macro}_GENERATED_DIR "${{CMAKE_CURRENT_BINARY_DIR}}/generated")
configure_file(
  "${{CMAKE_CURRENT_SOURCE_DIR}}/cmake/version.cppm.in"
  "${{{ctx.macro}_GENERATED_DIR}}/version.cppm"
  @ONLY
)
"""
        public_includes = f"""\
# Module interface units provide the public API; no classic include tree.
# Generated module unit lives under ${{{ctx.macro}_GENERATED_DIR}}.
"""
    else:
        version_generate = f"""\
# Generate the version API from cmake/version.{{hpp,cpp}}.in (values from VERSION).
set({ctx.macro}_GENERATED_DIR "${{CMAKE_CURRENT_BINARY_DIR}}/generated")
set({ctx.macro}_GENERATED_INCLUDE_DIR "${{{ctx.macro}_GENERATED_DIR}}/include")
configure_file(
  "${{CMAKE_CURRENT_SOURCE_DIR}}/cmake/version.hpp.in"
  "${{{ctx.macro}_GENERATED_INCLUDE_DIR}}/{ctx.namespace}/version.hpp"
  @ONLY
)
configure_file(
  "${{CMAKE_CURRENT_SOURCE_DIR}}/cmake/version.cpp.in"
  "${{{ctx.macro}_GENERATED_DIR}}/version.cpp"
  @ONLY
)
"""
        public_includes = f"""\
target_include_directories(${{PROJECT_NAME}}_lib
  PUBLIC
    $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include>
    $<BUILD_INTERFACE:${{{ctx.macro}_GENERATED_INCLUDE_DIR}}>
    $<INSTALL_INTERFACE:include>
)
"""

    cmake_min = "3.28" if ctx.with_modules else "3.20"
    return f"""\
cmake_minimum_required(VERSION {cmake_min})

# ---------------------------------------------------------------------------
# Single source of truth for the package version: the VERSION file at repo root.
# Edit that file only; CMake, --version, tests, and release checks all consume it.
# ---------------------------------------------------------------------------
file(STRINGS "${{CMAKE_CURRENT_SOURCE_DIR}}/VERSION" {ctx.macro}_VERSION_RAW
  LIMIT_COUNT 1
)
string(STRIP "${{{ctx.macro}_VERSION_RAW}}" {ctx.macro}_VERSION)
# Allow optional leading 'v' and ignore anything after '#' on the line.
string(REGEX REPLACE "^[vV]" "" {ctx.macro}_VERSION "${{{ctx.macro}_VERSION}}")
string(REGEX REPLACE "[ \\t]*#.*" "" {ctx.macro}_VERSION "${{{ctx.macro}_VERSION}}")
string(STRIP "${{{ctx.macro}_VERSION}}" {ctx.macro}_VERSION)
if(NOT {ctx.macro}_VERSION MATCHES "^[0-9]+\\\\.[0-9]+\\\\.[0-9]+([.-].*)?$")
  message(FATAL_ERROR
    "VERSION file must contain a semantic version like 0.1.0 "
    "(got '${{{ctx.macro}_VERSION}}')"
  )
endif()

project({ctx.name}
  VERSION ${{{ctx.macro}_VERSION}}
  DESCRIPTION "C++ project bootstrapped by cppboot"
  LANGUAGES CXX
)

# Exposed to version templates (configure_file @ONLY).
set(PROJECT_NAMESPACE "{ctx.namespace}")
set(PROJECT_VERSION_STRING "${{PROJECT_VERSION}}")

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Export a compilation database for clangd and other LSP tools.
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Put binaries under build/<config>/bin (and libs under lib/) so an executable
# named like a component directory (e.g. project "calc" + src/calc/) never
# collides with a source/build subdirectory path.
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${{CMAKE_BINARY_DIR}}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${{CMAKE_BINARY_DIR}}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${{CMAKE_BINARY_DIR}}/lib)

# Default to Debug when the user does not pass CMAKE_BUILD_TYPE (single-config).
if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Debug CACHE STRING "Build type" FORCE)
endif()

list(APPEND CMAKE_MODULE_PATH "${{CMAKE_CURRENT_SOURCE_DIR}}/cmake")
include(CompilerWarnings)
include(Sanitizers)

# Preferred third-party libraries (FetchContent). ON by default; turn off to skip.
option({ctx.macro}_WITH_CLI11 "CLI argument parsing via CLI11" ON)
option({ctx.macro}_WITH_JSON "JSON parsing via nlohmann/json" ON)
option({ctx.macro}_WITH_SPDLOG "Console/file logging via spdlog" ON)

option({ctx.macro}_BUILD_TESTS "Build unit tests" ON)
option({ctx.macro}_BUILD_BENCHMARKS "Build benchmarks" ON)
# ASan + UBSan for project targets (intended for Linux GCC/Clang; see make sanitizer).
option({ctx.macro}_ENABLE_SANITIZERS "Enable Address+UBSan on project targets" OFF)

include(Dependencies)

# Apply sanitizer flags only to targets created after this point (not FetchContent deps).
if({ctx.macro}_ENABLE_SANITIZERS)
  cppboot_enable_sanitizers()
endif()
{modules_block}
{version_generate}
add_library(${{PROJECT_NAME}}_lib {lib_type})
add_library(${{PROJECT_NAME}}::lib ALIAS ${{PROJECT_NAME}}_lib)

set_target_properties(${{PROJECT_NAME}}_lib PROPERTIES
  OUTPUT_NAME {ctx.target}
  EXPORT_NAME lib
  VERSION ${{PROJECT_VERSION}}
  SOVERSION ${{PROJECT_VERSION_MAJOR}}
)

{public_includes}
cppboot_set_project_warnings(${{PROJECT_NAME}}_lib)

# Preferred deps link PUBLIC so the app and tests inherit them with the library.
if({ctx.macro}_WITH_CLI11)
  target_link_libraries(${{PROJECT_NAME}}_lib PUBLIC CLI11::CLI11)
endif()
if({ctx.macro}_WITH_JSON)
  target_link_libraries(${{PROJECT_NAME}}_lib PUBLIC nlohmann_json::nlohmann_json)
endif()
if({ctx.macro}_WITH_SPDLOG)
  target_link_libraries(${{PROJECT_NAME}}_lib PUBLIC spdlog::spdlog)
endif()

add_subdirectory(src)

if({ctx.macro}_BUILD_TESTS)
  enable_testing()
  add_subdirectory(tests)
endif()

if({ctx.macro}_BUILD_BENCHMARKS)
  add_subdirectory(benchmarks)
endif()

# Keep a source-root compile_commands.json for clangd / VS Code IntelliSense.
# The database is written into the build tree; re-link/copy on every build.
if(CMAKE_EXPORT_COMPILE_COMMANDS)
  if(WIN32)
    add_custom_target(cppboot_compile_commands ALL
      COMMAND ${{CMAKE_COMMAND}} -E copy_if_different
        "${{CMAKE_BINARY_DIR}}/compile_commands.json"
        "${{CMAKE_SOURCE_DIR}}/compile_commands.json"
      COMMENT "Copying compile_commands.json to source root for clangd"
      VERBATIM
    )
  else()
    add_custom_target(cppboot_compile_commands ALL
      COMMAND ${{CMAKE_COMMAND}} -E rm -f
        "${{CMAKE_SOURCE_DIR}}/compile_commands.json"
      COMMAND ${{CMAKE_COMMAND}} -E create_symlink
        "${{CMAKE_BINARY_DIR}}/compile_commands.json"
        "${{CMAKE_SOURCE_DIR}}/compile_commands.json"
      COMMENT "Linking compile_commands.json to source root for clangd"
      VERBATIM
    )
  endif()
endif()

include(GNUInstallDirs)
{_install_rules(ctx)}
"""


def _install_rules(ctx: _Context) -> str:
    if ctx.with_modules:
        return """\
install(TARGETS ${PROJECT_NAME}_lib
  EXPORT ${PROJECT_NAME}Targets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
  FILE_SET CXX_MODULES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/modules
)
"""
    return f"""\
install(DIRECTORY include/
  DESTINATION ${{CMAKE_INSTALL_INCLUDEDIR}}
  FILES_MATCHING PATTERN "*.hpp" PATTERN "*.h"
)
# Generated version API header (from VERSION + cmake/version.hpp.in).
install(DIRECTORY ${{{ctx.macro}_GENERATED_INCLUDE_DIR}}/
  DESTINATION ${{CMAKE_INSTALL_INCLUDEDIR}}
  FILES_MATCHING PATTERN "*.hpp" PATTERN "*.h"
)
install(TARGETS ${{PROJECT_NAME}}_lib
  EXPORT ${{PROJECT_NAME}}Targets
  ARCHIVE DESTINATION ${{CMAKE_INSTALL_LIBDIR}}
  LIBRARY DESTINATION ${{CMAKE_INSTALL_LIBDIR}}
  RUNTIME DESTINATION ${{CMAKE_INSTALL_BINDIR}}
  INCLUDES DESTINATION ${{CMAKE_INSTALL_INCLUDEDIR}}
)
"""


def _dependencies_cmake(ctx: _Context) -> str:
    macro = ctx.macro
    return f"""\
# Third-party dependencies via FetchContent (pinned stable tags).
include(FetchContent)

set(GOOGLETEST_TAG {GOOGLETEST_TAG})
set(BENCHMARK_TAG {BENCHMARK_TAG})
set(CLI11_TAG {CLI11_TAG})
set(NLOHMANN_JSON_TAG {NLOHMANN_JSON_TAG})
set(SPDLOG_TAG {SPDLOG_TAG})

# ---------------------------------------------------------------------------
# Preferred application libraries (optional, ON by default — see root options)
# ---------------------------------------------------------------------------

if({macro}_WITH_CLI11)
  # CLI11 — header-only CLI parser (static-link friendly).
  set(CLI11_PRECOMPILED OFF CACHE BOOL "" FORCE)
  set(CLI11_BUILD_TESTS OFF CACHE BOOL "" FORCE)
  set(CLI11_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
  FetchContent_Declare(
    cli11
    GIT_REPOSITORY https://github.com/CLIUtils/CLI11.git
    GIT_TAG        ${{CLI11_TAG}}
    GIT_SHALLOW    TRUE
  )
  FetchContent_MakeAvailable(cli11)
  cppboot_mark_system_includes(CLI11)
endif()

if({macro}_WITH_JSON)
  # nlohmann/json — header-only JSON (static-link friendly).
  set(JSON_BuildTests OFF CACHE BOOL "" FORCE)
  set(JSON_Install OFF CACHE BOOL "" FORCE)
  FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        ${{NLOHMANN_JSON_TAG}}
    GIT_SHALLOW    TRUE
  )
  FetchContent_MakeAvailable(nlohmann_json)
  cppboot_mark_system_includes(nlohmann_json)
endif()

if({macro}_WITH_SPDLOG)
  # spdlog — fast logging; built as a static library by default.
  set(SPDLOG_BUILD_EXAMPLE OFF CACHE BOOL "" FORCE)
  set(SPDLOG_BUILD_TESTS OFF CACHE BOOL "" FORCE)
  set(SPDLOG_BUILD_BENCH OFF CACHE BOOL "" FORCE)
  set(SPDLOG_INSTALL OFF CACHE BOOL "" FORCE)
  set(SPDLOG_BUILD_SHARED OFF CACHE BOOL "" FORCE)
  FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG        ${{SPDLOG_TAG}}
    GIT_SHALLOW    TRUE
  )
  FetchContent_MakeAvailable(spdlog)
  cppboot_mark_system_includes(spdlog)
endif()

# ---------------------------------------------------------------------------
# Test / benchmark frameworks
# ---------------------------------------------------------------------------

# GoogleTest / GoogleMock
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
set(BUILD_GMOCK ON CACHE BOOL "" FORCE)
set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
  googletest
  GIT_REPOSITORY https://github.com/google/googletest.git
  GIT_TAG        ${{GOOGLETEST_TAG}}
  GIT_SHALLOW    TRUE
)

# Google Benchmark
set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
set(BENCHMARK_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
set(BENCHMARK_ENABLE_GTEST_TESTS OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
  benchmark
  GIT_REPOSITORY https://github.com/google/benchmark.git
  GIT_TAG        ${{BENCHMARK_TAG}}
  GIT_SHALLOW    TRUE
)

FetchContent_MakeAvailable(googletest benchmark)

# Suppress warnings from third-party headers when consumed by project TUs.
foreach(_cppboot_third_party IN ITEMS gtest gtest_main gmock gmock_main benchmark benchmark_main)
  cppboot_mark_system_includes(${{_cppboot_third_party}})
endforeach()

include(GoogleTest)
"""


def _warnings_cmake() -> str:
    return """\
# Treat warnings as errors to force good habits from day one.
function(cppboot_set_project_warnings target_name)
  if(MSVC)
    target_compile_options(${target_name} PRIVATE /W4 /WX /permissive-)
  else()
    target_compile_options(${target_name} PRIVATE
      -Wall
      -Wextra
      -Wpedantic
      -Werror
      -Wconversion
      -Wshadow
      -Wnon-virtual-dtor
      -Wold-style-cast
      -Wcast-align
      -Wunused
      -Woverloaded-virtual
    )
  endif()
endfunction()

# Prefer system includes for third-party targets so -Werror does not fire inside them.
function(cppboot_mark_system_includes target_name)
  if(TARGET ${target_name})
    get_target_property(_inc ${target_name} INTERFACE_INCLUDE_DIRECTORIES)
    if(_inc)
      set_target_properties(${target_name} PROPERTIES
        INTERFACE_SYSTEM_INCLUDE_DIRECTORIES "${_inc}"
      )
    endif()
  endif()
endfunction()
"""


def _sanitizers_cmake() -> str:
    return """\
# AddressSanitizer + UndefinedBehaviorSanitizer (GCC/Clang).
# Enable with -D<PROJECT>_ENABLE_SANITIZERS=ON (see `make sanitizer`).
# Intended primary platform: Linux. macOS is best-effort; MSVC is not supported here.
function(cppboot_enable_sanitizers)
  if(MSVC)
    message(FATAL_ERROR
      "Sanitizers via cppboot_enable_sanitizers() require GCC or Clang "
      "(not MSVC). Use Linux CI or a Clang toolset.")
  endif()
  if(NOT CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang")
    message(FATAL_ERROR
      "Sanitizers require GNU or Clang (got ${CMAKE_CXX_COMPILER_ID}).")
  endif()

  message(STATUS "Enabling AddressSanitizer + UndefinedBehaviorSanitizer on project targets")
  add_compile_options(
    -fsanitize=address,undefined
    -fno-omit-frame-pointer
    -fno-sanitize-recover=all
    -g
  )
  add_link_options(
    -fsanitize=address,undefined
  )
endfunction()
"""


def _src_cmake(ctx: _Context) -> str:
    return f"""\
# Library implementation components.
# Each logical subdirectory owns a CMakeLists.txt that lists sources explicitly.
add_subdirectory(version)
# Example for new code:
#   add_subdirectory(parser)

# Painfully obvious program entrypoint: src/main.cpp
# Do not add other executables here without a strong reason.
add_executable(${{PROJECT_NAME}}_app main.cpp)
set_target_properties(${{PROJECT_NAME}}_app PROPERTIES OUTPUT_NAME {ctx.name})
target_link_libraries(${{PROJECT_NAME}}_app PRIVATE ${{PROJECT_NAME}}_lib)
cppboot_set_project_warnings(${{PROJECT_NAME}}_app)
"""


def _version_src_cmake(ctx: _Context) -> str:
    if ctx.with_modules:
        return f"""\
# version component (C++20 module) — generated from cmake/version.cppm.in + VERSION.
target_sources(${{PROJECT_NAME}}_lib
  PUBLIC
    FILE_SET CXX_MODULES FILES
      ${{{ctx.macro}_GENERATED_DIR}}/version.cppm
)
"""
    return f"""\
# version component — generated from cmake/version.{{hpp,cpp}}.in + VERSION file.
# Edit the root VERSION file only; do not hand-edit the generated sources.
target_sources(${{PROJECT_NAME}}_lib
  PRIVATE
    ${{{ctx.macro}_GENERATED_DIR}}/version.cpp
)
"""


def _tests_cmake(ctx: _Context) -> str:
    _ = ctx
    return """\
# Unit tests — one subdirectory per component under test.
add_subdirectory(version)
"""


def _version_tests_cmake(ctx: _Context) -> str:
    return f"""\
add_executable({ctx.target}_version_test
  version_test.cpp
)
target_link_libraries({ctx.target}_version_test
  PRIVATE
    ${{PROJECT_NAME}}_lib
    GTest::gtest_main
)
cppboot_set_project_warnings({ctx.target}_version_test)
gtest_discover_tests({ctx.target}_version_test)
"""


def _benchmarks_cmake(ctx: _Context) -> str:
    _ = ctx
    return """\
# Microbenchmarks — one subdirectory per component.
add_subdirectory(version)
"""


def _version_bench_cmake(ctx: _Context) -> str:
    return f"""\
add_executable({ctx.target}_version_bench
  version_bench.cpp
)
target_link_libraries({ctx.target}_version_bench
  PRIVATE
    ${{PROJECT_NAME}}_lib
    benchmark::benchmark
    benchmark::benchmark_main
)
cppboot_set_project_warnings({ctx.target}_version_bench)
"""


def _makefile(ctx: _Context) -> str:
    target = ctx.target
    # Keep Makefile and CMakePresets/VS Code aligned: prefer Ninja when available.
    # Mixing Unix Makefiles (plain `cmake -B build/debug`) with presets that force
    # Ninja causes "generator does not match" errors on F5.
    if ctx.with_modules:
        generator_default = """
# C++20 modules require Ninja (or Visual Studio). Prefer Ninja by default.
# Must match CMakePresets.json so `make` and VS Code F5 share the same build tree.
ifeq ($(GENERATOR),)
  ifneq ($(shell command -v ninja 2>/dev/null),)
    GENERATOR := Ninja
  else
    $(warning C++20 modules need Ninja; install ninja or set GENERATOR=)
  endif
endif
"""
    else:
        generator_default = """
# Prefer Ninja when available so `make` matches CMakePresets.json / VS Code.
# Override with: make GENERATOR="Unix Makefiles"   or install ninja (brew/apt).
ifeq ($(GENERATOR),)
  ifneq ($(shell command -v ninja 2>/dev/null),)
    GENERATOR := Ninja
  endif
endif
"""
    if ctx.with_ctags:
        phony_extra = " tags"
        help_tags = (
            '\t@echo "  make tags           - regenerate ctags index (Universal Ctags)"\n'
        )
        tags_target = """
tags:
	@command -v ctags >/dev/null 2>&1 || { echo "ctags not found (install universal-ctags)"; exit 1; }
	ctags -R
	@echo "wrote tags"
"""
        clean_extra = " tags TAGS"
    else:
        phony_extra = ""
        help_tags = ""
        tags_target = ""
        clean_extra = ""

    return f"""\
# Idiomatic GNU Make wrapper around the CMake build.
# Prefer these targets for day-to-day work.

.PHONY: all debug release test bench sanitizer fmt doc clean reconfigure-debug reconfigure-release \\
        configure-debug configure-release link_compile_commands copy_compile_commands help{phony_extra}

PROJECT_NAME := {ctx.name}
PROJECT_MACRO := {ctx.macro}
TARGET_NAME  := {target}
BUILD_DEBUG  := build/debug
BUILD_RELEASE := build/release
BUILD_SANITIZER := build/sanitizer
GENERATOR    ?=
CMAKE_FLAGS  ?=
{generator_default}
ifeq ($(OS),Windows_NT)
  EXE_EXT := .exe
  COMPILE_COMMANDS_RULE := copy_compile_commands
else
  EXE_EXT :=
  COMPILE_COMMANDS_RULE := link_compile_commands
endif

CMAKE_GENERATOR_FLAG := $(if $(GENERATOR),-G "$(GENERATOR)",)

all: debug

help:
	@echo "Targets:"
	@echo "  make / make debug  - configure & build Debug (no opt, symbols)"
	@echo "  make release       - configure & build Release (optimized, stripped)"
	@echo "  make test          - run unit tests (Debug)"
	@echo "  make bench         - run microbenchmarks (Release preferred)"
	@echo "  make sanitizer     - ASan+UBSan build + ctest (Linux/Clang/GCC)"
	@echo "  make fmt           - run clang-format on all sources"
	@echo "  make doc           - generate Doxygen HTML under docs/html"
{help_tags}	@echo "  make reconfigure-debug  - wipe build/debug and reconfigure (fixes generator mismatches)"
	@echo "  make clean         - remove local build trees and compile_commands.json"

# Wipe a build tree when the generator changes (e.g. Makefiles vs Ninja / VS Code).
reconfigure-debug:
	rm -rf $(BUILD_DEBUG)
	$(MAKE) configure-debug

reconfigure-release:
	rm -rf $(BUILD_RELEASE)
	$(MAKE) configure-release

configure-debug:
	cmake -S . -B $(BUILD_DEBUG) $(CMAKE_GENERATOR_FLAG) \\
	  -DCMAKE_BUILD_TYPE=Debug \\
	  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \\
	  $(CMAKE_FLAGS)
	$(MAKE) $(COMPILE_COMMANDS_RULE) BUILD_DIR=$(BUILD_DEBUG)

configure-release:
	cmake -S . -B $(BUILD_RELEASE) $(CMAKE_GENERATOR_FLAG) \\
	  -DCMAKE_BUILD_TYPE=Release \\
	  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \\
	  $(CMAKE_FLAGS)

debug: configure-debug
	cmake --build $(BUILD_DEBUG) --parallel
	@# Convenience symlink so ./$(PROJECT_NAME) works from the project root.
	ln -sfn $(BUILD_DEBUG)/bin/$(PROJECT_NAME)$(EXE_EXT) $(PROJECT_NAME)$(EXE_EXT)

release: configure-release
	cmake --build $(BUILD_RELEASE) --parallel
	-@find $(BUILD_RELEASE)/bin -type f -name '*$(EXE_EXT)' 2>/dev/null \\
	  -exec strip -S {{}} + 2>/dev/null || true
	ln -sfn $(BUILD_RELEASE)/bin/$(PROJECT_NAME)$(EXE_EXT) $(PROJECT_NAME)$(EXE_EXT)

test: debug
	ctest --test-dir $(BUILD_DEBUG) --output-on-failure --parallel

# Runs the first Google Benchmark binary found under the Release build tree
# (e.g. <name>_version_bench). Missing benches exit successfully.
bench: release
	@found=$$(find $(BUILD_RELEASE)/bin $(BUILD_RELEASE) -type f \\( -name '*bench$(EXE_EXT)' -o -name '*_bench$(EXE_EXT)' \\) 2>/dev/null | head -n 1); \\
	if [ -z "$$found" ]; then \\
	  echo "No benchmark executables found. Add benchmarks/<component>/ then rebuild."; \\
	  exit 0; \\
	fi; \\
	echo "Running $$found"; \\
	"$$found" --benchmark_min_time=0.01s

# AddressSanitizer + UndefinedBehaviorSanitizer (project targets only).
# Primary platform: Linux. Failures abort so CI/jobs exit non-zero.
# Leak detection is Linux-only (ASan aborts on macOS if detect_leaks=1).
sanitizer:
ifeq ($(OS),Windows_NT)
	@echo "make sanitizer is intended for Linux (GCC/Clang), not Windows."; exit 1
endif
	@if [ "$$(uname -s 2>/dev/null)" = "Darwin" ]; then \\
	  echo "note: sanitizers are validated on Linux CI; macOS is best-effort (no LSan)"; \\
	fi
	cmake -S . -B $(BUILD_SANITIZER) $(CMAKE_GENERATOR_FLAG) \\
	  -DCMAKE_BUILD_TYPE=Debug \\
	  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \\
	  -D$(PROJECT_MACRO)_ENABLE_SANITIZERS=ON \\
	  $(CMAKE_FLAGS)
	cmake --build $(BUILD_SANITIZER) --parallel
	@if [ "$$(uname -s 2>/dev/null)" = "Linux" ]; then \\
	  export ASAN_OPTIONS=halt_on_error=1:abort_on_error=1:detect_leaks=1:detect_stack_use_after_return=1; \\
	else \\
	  export ASAN_OPTIONS=halt_on_error=1:abort_on_error=1:detect_leaks=0; \\
	fi; \\
	export UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1; \\
	ctest --test-dir $(BUILD_SANITIZER) --output-on-failure --parallel

fmt:
	@command -v clang-format >/dev/null 2>&1 || {{ echo "clang-format not found"; exit 1; }}
	@files=$$(find src tests benchmarks include -type f \\
	  \\( -name '*.cpp' -o -name '*.hpp' -o -name '*.h' -o -name '*.cc' -o -name '*.cxx' -o -name '*.cppm' -o -name '*.ixx' \\) \\
	  2>/dev/null); \\
	if [ -n "$$files" ]; then clang-format -i $$files; fi

doc:
	@command -v doxygen >/dev/null 2>&1 || {{ echo "doxygen not found"; exit 1; }}
	@ver=$$(tr -d '[:space:]' < VERSION | sed 's/^v//;s/#.*//'); \\
	sed "s/^PROJECT_NUMBER.*/PROJECT_NUMBER         = \\"$$ver\\"/" Doxyfile | doxygen -
{tags_target}
clean:
	rm -rf build docs/html docs/latex docs/xml compile_commands.json $(PROJECT_NAME)$(EXE_EXT){clean_extra}

link_compile_commands:
	@if [ -f "$(BUILD_DIR)/compile_commands.json" ]; then \\
	  ln -sfn "$(BUILD_DIR)/compile_commands.json" compile_commands.json; \\
	  echo "linked compile_commands.json -> $(BUILD_DIR)/compile_commands.json"; \\
	fi

copy_compile_commands:
	@if [ -f "$(BUILD_DIR)/compile_commands.json" ]; then \\
	  cp "$(BUILD_DIR)/compile_commands.json" compile_commands.json; \\
	  echo "copied compile_commands.json from $(BUILD_DIR)"; \\
	fi
"""


def _build_bat(ctx: _Context) -> str:
    """Windows cmd wrapper mirroring the GNU Makefile targets."""
    tags_help = ""
    tags_block = ""
    if ctx.with_ctags:
        tags_help = "echo   build.bat tags          - regenerate ctags index\n"
        tags_block = """
:tags
where ctags >nul 2>&1
if errorlevel 1 (
  echo ctags not found ^(install universal-ctags^)
  exit /b 1
)
ctags -R
echo wrote tags
goto :eof
"""
    tags_dispatch = ""
    if ctx.with_ctags:
        tags_dispatch = 'if /I "%CMD%"=="tags" goto tags\n'

    return f"""\
@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Idiomatic Windows wrapper around the CMake build (mirrors Makefile targets).
rem Usage: build.bat [target]
rem   build.bat            -> debug
rem   build.bat release
rem   build.bat test
rem   build.bat help

set "PROJECT_NAME={ctx.name}"
set "PROJECT_MACRO={ctx.macro}"
set "BUILD_DEBUG=build\\debug"
set "BUILD_RELEASE=build\\release"
set "BUILD_SANITIZER=build\\sanitizer"
set "EXE_NAME=%PROJECT_NAME%.exe"

set "GENERATOR_FLAG="
if defined GENERATOR (
  set "GENERATOR_FLAG=-G %GENERATOR%"
) else (
  where ninja >nul 2>&1
  if not errorlevel 1 set "GENERATOR_FLAG=-G Ninja"
)

set "CMD=%~1"
if "%CMD%"=="" set "CMD=debug"

if /I "%CMD%"=="help" goto help
if /I "%CMD%"=="/?" goto help
if /I "%CMD%"=="-h" goto help
if /I "%CMD%"=="all" goto debug
if /I "%CMD%"=="debug" goto debug
if /I "%CMD%"=="release" goto release
if /I "%CMD%"=="test" goto test
if /I "%CMD%"=="bench" goto bench
if /I "%CMD%"=="sanitizer" goto sanitizer
if /I "%CMD%"=="fmt" goto fmt
if /I "%CMD%"=="doc" goto doc
if /I "%CMD%"=="clean" goto clean
if /I "%CMD%"=="reconfigure-debug" goto reconfigure_debug
if /I "%CMD%"=="reconfigure-release" goto reconfigure_release
if /I "%CMD%"=="configure-debug" goto configure_debug
if /I "%CMD%"=="configure-release" goto configure_release
{tags_dispatch}echo Unknown target: %CMD%
echo Run "build.bat help" for usage.
exit /b 1

:help
echo Targets:
echo   build.bat / build.bat debug  - configure ^& build Debug
echo   build.bat release            - configure ^& build Release
echo   build.bat test               - run unit tests ^(Debug^)
echo   build.bat bench              - run microbenchmarks ^(Release^)
echo   build.bat sanitizer          - not supported on Windows ^(use Linux^)
echo   build.bat fmt                - run clang-format on sources
echo   build.bat doc                - generate Doxygen HTML under docs\\html
{tags_help}echo   build.bat reconfigure-debug  - wipe build\\debug and reconfigure
echo   build.bat clean              - remove local build trees
echo.
echo Environment:
echo   set GENERATOR=Ninja          - force a CMake generator
echo   set CMAKE_FLAGS=...          - extra flags passed to cmake configure
goto :eof

:reconfigure_debug
if exist "%BUILD_DEBUG%" rmdir /s /q "%BUILD_DEBUG%"
call :configure_debug
goto :eof

:reconfigure_release
if exist "%BUILD_RELEASE%" rmdir /s /q "%BUILD_RELEASE%"
call :configure_release
goto :eof

:configure_debug
cmake -S . -B "%BUILD_DEBUG%" %GENERATOR_FLAG% -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON %CMAKE_FLAGS%
if errorlevel 1 exit /b 1
if exist "%BUILD_DEBUG%\\compile_commands.json" (
  copy /Y "%BUILD_DEBUG%\\compile_commands.json" compile_commands.json >nul
  echo copied compile_commands.json from %BUILD_DEBUG%
)
goto :eof

:configure_release
cmake -S . -B "%BUILD_RELEASE%" %GENERATOR_FLAG% -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON %CMAKE_FLAGS%
if errorlevel 1 exit /b 1
goto :eof

:debug
call :configure_debug
if errorlevel 1 exit /b 1
cmake --build "%BUILD_DEBUG%" --parallel
if errorlevel 1 exit /b 1
if exist "%BUILD_DEBUG%\\bin\\%EXE_NAME%" copy /Y "%BUILD_DEBUG%\\bin\\%EXE_NAME%" "%EXE_NAME%" >nul
goto :eof

:release
call :configure_release
if errorlevel 1 exit /b 1
cmake --build "%BUILD_RELEASE%" --parallel
if errorlevel 1 exit /b 1
if exist "%BUILD_RELEASE%\\bin\\%EXE_NAME%" copy /Y "%BUILD_RELEASE%\\bin\\%EXE_NAME%" "%EXE_NAME%" >nul
goto :eof

:test
call :debug
if errorlevel 1 exit /b 1
ctest --test-dir "%BUILD_DEBUG%" --output-on-failure --parallel
goto :eof

:bench
call :release
if errorlevel 1 exit /b 1
set "FOUND="
for /r "%BUILD_RELEASE%" %%F in (*bench.exe *_bench.exe) do (
  if not defined FOUND set "FOUND=%%F"
)
if not defined FOUND (
  echo No benchmark executables found. Add benchmarks\\^<component^>\\ then rebuild.
  exit /b 0
)
echo Running %FOUND%
"%FOUND%" --benchmark_min_time=0.01s
goto :eof

:sanitizer
echo build.bat sanitizer is intended for Linux ^(GCC/Clang^), not Windows.
exit /b 1

:fmt
where clang-format >nul 2>&1
if errorlevel 1 (
  echo clang-format not found
  exit /b 1
)
for %%D in (src tests benchmarks include) do (
  if exist "%%D" (
    for /r "%%D" %%F in (*.cpp *.hpp *.h *.cc *.cxx *.cppm *.ixx) do (
      clang-format -i "%%F"
    )
  )
)
goto :eof

:doc
where doxygen >nul 2>&1
if errorlevel 1 (
  echo doxygen not found
  exit /b 1
)
set "VER="
for /f "usebackq tokens=* delims=" %%V in ("VERSION") do (
  if not defined VER set "VER=%%V"
)
set "VER=%VER: =%"
if /I "%VER:~0,1%"=="v" set "VER=%VER:~1%"
powershell -NoProfile -Command "(Get-Content -Raw Doxyfile) -replace 'PROJECT_NUMBER\\s*=.*', ('PROJECT_NUMBER         = \"' + $env:VER + '\"') | & doxygen -"
goto :eof

:clean
if exist build rmdir /s /q build
if exist docs\\html rmdir /s /q docs\\html
if exist docs\\latex rmdir /s /q docs\\latex
if exist docs\\xml rmdir /s /q docs\\xml
if exist compile_commands.json del /f /q compile_commands.json
if exist "%EXE_NAME%" del /f /q "%EXE_NAME%"
if exist tags del /f /q tags
if exist TAGS del /f /q TAGS
goto :eof
{tags_block}"""


def _readme(ctx: _Context) -> str:
    modules_note = (
        "This project uses **C++20 modules** (`--with-modules`). "
        "Module interface units live under `src/<component>/` as `.cppm` files."
        if ctx.with_modules
        else "This project uses **classic headers**. Public headers live under "
        f"`include/{ctx.namespace}/` (directory tree == namespace)."
    )
    vim_note = (
        "\nA project-local `.vimrc` was generated (default; disable with "
        "`cppboot --no-vim`). Enable `:set exrc` (and ideally `secure`) in your "
        "global Vim config to load it.\n"
        if ctx.with_vim
        else ""
    )
    vscode_note = (
        "\n**VS Code** config is included (default; disable with "
        "`cppboot --no-vscode`): open the folder, install recommended extensions, "
        "select the **debug** CMake preset, then Build / F5 / Test. See "
        "[Open in VS Code](#open-in-vs-code).\n"
        if ctx.with_vscode
        else ""
    )
    ctags_note = (
        "\n**ctags:** `.ctags` is configured for Universal Ctags (default; "
        "`cppboot --no-ctags` to skip). Run `make tags` to build the `tags` index.\n"
        if ctx.with_ctags
        else ""
    )
    sample_note = (
        "\nDefault library surface is the **version** component driven by the "
        "root **`VERSION`** file (single source of truth) with CLI "
        "`--version` / `-V`, unit tests, and a small benchmark. Bump "
        "`VERSION` only — CMake regenerates the version API. Add real "
        "features as new components under `src/<component>/`.\n"
    )
    gha_section = ""
    if ctx.with_github_actions:
        gha_section = """

## Continuous integration

GitHub Actions workflows (default; disable with `cppboot --no-github-actions`):

| Workflow | File | Purpose |
|----------|------|---------|
| **CI** | `.github/workflows/ci.yml` | Ubuntu/macOS/Windows × Debug+Release, tests, benches, artifacts |
| **Sanitizers** | `.github/workflows/sanitizers.yml` | Linux ASan+UBSan build + `ctest` (failures fail the job) |
| **Release** | `.github/workflows/release.yml` | Tag `v*` or manual dispatch → notes + zip assets |

**CI** (each OS):

1. Configure and build **Debug** (Ninja)
2. Run unit tests (CTest) on Debug
3. Configure and build **Release**
4. Run unit tests on Release
5. Run Google Benchmark binaries under `build/release` (short min time)
6. Package and upload zip artifacts via `actions/upload-artifact` for **Debug**
   and **Release** on each OS

Artifact archive name shape:

```text
<app>-<os>-<cpu-arch>-<debug|release>-<version>.zip
```

Examples: `myproj-linux-x86_64-debug-0.1.0.zip`,
`myproj-macos-arm64-release-0.1.0.zip`,
`myproj-windows-x86_64-release-0.1.0.zip`.

Each zip contains the contents of `build/<config>/bin/` (app, tests, benches).
Version comes from the root **`VERSION`** file (also what `./<app> --version`
prints after configure).

**Sanitizers** (Ubuntu + Clang): configure with
`-{ctx.macro}_ENABLE_SANITIZERS=ON`, build, run tests with
`ASAN_OPTIONS` / `UBSAN_OPTIONS` set so findings abort (non-zero exit).

Locally on Linux: `make sanitizer` (same flags and env).

### Creating a release

The root **`VERSION`** file is the only place to bump the package version.

1. Edit **`VERSION`** (e.g. `1.0.0`), commit, and merge to the default branch.
2. Either:
   - **Tag:** `git tag -a v1.0.0 -m v1.0.0 && git push origin v1.0.0`
     (tag **must** match `VERSION`), or
   - **Actions → Release → Run workflow** — leave the version input empty to
     use `VERSION`, or pass the same semver (mismatch fails the job).
3. The Release workflow builds **Release** on Linux/macOS/Windows, verifies the
   binary `--version` matches `VERSION`/tag, generates notes, and uploads zips
   named `<app>-<os>-<arch>-release-<version>.zip`.

Action pins use current stable majors (`actions/checkout@v7`,
`actions/upload-artifact@v7`, `actions/download-artifact@v7`,
`lukka/get-cmake@latest`, `softprops/action-gh-release@v3`).
"""
    codespaces_section = ""
    if ctx.with_codespaces:
        codespaces_section = f"""

## GitHub Codespaces (VS Code in the browser)

This repo includes a **Dev Container** (`.devcontainer/`) for
[GitHub Codespaces](https://github.com/features/codespaces) and local
VS Code Dev Containers.

### Open in Codespaces

1. Push the repo to GitHub (or use an existing remote).
2. On GitHub: **Code → Codespaces → Create codespace on &lt;branch&gt;**.
3. Wait for the container create hooks:
   - `onCreateCommand`: install Ninja, clang-format, Doxygen, ctags
   - `postCreateCommand`: `cmake --preset debug` + Debug build (FetchContent)
4. In the browser VS Code: **F5** (*Debug {ctx.name}*), Testing view, or terminal
   `make test` / `./build/debug/bin/{ctx.name} --version`.

### Local Dev Container

In desktop VS Code with the Dev Containers extension:
**Dev Containers: Reopen in Container**.

Disable with `cppboot --no-codespaces` when regenerating a project.
"""
    vscode_section = ""
    if ctx.with_vscode:
        vscode_section = f"""

## Open in VS Code

1. Open this folder in VS Code (`code .`).
2. Install the **recommended extensions** when prompted
   (clangd, CMake Tools, CodeLLDB, **C++ TestMate**).
3. Install **Ninja** (`brew install ninja` / `apt install ninja-build`). VS Code
   presets and `make` both prefer Ninja so they share the same `build/debug` tree.
4. **Build once:** `Ctrl/Cmd+Shift+B` (*Build Debug*). This configures CMake,
   builds, and places `compile_commands.json` at the repo root for **clangd**.
5. If red squiggles remain: Command Palette → **clangd: Restart language server**
   (or reload the window). IntelliSense needs that compilation database.
6. **Debug the app:** F5 → *Debug {ctx.name}* (rebuilds Debug first).
7. **Unit tests (per-test ▶):** open the **Testing** view (beaker icon).
   After a Debug build, **C++ TestMate** discovers GoogleTest binaries under
   `build/debug/bin/` and offers run/debug for suites and individual `TEST`s.
8. **Bulk tests:** Task *Test*, CMake Tools CTest, or `make test`.

Presets live in `CMakePresets.json` (`debug` → `build/debug`, `release` → `build/release`).

**Generator mismatch:** If you see *generator : Ninja Does not match ... Unix Makefiles*,
the build tree was configured with a different generator. Fix with:

```bash
make reconfigure-debug
# or: rm -rf build/debug && cmake --preset debug
```

Then F5 again. Prefer always using Ninja (install it; both `make` and VS Code will use it).

**IntelliSense note:** Disable Microsoft C/C++ IntelliSense (already set) and use
**clangd** only. Do not enable both. `std::string` / CLI11 / project headers resolve
from `compile_commands.json` after the first successful configure+build.

**Tests note:** TestMate needs built test executables — Build Debug first.
Individual test debug uses CodeLLDB (`lldb`) on macOS/Linux; on Windows you may
set `testMate.cpp.debug.configTemplate.type` to `cppvsdbg`.

Windows: use the *Debug {ctx.name} (Windows)* launch config (MSVC debugger).
"""
    return f"""\
# {ctx.name}

Developer guide for this **cppboot** environment. This README orients you to
the build, test, and source-onboarding workflows — not product requirements.
{sample_note}

## Prerequisites

- CMake **3.20+** (3.28+ if this project was generated with C++20 modules)
- A **C++20** compiler (GCC, Clang, or MSVC recent enough for C++20)
- GNU Make (or another make that understands this Makefile)
- **Ninja** is required when this project uses C++20 modules (`--with-modules`)
- Optional tools: `clang-format`, `doxygen`, an LSP client with clangd
- Network access on first configure (CMake **FetchContent** downloads pinned deps)
{gha_section}{codespaces_section}{vscode_section}
## Preferred third-party libraries

These are **imported by default** via FetchContent (see `cmake/Dependencies.cmake`)
and linked into the project library. Prefer them for the jobs below instead of
adding alternate stacks without a strong reason.

| Purpose | Library | CMake option (default **ON**) | CMake target |
|---------|---------|-------------------------------|--------------|
| CLI arguments | [CLI11](https://github.com/CLIUtils/CLI11) | `-D{ctx.macro}_WITH_CLI11=OFF` | `CLI11::CLI11` |
| JSON | [nlohmann/json](https://github.com/nlohmann/json) | `-D{ctx.macro}_WITH_JSON=OFF` | `nlohmann_json::nlohmann_json` |
| Console logging | [spdlog](https://github.com/gabime/spdlog) | `-D{ctx.macro}_WITH_SPDLOG=OFF` | `spdlog::spdlog` |

Example headers:

```cpp
#include <CLI/CLI.hpp>
#include <nlohmann/json.hpp>
#include <spdlog/spdlog.h>
```

Disable any of them at configure time if you do not need them:

```bash
cmake -S . -B build/debug \\
  -D{ctx.macro}_WITH_CLI11=OFF \\
  -D{ctx.macro}_WITH_JSON=OFF \\
  -D{ctx.macro}_WITH_SPDLOG=OFF
```

## Layout

```text
{ctx.name}/
  VERSION              # single source of truth for package version
  src/main.cpp         # THE program entrypoint (always here)
  src/<component>/     # library implementation; each dir has CMakeLists.txt
  include/             # public headers (classic layout only; version.hpp is generated)
  tests/<component>/   # GoogleTest / GoogleMock
  benchmarks/<component>/
  cmake/               # shared CMake modules + version.*.in templates
  CMakeLists.txt
  Makefile             # macOS / Linux day-to-day targets
  build.bat            # Windows day-to-day targets (mirrors Makefile)
```

{modules_note}

**Modules toolchain note:** CMake C++20 modules need **Ninja** (the Makefile
selects it automatically when `ninja` is on `PATH`), **CMake 3.28+**, and a
compiler with module dependency scanning (**Clang 16+**, **GCC 14+**, or
**MSVC 17.4+**). Stock **AppleClang** often cannot scan modules for CMake yet;
use a recent LLVM Clang/GCC/MSVC when building a modules project.
{vim_note}{vscode_note}{ctags_note}
## Versioning

Package version lives in the root **`VERSION`** file (one line, e.g. `0.1.0`).

| Consumer | How it gets the version |
|----------|-------------------------|
| CMake `project(... VERSION ...)` | Reads `VERSION` at configure time |
| `{ctx.namespace}::Version()` / CLI `--version` | Generated from `cmake/version.*.in` |
| GitHub Release workflow | Requires tag / dispatch input to match `VERSION` |
| Doxygen `PROJECT_NUMBER` | Injected from `VERSION` by `make doc` / `build.bat doc` |

**To ship a new version:** edit `VERSION` only, commit, then tag `vX.Y.Z` (or
run the Release workflow). Do not hand-edit generated version sources under the
build tree.

## Build

Out-of-source builds only. Artifacts land under `build/`.

| Command (Unix) | Command (Windows) | Meaning |
|----------------|-------------------|---------|
| `make` / `make debug` | `build.bat` / `build.bat debug` | Configure and build **Debug** |
| `make release` | `build.bat release` | Configure and build **Release** |
| `make test` | `build.bat test` | Unit tests (Debug) |
| `make bench` | `build.bat bench` | Microbenchmarks (Release) |
| `make fmt` | `build.bat fmt` | clang-format |
| `make doc` | `build.bat doc` | Doxygen HTML |
| `make clean` | `build.bat clean` | Remove build trees |

Debug tree: `build/debug`  
Release tree: `build/release`

The Debug configure step links/copies `compile_commands.json` at the repo root for LSP.

### Windows

Prefer **`build.bat`** (same targets as the Makefile). Open a **Developer
Command Prompt for VS** or ensure `cmake` (and ideally `ninja`) are on `PATH`:

```bat
build.bat
build.bat test
build.bat release
build.bat help
```

WSL / MSYS2 can keep using `make` if you prefer.

## Run the app

The program entrypoint is always **`src/main.cpp`**.
`make` links **`./{ctx.name}`** at the project root to `build/debug/bin/{ctx.name}`.

After `make debug`:

```bash
./{ctx.name}
./{ctx.name} --version
./{ctx.name} -V
```

## Tests

```bash
make test
```

Runs CTest against the Debug build (includes version API tests).

## Benchmarks

```bash
make bench
```

Builds **Release** and runs Google Benchmark binaries (short min time for smoke runs).

## Format

```bash
make fmt
```

Runs **clang-format** with the checked-in `.clang-format` (**Microsoft** style).

**Formatting** uses Microsoft clang-format; **code logic/naming/design** follow
the **Google C++ Style Guide** (see AGENTS.md).

## Documentation

```bash
make doc
```

Runs **Doxygen** using the checked-in `Doxyfile`. HTML output: `docs/html/`.

## Clean

```bash
make clean
```

Removes `build/`, generated docs, and the root `compile_commands.json` link.

## LSP / clangd

- CMake exports a compilation database (`CMAKE_EXPORT_COMPILE_COMMANDS=ON`).
- After `make debug`, `compile_commands.json` is available at the **project root**.
- Open the project root in your editor so clangd picks it up.
- See `.clangd` for the minimal clangd config.

## Compiler warnings

This project compiles with **warnings as errors** (`-Wall -Wextra -Wpedantic -Werror`
on GCC/Clang; `/W4 /WX` on MSVC). Fix warnings instead of silencing them.

## Onboarding new source files

Sources are organized by **logical component**. Each component directory has its
own `CMakeLists.txt` and **lists files explicitly** (no `file(GLOB)`).

### Example: add a `parser` component

1. **Public header** (classic layout):

   `include/{ctx.namespace}/parser.hpp`

2. **Implementation**:

   ```text
   src/parser/
     CMakeLists.txt
     parser.cpp
   ```

3. **`src/parser/CMakeLists.txt`**:

   ```cmake
   target_sources(${{PROJECT_NAME}}_lib
     PRIVATE
       parser.cpp
   )
   ```

4. **Register the component** in `src/CMakeLists.txt`:

   ```cmake
   add_subdirectory(version)
   add_subdirectory(parser)
   ```

5. **Tests** (same pattern):

   ```text
   tests/parser/
     CMakeLists.txt
     parser_test.cpp
   ```

   And `add_subdirectory(parser)` in `tests/CMakeLists.txt`.

### Rules of thumb

- The only program entrypoint is **`src/main.cpp`**. Keep it thin; put logic in library components.
- Library code goes under `src/<component>/`, never into `src/main.cpp` beyond startup wiring.
- List every `.cpp` / `.cppm` in the component `CMakeLists.txt`.
- Mirror component names under `tests/` and `benchmarks/`.
- Do not rely on directory globs for sources — explicit lists keep reviews and CI unambiguous.

## Agent / contributor conventions

See **[AGENTS.md](AGENTS.md)** for coding standards, documentation rules, and
how automated agents (and humans) should work in this repository.

## License

See `LICENSE` ({ctx.license_id}).
"""


def _agents_md(ctx: _Context) -> str:
    layout_api = (
        f"Public module interfaces live under `src/<component>/` as `.cppm` "
        f"(module name `{ctx.namespace}.<component>`)."
        if ctx.with_modules
        else f"Public headers live under `include/{ctx.namespace}/` "
        f"(directory tree matches the C++ namespace)."
    )
    return f"""\
# AGENTS.md — working in `{ctx.name}`

This file orients **human contributors and coding agents** to how this
cppboot-generated C++ project is structured and how code should be written.
For day-to-day build commands, see [README.md](README.md).

## Project model

- **Entrypoint:** the program starts in **`src/main.cpp`** — always. No alternate
  app tree; do not invent a second `main`.
- **Library first:** reusable code belongs in the library target under
  `src/<component>/`, not in `main.cpp`.
- **Main is thin:** `src/main.cpp` only wires startup and calls into the library.
- **Components:** group related code under `src/<component>/`, `tests/<component>/`,
  and `benchmarks/<component>/`.
- **Explicit sources:** every translation unit is listed in that directory's
  `CMakeLists.txt`. Never use `file(GLOB)` for project sources.
- **Onboard a component:** add the directory, list files in its `CMakeLists.txt`,
  then `add_subdirectory(...)` from the parent.

{layout_api}

## Preferred libraries

Use these **default** third-party libraries (FetchContent, ON unless turned off
in CMake) instead of inventing a parallel stack:

| Need | Prefer | Notes |
|------|--------|--------|
| Parse CLI args | **CLI11** (`CLI11::CLI11`) | `#include <CLI/CLI.hpp>` |
| Parse / emit JSON | **nlohmann/json** (`nlohmann_json::nlohmann_json`) | `#include <nlohmann/json.hpp>` |
| Console (and file) logging | **spdlog** (`spdlog::spdlog`) | `#include <spdlog/spdlog.h>` |

They are linked `PUBLIC` on the project library when enabled. Options:

- `{ctx.macro}_WITH_CLI11` (default ON)
- `{ctx.macro}_WITH_JSON` (default ON)
- `{ctx.macro}_WITH_SPDLOG` (default ON)

Do not add competing CLI/JSON/logging libraries unless there is a clear,
documented reason. See `cmake/Dependencies.cmake` for pinned tags.

## Tooling workflow

Prefer the Makefile (Unix) or `build.bat` (Windows) wrappers:

| Goal | Unix | Windows |
|------|------|---------|
| Debug build | `make` / `make debug` | `build.bat` / `build.bat debug` |
| Release build | `make release` | `build.bat release` |
| Unit tests | `make test` | `build.bat test` |
| Benchmarks | `make bench` | `build.bat bench` |
| ASan+UBSan (Linux) | `make sanitizer` | n/a (use Linux/CI) |
| Format | `make fmt` | `build.bat fmt` |
| API docs | `make doc` | `build.bat doc` |
| ctags index | `make tags` (if enabled) | `build.bat tags` |
| Clean | `make clean` | `build.bat clean` |

- Builds are **out-of-source** under `build/`.
- After a Debug configure, `compile_commands.json` at the repo root supports clangd/LSP.
- **Warnings are errors.** Fix warnings; do not silence them without strong reason.
- If present, `.ctags` + `make tags` produce a repo-root `tags` file for editors
  (Universal Ctags recommended).
- If present, `.github/workflows/ci.yml` is the multi-OS CI contract (Debug +
  Release, tests, benchmarks on Linux/macOS/Windows). Keep it green.
- If present, `.github/workflows/sanitizers.yml` runs ASan+UBSan on Linux;
  treat sanitizer failures as bugs. Locally: `make sanitizer`.
- **Version:** edit the root **`VERSION`** file only. CMake generates
  `{ctx.namespace}::Version()` / CLI `--version` from `cmake/version.*.in`.
  Ship releases with annotated tags `vX.Y.Z` matching `VERSION` (or
  workflow_dispatch); the release job fails on mismatch.
- If present, `.devcontainer/` enables **GitHub Codespaces** / Dev Containers
  (browser or local VS Code in a C++ toolchain container).
- Default library API includes **`Version()`** (from `VERSION`) and the app
  exposes **`--version` / `-V`** via CLI11.
- Mechanical formatting is enforced by **clang-format** via the checked-in
  `.clang-format` (**Microsoft** style). Run `make fmt`.
- **Logic, naming, API design, and code organization** follow the
  **Google C++ Style Guide** (see Coding standards below). These are two
  separate concerns: Microsoft for whitespace/braces layout; Google for how
  the C++ is written.

## Coding standards

### Formatting vs. language style (two different layers)

| Layer | Standard | How it is applied |
|-------|----------|-------------------|
| **Formatting** | Microsoft (clang-format) | `.clang-format`, `make fmt` — indentation, braces, wrapping, spacing |
| **Language / design style** | [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html) | Naming, headers, ownership, construct choices, readability norms |

Do not treat clang-format as a substitute for the Google guide, or vice versa.

### Style (Google C++ Style Guide)

Follow the [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html)
for source code logic and structure:

- Clear, consistent naming (`PascalCase` types, Google-style functions/members;
  match existing code in this tree).
- Prefer headers that express a stable API; keep implementation details out of
  public headers when practical.
- Avoid non-portable extensions and clever syntax that hurts readability.
- Keep functions small and focused; prefer early returns over deep nesting.

### Design (SOLID, readability, maintainability)

Write code that a future human can change safely:

- **Single responsibility:** one class/function does one coherent job.
- **Open/closed:** extend behavior via new types or composition, not by growing
  god-objects or switch-on-type forests.
- **Liskov substitution:** derived types honor base contracts; do not surprise
  callers.
- **Interface segregation:** prefer small, purpose-built interfaces over wide ones.
- **Dependency inversion:** depend on abstractions at boundaries; inject
  collaborators rather than hard-wiring concrete types deep in call chains.

Additional habits:

- Optimize for **clarity over cleverness**. The default reader is a teammate,
  not a compiler.
- Prefer **composition** and explicit ownership (`std::unique_ptr`, values,
  spans) over hidden global state.
- Keep APIs **minimal and intentional**. Every public symbol is a long-term
  commitment.
- Fail loudly and locally: validate preconditions at boundaries; use types and
  names that make invalid states hard to represent.
- Tests are part of the product: add or update unit tests (and mocks where they
  clarify collaboration) when behavior changes.

### Documentation and comments

**Public symbols** (public headers / exported module interfaces, public classes,
functions, enums, and type aliases intended for use outside the defining
translation unit):

- Provide **professional Doxygen** documentation: brief description, parameters,
  return values, pre/postconditions, and ownership or lifetime notes when
  relevant.
- Use `/** ... */` with `@brief`, `@param`, `@return`, and related tags so
  `make doc` stays useful.
- Document *what* and *why* at the API boundary, not line-by-line mechanics.

**Internal code** (`.cpp` bodies, private helpers, anonymous namespaces, test
helpers):

- Favor **self-documenting** names and structure over commentary.
- Use comments **sparsely**.
- When you comment, write **long-lived** notes: invariants, non-obvious
  algorithms, protocol constraints, performance tradeoffs, or security
  boundaries that will still matter months later.
- Do **not** write tactical comments: no "increment i", no narrating the next
  line, no TODOs that only make sense during an unfinished edit, no
  change-log commentary that belongs in version control.

### Tests and benchmarks under warnings-as-errors

- Project flags apply to **your** TUs (lib, app, tests, benchmarks), not only
  production code.
- For `[[nodiscard]]` APIs with GoogleTest throws, bind the result:

  ```cpp
  EXPECT_THROW(
      {{
        auto value = ApiThatIsNodiscard();
        static_cast<void>(value);
      }},
      std::runtime_error);
  ```

- For Google Benchmark, pass a **mutable lvalue** to `DoNotOptimize` (const-ref
  overloads are deprecated and fail `-Werror`):

  ```cpp
  auto value = Compute();
  benchmark::DoNotOptimize(value);
  ```

### What to avoid

- Drive-by refactors unrelated to the task.
- Silent warning suppressions and `#pragma` noise without justification.
- New dependencies without a clear need (third-party code is pinned via
  FetchContent in `cmake/Dependencies.cmake`). Prefer the default CLI11 /
  nlohmann/json / spdlog stack for CLI, JSON, and logging.
- Alternate CLI/JSON/logging libraries when the preferred ones are enabled.
- Globs for source lists; dumping library logic into `src/main.cpp` or a single
  catch-all source file.

## Checklist before finishing a change

1. Sources listed explicitly in the right component `CMakeLists.txt`.
2. `make` (or `make release`) succeeds with warnings-as-errors.
3. `make test` passes; add coverage for new behavior.
4. Public API has Doxygen; internal comments (if any) are durable.
5. `make fmt` leaves formatting clean.
6. Logic/naming match Google C++ guidance; formatting matches `.clang-format`.

## Scope of this file

`AGENTS.md` is about **how to work in this repository**. Product requirements
and design docs for the application itself belong elsewhere.
"""


def _devcontainer_json(ctx: _Context) -> str:
    """GitHub Codespaces / VS Code Dev Containers configuration."""
    return f"""\
{{
  "name": "{ctx.name}",
  "image": "mcr.microsoft.com/devcontainers/cpp:1-ubuntu-24.04",
  "features": {{
    "ghcr.io/devcontainers/features/github-cli:1": {{}}
  }},
  "containerEnv": {{
    "CMAKE_GENERATOR": "Ninja",
    "CMAKE_BUILD_PARALLEL_LEVEL": "4"
  }},
  "customizations": {{
    "vscode": {{
      "extensions": [
        "llvm-vs-code-extensions.vscode-clangd",
        "ms-vscode.cmake-tools",
        "vadimcn.vscode-lldb",
        "matepek.vscode-catch2-test-adapter",
        "twxs.cmake"
      ],
      "settings": {{
        "C_Cpp.intelliSenseEngine": "disabled",
        "cmake.useCMakePresets": "always",
        "cmake.copyCompileCommands": "${{workspaceFolder}}/compile_commands.json",
        "cmake.buildDirectory": "${{workspaceFolder}}/build/debug",
        "testMate.cpp.test.executables": [
          "${{workspaceFolder}}/build/debug/bin/*test*",
          "${{workspaceFolder}}/build/debug/bin/*_test"
        ],
        "testMate.cpp.debug.configTemplate": {{
          "type": "lldb",
          "request": "launch",
          "program": "${{exec}}",
          "args": "${{argsArray}}",
          "cwd": "${{workspaceFolder}}"
        }}
      }}
    }}
  }},
  "onCreateCommand": "bash .devcontainer/setup.sh deps",
  "postCreateCommand": "bash .devcontainer/setup.sh build",
  "postStartCommand": "cmake -E create_symlink build/debug/compile_commands.json compile_commands.json || true",
  "remoteUser": "vscode",
  "hostRequirements": {{
    "cpus": 2,
    "memory": "4gb",
    "storage": "32gb"
  }}
}}
"""


def _devcontainer_setup_sh(ctx: _Context) -> str:
    """Setup script for Codespaces create/build steps."""
    _ = ctx
    return """\
#!/usr/bin/env bash
# GitHub Codespaces / Dev Container setup for cppboot projects.
set -euo pipefail

mode="${1:-all}"

install_deps() {
  echo "[devcontainer] installing Ninja, clang-format, Doxygen, Universal Ctags..."
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\
    ninja-build \\
    clang-format \\
    doxygen \\
    universal-ctags \\
    gdb
}

configure_and_build() {
  echo "[devcontainer] configuring Debug preset (FetchContent may take a few minutes)..."
  cmake --preset debug
  echo "[devcontainer] building Debug..."
  cmake --build --preset debug --parallel
  if [ -f build/debug/compile_commands.json ]; then
    ln -sfn build/debug/compile_commands.json compile_commands.json
    echo "[devcontainer] linked compile_commands.json for clangd"
  fi
  echo "[devcontainer] build complete. Try: ./build/debug/bin/* --version  or  make test"
}

case "${mode}" in
  deps) install_deps ;;
  build) configure_and_build ;;
  all)
    install_deps
    configure_and_build
    ;;
  *)
    echo "usage: $0 [deps|build|all]" >&2
    exit 2
    ;;
esac
"""


def _cmake_presets(ctx: _Context) -> str:
    """CMake presets shared by VS Code CMake Tools and CLI."""
    _ = ctx
    return """\
{
  "version": 6,
  "cmakeMinimumRequired": {
    "major": 3,
    "minor": 20,
    "patch": 0
  },
  "configurePresets": [
    {
      "name": "debug",
      "displayName": "Debug",
      "description": "Debug build under build/debug (matches make debug)",
      "generator": "Ninja",
      "binaryDir": "${sourceDir}/build/debug",
      "cacheVariables": {
        "CMAKE_BUILD_TYPE": "Debug",
        "CMAKE_EXPORT_COMPILE_COMMANDS": "ON"
      }
    },
    {
      "name": "release",
      "displayName": "Release",
      "description": "Release build under build/release (matches make release)",
      "generator": "Ninja",
      "binaryDir": "${sourceDir}/build/release",
      "cacheVariables": {
        "CMAKE_BUILD_TYPE": "Release",
        "CMAKE_EXPORT_COMPILE_COMMANDS": "ON"
      }
    }
  ],
  "buildPresets": [
    {
      "name": "debug",
      "configurePreset": "debug"
    },
    {
      "name": "release",
      "configurePreset": "release"
    }
  ],
  "testPresets": [
    {
      "name": "debug",
      "configurePreset": "debug",
      "output": {
        "outputOnFailure": true
      }
    },
    {
      "name": "release",
      "configurePreset": "release",
      "output": {
        "outputOnFailure": true
      }
    }
  ]
}
"""


def _vscode_extensions() -> str:
    return """\
{
  "recommendations": [
    "llvm-vs-code-extensions.vscode-clangd",
    "ms-vscode.cmake-tools",
    "vadimcn.vscode-lldb",
    "matepek.vscode-catch2-test-adapter",
    "twxs.cmake"
  ],
  "unwantedRecommendations": [
    "ms-vscode.cpptools-extension-pack"
  ]
}
"""


def _vscode_settings(ctx: _Context) -> str:
    _ = ctx
    return """\
{
  "editor.formatOnSave": false,
  "files.insertFinalNewline": true,
  "files.trimTrailingWhitespace": true,
  "C_Cpp.intelliSenseEngine": "disabled",
  "clangd.path": "clangd",
  "clangd.arguments": [
    "--compile-commands-dir=${workspaceFolder}",
    "--header-insertion=never",
    "--background-index",
    "--query-driver=/**/clang*,/**/g++,/**/gcc*,/**/c++,/**/cc,/**/clang-cl*"
  ],
  "clangd.onConfigChanged": "restart",
  "cmake.configureOnOpen": true,
  "cmake.useCMakePresets": "always",
  "cmake.options.statusBarVisibility": "visible",
  "cmake.copyCompileCommands": "${workspaceFolder}/compile_commands.json",
  "cmake.generator": "Ninja",
  "cmake.buildDirectory": "${workspaceFolder}/build/debug",
  "cmake.ctestArgs": [
    "--output-on-failure",
    "--parallel"
  ],
  "testMate.cpp.test.executables": [
    "${workspaceFolder}/build/debug/bin/*test*",
    "${workspaceFolder}/build/debug/bin/*_test",
    "${workspaceFolder}/build/debug/bin/*_test.exe",
    "${workspaceFolder}/build/debug/bin/*test*.exe"
  ],
  "testMate.cpp.test.advancedExecutables": [
    {
      "pattern": "${workspaceFolder}/build/debug/bin/*test*",
      "cwd": "${workspaceFolder}",
      "env": {
        "GTEST_COLOR": "1"
      }
    }
  ],
  "testMate.cpp.debug.configTemplate": {
    "type": "lldb",
    "request": "launch",
    "program": "${exec}",
    "args": "${argsArray}",
    "cwd": "${workspaceFolder}",
    "sourceFileMap": {
      "/__w/": "${workspaceFolder}/"
    }
  },
  "testMate.cpp.test.workingDirectory": "${workspaceFolder}",
  "testMate.cpp.log.logpanel": false,
  "files.associations": {
    "CMakeLists.txt": "cmake",
    "*.hpp": "cpp",
    "*.cpp": "cpp",
    "*.cppm": "cpp"
  }
}
"""


def _vscode_tasks(ctx: _Context) -> str:
    _ = ctx
    # After configure, place compile_commands.json at the repo root for clangd.
    # (CMake Tools copyCompileCommands only runs when CMake Tools configures.)
    return """\
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Configure Debug",
      "type": "shell",
      "command": "cmake",
      "args": ["--preset", "debug"],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "problemMatcher": []
    },
    {
      "label": "Reconfigure Debug (clean)",
      "type": "shell",
      "command": "cmake",
      "args": [
        "-E",
        "rm",
        "-rf",
        "build/debug"
      ],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "problemMatcher": [],
      "presentation": {
        "reveal": "always",
        "panel": "shared"
      }
    },
    {
      "label": "Configure Debug (after clean)",
      "dependsOrder": "sequence",
      "dependsOn": [
        "Reconfigure Debug (clean)",
        "Configure Debug"
      ],
      "problemMatcher": []
    },
    {
      "label": "Link compile_commands (Debug)",
      "type": "shell",
      "command": "cmake",
      "args": [
        "-E",
        "create_symlink",
        "build/debug/compile_commands.json",
        "compile_commands.json"
      ],
      "windows": {
        "command": "cmake",
        "args": [
          "-E",
          "copy_if_different",
          "build/debug/compile_commands.json",
          "compile_commands.json"
        ]
      },
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "dependsOn": "Configure Debug",
      "problemMatcher": []
    },
    {
      "label": "Build Debug",
      "type": "shell",
      "command": "cmake",
      "args": ["--build", "--preset", "debug", "--parallel"],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "group": {
        "kind": "build",
        "isDefault": true
      },
      "dependsOn": "Link compile_commands (Debug)",
      "problemMatcher": ["$gcc"]
    },
    {
      "label": "Build Debug (clean reconfigure)",
      "dependsOrder": "sequence",
      "dependsOn": [
        "Reconfigure Debug (clean)",
        "Link compile_commands (Debug)",
        "Build Debug core"
      ],
      "group": "build",
      "problemMatcher": []
    },
    {
      "label": "Build Debug core",
      "type": "shell",
      "command": "cmake",
      "args": ["--build", "--preset", "debug", "--parallel"],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "problemMatcher": ["$gcc"]
    },
    {
      "label": "Configure Release",
      "type": "shell",
      "command": "cmake",
      "args": ["--preset", "release"],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "problemMatcher": []
    },
    {
      "label": "Build Release",
      "type": "shell",
      "command": "cmake",
      "args": ["--build", "--preset", "release", "--parallel"],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "group": "build",
      "dependsOn": "Configure Release",
      "problemMatcher": ["$gcc"]
    },
    {
      "label": "Test",
      "type": "shell",
      "command": "ctest",
      "args": [
        "--test-dir",
        "build/debug",
        "--output-on-failure",
        "--parallel"
      ],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "group": {
        "kind": "test",
        "isDefault": true
      },
      "dependsOn": "Build Debug",
      "problemMatcher": []
    },
    {
      "label": "Bench",
      "type": "shell",
      "command": "bash",
      "args": [
        "-lc",
        "found=$(find build/release -type f \\\\( -name '*bench' -o -name '*_bench' -o -name '*bench.exe' -o -name '*_bench.exe' \\\\) 2>/dev/null | head -n 1); if [ -z \\"$found\\" ]; then echo 'No benchmark binaries found'; exit 0; fi; echo Running $found; \\"$found\\" --benchmark_min_time=0.01s"
      ],
      "options": {
        "cwd": "${workspaceFolder}"
      },
      "dependsOn": "Build Release",
      "problemMatcher": []
    }
  ]
}
"""


def _vscode_launch(ctx: _Context) -> str:
    program_unix = f"${{workspaceFolder}}/build/debug/bin/{ctx.name}"
    program_win = f"${{workspaceFolder}}/build/debug/bin/{ctx.name}.exe"
    return f"""\
{{
  "version": "0.2.0",
  "configurations": [
    {{
      "name": "Debug {ctx.name}",
      "type": "lldb",
      "request": "launch",
      "program": "{program_unix}",
      "args": [],
      "cwd": "${{workspaceFolder}}",
      "preLaunchTask": "Build Debug"
    }},
    {{
      "name": "Debug {ctx.name} (Windows)",
      "type": "cppvsdbg",
      "request": "launch",
      "program": "{program_win}",
      "args": [],
      "cwd": "${{workspaceFolder}}",
      "preLaunchTask": "Build Debug",
      "console": "integratedTerminal"
    }}
  ]
}}
"""



def _github_actions_workflow(ctx: _Context) -> str:
    """Cross-platform CI: Linux/macOS/Windows × Debug+Release, test, bench."""
    return f"""\
# Generated by cppboot (default; --no-github-actions to skip)
# Matrix CI: Ubuntu, macOS, Windows — Debug + Release builds, tests, benchmarks.
# Action pins: latest stable majors (checkout/upload-artifact v7; get-cmake latest CMake/Ninja).
name: CI

on:
  push:
  pull_request:

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  build:
    name: ${{{{ matrix.os }}}}
    runs-on: ${{{{ matrix.os }}}}
    strategy:
      fail-fast: false
      matrix:
        os:
          - ubuntu-latest
          - macos-latest
          - windows-latest
    env:
      APP_NAME: {ctx.name}

    defaults:
      run:
        shell: bash

    steps:
      - name: Checkout
        uses: actions/checkout@v7

      - name: Install latest CMake and Ninja
        uses: lukka/get-cmake@latest
        with:
          cmakeVersion: latest
          ninjaVersion: latest

      - name: Enable MSVC developer command prompt
        if: runner.os == 'Windows'
        uses: TheMrMilchmann/setup-msvc-dev@v4
        with:
          arch: x64

      - name: Configure Debug
        run: >
          cmake -S . -B build/debug -G Ninja
          -DCMAKE_BUILD_TYPE=Debug
          -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

      - name: Build Debug
        run: cmake --build build/debug --parallel

      - name: Test Debug
        run: ctest --test-dir build/debug --output-on-failure --parallel

      - name: Configure Release
        run: >
          cmake -S . -B build/release -G Ninja
          -DCMAKE_BUILD_TYPE=Release

      - name: Build Release
        run: cmake --build build/release --parallel

      - name: Test Release
        run: ctest --test-dir build/release --output-on-failure --parallel

      - name: Benchmark (Release)
        run: |
          set -euo pipefail
          # Collect Google Benchmark binaries (none is OK).
          bins="$(find build/release -type f \\( -name '*bench' -o -name '*_bench' -o -name '*bench.exe' -o -name '*_bench.exe' \\) 2>/dev/null | head -n 20 || true)"
          if [ -z "${{bins}}" ]; then
            echo "No benchmark binaries found; skipping."
            exit 0
          fi
          while IFS= read -r bin; do
            [ -z "${{bin}}" ] && continue
            # Skip non-executables if any slip through on Windows.
            if [ ! -x "${{bin}}" ] && [[ "${{bin}}" != *.exe ]]; then
              continue
            fi
            echo "Running ${{bin}}"
            "${{bin}}" --benchmark_min_time=0.01s
          done <<< "${{bins}}"

      # Archives: <app>-<os>-<arch>-<debug|release>-<version>.zip
      - name: Package Debug artifacts
        id: pkg_debug
        run: |
          set -euo pipefail
          python3 - <<'PY'
          import os, re, shutil, subprocess
          from pathlib import Path

          app = os.environ["APP_NAME"]
          os_name = {{"Linux": "linux", "macOS": "macos", "Windows": "windows"}}.get(
              os.environ.get("RUNNER_OS", ""), os.environ.get("RUNNER_OS", "unknown").lower()
          )
          arch = {{"X64": "x86_64", "ARM64": "arm64", "X86": "x86"}}.get(
              os.environ.get("RUNNER_ARCH", ""), os.environ.get("RUNNER_ARCH", "unknown").lower()
          )
          config = "debug"
          bin_dir = Path("build") / config / "bin"
          version = "0.1.0"
          for candidate in (bin_dir / app, bin_dir / f"{{app}}.exe"):
              if candidate.is_file():
                  try:
                      out = subprocess.check_output([str(candidate), "--version"], text=True, stderr=subprocess.STDOUT)
                      m = re.search(r"\\d+\\.\\d+\\.\\d+", out)
                      if m:
                          version = m.group(0)
                  except Exception:
                      pass
                  break
          stem = f"{{app}}-{{os_name}}-{{arch}}-{{config}}-{{version}}"
          staging = Path("dist") / stem
          if staging.exists():
              shutil.rmtree(staging)
          staging.mkdir(parents=True)
          if bin_dir.is_dir():
              for p in bin_dir.iterdir():
                  dest = staging / p.name
                  if p.is_file():
                      shutil.copy2(p, dest)
                  elif p.is_dir():
                      shutil.copytree(p, dest)
          archive = shutil.make_archive(str(Path("dist") / stem), "zip", root_dir="dist", base_dir=stem)
          print(f"Created {{archive}}")
          with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
              fh.write(f"artifact_name={{stem}}\\n")
              fh.write(f"artifact_path={{archive}}\\n")
          PY

      - name: Upload Debug artifact
        uses: actions/upload-artifact@v7
        with:
          name: ${{{{ steps.pkg_debug.outputs.artifact_name }}}}
          path: ${{{{ steps.pkg_debug.outputs.artifact_path }}}}
          if-no-files-found: error
          retention-days: 14

      - name: Package Release artifacts
        id: pkg_release
        run: |
          set -euo pipefail
          python3 - <<'PY'
          import os, re, shutil, subprocess
          from pathlib import Path

          app = os.environ["APP_NAME"]
          os_name = {{"Linux": "linux", "macOS": "macos", "Windows": "windows"}}.get(
              os.environ.get("RUNNER_OS", ""), os.environ.get("RUNNER_OS", "unknown").lower()
          )
          arch = {{"X64": "x86_64", "ARM64": "arm64", "X86": "x86"}}.get(
              os.environ.get("RUNNER_ARCH", ""), os.environ.get("RUNNER_ARCH", "unknown").lower()
          )
          config = "release"
          bin_dir = Path("build") / config / "bin"
          version = "0.1.0"
          for candidate in (bin_dir / app, bin_dir / f"{{app}}.exe"):
              if candidate.is_file():
                  try:
                      out = subprocess.check_output([str(candidate), "--version"], text=True, stderr=subprocess.STDOUT)
                      m = re.search(r"\\d+\\.\\d+\\.\\d+", out)
                      if m:
                          version = m.group(0)
                  except Exception:
                      pass
                  break
          stem = f"{{app}}-{{os_name}}-{{arch}}-{{config}}-{{version}}"
          staging = Path("dist") / stem
          if staging.exists():
              shutil.rmtree(staging)
          staging.mkdir(parents=True)
          if bin_dir.is_dir():
              for p in bin_dir.iterdir():
                  dest = staging / p.name
                  if p.is_file():
                      shutil.copy2(p, dest)
                  elif p.is_dir():
                      shutil.copytree(p, dest)
          archive = shutil.make_archive(str(Path("dist") / stem), "zip", root_dir="dist", base_dir=stem)
          print(f"Created {{archive}}")
          with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
              fh.write(f"artifact_name={{stem}}\\n")
              fh.write(f"artifact_path={{archive}}\\n")
          PY

      - name: Upload Release artifact
        uses: actions/upload-artifact@v7
        with:
          name: ${{{{ steps.pkg_release.outputs.artifact_name }}}}
          path: ${{{{ steps.pkg_release.outputs.artifact_path }}}}
          if-no-files-found: error
          retention-days: 14
"""


def _github_actions_sanitizers_workflow(ctx: _Context) -> str:
    """Linux ASan+UBSan build and test; failures fail the job."""
    return f"""\
# Generated by cppboot (default; --no-github-actions to skip)
# Linux AddressSanitizer + UndefinedBehaviorSanitizer: build and run unit tests.
# Sanitizer errors abort the process so the job fails.
name: Sanitizers

on:
  push:
  pull_request:

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  asan-ubsan:
    name: ASan+UBSan (ubuntu-latest)
    runs-on: ubuntu-latest
    defaults:
      run:
        shell: bash

    steps:
      - name: Checkout
        uses: actions/checkout@v7

      - name: Install latest CMake and Ninja
        uses: lukka/get-cmake@latest
        with:
          cmakeVersion: latest
          ninjaVersion: latest

      - name: Configure (sanitizers)
        run: >
          cmake -S . -B build/sanitizer -G Ninja
          -DCMAKE_BUILD_TYPE=Debug
          -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
          -DCMAKE_C_COMPILER=clang
          -DCMAKE_CXX_COMPILER=clang++
          -D{ctx.macro}_ENABLE_SANITIZERS=ON

      - name: Build
        run: cmake --build build/sanitizer --parallel

      - name: Test under ASan+UBSan
        env:
          ASAN_OPTIONS: halt_on_error=1:abort_on_error=1:detect_leaks=1:detect_stack_use_after_return=1
          UBSAN_OPTIONS: halt_on_error=1:print_stacktrace=1
        run: ctest --test-dir build/sanitizer --output-on-failure --parallel

      - name: Smoke run app under sanitizers
        env:
          ASAN_OPTIONS: halt_on_error=1:abort_on_error=1:detect_leaks=1
          UBSAN_OPTIONS: halt_on_error=1:print_stacktrace=1
        run: |
          set -euo pipefail
          bin="build/sanitizer/bin/{ctx.name}"
          if [ ! -x "${{bin}}" ]; then
            echo "app binary not found at ${{bin}}"
            exit 1
          fi
          "${{bin}}" --version
"""


def _github_actions_release_workflow(ctx: _Context) -> str:
    """Tag / dispatch release: matrix Release builds, notes, zip assets."""
    return f"""\
# Generated by cppboot (default; --no-github-actions to skip)
# Create GitHub Releases from v* tags or workflow_dispatch.
# Version source of truth is the root VERSION file (must match tag / input).
# Attaches <app>-<os>-<arch>-release-<version>.zip and auto-generated notes.
name: Release

on:
  push:
    tags:
      - "v*"
  workflow_dispatch:
    inputs:
      version:
        description: "Semver without leading v (must match VERSION file; leave empty to use VERSION)"
        required: false
        type: string
        default: ""
      prerelease:
        description: "Mark as prerelease"
        required: false
        type: boolean
        default: false
      dry_run:
        description: "Build and draft only (do not publish release)"
        required: false
        type: boolean
        default: false

permissions:
  contents: write

concurrency:
  group: release-${{{{ github.ref }}}}-${{{{ github.event_name }}}}
  cancel-in-progress: false

jobs:
  prepare:
    name: Resolve version
    runs-on: ubuntu-latest
    outputs:
      version: ${{{{ steps.meta.outputs.version }}}}
      tag: ${{{{ steps.meta.outputs.tag }}}}
      prerelease: ${{{{ steps.meta.outputs.prerelease }}}}
      dry_run: ${{{{ steps.meta.outputs.dry_run }}}}
    steps:
      - name: Checkout
        uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - name: Resolve tag and version (synced with VERSION file)
        id: meta
        env:
          INPUT_VERSION: ${{{{ github.event.inputs.version || '' }}}}
          INPUT_PRERELEASE: ${{{{ github.event.inputs.prerelease || 'false' }}}}
          INPUT_DRY_RUN: ${{{{ github.event.inputs.dry_run || 'false' }}}}
        run: |
          set -euo pipefail
          if [ ! -f VERSION ]; then
            echo "Missing VERSION file at repo root (single source of truth)."
            exit 1
          fi
          FILE_VERSION="$(tr -d '[:space:]' < VERSION | sed 's/^v//;s/^V//;s/#.*//')"
          if ! [[ "${{FILE_VERSION}}" =~ ^[0-9]+\\.[0-9]+\\.[0-9]+([.-].*)?$ ]]; then
            echo "Invalid VERSION file contents: '${{FILE_VERSION}}' (expected semver like 1.0.0)"
            exit 1
          fi

          if [ "${{{{ github.event_name }}}}" = "workflow_dispatch" ]; then
            if [ -z "${{INPUT_VERSION}}" ]; then
              VERSION="${{FILE_VERSION}}"
            else
              VERSION="${{INPUT_VERSION#v}}"
              VERSION="${{VERSION#V}}"
            fi
            if [ "${{VERSION}}" != "${{FILE_VERSION}}" ]; then
              echo "Release version '${{VERSION}}' does not match VERSION file '${{FILE_VERSION}}'."
              echo "Bump the VERSION file (and only that file), commit, then re-run the release."
              exit 1
            fi
            TAG="v${{VERSION}}"
            PRERELEASE="${{INPUT_PRERELEASE}}"
            DRY_RUN="${{INPUT_DRY_RUN}}"
            # Do not push tags here — that would re-trigger this workflow.
            # softprops/action-gh-release creates the tag on publish when missing.
          else
            TAG="${{{{ github.ref_name }}}}"
            VERSION="${{TAG#v}}"
            VERSION="${{VERSION#V}}"
            PRERELEASE=false
            DRY_RUN=false
            if [[ "${{TAG}}" == *-* ]] || [[ "${{TAG}}" == *alpha* ]] || [[ "${{TAG}}" == *beta* ]] || [[ "${{TAG}}" == *rc* ]]; then
              PRERELEASE=true
            fi
            if [ "${{VERSION}}" != "${{FILE_VERSION}}" ]; then
              echo "Tag version '${{VERSION}}' does not match VERSION file '${{FILE_VERSION}}'."
              echo "Bump VERSION, commit, then tag v${{FILE_VERSION}} (or retag after fixing VERSION)."
              exit 1
            fi
          fi
          {{
            echo "version=${{VERSION}}"
            echo "tag=${{TAG}}"
            echo "prerelease=${{PRERELEASE}}"
            echo "dry_run=${{DRY_RUN}}"
          }} >> "${{{{ github.output }}}}"
          echo "Resolved release ${{TAG}} (version=${{VERSION}}, file=${{FILE_VERSION}}, prerelease=${{PRERELEASE}}, dry_run=${{DRY_RUN}})"

  build:
    name: build-${{{{ matrix.os }}}}
    needs: prepare
    runs-on: ${{{{ matrix.os }}}}
    strategy:
      fail-fast: false
      matrix:
        os:
          - ubuntu-latest
          - macos-latest
          - windows-latest
    env:
      APP_NAME: {ctx.name}
      RELEASE_VERSION: ${{{{ needs.prepare.outputs.version }}}}
    defaults:
      run:
        shell: bash
    steps:
      - name: Checkout
        uses: actions/checkout@v7

      - name: Install latest CMake and Ninja
        uses: lukka/get-cmake@latest
        with:
          cmakeVersion: latest
          ninjaVersion: latest

      - name: Enable MSVC developer command prompt
        if: runner.os == 'Windows'
        uses: TheMrMilchmann/setup-msvc-dev@v4
        with:
          arch: x64

      - name: Configure Release
        run: >
          cmake -S . -B build/release -G Ninja
          -DCMAKE_BUILD_TYPE=Release

      - name: Build Release
        run: cmake --build build/release --parallel

      - name: Test Release
        run: ctest --test-dir build/release --output-on-failure --parallel

      - name: Verify binary version matches release
        run: |
          set -euo pipefail
          bin="build/release/bin/${{APP_NAME}}"
          if [ ! -x "${{bin}}" ] && [ -f "${{bin}}.exe" ]; then
            bin="${{bin}}.exe"
          fi
          if [ ! -f "${{bin}}" ]; then
            echo "Missing app binary at build/release/bin/${{APP_NAME}}"
            exit 1
          fi
          out="$("${{bin}}" --version 2>&1 || true)"
          echo "Binary --version output: ${{out}}"
          if ! echo "${{out}}" | grep -Eq "(^|[[:space:]])${{RELEASE_VERSION}}([[:space:]]|$)"; then
            echo "Version mismatch: expected ${{RELEASE_VERSION}} from VERSION/tag, got: ${{out}}"
            echo "Edit the root VERSION file only, reconfigure/rebuild, then release."
            exit 1
          fi
          file_ver="$(tr -d '[:space:]' < VERSION | sed 's/^v//;s/^V//;s/#.*//')"
          if [ "${{file_ver}}" != "${{RELEASE_VERSION}}" ]; then
            echo "VERSION file (${{file_ver}}) drifted from release version (${{RELEASE_VERSION}})."
            exit 1
          fi

      - name: Package Release zip
        id: pkg
        run: |
          set -euo pipefail
          python3 - <<'PY'
          import os, re, shutil, subprocess
          from pathlib import Path

          app = os.environ["APP_NAME"]
          version = os.environ["RELEASE_VERSION"]
          os_name = {{"Linux": "linux", "macOS": "macos", "Windows": "windows"}}.get(
              os.environ.get("RUNNER_OS", ""), os.environ.get("RUNNER_OS", "unknown").lower()
          )
          arch = {{"X64": "x86_64", "ARM64": "arm64", "X86": "x86"}}.get(
              os.environ.get("RUNNER_ARCH", ""), os.environ.get("RUNNER_ARCH", "unknown").lower()
          )
          config = "release"
          bin_dir = Path("build") / config / "bin"
          stem = f"{{app}}-{{os_name}}-{{arch}}-{{config}}-{{version}}"
          staging = Path("dist") / stem
          if staging.exists():
              shutil.rmtree(staging)
          staging.mkdir(parents=True)
          if not bin_dir.is_dir():
              raise SystemExit(f"missing {{bin_dir}}")
          for p in bin_dir.iterdir():
              dest = staging / p.name
              if p.is_file():
                  shutil.copy2(p, dest)
              elif p.is_dir():
                  shutil.copytree(p, dest)
          archive = shutil.make_archive(str(Path("dist") / stem), "zip", root_dir="dist", base_dir=stem)
          print(f"Created {{archive}}")
          with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
              fh.write(f"artifact_name={{stem}}\\n")
              fh.write(f"artifact_path={{archive}}\\n")
          PY

      - name: Upload Release zip (workflow artifact)
        uses: actions/upload-artifact@v7
        with:
          name: ${{{{ steps.pkg.outputs.artifact_name }}}}
          path: ${{{{ steps.pkg.outputs.artifact_path }}}}
          if-no-files-found: error
          retention-days: 14

  publish:
    name: Publish GitHub Release
    needs: [prepare, build]
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - name: Download build zips
        uses: actions/download-artifact@v7
        with:
          path: release-assets
          pattern: "{ctx.name}-*"
          merge-multiple: true

      - name: List assets
        run: |
          set -euo pipefail
          find release-assets -type f -name '*.zip' | tee assets.list
          test -s assets.list

      - name: Create GitHub Release
        if: needs.prepare.outputs.dry_run != 'true'
        uses: softprops/action-gh-release@v3
        with:
          tag_name: ${{{{ needs.prepare.outputs.tag }}}}
          name: ${{{{ needs.prepare.outputs.tag }}}}
          generate_release_notes: true
          prerelease: ${{{{ needs.prepare.outputs.prerelease == 'true' }}}}
          files: release-assets/**/*.zip
          fail_on_unmatched_files: true
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}

      - name: Dry-run summary
        if: needs.prepare.outputs.dry_run == 'true'
        run: |
          echo "Dry run complete for ${{{{ needs.prepare.outputs.tag }}}} — assets:"
          find release-assets -type f -name '*.zip' -print
"""


def _code_of_conduct_md() -> str:
    """Short, technology-first code of conduct (not Contributor Covenant)."""
    return """\
# Code of Conduct

This project is a technical collaboration space. The standard is simple:
**be an adult, be respectful, and keep the work about the work.**

## Principles

1. **Treat others as you would want to be treated.** Assume good faith until
   shown otherwise.
2. **Be mature and professional.** Disagreement is fine; contempt is not.
3. **Focus on the technology.** Prefer technical arguments, evidence, and
   clear tradeoffs over personal attacks, tribal signaling, or off-topic
   politics.
4. **Be direct and civil.** Critique ideas and code, not people. Avoid sarcasm
   that exists only to belittle.
5. **Be responsible.** Own mistakes, fix what you break, and do not waste
   others' time with spam, trolling, or bad-faith engagement.
6. **Respect privacy and safety.** Do not share private information without
   consent. Do not threaten, stalk, or harass anyone.

## What this is not

This is not a speech code about identity, ideology, or belief. Contributors of
any background are welcome on equal terms: the bar is competence, honesty, and
conduct.

## Unacceptable behavior

- Harassment, intimidation, or sustained personal attacks
- Doxxing or publishing private information without consent
- Sexual advances or sexualized content in project spaces
- Spam, vandalism, or deliberate disruption
- Using the project primarily as a vehicle for unrelated political agitation

## Scope

These expectations apply in project spaces: issues, pull requests, discussions,
chats tied to the project, and similar venues when acting as a participant in
this project.

## Enforcement

Maintainers may warn, moderate, block, or remove contributions that violate
this standard. Serious or repeated abuse may result in a temporary or permanent
ban from project spaces.

Report problems privately to a maintainer (see the repository owner/maintainers,
or [SECURITY.md](SECURITY.md) for security-sensitive matters). Do not file public
issues solely to air personal grievances.

## In one line

**Be excellent to each other; ship good software.**
"""


def _contributing_md(ctx: _Context) -> str:
    return f"""\
# Contributing to {ctx.name}

Thank you for considering a contribution. This guide is intentionally generic
and works for most open-source C++ projects bootstrapped with cppboot.

## Code of conduct

Be mature, respectful, and technical. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Getting started

1. Fork the repository and clone your fork.
2. Install a C++20 toolchain, CMake 3.20+, Ninja (recommended), and Make.
3. Build and test:

   ```bash
   make
   make test
   ./{ctx.name} --version
   ```

4. Optional: open the folder in VS Code and install recommended extensions
   (see README).

## Development workflow

- Prefer small, focused pull requests.
- Follow [AGENTS.md](AGENTS.md) for layout, style, and documentation rules:
  - **Google C++ Style Guide** for code logic and naming
  - **Microsoft** `.clang-format` for formatting (`make fmt`)
- List new sources explicitly in the component `CMakeLists.txt` (no globs).
- Add or update unit tests for behavior changes.
- Keep `make` and `make test` green. On Linux, `make sanitizer` is encouraged
  for memory/UB issues.

## Reporting bugs and proposing features

- Use GitHub Issues for bugs and feature requests.
- Include OS, compiler, CMake version, and steps to reproduce when filing bugs.
- Search existing issues before opening a new one.

## Security vulnerabilities

Do **not** open a public issue for security problems. See
[SECURITY.md](SECURITY.md).

## Pull request checklist

- [ ] Code builds (`make`)
- [ ] Tests pass (`make test`)
- [ ] Formatted (`make fmt`)
- [ ] Public APIs have Doxygen where appropriate
- [ ] Commit messages are clear; PR description explains *why*

## License

By contributing, you agree that your contributions will be licensed under the
same license as this repository (see [LICENSE](LICENSE)).
"""


def _security_md(ctx: _Context) -> str:
    return f"""\
# Security Policy

## Supported versions and fix policy

**{ctx.name}** treats security seriously, with a simple support model:

- Security fixes are developed on the default branch and **ship in the next
  release** (or sooner via an out-of-band release if warranted).
- **We do not backport security fixes to older releases by default.**
- Exceptions may be made for **compelling reasons** (for example, a widely used
  previous release with a severe issue and a clear maintainer commitment). Any
  such exception is discretionary and will be called out in release notes.

| Line | Security fixes |
|------|----------------|
| Default branch (development) | Yes — fixed here first |
| Next / upcoming release | Yes — normal ship vehicle for fixes |
| Older released versions | **No** (unless an explicit exception) |

Always prefer upgrading to the latest release when a security fix is announced.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Prefer one of these private channels (first that applies):

1. **GitHub Private Vulnerability Reporting** (Security tab → Advisories →
   Report a vulnerability), if enabled on this repository.
2. Contact a repository maintainer privately (see the owner/maintainer profile
   or organization security contact).

Include:

- A description of the issue and its impact
- Steps to reproduce or a proof of concept if available
- Affected versions / commit SHAs if known

We will acknowledge receipt when possible and work with you on a coordinated
disclosure timeline. Please give maintainers reasonable time to investigate and
ship a fix (typically via the next release) before any public discussion.

## Preferred languages

English is preferred for security reports.
"""


def _gitignore() -> str:
    return """\
# Build trees
build/
cmake-build-*/
out/
install/

# Compilation database (regenerated by make debug)
compile_commands.json

# ctags index (regenerated by make tags)
tags
TAGS
.tags

# Doxygen
docs/html/
docs/latex/
docs/xml/
docs/rtf/
docs/man/

# IDE / editor
.idea/
# Keep shared VS Code project files; ignore only local/unshared editor state.
.vscode/*
!.vscode/extensions.json
!.vscode/settings.json
!.vscode/tasks.json
!.vscode/launch.json
*.swp
*.swo
*~
.DS_Store
CMakeUserPresets.json

# Python / tooling
__pycache__/
*.pyc
.venv/
venv/

# Coverage / sanitizers
*.gcda
*.gcno
*.profraw
*.profdata
default.profraw

# Package / install leftovers
*.a
*.so
*.so.*
*.dylib
*.dll
*.lib
*.exe
*.pdb
"""


def _gitattributes() -> str:
    return """\
* text=auto eol=lf
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.pdf binary
"""


def _clang_format() -> str:
    return """\
BasedOnStyle: Microsoft
Language: Cpp
Standard: c++20
ColumnLimit: 100
SortIncludes: true
IncludeBlocks: Regroup
"""


def _clangd() -> str:
    # Prefer the source-root database (symlinked/copied from the build tree).
    # Fallback paths help before the first build finishes linking the root file.
    return """\
CompileFlags:
  CompilationDatabase: .
---
If:
  PathMatch: .*
CompileFlags:
  Add:
    - -std=c++20
    - -Iinclude
"""


def _doxyfile(ctx: _Context) -> str:
    return f"""\
# Doxyfile generated by cppboot — minimal professional defaults.
# PROJECT_NUMBER is overridden from the root VERSION file by `make doc` /
# `build.bat doc`; the value below is only a fallback.
PROJECT_NAME           = "{ctx.name}"
PROJECT_NUMBER         = "0.1.0"
OUTPUT_DIRECTORY       = docs
CREATE_SUBDIRS         = NO
ALLOW_UNICODE_NAMES    = YES
OUTPUT_LANGUAGE        = English
BRIEF_MEMBER_DESC      = YES
REPEAT_BRIEF           = YES
ALWAYS_DETAILED_SEC    = NO
FULL_PATH_NAMES        = YES
STRIP_FROM_PATH        = .
JAVADOC_AUTOBRIEF      = YES
QT_AUTOBRIEF           = YES
MULTILINE_CPP_IS_BRIEF = NO
INHERIT_DOCS           = YES
SEPARATE_MEMBER_PAGES  = NO
TAB_SIZE               = 2
OPTIMIZE_OUTPUT_FOR_C  = NO
BUILTIN_STL_SUPPORT    = YES
EXTRACT_ALL            = YES
EXTRACT_PRIVATE        = NO
EXTRACT_STATIC         = YES
HIDE_UNDOC_MEMBERS     = NO
HIDE_UNDOC_CLASSES     = NO
CASE_SENSE_NAMES       = YES
SHOW_INCLUDE_FILES     = YES
SHOW_FILES             = YES
SHOW_NAMESPACES        = YES
QUIET                  = YES
WARNINGS               = YES
WARN_IF_UNDOCUMENTED   = YES
WARN_IF_DOC_ERROR      = YES
INPUT                  = src include
FILE_PATTERNS          = *.cpp *.hpp *.h *.cc *.cxx *.cppm *.ixx
RECURSIVE              = YES
EXCLUDE_PATTERNS       = */build/* */.git/*
SOURCE_BROWSER         = YES
INLINE_SOURCES         = NO
REFERENCED_BY_RELATION = YES
REFERENCES_RELATION    = YES
GENERATE_HTML          = YES
HTML_OUTPUT            = html
GENERATE_LATEX         = NO
HAVE_DOT               = NO
"""


def _ctags_config() -> str:
    """Universal Ctags options file (read automatically as .ctags)."""
    return """\
# Universal Ctags config generated by cppboot.
# Regenerate the index with: make tags
# Prefer https://github.com/universal-ctags/ctags (not legacy Exuberant Ctags).

--recurse=yes
--languages=C,C++
--langmap=C++:+.hpp.hh.h++.hxx.cpp.cxx.cc.ipp.tpp.cppm.ixx
--exclude=.git
--exclude=build
--exclude=cmake-build-*
--exclude=out
--exclude=install
--exclude=docs/html
--exclude=docs/latex
--exclude=docs/xml
--exclude=_deps
--exclude=*.json
--fields=+iaS
--extras=+q
--c++-kinds=+p
--tag-relative=never
-f tags
"""


def _vimrc(ctx: _Context) -> str:
    ctags_block = ""
    if ctx.with_ctags:
        ctags_block = """
" ctags: search upward for tags; regenerate with :make tags
set tags=./tags;,tags
nnoremap <leader>c :make tags<CR>
"""
    return f"""\
" Minimal project-local Vim profile generated by cppboot.
" Load with :set exrc secure in your global vimrc.

set nocompatible
set encoding=utf-8
set fileformat=unix

" Indentation aligned with common C++ / Microsoft-format habits.
set expandtab
set shiftwidth=4
set tabstop=4
set softtabstop=4
set autoindent
set smartindent

" UX
set number
set relativenumber
set ruler
set showcmd
set wildmenu
set incsearch
set hlsearch
set ignorecase
set smartcase
{ctags_block}
" Prefer repo-root compile_commands.json for ALE/coc/clangd integrations.
let g:cppboot_project_root = expand('<sfile>:p:h')

" Use the project Makefile as the default build command.
set makeprg=make
nnoremap <leader>m :make<CR>
nnoremap <leader>t :make test<CR>
nnoremap <leader>f :make fmt<CR>
"""



def _version_file() -> str:
    """Single source of truth for package version (edit this file only)."""
    return "0.1.0\n"


def _version_header_in(ctx: _Context) -> str:
    """CMake configure_file template for the public version header."""
    _ = ctx
    return """\
#pragma once

#include <string_view>

/**
 * @file version.hpp
 * @brief Package version API (generated from VERSION + cmake/version.hpp.in).
 *
 * Do not edit this file by hand. Change the root VERSION file and reconfigure.
 */

namespace @PROJECT_NAMESPACE@ {

/// Semantic version major component.
inline constexpr int kVersionMajor = @PROJECT_VERSION_MAJOR@;
/// Semantic version minor component.
inline constexpr int kVersionMinor = @PROJECT_VERSION_MINOR@;
/// Semantic version patch component.
inline constexpr int kVersionPatch = @PROJECT_VERSION_PATCH@;

/**
 * @brief Returns the package version string (semantic version).
 * @return Version such as "0.1.0". Never empty.
 */
[[nodiscard]] std::string_view Version() noexcept;

}  // namespace @PROJECT_NAMESPACE@
"""


def _version_source_in(ctx: _Context) -> str:
    """CMake configure_file template for the version translation unit."""
    _ = ctx
    return """\
#include "@PROJECT_NAMESPACE@/version.hpp"

namespace @PROJECT_NAMESPACE@ {

std::string_view Version() noexcept {
  return "@PROJECT_VERSION_STRING@";
}

}  // namespace @PROJECT_NAMESPACE@
"""


def _version_module_in(ctx: _Context) -> str:
    """CMake configure_file template for the C++20 version module."""
    return f"""\
/**
 * @file version.cppm
 * @brief C++20 module interface for the package version API (generated).
 *
 * Do not edit this file by hand. Change the root VERSION file and reconfigure.
 */

module;

#include <string_view>

export module {ctx.namespace}.version;

/**
 * @brief Package version helpers for {ctx.name}.
 */
export namespace {ctx.namespace} {{

inline constexpr int kVersionMajor = @PROJECT_VERSION_MAJOR@;
inline constexpr int kVersionMinor = @PROJECT_VERSION_MINOR@;
inline constexpr int kVersionPatch = @PROJECT_VERSION_PATCH@;

[[nodiscard]] std::string_view Version() noexcept;

}}  // namespace {ctx.namespace}

namespace {ctx.namespace} {{

std::string_view Version() noexcept {{
  return "@PROJECT_VERSION_STRING@";
}}

}}  // namespace {ctx.namespace}
"""


def _main_cpp(ctx: _Context) -> str:
    if ctx.with_modules:
        version_include = f"import {ctx.namespace}.version;"
    else:
        version_include = f'#include "{ctx.namespace}/version.hpp"'
    return f"""\
/**
 * @file main.cpp
 * @brief Program entrypoint (always src/main.cpp in cppboot projects).
 *
 * Keep this file thin: parse args / wire dependencies, then call library code.
 */

{version_include}

#include <CLI/CLI.hpp>

#include <iostream>
#include <string>

/**
 * @brief Program entry.
 * @param argc Argument count.
 * @param argv Argument vector.
 * @return Exit status.
 */
int main(int argc, char** argv) {{
  CLI::App app{{"{ctx.name} — cppboot project"}};
  app.set_version_flag("-V,--version", std::string{{{ctx.namespace}::Version()}});
  CLI11_PARSE(app, argc, argv);

  std::cout << "{ctx.name} " << {ctx.namespace}::Version()
            << " — add components under src/ (see README.md / AGENTS.md)\\n";
  return 0;
}}
"""


def _version_test(ctx: _Context) -> str:
    if ctx.with_modules:
        includes = f"import {ctx.namespace}.version;\n\n#include <gtest/gtest.h>"
    else:
        includes = (
            f'#include "{ctx.namespace}/version.hpp"\n\n'
            "#include <gtest/gtest.h>"
        )
    return f"""\
/**
 * @file version_test.cpp
 * @brief Unit tests for {ctx.namespace}::Version.
 */

{includes}

#include <string>
#include <string_view>

namespace {{

TEST(VersionTest, IsNonEmpty) {{
  const std::string_view version = {ctx.namespace}::Version();
  EXPECT_FALSE(version.empty());
}}

TEST(VersionTest, MatchesComponentConstants) {{
  // Version() is generated from the root VERSION file; constants must agree.
  const std::string expected =
      std::to_string({ctx.namespace}::kVersionMajor) + "." +
      std::to_string({ctx.namespace}::kVersionMinor) + "." +
      std::to_string({ctx.namespace}::kVersionPatch);
  EXPECT_EQ({ctx.namespace}::Version(), expected);
  EXPECT_GE({ctx.namespace}::kVersionMajor, 0);
  EXPECT_GE({ctx.namespace}::kVersionMinor, 0);
  EXPECT_GE({ctx.namespace}::kVersionPatch, 0);
}}

TEST(VersionTest, HasThreeNumericComponents) {{
  const std::string_view version = {ctx.namespace}::Version();
  EXPECT_NE(version.find('.'), std::string_view::npos);
  EXPECT_NE(version.rfind('.'), std::string_view::npos);
  EXPECT_NE(version.find('.'), version.rfind('.'));
}}

}}  // namespace
"""


def _version_bench(ctx: _Context) -> str:
    if ctx.with_modules:
        includes = f"import {ctx.namespace}.version;\n\n#include <benchmark/benchmark.h>"
    else:
        includes = (
            f'#include "{ctx.namespace}/version.hpp"\n\n'
            "#include <benchmark/benchmark.h>"
        )
    return f"""\
/**
 * @file version_bench.cpp
 * @brief Microbenchmarks for {ctx.namespace}::Version.
 */

{includes}

#include <string_view>

namespace {{

void BM_Version(benchmark::State& state) {{
  for (auto _ : state) {{
    // Mutable lvalue required: const-ref DoNotOptimize is deprecated under -Werror.
    std::string_view version = {ctx.namespace}::Version();
    benchmark::DoNotOptimize(version);
  }}
}}
BENCHMARK(BM_Version);

}}  // namespace
"""

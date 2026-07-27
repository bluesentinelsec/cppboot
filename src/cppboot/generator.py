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
    with_sample: bool = True
    shared_library: bool = False
    with_vim: bool = True
    with_ctags: bool = True
    with_vscode: bool = True
    create_github: bool = False
    with_github_actions: bool = True
    verbose: bool = False


@dataclass
class GenerateResult:
    """Outcome of scaffolding a project."""

    project_dir: Path
    files_written: list[Path]
    git_initialized: bool
    github_created: bool
    license_source: str


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
        with_sample=options.with_sample,
        shared_library=options.shared_library,
        with_vim=options.with_vim,
        with_ctags=options.with_ctags,
        with_vscode=options.with_vscode,
        with_github_actions=options.with_github_actions,
        year=str(_dt.date.today().year),
    )

    if options.with_modules:
        logger.info(
            "C++20 modules scaffold enabled: requires CMake 3.28+, Ninja, and a "
            "compiler with module dependency scanning (Clang 16+, GCC 14+, or "
            "MSVC 17.4+). AppleClang often lacks CMake module scanning support."
        )
    if not options.with_sample:
        logger.info(
            "sample code disabled (--no-sample): no Calc demo; empty component layout"
        )

    written: list[Path] = []

    def write(relpath: str, content: str) -> None:
        path = project_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
        logger.debug("wrote %s", path)

    # Root files
    write("CMakeLists.txt", _root_cmake(ctx))
    write("Makefile", _makefile(ctx))
    write("README.md", _readme(ctx))
    write("AGENTS.md", _agents_md(ctx))
    write(".gitignore", _gitignore())
    write(".gitattributes", _gitattributes())
    write(".clang-format", _clang_format())
    write(".clangd", _clangd())
    write("Doxyfile", _doxyfile(ctx))
    write("cmake/Dependencies.cmake", _dependencies_cmake(ctx))
    write("cmake/CompilerWarnings.cmake", _warnings_cmake())

    # Library sources + single obvious entrypoint at src/main.cpp
    write("src/CMakeLists.txt", _src_cmake(ctx))
    write("src/main.cpp", _main_cpp(ctx))
    if ctx.with_sample:
        write("src/calc/CMakeLists.txt", _calc_src_cmake(ctx))
        if ctx.with_modules:
            write("src/calc/calc.cppm", _calc_module(ctx))
        else:
            write(f"include/{ctx.namespace}/calc.hpp", _calc_header(ctx))
            write("src/calc/calc.cpp", _calc_source(ctx))
    else:
        # Keeps the static/shared library target valid before real components exist.
        write("src/library_anchor.cpp", _library_anchor_cpp(ctx))

    # Tests
    write("tests/CMakeLists.txt", _tests_cmake(ctx))
    if ctx.with_sample:
        write("tests/calc/CMakeLists.txt", _calc_tests_cmake(ctx))
        write("tests/calc/calc_test.cpp", _calc_test(ctx))
        write("tests/calc/mock_calc_test.cpp", _mock_calc_test(ctx))

    # Benchmarks
    write("benchmarks/CMakeLists.txt", _benchmarks_cmake(ctx))
    if ctx.with_sample:
        write("benchmarks/calc/CMakeLists.txt", _calc_bench_cmake(ctx))
        write("benchmarks/calc/calc_bench.cpp", _calc_bench(ctx))

    if ctx.with_vim:
        write(".vimrc", _vimrc(ctx))

    if ctx.with_ctags:
        write(".ctags", _ctags_config())
        logger.info("wrote Universal Ctags config (.ctags); run: make tags")

    if ctx.with_vscode:
        write("CMakePresets.json", _cmake_presets(ctx))
        write(".vscode/extensions.json", _vscode_extensions())
        write(".vscode/settings.json", _vscode_settings(ctx))
        write(".vscode/tasks.json", _vscode_tasks(ctx))
        write(".vscode/launch.json", _vscode_launch(ctx))
        logger.info("wrote VS Code config under .vscode/ and CMakePresets.json")

    if ctx.with_github_actions:
        write(".github/workflows/ci.yml", _github_actions_workflow(ctx))
        logger.info("wrote GitHub Actions workflow at .github/workflows/ci.yml")

    year = ctx.year
    holder = name
    license_result = fetch_license_text(license_id, year=year, holder=holder)
    write("LICENSE", license_result.text)
    logger.info(
        "license %s written from %s",
        license_result.license_id,
        license_result.source,
    )

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
    with_sample: bool
    shared_library: bool
    with_vim: bool
    with_ctags: bool
    with_vscode: bool
    with_github_actions: bool
    year: str


def _git_init(project_dir: Path) -> bool:
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
        logger.info("initialized git repository in %s", project_dir)
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
    public_includes = ""
    if not ctx.with_modules:
        public_includes = f"""
target_include_directories(${{PROJECT_NAME}}_lib
  PUBLIC
    $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include>
    $<INSTALL_INTERFACE:include>
)
"""
    else:
        public_includes = """
# Module interface units provide the public API; no classic include tree.
"""

    cmake_min = "3.28" if ctx.with_modules else "3.20"
    return f"""\
cmake_minimum_required(VERSION {cmake_min})

project({ctx.name}
  VERSION 0.1.0
  DESCRIPTION "C++ project bootstrapped by cppboot"
  LANGUAGES CXX
)

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

# Preferred third-party libraries (FetchContent). ON by default; turn off to skip.
option({ctx.macro}_WITH_CLI11 "CLI argument parsing via CLI11" ON)
option({ctx.macro}_WITH_JSON "JSON parsing via nlohmann/json" ON)
option({ctx.macro}_WITH_SPDLOG "Console/file logging via spdlog" ON)

option({ctx.macro}_BUILD_TESTS "Build unit tests" ON)
option({ctx.macro}_BUILD_BENCHMARKS "Build benchmarks" ON)

include(Dependencies)
{modules_block}
add_library(${{PROJECT_NAME}}_lib {lib_type})
add_library(${{PROJECT_NAME}}::lib ALIAS ${{PROJECT_NAME}}_lib)

set_target_properties(${{PROJECT_NAME}}_lib PROPERTIES
  OUTPUT_NAME {ctx.target}
  EXPORT_NAME lib
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
    return """\
install(DIRECTORY include/
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
  FILES_MATCHING PATTERN "*.hpp" PATTERN "*.h"
)
install(TARGETS ${PROJECT_NAME}_lib
  EXPORT ${PROJECT_NAME}Targets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
  INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
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


def _src_cmake(ctx: _Context) -> str:
    if ctx.with_sample:
        library_bits = "add_subdirectory(calc)\n"
    else:
        library_bits = (
            "# Example once you add code:\n"
            "#   add_subdirectory(parser)\n"
            "#\n"
            "# Until then, library_anchor.cpp keeps the library target non-empty. "
            "Remove that\n"
            "# file and the target_sources line below when your first real "
            "component lands.\n"
            "target_sources(${PROJECT_NAME}_lib PRIVATE library_anchor.cpp)\n"
        )

    return (
        "# Library implementation components.\n"
        "# Each logical subdirectory owns a CMakeLists.txt that lists sources "
        "explicitly.\n"
        f"{library_bits}\n"
        "# Painfully obvious program entrypoint: src/main.cpp\n"
        "# Do not add other executables here without a strong reason.\n"
        "add_executable(${PROJECT_NAME}_app main.cpp)\n"
        f"set_target_properties(${{PROJECT_NAME}}_app PROPERTIES "
        f"OUTPUT_NAME {ctx.name})\n"
        "target_link_libraries(${PROJECT_NAME}_app PRIVATE ${PROJECT_NAME}_lib)\n"
        "cppboot_set_project_warnings(${PROJECT_NAME}_app)\n"
    )


def _calc_src_cmake(ctx: _Context) -> str:
    if ctx.with_modules:
        return f"""\
# calc component (C++20 module).
# List every module unit and implementation file explicitly.
target_sources(${{PROJECT_NAME}}_lib
  PUBLIC
    FILE_SET CXX_MODULES FILES
      calc.cppm
)
"""
    return f"""\
# calc component.
# List every translation unit explicitly — do not use file(GLOB).
target_sources(${{PROJECT_NAME}}_lib
  PRIVATE
    calc.cpp
)
"""


def _tests_cmake(ctx: _Context) -> str:
    if ctx.with_sample:
        return """\
# Unit tests — one subdirectory per component under test.
add_subdirectory(calc)
"""
    return """\
# Unit tests — one subdirectory per component under test.
# Example: add_subdirectory(parser)
"""


def _calc_tests_cmake(ctx: _Context) -> str:
    return f"""\
add_executable({ctx.target}_calc_test
  calc_test.cpp
  mock_calc_test.cpp
)
target_link_libraries({ctx.target}_calc_test
  PRIVATE
    ${{PROJECT_NAME}}_lib
    GTest::gtest_main
    GTest::gmock
)
cppboot_set_project_warnings({ctx.target}_calc_test)
gtest_discover_tests({ctx.target}_calc_test)
"""


def _benchmarks_cmake(ctx: _Context) -> str:
    if ctx.with_sample:
        return """\
# Microbenchmarks — one subdirectory per component.
add_subdirectory(calc)
"""
    return """\
# Microbenchmarks — one subdirectory per component.
# Example: add_subdirectory(parser)
"""


def _calc_bench_cmake(ctx: _Context) -> str:
    return f"""\
add_executable({ctx.target}_calc_bench
  calc_bench.cpp
)
target_link_libraries({ctx.target}_calc_bench
  PRIVATE
    ${{PROJECT_NAME}}_lib
    benchmark::benchmark
    benchmark::benchmark_main
)
cppboot_set_project_warnings({ctx.target}_calc_bench)
"""


def _makefile(ctx: _Context) -> str:
    target = ctx.target
    # C++20 modules require Ninja or VS generators; default to Ninja when modules are on.
    if ctx.with_modules:
        generator_default = """
# C++20 modules require Ninja (or Visual Studio). Prefer Ninja by default.
ifeq ($(GENERATOR),)
  ifneq ($(shell command -v ninja 2>/dev/null),)
    GENERATOR := Ninja
  else
    $(warning C++20 modules need the Ninja generator; install ninja or set GENERATOR=)
  endif
endif
"""
    else:
        generator_default = """
# Optional: export GENERATOR=Ninja to use the Ninja CMake generator.
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

.PHONY: all debug release test bench fmt doc clean configure-debug configure-release \\
        link_compile_commands copy_compile_commands help{phony_extra}

PROJECT_NAME := {ctx.name}
TARGET_NAME  := {target}
BUILD_DEBUG  := build/debug
BUILD_RELEASE := build/release
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
	@echo "  make fmt           - run clang-format on all sources"
	@echo "  make doc           - generate Doxygen HTML under docs/html"
{help_tags}	@echo "  make clean         - remove local build trees and compile_commands.json"

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

release: configure-release
	cmake --build $(BUILD_RELEASE) --parallel
	-@find $(BUILD_RELEASE)/bin -type f -name '*$(EXE_EXT)' 2>/dev/null \\
	  -exec strip -S {{}} + 2>/dev/null || true

test: debug
	ctest --test-dir $(BUILD_DEBUG) --output-on-failure --parallel

# Runs the first Google Benchmark binary found under the Release build tree.
# With the sample scaffold that is typically <name>_calc_bench; with your own
# components any *bench* executable works the same way.
bench: release
	@found=$$(find $(BUILD_RELEASE)/bin $(BUILD_RELEASE) -type f \\( -name '*bench$(EXE_EXT)' -o -name '*_bench$(EXE_EXT)' \\) 2>/dev/null | head -n 1); \\
	if [ -z "$$found" ]; then \\
	  echo "No benchmark executables found. Add benchmarks/<component>/ then rebuild."; \\
	  exit 0; \\
	fi; \\
	echo "Running $$found"; \\
	"$$found" --benchmark_min_time=0.01s

fmt:
	@command -v clang-format >/dev/null 2>&1 || {{ echo "clang-format not found"; exit 1; }}
	@files=$$(find src tests benchmarks include -type f \\
	  \\( -name '*.cpp' -o -name '*.hpp' -o -name '*.h' -o -name '*.cc' -o -name '*.cxx' -o -name '*.cppm' -o -name '*.ixx' \\) \\
	  2>/dev/null); \\
	if [ -n "$$files" ]; then clang-format -i $$files; fi

doc:
	@command -v doxygen >/dev/null 2>&1 || {{ echo "doxygen not found"; exit 1; }}
	doxygen Doxyfile
{tags_target}
clean:
	rm -rf build docs/html docs/latex docs/xml compile_commands.json{clean_extra}

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
        "\nThis tree includes a small **Calc** sample component (library, tests, "
        "mock, benchmark) so the toolchain is immediately exercisable.\n"
        if ctx.with_sample
        else "\nScaffolded with **`--no-sample`**: no Calc demo. Add your first "
        "component under `src/<name>/` (and drop `library_anchor.cpp` when you do).\n"
    )
    gha_section = ""
    if ctx.with_github_actions:
        gha_section = """

## Continuous integration

A GitHub Actions workflow is checked in at `.github/workflows/ci.yml`
(default; disable with `cppboot --no-github-actions`). On every push and pull
request it runs a matrix across **Ubuntu**, **macOS**, and **Windows**, for each
OS:

1. Configure and build **Debug** (Ninja)
2. Run unit tests (CTest) on Debug
3. Configure and build **Release**
4. Run unit tests on Release
5. Run Google Benchmark binaries found under `build/release` (short min time)
6. Upload `build/*/bin` artifacts for that OS

The workflow uses CMake + Ninja directly (not the Makefile) so Windows runners
behave like Unix. First runs download FetchContent dependencies and may take a
few minutes.
"""
    vscode_section = ""
    if ctx.with_vscode:
        vscode_section = f"""

## Open in VS Code

1. Open this folder in VS Code (`code .`).
2. Install the **recommended extensions** when prompted (clangd, CMake Tools, CodeLLDB).
3. **CMake: Select Configure Preset** → `debug` (or use the CMake status bar).
4. **Build:** `Ctrl/Cmd+Shift+B` (task *Build Debug*) or CMake Tools Build.
5. **Debug the app:** F5 → *Debug {ctx.name}* (builds Debug first).
6. **Tests:** Task *Test* / CMake Tools CTest, or `make test` in the terminal.

Presets live in `CMakePresets.json` (`debug` → `build/debug`, `release` → `build/release`).
clangd uses the root `compile_commands.json` after the first configure (also
copied by CMake Tools via workspace settings).

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
{gha_section}{vscode_section}
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
  src/main.cpp         # THE program entrypoint (always here)
  src/<component>/     # library implementation; each dir has CMakeLists.txt
  include/             # public headers (classic layout only)
  tests/<component>/   # GoogleTest / GoogleMock
  benchmarks/<component>/
  cmake/               # shared CMake modules
  CMakeLists.txt
  Makefile
```

{modules_note}

**Modules toolchain note:** CMake C++20 modules need **Ninja** (the Makefile
selects it automatically when `ninja` is on `PATH`), **CMake 3.28+**, and a
compiler with module dependency scanning (**Clang 16+**, **GCC 14+**, or
**MSVC 17.4+**). Stock **AppleClang** often cannot scan modules for CMake yet;
use a recent LLVM Clang/GCC/MSVC when building a modules project.
{vim_note}{vscode_note}{ctags_note}
## Build

Out-of-source builds only. Artifacts land under `build/`.

| Command | Meaning |
|---------|---------|
| `make` / `make debug` | Configure and build **Debug** (no optimization, debug symbols) |
| `make release` | Configure and build **Release** (optimized; strip symbols when possible) |

Debug tree: `build/debug`  
Release tree: `build/release`

The Debug configure step links `compile_commands.json` at the repo root for LSP.

### Windows note

The Makefile is the happy path on macOS/Linux. On Windows, either use a Unix-like
environment (MSYS2, WSL) or invoke CMake directly:

```bat
cmake -S . -B build/debug -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build/debug
```

## Run the sample app

The program entrypoint is always **`src/main.cpp`**.
Built executables land under **`build/<config>/bin/`** (never beside component
folders, so a project named like a component cannot collide).

After `make debug`:

```bash
./build/debug/bin/{ctx.name}
```

## Tests

```bash
make test
```

Runs CTest against the Debug build. Tests use **GoogleTest** and **GoogleMock**.

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
   add_subdirectory(calc)
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

Prefer the Makefile wrappers:

| Goal | Command |
|------|---------|
| Debug build | `make` / `make debug` |
| Release build | `make release` |
| Unit tests | `make test` |
| Benchmarks | `make bench` |
| Format | `make fmt` |
| API docs | `make doc` |
| ctags index | `make tags` (if enabled) |
| Clean | `make clean` |

- Builds are **out-of-source** under `build/`.
- After `make debug`, `compile_commands.json` at the repo root supports clangd/LSP.
- **Warnings are errors.** Fix warnings; do not silence them without strong reason.
- If present, `.ctags` + `make tags` produce a repo-root `tags` file for editors
  (Universal Ctags recommended).
- If present, `.github/workflows/ci.yml` is the multi-OS CI contract (Debug +
  Release, tests, benchmarks on Linux/macOS/Windows). Keep it green.
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
  "clangd.arguments": [
    "--compile-commands-dir=${workspaceFolder}",
    "--header-insertion=never"
  ],
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
      "dependsOn": "Configure Debug",
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

    defaults:
      run:
        shell: bash

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install CMake and Ninja
        uses: lukka/get-cmake@v4

      - name: Enable MSVC developer command prompt
        if: runner.os == 'Windows'
        uses: ilammy/msvc-dev-cmd@v1

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
          # Collect Google Benchmark binaries (handles --no-sample with none).
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

      - name: Upload Debug binaries
        uses: actions/upload-artifact@v4
        with:
          name: {ctx.name}-${{{{ matrix.os }}}}-debug
          path: build/debug/bin/*
          if-no-files-found: warn
          retention-days: 14

      - name: Upload Release binaries
        uses: actions/upload-artifact@v4
        with:
          name: {ctx.name}-${{{{ matrix.os }}}}-release
          path: build/release/bin/*
          if-no-files-found: warn
          retention-days: 14
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
    return """\
CompileFlags:
  CompilationDatabase: .
"""


def _doxyfile(ctx: _Context) -> str:
    return f"""\
# Doxyfile generated by cppboot — minimal professional defaults.
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


def _calc_header(ctx: _Context) -> str:
    return f"""\
#pragma once

/**
 * @file calc.hpp
 * @brief Trivial calculator type used as the sample library surface.
 */

namespace {ctx.namespace} {{

/**
 * @brief Integer calculator with basic arithmetic.
 *
 * This type is intentionally small: it demonstrates the library layer,
 * unit tests, mocks, and benchmarks produced by cppboot.
 */
class Calc {{
 public:
  /// Constructs a calculator with accumulator value zero.
  Calc() = default;

  /**
   * @brief Constructs a calculator with an initial accumulator value.
   * @param value Initial accumulator.
   */
  explicit Calc(int value);

  /**
   * @brief Adds @p x to the accumulator.
   * @param x Value to add.
   * @return Reference to this calculator.
   */
  Calc& Add(int x);

  /**
   * @brief Subtracts @p x from the accumulator.
   * @param x Value to subtract.
   * @return Reference to this calculator.
   */
  Calc& Sub(int x);

  /**
   * @brief Multiplies the accumulator by @p x.
   * @param x Multiplier.
   * @return Reference to this calculator.
   */
  Calc& Mul(int x);

  /**
   * @brief Returns the current accumulator value.
   */
  [[nodiscard]] int value() const;

 private:
  int value_{{0}};
}};

}}  // namespace {ctx.namespace}
"""


def _calc_source(ctx: _Context) -> str:
    return f"""\
#include "{ctx.namespace}/calc.hpp"

namespace {ctx.namespace} {{

Calc::Calc(int value) : value_(value) {{}}

Calc& Calc::Add(int x) {{
  value_ += x;
  return *this;
}}

Calc& Calc::Sub(int x) {{
  value_ -= x;
  return *this;
}}

Calc& Calc::Mul(int x) {{
  value_ *= x;
  return *this;
}}

int Calc::value() const {{ return value_; }}

}}  // namespace {ctx.namespace}
"""


def _calc_module(ctx: _Context) -> str:
    return f"""\
/**
 * @file calc.cppm
 * @brief C++20 module interface for the sample calculator.
 */

module;

export module {ctx.namespace}.calc;

/**
 * @brief Integer calculator with basic arithmetic.
 */
export namespace {ctx.namespace} {{

class Calc {{
 public:
  Calc() = default;
  explicit Calc(int value);

  Calc& Add(int x);
  Calc& Sub(int x);
  Calc& Mul(int x);

  [[nodiscard]] int value() const;

 private:
  int value_{{0}};
}};

}}  // namespace {ctx.namespace}

namespace {ctx.namespace} {{

Calc::Calc(int value) : value_(value) {{}}

Calc& Calc::Add(int x) {{
  value_ += x;
  return *this;
}}

Calc& Calc::Sub(int x) {{
  value_ -= x;
  return *this;
}}

Calc& Calc::Mul(int x) {{
  value_ *= x;
  return *this;
}}

int Calc::value() const {{ return value_; }}

}}  // namespace {ctx.namespace}
"""


def _library_anchor_cpp(ctx: _Context) -> str:
    return f"""\
/**
 * @file library_anchor.cpp
 * @brief Placeholder translation unit so the library target is non-empty.
 *
 * Generated because this project was created with --no-sample. Delete this file
 * and its target_sources entry in src/CMakeLists.txt when you add a real
 * component under src/<component>/.
 */

namespace {ctx.namespace} {{
namespace {{

// Ensures the TU is not completely empty under pedantic toolchains.
constexpr int kLibraryAnchor = 0;

}}  // namespace

// ODR-used from main so the anchor is not stripped as unused.
int LibraryAnchor() {{ return kLibraryAnchor; }}

}}  // namespace {ctx.namespace}
"""


def _main_cpp(ctx: _Context) -> str:
    if not ctx.with_sample:
        return f"""\
/**
 * @file main.cpp
 * @brief Program entrypoint (always src/main.cpp in cppboot projects).
 *
 * Keep this file thin: parse args / wire dependencies, then call library code.
 * Sample library code was omitted (--no-sample); add components under src/.
 */

#include <iostream>

namespace {ctx.namespace} {{
int LibraryAnchor();
}}  // namespace {ctx.namespace}

/**
 * @brief Program entry.
 * @return Exit status.
 */
int main() {{
  // Touch the library so the empty-project anchor links cleanly.
  static_cast<void>({ctx.namespace}::LibraryAnchor());
  std::cout << "{ctx.name}: ready. Add components under src/ "
            << "(see README.md / AGENTS.md).\\n";
  return 0;
}}
"""

    if ctx.with_modules:
        return f"""\
/**
 * @file main.cpp
 * @brief Program entrypoint (always src/main.cpp in cppboot projects).
 *
 * Keep this file thin: parse args / wire dependencies, then call library code.
 */

import {ctx.namespace}.calc;

#include <iostream>

/**
 * @brief Program entry.
 * @return Exit status.
 */
int main() {{
  {ctx.namespace}::Calc calc(2);
  calc.Add(3).Mul(4);
  std::cout << "{ctx.name} sample: " << calc.value() << '\\n';
  return 0;
}}
"""
    return f"""\
/**
 * @file main.cpp
 * @brief Program entrypoint (always src/main.cpp in cppboot projects).
 *
 * Keep this file thin: parse args / wire dependencies, then call library code.
 */

#include "{ctx.namespace}/calc.hpp"

#include <iostream>

/**
 * @brief Program entry.
 * @return Exit status.
 */
int main() {{
  {ctx.namespace}::Calc calc(2);
  calc.Add(3).Mul(4);
  std::cout << "{ctx.name} sample: " << calc.value() << '\\n';
  return 0;
}}
"""


def _calc_test(ctx: _Context) -> str:
    if ctx.with_modules:
        includes = f"import {ctx.namespace}.calc;\n\n#include <gtest/gtest.h>"
    else:
        includes = (
            f'#include "{ctx.namespace}/calc.hpp"\n\n'
            "#include <gtest/gtest.h>"
        )
    return f"""\
/**
 * @file calc_test.cpp
 * @brief Unit tests for {ctx.namespace}::Calc.
 */

{includes}

namespace {{

TEST(CalcTest, DefaultIsZero) {{
  {ctx.namespace}::Calc calc;
  EXPECT_EQ(calc.value(), 0);
}}

TEST(CalcTest, AddSubMul) {{
  {ctx.namespace}::Calc calc(10);
  calc.Add(5).Sub(3).Mul(2);
  EXPECT_EQ(calc.value(), 24);
}}

}}  // namespace
"""


def _mock_calc_test(ctx: _Context) -> str:
    # GoogleMock example: mock a dependency interface and exercise collaboration.
    if ctx.with_modules:
        calc_import = f"import {ctx.namespace}.calc;\n\n"
        # For modules, we still define the mockable interface in the test TU.
        calc_include = ""
    else:
        calc_import = ""
        calc_include = f'#include "{ctx.namespace}/calc.hpp"\n\n'
    return f"""\
/**
 * @file mock_calc_test.cpp
 * @brief GoogleMock example around a calculator-facing interface.
 */

{calc_import}{calc_include}#include <gmock/gmock.h>
#include <gtest/gtest.h>

namespace {{

/**
 * @brief Narrow interface used to demonstrate GoogleMock.
 */
class Adder {{
 public:
  virtual ~Adder() = default;
  virtual int Add(int a, int b) const = 0;
}};

class MockAdder : public Adder {{
 public:
  MOCK_METHOD(int, Add, (int a, int b), (const, override));
}};

/**
 * @brief Uses an Adder to combine the calculator accumulator with a delta.
 */
int CombineWithAdder(const {ctx.namespace}::Calc& calc, const Adder& adder, int delta) {{
  return adder.Add(calc.value(), delta);
}}

using ::testing::Return;

TEST(MockCalcTest, UsesMockAdder) {{
  {ctx.namespace}::Calc calc(7);
  MockAdder mock_adder;
  EXPECT_CALL(mock_adder, Add(7, 3)).WillOnce(Return(10));
  EXPECT_EQ(CombineWithAdder(calc, mock_adder, 3), 10);
}}

}}  // namespace
"""


def _calc_bench(ctx: _Context) -> str:
    if ctx.with_modules:
        includes = f"import {ctx.namespace}.calc;\n\n#include <benchmark/benchmark.h>"
    else:
        includes = (
            f'#include "{ctx.namespace}/calc.hpp"\n\n'
            "#include <benchmark/benchmark.h>"
        )
    return f"""\
/**
 * @file calc_bench.cpp
 * @brief Microbenchmarks for {ctx.namespace}::Calc.
 */

{includes}

namespace {{

void BM_CalcAdd(benchmark::State& state) {{
  {ctx.namespace}::Calc calc;
  for (auto _ : state) {{
    calc.Add(1);
    benchmark::DoNotOptimize(calc.value());
  }}
}}
BENCHMARK(BM_CalcAdd);

void BM_CalcMul(benchmark::State& state) {{
  for (auto _ : state) {{
    {ctx.namespace}::Calc calc(2);
    calc.Mul(3).Mul(5);
    benchmark::DoNotOptimize(calc.value());
  }}
}}
BENCHMARK(BM_CalcMul);

}}  // namespace
"""

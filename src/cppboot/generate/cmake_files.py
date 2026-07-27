"""CMakeLists and cmake/ module templates for generated projects."""

from __future__ import annotations

from cppboot.generate.context import Context
from cppboot.generate.deps import (
    BENCHMARK_TAG,
    CLI11_TAG,
    GOOGLETEST_TAG,
    NLOHMANN_JSON_TAG,
    SPDLOG_TAG,
)

# Template helpers historically used _Context; alias for readability.
_Context = Context


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
        # BASE_DIRS must include the generated .cppm path; CMake rejects FILE_SET
        # members outside the set's base directories (often defaults to this dir).
        return f"""\
# version component (C++20 module) — generated from cmake/version.cppm.in + VERSION.
# Generated unit lives under the build tree; BASE_DIRS must cover that path.
target_sources(${{PROJECT_NAME}}_lib
  PUBLIC
    FILE_SET CXX_MODULES
    BASE_DIRS
      ${{{ctx.macro}_GENERATED_DIR}}
    FILES
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

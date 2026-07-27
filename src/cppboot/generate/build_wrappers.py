"""Makefile and Windows build.bat wrappers around CMake."""

from __future__ import annotations

from cppboot.generate.context import Context

_Context = Context


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

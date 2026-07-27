"""Editor, IDE, and Codespaces templates for generated projects."""

from __future__ import annotations

from cppboot.generate.context import Context

_Context = Context


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

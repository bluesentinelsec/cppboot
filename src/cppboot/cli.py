"""Command-line interface for cppboot."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from cppboot import __version__
from cppboot.generator import ProjectOptions, generate_project
from cppboot.licenses import DEFAULT_LICENSE, LICENSE_CHOICES


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="cppboot",
        description=(
            "Bootstrap a professional-grade C++ project environment "
            "(CMake, tests, benchmarks, format, docs)."
        ),
    )
    parser.add_argument(
        "-n",
        "--name",
        help="Output project / program name. Prompted if omitted.",
    )
    parser.add_argument(
        "--license",
        default=DEFAULT_LICENSE,
        metavar="ID",
        help=(
            "License identifier "
            f"(default: {DEFAULT_LICENSE}; choices: {', '.join(LICENSE_CHOICES)})"
        ),
    )
    parser.add_argument(
        "--build-system",
        default="cmake",
        choices=["cmake"],
        help="Build system to scaffold (only cmake is supported).",
    )
    parser.add_argument(
        "--with-modules",
        action="store_true",
        help="Structure the project around C++20 modules instead of classic headers.",
    )
    parser.add_argument(
        "--shared",
        action="store_true",
        help="Build the library as a shared library (default: static).",
    )
    parser.add_argument(
        "--vim",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write a minimal project-local .vimrc (default: on). Use --no-vim to skip.",
    )
    parser.add_argument(
        "--ctags",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Write Universal Ctags config and make tags target (default: on). "
            "Use --no-ctags to skip."
        ),
    )
    parser.add_argument(
        "--vscode",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Write VS Code config + CMakePresets (default: on). "
            "Use --no-vscode to skip."
        ),
    )
    parser.add_argument(
        "--github-actions",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Write cross-platform GitHub Actions CI (default: on). "
            "Use --no-github-actions to skip."
        ),
    )
    parser.add_argument(
        "--codespaces",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Write GitHub Codespaces / Dev Container config (default: on). "
            "Use --no-codespaces to skip."
        ),
    )
    parser.add_argument(
        "--github",
        action="store_true",
        default=False,
        help=(
            "Create a public GitHub upstream repository using the gh client "
            "(default: off; opt-in only)."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Parent directory for the new project (default: current directory).",
    )
    return parser


def _prompt_name() -> str:
    while True:
        try:
            value = input("Project name: ").strip()
        except EOFError as exc:
            raise SystemExit("project name is required") from exc
        if value:
            return value
        print("Name must not be empty.", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    name = args.name or _prompt_name()

    options = ProjectOptions(
        name=name,
        root=args.output_dir.resolve(),
        license_id=args.license,
        build_system=args.build_system,
        with_modules=args.with_modules,
        shared_library=args.shared,
        with_vim=args.vim,
        with_ctags=args.ctags,
        with_vscode=args.vscode,
        with_codespaces=args.codespaces,
        create_github=args.github,
        with_github_actions=args.github_actions,
        verbose=args.verbose,
    )

    try:
        result = generate_project(options)
    except (ValueError, FileExistsError, OSError) as exc:
        logging.error("%s", exc)
        return 1

    print(f"Created project at {result.project_dir}")
    print(f"  files: {len(result.files_written)}")
    print(f"  license source: {result.license_source}")
    print(f"  formatted (make fmt): {'yes' if result.formatted else 'no'}")
    print(f"  git initial commit: {'yes' if result.git_initialized else 'no'}")
    print(f"  vim: {'yes' if options.with_vim else 'no'}")
    print(f"  ctags: {'yes' if options.with_ctags else 'no'}")
    print(f"  vscode: {'yes' if options.with_vscode else 'no'}")
    print(f"  github-actions: {'yes' if options.with_github_actions else 'no'}")
    print(f"  codespaces: {'yes' if options.with_codespaces else 'no'}")
    if options.create_github:
        print(f"  github remote: {'yes' if result.github_created else 'failed'}")
    print()
    print("Scaffold is formatted and committed — ready for real work.")
    print("Next steps:")
    print(f"  cd {result.project_dir}")
    if options.with_vscode:
        print("  code .   # install recommended extensions when prompted")
    print("  make")
    print("  make test")
    if options.with_ctags:
        print("  make tags   # requires universal-ctags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

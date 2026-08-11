"""Unit tests for the cppboot CLI parser and main() wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from cppboot.cli import build_parser, main
from cppboot.generator import GenerateResult, ProjectOptions


def test_parser_defaults() -> None:
    args = build_parser().parse_args(["-n", "demo"])
    assert args.name == "demo"
    assert args.vim is True
    assert args.ctags is True
    assert args.vscode is True
    assert args.github_actions is True
    assert args.codespaces is True
    assert args.git is True
    assert args.fmt is True
    assert args.community_docs is True
    assert args.github is False
    assert args.with_modules is False
    assert args.shared is False
    assert args.with_android_ci is False


def test_parser_opt_outs() -> None:
    args = build_parser().parse_args(
        [
            "-n",
            "demo",
            "--no-vim",
            "--no-ctags",
            "--no-vscode",
            "--no-github-actions",
            "--no-codespaces",
            "--no-git",
            "--no-fmt",
            "--no-community-docs",
        ]
    )
    assert args.vim is False
    assert args.ctags is False
    assert args.vscode is False
    assert args.github_actions is False
    assert args.codespaces is False
    assert args.git is False
    assert args.fmt is False
    assert args.community_docs is False


def test_help_lists_opt_outs_not_positive_toggles() -> None:
    """Opinionated features are default-on; only --no-* should appear in help."""
    parser = build_parser()
    option_strings = {opt for action in parser._actions for opt in action.option_strings}
    for opt_out in (
        "--no-vim",
        "--no-ctags",
        "--no-vscode",
        "--no-github-actions",
        "--no-codespaces",
        "--no-git",
        "--no-fmt",
        "--no-community-docs",
    ):
        assert opt_out in option_strings
    # Positive mirrors must not exist (defaults are always on).
    for positive in ("--vim", "--ctags", "--vscode", "--git", "--fmt", "--community-docs"):
        assert positive not in option_strings
    # Opt-in flags remain.
    assert "--github" in option_strings
    assert "--with-modules" in option_strings
    assert "--with-android-ci" in option_strings


def test_positive_toggle_flags_are_rejected() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["-n", "demo", "--vim"])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["-n", "demo", "--fmt"])
    # Note: argparse may treat "--git" as an abbreviation of "--github" when
    # allow_abbrev is true; the explicit option is only "--no-git".


def test_parser_opt_in_features() -> None:
    args = build_parser().parse_args(["-n", "demo", "--with-modules", "--shared", "--github"])
    assert args.with_modules is True
    assert args.shared is True
    assert args.github is True
    assert args.with_android_ci is False


def test_parser_android_ci_opt_in() -> None:
    args = build_parser().parse_args(["-n", "demo", "--with-android-ci"])
    assert args.with_android_ci is True


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--version"])
    assert exc.value.code == 0


def test_main_wires_options(tmp_path: Path) -> None:
    captured: dict[str, ProjectOptions] = {}

    def fake_generate(options: ProjectOptions) -> GenerateResult:
        captured["opts"] = options
        return GenerateResult(
            project_dir=tmp_path / options.name,
            files_written=[],
            git_initialized=False,
            github_created=False,
            license_source="offline-fallback:mit",
            formatted=False,
        )

    with patch("cppboot.cli.generate_project", side_effect=fake_generate):
        rc = main(
            [
                "-n",
                "wired",
                "--output-dir",
                str(tmp_path),
                "--no-git",
                "--no-fmt",
                "--no-community-docs",
                "--no-vim",
                "--with-android-ci",
                "--license",
                "mit",
            ]
        )
    assert rc == 0
    opts = captured["opts"]
    assert opts.name == "wired"
    assert opts.with_git is False
    assert opts.with_fmt is False
    assert opts.with_community_docs is False
    assert opts.with_vim is False
    assert opts.with_android_ci is True
    assert opts.license_id == "mit"


def test_main_invalid_name_returns_one(tmp_path: Path) -> None:
    rc = main(["-n", "bad name", "--output-dir", str(tmp_path), "--no-git", "--no-fmt"])
    assert rc == 1


def test_main_prompts_when_name_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt="": "prompted_app")

    def fake_generate(options: ProjectOptions) -> GenerateResult:
        assert options.name == "prompted_app"
        return GenerateResult(
            project_dir=tmp_path / "prompted_app",
            files_written=[],
            git_initialized=False,
            github_created=False,
            license_source="x",
            formatted=False,
        )

    with patch("cppboot.cli.generate_project", side_effect=fake_generate):
        rc = main(["--output-dir", str(tmp_path), "--no-git", "--no-fmt"])
    assert rc == 0

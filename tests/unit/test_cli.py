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


def test_parser_opt_in_features() -> None:
    args = build_parser().parse_args(
        ["-n", "demo", "--with-modules", "--shared", "--github"]
    )
    assert args.with_modules is True
    assert args.shared is True
    assert args.github is True


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

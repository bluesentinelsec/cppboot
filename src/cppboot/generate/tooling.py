"""Post-scaffold tooling: format, git init, optional gh repo create."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


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

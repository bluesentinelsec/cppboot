"""Integrity checks for the bundled Android Gradle wrapper assets."""

from __future__ import annotations

import hashlib
from importlib import resources

from cppboot.generate.android import GRADLE_VERSION, GRADLE_WRAPPER_JAR_SHA256


def _asset(name: str) -> bytes:
    return resources.files("cppboot").joinpath(f"data/android/{name}").read_bytes()


def test_gradle_wrapper_jar_bundled_and_unmodified() -> None:
    jar = _asset("gradle-wrapper.jar")
    assert jar, "bundled gradle-wrapper.jar must not be empty"
    assert hashlib.sha256(jar).hexdigest() == GRADLE_WRAPPER_JAR_SHA256


def test_gradle_wrapper_scripts_bundled() -> None:
    gradlew = _asset("gradlew").decode("utf-8")
    gradlew_bat = _asset("gradlew.bat").decode("utf-8")
    assert gradlew.startswith("#!/bin/sh")
    assert "org.gradle.wrapper.GradleWrapperMain" in gradlew
    assert "gradle-wrapper.jar" in gradlew
    assert "org.gradle.wrapper.GradleWrapperMain" in gradlew_bat
    assert "gradle-wrapper.jar" in gradlew_bat


def test_pinned_gradle_version_is_semverish() -> None:
    parts = GRADLE_VERSION.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts)

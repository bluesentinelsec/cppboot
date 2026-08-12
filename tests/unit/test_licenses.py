"""Unit tests for license normalization and offline fetch."""

from __future__ import annotations

import pytest

from cppboot.licenses import (
    DEFAULT_LICENSE,
    LICENSE_CHOICES,
    fetch_license_text,
    normalize_license_id,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("apache-2.0", "apache-2.0"),
        ("Apache", "apache-2.0"),
        ("MIT", "mit"),
        ("bsd", "bsd-3-clause"),
        ("gpl3", "gpl-3.0"),
        ("mpl2", "mpl-2.0"),
        ("zlib", "zlib"),
        ("Zlib", "zlib"),
        ("zlib/libpng", "zlib"),
    ],
)
def test_normalize_license_id(raw: str, expected: str) -> None:
    assert normalize_license_id(raw) == expected


def test_normalize_unknown_raises() -> None:
    with pytest.raises(ValueError, match="unsupported license"):
        normalize_license_id("proprietary-secret")


def test_default_license_is_choice() -> None:
    assert DEFAULT_LICENSE in LICENSE_CHOICES


def test_offline_mit_contains_year_and_holder() -> None:
    result = fetch_license_text(
        "mit",
        year="2026",
        holder="Acme Corp",
        offline=True,
    )
    assert result.license_id == "mit"
    assert "offline" in result.source
    assert "2026" in result.text
    assert "Acme Corp" in result.text
    assert "MIT License" in result.text


def test_offline_apache_has_body() -> None:
    result = fetch_license_text("apache-2.0", year="2026", holder="x", offline=True)
    assert "Apache License" in result.text
    assert result.source.startswith("offline-")


def test_offline_zlib_has_full_body() -> None:
    result = fetch_license_text("zlib", year="2026", holder="Acme Corp", offline=True)
    assert result.license_id == "zlib"
    assert result.source == "offline-fallback:zlib"
    assert "zlib License" in result.text
    assert "2026" in result.text
    assert "Acme Corp" in result.text
    assert "must not be misrepresented" in result.text


def test_offline_gpl_uses_stub() -> None:
    """GPL has no embedded full text; offline mode must still return a stub."""
    result = fetch_license_text("gpl-3.0", year="2026", holder="x", offline=True)
    assert result.license_id == "gpl-3.0"
    assert "2026" in result.text
    assert "offline" in result.source


def test_offline_does_not_call_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("network should not be used in offline mode")

    monkeypatch.setattr("cppboot.licenses._download_text", boom)
    fetch_license_text("mit", year="2026", holder="h", offline=True)

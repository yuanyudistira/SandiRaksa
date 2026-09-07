"""Tests for version module."""

from sandiraksa.version import __version__, __version_info__


def test_version_format():
    """Version should be a valid semver string."""
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_version_info_tuple():
    """Version info should be a tuple of integers."""
    assert isinstance(__version_info__, tuple)
    assert len(__version_info__) == 3
    assert all(isinstance(v, int) for v in __version_info__)


def test_version_consistency():
    """Version string and tuple should be consistent."""
    expected = tuple(int(x) for x in __version__.split("."))
    assert __version_info__ == expected

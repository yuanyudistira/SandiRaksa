"""Version information for SandiRaksa."""

__version__ = "1.0.4"
__version_info__ = tuple(int(x) for x in __version__.split("."))

# Build metadata - populated during release build
BUILD_NUMBER: str | None = None
BUILD_DATE: str | None = None
GIT_COMMIT: str | None = None

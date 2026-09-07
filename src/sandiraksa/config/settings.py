"""
Application settings and configuration management.

This module provides typed configuration using Pydantic models,
supporting multiple configuration sources with proper precedence.
"""

from __future__ import annotations

import tomllib
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Self

from platformdirs import PlatformDirs
from pydantic import BaseModel, Field, field_validator


# Application directory manager
_platform_dirs = PlatformDirs(
    appname="SandiRaksa",
    appauthor="SandiRaksa",
    ensure_exists=True,
)


class Language(str, Enum):
    """Supported UI languages."""

    INDONESIAN = "id-ID"
    ENGLISH = "en-US"


class RetentionPolicy(str, Enum):
    """Mapping retention policies."""

    UNTIL_DELETED = "until_deleted"
    DAYS_7 = "7_days"
    DAYS_30 = "30_days"
    DAYS_90 = "90_days"
    SESSION_ONLY = "session_only"


class LogLevel(str, Enum):
    """Log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ProductConfig(BaseModel):
    """Product identity and branding configuration."""

    name: str = "SandiRaksa"
    display_name: str = "SandiRaksa"
    company: str = "SandiRaksa Team"
    description: str = "Local Privacy Gateway for AI"
    tagline_id: str = "Lindungi Data Sebelum Berbagi ke AI"
    tagline_en: str = "Local Privacy Gateway for AI"


class UrlsConfig(BaseModel):
    """External URLs configuration."""

    support_email: str = "support@sandiraksa.example.com"
    support_url: str = "https://sandiraksa.example.com/support"
    documentation_url: str = "https://sandiraksa.example.com/docs"
    privacy_url: str = "https://sandiraksa.example.com/privacy"
    donation_url: str = "https://sandiraksa.example.com/donate"
    release_url: str = "https://sandiraksa.example.com/download"
    homepage: str = "https://sandiraksa.example.com"


class DefaultsConfig(BaseModel):
    """Default application settings."""

    language: Language = Language.INDONESIAN
    reversible_enabled: bool = True
    retention_policy: RetentionPolicy = RetentionPolicy.UNTIL_DELETED
    remember_source_paths: bool = False
    default_profile: str = "standard_pii"


class LimitsConfig(BaseModel):
    """Resource limits configuration."""

    max_file_size_bytes: int = Field(default=104857600, ge=1048576)  # Min 1MB
    max_expanded_size_bytes: int = Field(default=524288000, ge=10485760)  # Min 10MB
    max_zip_entries: int = Field(default=10000, ge=100)
    max_projects: int = Field(default=1000, ge=1)
    detection_batch_segments: int = Field(default=1000, ge=100)
    detection_batch_chars: int = Field(default=500000, ge=10000)
    large_file_threshold_bytes: int = Field(default=52428800, ge=1048576)
    large_workbook_cells_threshold: int = Field(default=500000, ge=10000)


class SecurityConfig(BaseModel):
    """Security-related configuration."""

    pbkdf2_iterations: int = Field(default=600000, ge=100000)
    min_key_bits: int = Field(default=256, ge=128)
    secure_memory: bool = True
    xml_max_entity_expansions: int = Field(default=0, ge=0)
    xml_forbid_dtd: bool = True
    xml_forbid_external_entities: bool = True


class LoggingConfig(BaseModel):
    """Logging configuration."""

    default_level: LogLevel = LogLevel.INFO
    pii_redaction: bool = True
    max_log_size_bytes: int = Field(default=10485760, ge=1048576)
    log_backup_count: int = Field(default=5, ge=1)


class UserSettings(BaseModel):
    """User-configurable settings (persisted locally)."""

    language: Language = Language.INDONESIAN
    theme: str = "system"  # system, light, dark
    default_output_folder: str | None = None
    default_reversible_mode: bool = True
    default_retention_policy: RetentionPolicy = RetentionPolicy.UNTIL_DELETED
    default_profile: str = "standard_pii"
    remember_window_state: bool = True
    window_geometry: dict[str, int] | None = None
    recent_projects: list[str] = Field(default_factory=list)
    max_recent_projects: int = Field(default=10, ge=1, le=50)

    @field_validator("recent_projects")
    @classmethod
    def limit_recent_projects(cls, v: list[str], info: Any) -> list[str]:
        """Limit recent projects list size."""
        max_size = info.data.get("max_recent_projects", 10)
        return v[:max_size]

    def add_recent_project(self, project_id: str) -> None:
        """Add a project to recent list, maintaining order and limit."""
        if project_id in self.recent_projects:
            self.recent_projects.remove(project_id)
        self.recent_projects.insert(0, project_id)
        self.recent_projects = self.recent_projects[: self.max_recent_projects]


class AppConfig(BaseModel):
    """Complete application configuration."""

    product: ProductConfig = Field(default_factory=ProductConfig)
    urls: UrlsConfig = Field(default_factory=UrlsConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def from_toml(cls, path: Path) -> Self:
        """Load configuration from a TOML file."""
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.model_validate(data)

    @classmethod
    def load_bundled(cls) -> Self:
        """Load the bundled product.toml configuration."""
        bundled_path = Path(__file__).parent / "product.toml"
        if bundled_path.exists():
            return cls.from_toml(bundled_path)
        return cls()


class AppPaths:
    """Application paths manager using platformdirs."""

    @property
    def data_dir(self) -> Path:
        """User data directory for database and vault."""
        return Path(_platform_dirs.user_data_dir)

    @property
    def config_dir(self) -> Path:
        """User configuration directory for settings."""
        return Path(_platform_dirs.user_config_dir)

    @property
    def cache_dir(self) -> Path:
        """Cache directory for temporary data."""
        return Path(_platform_dirs.user_cache_dir)

    @property
    def log_dir(self) -> Path:
        """Log directory."""
        return Path(_platform_dirs.user_log_dir)

    @property
    def database_path(self) -> Path:
        """Path to the main SQLite database."""
        return self.data_dir / "sandiraksa.db"

    @property
    def settings_path(self) -> Path:
        """Path to user settings file."""
        return self.config_dir / "settings.json"

    @property
    def vault_dir(self) -> Path:
        """Directory for encrypted vault files."""
        vault_path = self.data_dir / "vault"
        vault_path.mkdir(parents=True, exist_ok=True)
        return vault_path

    @property
    def temp_dir(self) -> Path:
        """Temporary directory for processing."""
        temp_path = self.cache_dir / "temp"
        temp_path.mkdir(parents=True, exist_ok=True)
        return temp_path

    @property
    def profiles_dir(self) -> Path:
        """Directory for custom privacy profiles."""
        profiles_path = self.config_dir / "profiles"
        profiles_path.mkdir(parents=True, exist_ok=True)
        return profiles_path

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)


class SettingsManager:
    """Manages loading and saving of user settings."""

    def __init__(self, paths: AppPaths | None = None) -> None:
        self._paths = paths or AppPaths()
        self._settings: UserSettings | None = None

    @property
    def settings(self) -> UserSettings:
        """Get current user settings, loading if necessary."""
        if self._settings is None:
            self._settings = self.load()
        return self._settings

    def load(self) -> UserSettings:
        """Load user settings from disk."""
        import json

        settings_path = self._paths.settings_path
        if settings_path.exists():
            try:
                with open(settings_path, encoding="utf-8") as f:
                    data = json.load(f)
                return UserSettings.model_validate(data)
            except Exception:
                # If settings are corrupted, return defaults
                pass
        return UserSettings()

    def save(self, settings: UserSettings | None = None) -> None:
        """Save user settings to disk."""
        import json

        if settings is not None:
            self._settings = settings
        if self._settings is None:
            return

        settings_path = self._paths.settings_path
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        # Write atomically
        temp_path = settings_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self._settings.model_dump(mode="json"), f, indent=2)
        temp_path.replace(settings_path)

    def update(self, **kwargs: Any) -> UserSettings:
        """Update specific settings values."""
        current = self.settings.model_dump()
        current.update(kwargs)
        self._settings = UserSettings.model_validate(current)
        self.save()
        return self._settings


# Global instances
@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    """Get the application configuration (cached)."""
    return AppConfig.load_bundled()


@lru_cache(maxsize=1)
def get_app_paths() -> AppPaths:
    """Get the application paths manager (cached)."""
    return AppPaths()


# Singleton settings manager
_settings_manager: SettingsManager | None = None


def get_settings_manager() -> SettingsManager:
    """Get the settings manager singleton."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager


def get_user_settings() -> UserSettings:
    """Get current user settings."""
    return get_settings_manager().settings

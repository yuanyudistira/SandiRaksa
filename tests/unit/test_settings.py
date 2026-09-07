"""Tests for settings and configuration."""

import json
import tempfile
from pathlib import Path

import pytest

from sandiraksa.config.settings import (
    AppConfig,
    AppPaths,
    DefaultsConfig,
    Language,
    LimitsConfig,
    LogLevel,
    LoggingConfig,
    ProductConfig,
    RetentionPolicy,
    SecurityConfig,
    SettingsManager,
    UrlsConfig,
    UserSettings,
    get_app_config,
)


class TestProductConfig:
    """Tests for ProductConfig."""

    def test_default_values(self):
        """ProductConfig should have sensible defaults."""
        config = ProductConfig()
        assert config.name == "SandiRaksa"
        assert config.display_name == "SandiRaksa"
        assert "AI" in config.tagline_en

    def test_custom_values(self):
        """ProductConfig should accept custom values."""
        config = ProductConfig(
            name="CustomApp",
            company="Custom Company"
        )
        assert config.name == "CustomApp"
        assert config.company == "Custom Company"


class TestUrlsConfig:
    """Tests for UrlsConfig."""

    def test_default_urls(self):
        """UrlsConfig should have default URLs."""
        config = UrlsConfig()
        assert config.support_email.endswith("@sandiraksa.example.com")
        assert config.support_url.startswith("https://")


class TestDefaultsConfig:
    """Tests for DefaultsConfig."""

    def test_language_default_indonesian(self):
        """Default language should be Indonesian."""
        config = DefaultsConfig()
        assert config.language == Language.INDONESIAN

    def test_reversible_default_true(self):
        """Reversible mode should be ON by default."""
        config = DefaultsConfig()
        assert config.reversible_enabled is True

    def test_retention_default_until_deleted(self):
        """Default retention should be until deleted."""
        config = DefaultsConfig()
        assert config.retention_policy == RetentionPolicy.UNTIL_DELETED


class TestLimitsConfig:
    """Tests for LimitsConfig."""

    def test_default_limits(self):
        """LimitsConfig should have sensible defaults."""
        config = LimitsConfig()
        assert config.max_file_size_bytes == 104857600  # 100 MB
        assert config.max_projects == 1000

    def test_minimum_limits(self):
        """Limits should enforce minimums."""
        with pytest.raises(ValueError):
            LimitsConfig(max_file_size_bytes=100)  # Too small

    def test_valid_custom_limits(self):
        """Custom limits within bounds should work."""
        config = LimitsConfig(
            max_file_size_bytes=50000000,
            max_projects=500
        )
        assert config.max_file_size_bytes == 50000000


class TestSecurityConfig:
    """Tests for SecurityConfig."""

    def test_default_security(self):
        """Security defaults should be conservative."""
        config = SecurityConfig()
        assert config.pbkdf2_iterations >= 100000
        assert config.min_key_bits >= 256
        assert config.xml_forbid_dtd is True
        assert config.xml_forbid_external_entities is True

    def test_minimum_iterations(self):
        """PBKDF2 iterations should have minimum."""
        with pytest.raises(ValueError):
            SecurityConfig(pbkdf2_iterations=1000)


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_default_logging(self):
        """Logging defaults should be safe."""
        config = LoggingConfig()
        assert config.default_level == LogLevel.INFO
        assert config.pii_redaction is True


class TestUserSettings:
    """Tests for UserSettings."""

    def test_default_settings(self):
        """UserSettings should have sensible defaults."""
        settings = UserSettings()
        assert settings.language == Language.INDONESIAN
        assert settings.default_reversible_mode is True
        assert settings.recent_projects == []

    def test_add_recent_project(self):
        """Adding recent project should maintain order and limit."""
        settings = UserSettings(max_recent_projects=3)
        
        settings.add_recent_project("proj1")
        settings.add_recent_project("proj2")
        settings.add_recent_project("proj3")
        
        assert settings.recent_projects == ["proj3", "proj2", "proj1"]
        
        settings.add_recent_project("proj4")
        assert settings.recent_projects == ["proj4", "proj3", "proj2"]
        assert "proj1" not in settings.recent_projects

    def test_add_duplicate_project(self):
        """Adding existing project should move it to front."""
        settings = UserSettings()
        settings.add_recent_project("proj1")
        settings.add_recent_project("proj2")
        settings.add_recent_project("proj1")
        
        assert settings.recent_projects[0] == "proj1"
        assert settings.recent_projects.count("proj1") == 1


class TestAppConfig:
    """Tests for AppConfig."""

    def test_default_config(self):
        """AppConfig should have all sections with defaults."""
        config = AppConfig()
        assert isinstance(config.product, ProductConfig)
        assert isinstance(config.urls, UrlsConfig)
        assert isinstance(config.defaults, DefaultsConfig)
        assert isinstance(config.limits, LimitsConfig)
        assert isinstance(config.security, SecurityConfig)
        assert isinstance(config.logging, LoggingConfig)

    def test_load_bundled(self):
        """Should load bundled product.toml."""
        config = AppConfig.load_bundled()
        assert config.product.name == "SandiRaksa"

    def test_from_toml(self):
        """Should load from TOML file."""
        toml_content = """
[product]
name = "TestApp"
company = "Test Company"

[defaults]
language = "en-US"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            temp_path = Path(f.name)

        try:
            config = AppConfig.from_toml(temp_path)
            assert config.product.name == "TestApp"
            assert config.defaults.language == Language.ENGLISH
        finally:
            temp_path.unlink()


class TestAppPaths:
    """Tests for AppPaths."""

    def test_paths_are_absolute(self):
        """All paths should be absolute."""
        paths = AppPaths()
        assert paths.data_dir.is_absolute()
        assert paths.config_dir.is_absolute()
        assert paths.database_path.is_absolute()

    def test_database_path_extension(self):
        """Database path should have .db extension."""
        paths = AppPaths()
        assert paths.database_path.suffix == ".db"

    def test_settings_path_extension(self):
        """Settings path should have .json extension."""
        paths = AppPaths()
        assert paths.settings_path.suffix == ".json"


class TestSettingsManager:
    """Tests for SettingsManager."""

    def test_load_default_when_no_file(self):
        """Should return defaults when settings file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock AppPaths
            class MockPaths:
                settings_path = Path(tmpdir) / "nonexistent" / "settings.json"

            manager = SettingsManager(MockPaths())
            settings = manager.load()
            
            assert settings.language == Language.INDONESIAN

    def test_save_and_load(self):
        """Should save and load settings correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            class MockPaths:
                settings_path = Path(tmpdir) / "settings.json"

            manager = SettingsManager(MockPaths())
            
            # Save custom settings
            custom_settings = UserSettings(
                language=Language.ENGLISH,
                theme="dark"
            )
            manager.save(custom_settings)
            
            # Verify file exists
            assert MockPaths.settings_path.exists()
            
            # Load and verify
            manager2 = SettingsManager(MockPaths())
            loaded = manager2.load()
            
            assert loaded.language == Language.ENGLISH
            assert loaded.theme == "dark"

    def test_update_settings(self):
        """Should update specific settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            class MockPaths:
                settings_path = Path(tmpdir) / "settings.json"

            manager = SettingsManager(MockPaths())
            
            # Update specific fields
            updated = manager.update(language=Language.ENGLISH, theme="light")
            
            assert updated.language == Language.ENGLISH
            assert updated.theme == "light"
            assert updated.default_reversible_mode is True  # Unchanged


class TestGetAppConfig:
    """Tests for get_app_config function."""

    def test_returns_config(self):
        """get_app_config should return AppConfig instance."""
        config = get_app_config()
        assert isinstance(config, AppConfig)

    def test_cached(self):
        """get_app_config should return same instance."""
        config1 = get_app_config()
        config2 = get_app_config()
        assert config1 is config2

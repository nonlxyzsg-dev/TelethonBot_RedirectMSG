"""Тесты загрузки конфига и миграции из config.json."""

from __future__ import annotations

import json
import os

import pytest

from bot.config import (
    Settings,
    _is_missing,
    _to_int,
    load_settings,
    migrate_legacy_if_needed,
)


class TestHelpers:
    def test_is_missing_none(self):
        assert _is_missing(None) is True

    def test_is_missing_empty_string(self):
        assert _is_missing("") is True
        assert _is_missing("   ") is True

    def test_is_missing_zero_is_not_missing(self):
        """Регрессия: в старом коде not value ломался на 0."""
        assert _is_missing(0) is False

    def test_is_missing_real_string(self):
        assert _is_missing("x") is False

    def test_to_int_positive(self):
        assert _to_int("42", "x") == 42

    def test_to_int_negative(self):
        assert _to_int("-100123", "chat_id") == -100123

    def test_to_int_raises_with_field_name(self):
        with pytest.raises(ValueError, match="API_ID"):
            _to_int("not-a-number", "API_ID")


class TestMigration:
    def test_migration_from_config_json(self, tmp_path, monkeypatch):
        """config.json переносится в .env, старый файл → .bak."""
        env = tmp_path / ".env"
        js = tmp_path / "config.json"
        bak = tmp_path / "config.json.bak"

        js.write_text(
            json.dumps({
                "api_id": 111222,
                "api_hash": "deadbeef",
                "monitored_chat_id": -1001111111111,
                "chat_id_to_redirect_messages": -1002222222222,
                "device_model": "Custom Device",
                "system_version": "4.16.30-vxCUSTOM",
                "app_version": "1.0",
                "temp_files_dir": "temp_files",
            }),
            encoding="utf-8",
        )

        assert migrate_legacy_if_needed(env_path=env, json_path=js, bak_path=bak) is True
        assert env.exists()
        assert not js.exists()
        assert bak.exists()
        content = env.read_text(encoding="utf-8")
        assert "API_ID=111222" in content
        assert "API_HASH=deadbeef" in content
        assert "MONITORED_CHAT_ID=-1001111111111" in content

    def test_no_migration_if_env_exists(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("API_ID=1\n", encoding="utf-8")
        js = tmp_path / "config.json"
        js.write_text("{}", encoding="utf-8")
        bak = tmp_path / "config.json.bak"

        assert migrate_legacy_if_needed(env_path=env, json_path=js, bak_path=bak) is False
        assert js.exists()

    def test_no_migration_if_json_absent(self, tmp_path):
        env = tmp_path / ".env"
        js = tmp_path / "config.json"
        bak = tmp_path / "config.json.bak"
        assert migrate_legacy_if_needed(env_path=env, json_path=js, bak_path=bak) is False

    def test_migration_skips_empty_fields(self, tmp_path):
        env = tmp_path / ".env"
        js = tmp_path / "config.json"
        bak = tmp_path / "config.json.bak"
        js.write_text(json.dumps({"api_id": "", "api_hash": "x"}), encoding="utf-8")
        assert migrate_legacy_if_needed(env_path=env, json_path=js, bak_path=bak) is True
        content = env.read_text(encoding="utf-8")
        assert "API_HASH=x" in content
        assert "API_ID=" not in content


class TestLoadSettings:
    def test_load_from_env_file(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text(
            "API_ID=1234\n"
            "API_HASH=abc\n"
            "MONITORED_CHAT_ID=-10011\n"
            "CHAT_ID_TO_REDIRECT_MESSAGES=-10022\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("bot.config.path_for", lambda _: env)
        for k in ("API_ID", "API_HASH", "MONITORED_CHAT_ID", "CHAT_ID_TO_REDIRECT_MESSAGES"):
            monkeypatch.delenv(k, raising=False)

        s = load_settings(interactive=False)
        assert isinstance(s, Settings)
        assert s.api_id == 1234
        assert s.api_hash == "abc"
        assert s.monitored_chat_id == -10011
        assert s.chat_id_to_redirect_messages == -10022
        assert s.device_model == "Custom Device"
        assert s.log_level == "INFO"

    def test_missing_required_raises_in_non_interactive(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.touch()
        monkeypatch.setattr("bot.config.path_for", lambda _: env)
        for k in ("API_ID", "API_HASH", "MONITORED_CHAT_ID", "CHAT_ID_TO_REDIRECT_MESSAGES"):
            monkeypatch.delenv(k, raising=False)

        with pytest.raises(RuntimeError, match="обязательные"):
            load_settings(interactive=False)

    def test_os_env_takes_precedence(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text(
            "API_ID=111\n"
            "API_HASH=file_hash\n"
            "MONITORED_CHAT_ID=1\n"
            "CHAT_ID_TO_REDIRECT_MESSAGES=2\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("bot.config.path_for", lambda _: env)
        monkeypatch.setenv("API_HASH", "env_hash")
        for k in ("API_ID", "MONITORED_CHAT_ID", "CHAT_ID_TO_REDIRECT_MESSAGES"):
            os.environ.pop(k, None)

        s = load_settings(interactive=False)
        assert s.api_hash == "env_hash"

"""Тесты слойной загрузки конфигурации (.env / config.json / окружение)."""

from __future__ import annotations

import json
import os

import pytest

from bot.config import (
    Settings,
    _is_missing,
    _parse_int_list,
    _to_bool,
    _to_int,
    load_settings,
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

    def test_to_int_negative_for_supergroup(self):
        assert _to_int("-1001234567890", "chat") == -1001234567890

    def test_to_int_field_in_error(self):
        with pytest.raises(ValueError, match="API_ID"):
            _to_int("foo", "API_ID")

    def test_parse_int_list_from_list(self):
        assert _parse_int_list([1, 2, 3]) == (1, 2, 3)

    def test_parse_int_list_from_int(self):
        assert _parse_int_list(42) == (42,)

    def test_parse_int_list_from_csv(self):
        assert _parse_int_list("738212658, 4122528496") == (738212658, 4122528496)
        assert _parse_int_list("1;2;3") == (1, 2, 3)

    def test_parse_int_list_empty(self):
        assert _parse_int_list(None) == ()
        assert _parse_int_list("") == ()
        assert _parse_int_list([]) == ()

    def test_to_bool(self):
        assert _to_bool(True) is True
        assert _to_bool("true") is True
        assert _to_bool("YES") is True
        assert _to_bool("1") is True
        assert _to_bool("да") is True
        assert _to_bool("false") is False
        assert _to_bool(None) is False


class TestLoadFromEnv:
    def test_load_simple_env(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text(
            "API_ID=1234\n"
            "API_HASH=abc\n"
            "MONITORED_CHAT_IDS=-10011\n"
            "CHAT_ID_TO_REDIRECT_MESSAGES=-10022\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("bot.config.path_for", lambda _: env)
        monkeypatch.setattr("bot.config.app_dir", lambda: tmp_path)
        for k in (
            "API_ID", "API_HASH", "MONITORED_CHAT_IDS", "MONITORED_CHAT_ID",
            "CHAT_ID_TO_REDIRECT_MESSAGES", "USE_TOPICS",
        ):
            monkeypatch.delenv(k, raising=False)

        s = load_settings(interactive=False)
        assert isinstance(s, Settings)
        assert s.api_id == 1234
        assert s.api_hash == "abc"
        assert s.monitored_chat_ids == (-10011,)
        assert s.chat_id_to_redirect_messages == -10022
        assert s.use_topics is False
        assert s.topic_rules == ()

    def test_csv_monitored_ids(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text(
            "API_ID=1\nAPI_HASH=h\n"
            "MONITORED_CHAT_IDS=738212658,4122528496\n"
            "CHAT_ID_TO_REDIRECT_MESSAGES=1271568832\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("bot.config.path_for", lambda _: env)
        monkeypatch.setattr("bot.config.app_dir", lambda: tmp_path)
        for k in ("API_ID", "API_HASH", "MONITORED_CHAT_IDS", "CHAT_ID_TO_REDIRECT_MESSAGES"):
            monkeypatch.delenv(k, raising=False)

        s = load_settings(interactive=False)
        assert s.monitored_chat_ids == (738212658, 4122528496)

    def test_missing_required_raises(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.touch()
        monkeypatch.setattr("bot.config.path_for", lambda _: env)
        monkeypatch.setattr("bot.config.app_dir", lambda: tmp_path)
        for k in ("API_ID", "API_HASH", "MONITORED_CHAT_IDS", "CHAT_ID_TO_REDIRECT_MESSAGES"):
            monkeypatch.delenv(k, raising=False)

        with pytest.raises(RuntimeError, match="обязательные"):
            load_settings(interactive=False)


class TestLayeringJsonOverEnv:
    def test_json_overrides_env(self, tmp_path, monkeypatch):
        """Если есть и .env, и config.json — JSON выигрывает."""
        env = tmp_path / ".env"
        env.write_text(
            "API_ID=11\nAPI_HASH=env_hash\n"
            "MONITORED_CHAT_IDS=1\nCHAT_ID_TO_REDIRECT_MESSAGES=2\n",
            encoding="utf-8",
        )
        js = tmp_path / "config.json"
        js.write_text(
            json.dumps({
                "api_id": 99,
                "api_hash": "json_hash",
                "monitored_chat_id": [100, 200],
                "chat_id_to_redirect_messages": 300,
            }),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "bot.config.path_for",
            lambda key: env if key == "ENV_FILE" else js,
        )
        monkeypatch.setattr("bot.config.app_dir", lambda: tmp_path)
        for k in (
            "API_ID", "API_HASH", "MONITORED_CHAT_IDS", "MONITORED_CHAT_ID",
            "CHAT_ID_TO_REDIRECT_MESSAGES",
        ):
            monkeypatch.delenv(k, raising=False)

        s = load_settings(interactive=False)
        assert s.api_id == 99
        assert s.api_hash == "json_hash"
        assert s.monitored_chat_ids == (100, 200)
        assert s.chat_id_to_redirect_messages == 300

    def test_user_full_format_json_with_topics(self, tmp_path, monkeypatch):
        """Реальный формат пользователя: массив + use_topics + tags_for_topics."""
        env = tmp_path / ".env"
        js = tmp_path / "config.json"
        js.write_text(
            json.dumps({
                "device_model": "Custom Device",
                "system_version": "4.16.30-vxCUSTOM",
                "app_version": "1.0",
                "temp_files_dir": "temp_files",
                "api_id": 23265814,
                "api_hash": "4a82535dd8bdd7886562e6a6c4359949",
                "monitored_chat_id": [738212658, 4122528496],
                "chat_id_to_redirect_messages": 1271568832,
                "use_topics": True,
                "tags_for_topics": {
                    "1": {"include": {"or": []}, "exclude": {"or": []}},
                    "9233": {
                        "include": {"or": ["#Indiana_jones"]},
                        "exclude": {"or": []},
                    },
                    "9211": {
                        "include": {"and": ["#Indiana_jones", "#трейд"]},
                        "exclude": {"or": []},
                    },
                    "9278": {
                        "include": {"or": []},
                        "exclude": {"or": ["#трейд"]},
                    },
                },
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "bot.config.path_for",
            lambda key: env if key == "ENV_FILE" else js,
        )
        monkeypatch.setattr("bot.config.app_dir", lambda: tmp_path)
        for k in (
            "API_ID", "API_HASH", "MONITORED_CHAT_IDS", "MONITORED_CHAT_ID",
            "CHAT_ID_TO_REDIRECT_MESSAGES", "USE_TOPICS",
        ):
            monkeypatch.delenv(k, raising=False)

        s = load_settings(interactive=False)
        assert s.api_id == 23265814
        assert s.monitored_chat_ids == (738212658, 4122528496)
        assert s.chat_id_to_redirect_messages == 1271568832
        assert s.use_topics is True
        assert len(s.topic_rules) == 4
        topic_ids = sorted(r.topic_id for r in s.topic_rules)
        assert topic_ids == [1, 9211, 9233, 9278]
        # Тема 9233 должна содержать #Indiana_jones в include.or
        rule_9233 = next(r for r in s.topic_rules if r.topic_id == 9233)
        assert rule_9233.include_or == ("#Indiana_jones",)


class TestRoutesSidecar:
    def test_routes_json_loaded_when_no_config_json(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text(
            "API_ID=1\nAPI_HASH=h\n"
            "MONITORED_CHAT_IDS=10\nCHAT_ID_TO_REDIRECT_MESSAGES=20\n"
            "USE_TOPICS=true\n",
            encoding="utf-8",
        )
        routes = tmp_path / "routes.json"
        routes.write_text(
            json.dumps({"42": {"include": {"or": ["#x"]}, "exclude": {"or": []}}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "bot.config.path_for",
            lambda key: env if key == "ENV_FILE" else tmp_path / "config.json",
        )
        monkeypatch.setattr("bot.config.app_dir", lambda: tmp_path)
        for k in (
            "API_ID", "API_HASH", "MONITORED_CHAT_IDS", "CHAT_ID_TO_REDIRECT_MESSAGES",
            "USE_TOPICS",
        ):
            monkeypatch.delenv(k, raising=False)

        s = load_settings(interactive=False)
        assert s.use_topics is True
        assert len(s.topic_rules) == 1
        assert s.topic_rules[0].topic_id == 42
        assert s.topic_rules[0].include_or == ("#x",)

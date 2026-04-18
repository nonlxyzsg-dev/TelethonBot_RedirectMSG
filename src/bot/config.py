"""Загрузка конфигурации приложения.

Приоритет источников:
    1. Переменные окружения (загружаются из .env рядом с приложением через python-dotenv).
    2. Legacy config.json (с автоматической миграцией в .env при первом запуске).
    3. Интерактивный ввод пользователя (сохраняется в .env).

Авто-миграция: если найден config.json и нет .env — создаётся .env на основе json,
а старый файл переименовывается в config.json.bak.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key

from bot.paths import CONFIG_BAK, CONFIG_JSON, ENV_FILE, path_for

log = logging.getLogger(__name__)

REQUIRED_NUMERIC = ("API_ID", "MONITORED_CHAT_ID", "CHAT_ID_TO_REDIRECT_MESSAGES")
REQUIRED_STRING = ("API_HASH",)

DEFAULTS: dict[str, str] = {
    "DEVICE_MODEL": "Custom Device",
    "SYSTEM_VERSION": "4.16.30-vxCUSTOM",
    "APP_VERSION": "1.0",
    "TEMP_FILES_DIR": "temp_files",
    "SESSION_NAME": "telethon",
    "LOG_LEVEL": "INFO",
}

LEGACY_KEY_MAP: dict[str, str] = {
    "api_id": "API_ID",
    "api_hash": "API_HASH",
    "monitored_chat_id": "MONITORED_CHAT_ID",
    "chat_id_to_redirect_messages": "CHAT_ID_TO_REDIRECT_MESSAGES",
    "device_model": "DEVICE_MODEL",
    "system_version": "SYSTEM_VERSION",
    "app_version": "APP_VERSION",
    "temp_files_dir": "TEMP_FILES_DIR",
}


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    monitored_chat_id: int
    chat_id_to_redirect_messages: int
    device_model: str = DEFAULTS["DEVICE_MODEL"]
    system_version: str = DEFAULTS["SYSTEM_VERSION"]
    app_version: str = DEFAULTS["APP_VERSION"]
    temp_files_dir: str = DEFAULTS["TEMP_FILES_DIR"]
    session_name: str = DEFAULTS["SESSION_NAME"]
    log_level: str = DEFAULTS["LOG_LEVEL"]
    extras: dict[str, str] = field(default_factory=dict)


def _is_missing(value: object) -> bool:
    """Корректная проверка пустоты: не ломается на числе 0."""
    return value is None or (isinstance(value, str) and value.strip() == "")


def _to_int(value: object, key: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} должно быть числом, получено: {value!r}") from exc


def _read_legacy_json(path: Path) -> dict[str, str]:
    """Читает старый config.json и возвращает словарь с KEY=VALUE для .env."""
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    env_data: dict[str, str] = {}
    for legacy_key, env_key in LEGACY_KEY_MAP.items():
        value = raw.get(legacy_key)
        if _is_missing(value):
            continue
        env_data[env_key] = str(value)
    return env_data


def _write_env(env_path: Path, data: dict[str, str]) -> None:
    """Записывает словарь в .env-файл (через python-dotenv)."""
    env_path.touch(exist_ok=True)
    for key, value in data.items():
        set_key(str(env_path), key, value, quote_mode="never")


def migrate_legacy_if_needed(
    env_path: Path | None = None,
    json_path: Path | None = None,
    bak_path: Path | None = None,
) -> bool:
    """Если есть config.json и нет .env — переносит значения в .env.

    Возвращает True, если миграция была выполнена.
    """
    env_path = env_path or path_for(ENV_FILE)
    json_path = json_path or path_for(CONFIG_JSON)
    bak_path = bak_path or path_for(CONFIG_BAK)

    if env_path.exists() or not json_path.exists():
        return False

    try:
        migrated = _read_legacy_json(json_path)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Не удалось прочитать legacy config.json (%s): %s", json_path, exc)
        return False

    if not migrated:
        return False

    _write_env(env_path, migrated)
    json_path.replace(bak_path)
    log.warning(
        "Миграция config.json → .env выполнена. Старый файл сохранён как %s", bak_path.name
    )
    return True


def _prompt(key: str, is_numeric: bool) -> str:
    """Интерактивный ввод одного значения с валидацией."""
    while True:
        value = input(f"Введите значение для '{key}': ").strip()
        if _is_missing(value):
            print("Значение не может быть пустым. Попробуйте снова.")
            continue
        if is_numeric and not value.lstrip("-").isdigit():
            print(f"Значение для '{key}' должно быть числом. Попробуйте снова.")
            continue
        return value


def _prompt_missing(env_path: Path, current: dict[str, str]) -> dict[str, str]:
    """Запрашивает у пользователя недостающие обязательные параметры и пишет в .env."""
    filled = dict(current)
    for key in REQUIRED_STRING + REQUIRED_NUMERIC:
        if _is_missing(filled.get(key)) and _is_missing(os.environ.get(key)):
            value = _prompt(key, is_numeric=key in REQUIRED_NUMERIC)
            filled[key] = value
            _write_env(env_path, {key: value})
            os.environ[key] = value
    return filled


def load_settings(interactive: bool = True) -> Settings:
    """Главная точка входа: загружает настройки из всех доступных источников."""
    env_path = path_for(ENV_FILE)

    migrate_legacy_if_needed(env_path=env_path)

    if env_path.exists():
        load_dotenv(env_path, override=False)
        file_values = dict(dotenv_values(env_path))
    else:
        file_values = {}

    def get(key: str, default: str | None = None) -> str | None:
        return os.environ.get(key) or file_values.get(key) or default

    needs = {k: get(k) for k in REQUIRED_STRING + REQUIRED_NUMERIC}
    if any(_is_missing(v) for v in needs.values()):
        if not interactive:
            missing = [k for k, v in needs.items() if _is_missing(v)]
            raise RuntimeError(f"Не заданы обязательные параметры: {', '.join(missing)}")
        filled = _prompt_missing(env_path, {k: v or "" for k, v in needs.items()})
        for k, v in filled.items():
            os.environ.setdefault(k, v)

    return Settings(
        api_id=_to_int(get("API_ID"), "API_ID"),
        api_hash=str(get("API_HASH")).strip(),
        monitored_chat_id=_to_int(get("MONITORED_CHAT_ID"), "MONITORED_CHAT_ID"),
        chat_id_to_redirect_messages=_to_int(
            get("CHAT_ID_TO_REDIRECT_MESSAGES"), "CHAT_ID_TO_REDIRECT_MESSAGES"
        ),
        device_model=get("DEVICE_MODEL", DEFAULTS["DEVICE_MODEL"]),
        system_version=get("SYSTEM_VERSION", DEFAULTS["SYSTEM_VERSION"]),
        app_version=get("APP_VERSION", DEFAULTS["APP_VERSION"]),
        temp_files_dir=get("TEMP_FILES_DIR", DEFAULTS["TEMP_FILES_DIR"]),
        session_name=get("SESSION_NAME", DEFAULTS["SESSION_NAME"]),
        log_level=(get("LOG_LEVEL", DEFAULTS["LOG_LEVEL"]) or "INFO").upper(),
    )

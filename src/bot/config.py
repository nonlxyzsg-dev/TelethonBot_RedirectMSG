"""Загрузка конфигурации приложения.

Стратегия слоёв (каждый следующий перетирает предыдущий):
    1. Хардкод-дефолты (DEFAULTS).
    2. Шаблонный .env.example рядом с приложением (если есть).
    3. Пользовательский .env рядом с приложением.
    4. Переменные окружения (os.environ).
    5. config.json — поверх всего, "правда последней инстанции".

Конфиг пользователя в config.json может быть как простой (один источник
и один получатель), так и расширенный — со списком monitored_chat_id,
флагом use_topics и секцией tags_for_topics для маршрутизации по темам.
Формат не мигрируется и не трогается: запустил рядом — заработало.

Если config.json нет, но нужны правила тем — рядом с .env можно положить
routes.json вида {"1": {"include": {"or": []}, "exclude": {"or": []}}, ...}.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key

from bot.paths import CONFIG_JSON, ENV_FILE, app_dir, path_for
from bot.routing import TopicRule, parse_topic_rules

log = logging.getLogger(__name__)

REQUIRED_NUMERIC = ("API_ID", "CHAT_ID_TO_REDIRECT_MESSAGES")
REQUIRED_STRING = ("API_HASH",)

DEFAULTS: dict[str, str] = {
    "DEVICE_MODEL": "Custom Device",
    "SYSTEM_VERSION": "4.16.30-vxCUSTOM",
    "APP_VERSION": "1.0",
    "TEMP_FILES_DIR": "temp_files",
    "SESSION_NAME": "telethon",
    "LOG_LEVEL": "INFO",
    "USE_TOPICS": "false",
}

ROUTES_FILE_NAME = "routes.json"
ENV_EXAMPLE_NAME = ".env.example"

JSON_KEY_TO_ENV: dict[str, str] = {
    "api_id": "API_ID",
    "api_hash": "API_HASH",
    "chat_id_to_redirect_messages": "CHAT_ID_TO_REDIRECT_MESSAGES",
    "device_model": "DEVICE_MODEL",
    "system_version": "SYSTEM_VERSION",
    "app_version": "APP_VERSION",
    "temp_files_dir": "TEMP_FILES_DIR",
    "session_name": "SESSION_NAME",
    "log_level": "LOG_LEVEL",
}


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    monitored_chat_ids: tuple[int, ...]
    chat_id_to_redirect_messages: int
    use_topics: bool = False
    topic_rules: tuple[TopicRule, ...] = ()
    device_model: str = DEFAULTS["DEVICE_MODEL"]
    system_version: str = DEFAULTS["SYSTEM_VERSION"]
    app_version: str = DEFAULTS["APP_VERSION"]
    temp_files_dir: str = DEFAULTS["TEMP_FILES_DIR"]
    session_name: str = DEFAULTS["SESSION_NAME"]
    log_level: str = DEFAULTS["LOG_LEVEL"]
    extras: dict[str, str] = field(default_factory=dict)


def _is_missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _to_int(value: object, key: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} должно быть числом, получено: {value!r}") from exc


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "да"}


def _parse_int_list(value: object) -> tuple[int, ...]:
    """Парсит список chat_id из любого формата: list[int], int, csv-строка."""
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(int(x) for x in value if not _is_missing(x))
    if isinstance(value, int):
        return (value,)
    s = str(value).strip()
    if not s:
        return ()
    parts = [p.strip() for p in s.replace(";", ",").split(",")]
    return tuple(int(p) for p in parts if p)


def _write_env(env_path: Path, data: dict[str, str]) -> None:
    env_path.touch(exist_ok=True)
    for key, value in data.items():
        set_key(str(env_path), key, value, quote_mode="never")


def _layer_dotenv(target: dict[str, str], path: Path) -> None:
    """Накатывает поверх target значения из .env-файла, если он существует."""
    if not path.exists():
        return
    for key, value in dotenv_values(path).items():
        if value is not None and not _is_missing(value):
            target[key] = value


def _layer_environ(target: dict[str, str]) -> None:
    """Накатывает поверх target переменные окружения os.environ."""
    relevant = (
        *REQUIRED_NUMERIC,
        *REQUIRED_STRING,
        *DEFAULTS.keys(),
        "MONITORED_CHAT_IDS",
        "MONITORED_CHAT_ID",
    )
    for key in relevant:
        env_value = os.environ.get(key)
        if env_value is not None and not _is_missing(env_value):
            target[key] = env_value


def _layer_json(
    target: dict[str, str], json_path: Path
) -> tuple[tuple[int, ...] | None, list[TopicRule] | None, bool | None]:
    """Накатывает config.json поверх target.

    Возвращает (monitored_chat_ids, topic_rules, use_topics) — те поля,
    которые в .env плохо описываются (списки и вложенные структуры).
    """
    if not json_path.exists():
        return (None, None, None)

    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Не удалось прочитать %s: %s", json_path, exc)
        return (None, None, None)

    if not isinstance(raw, dict):
        return (None, None, None)

    for json_key, env_key in JSON_KEY_TO_ENV.items():
        value = raw.get(json_key)
        if not _is_missing(value):
            target[env_key] = str(value)

    monitored_ids = None
    if "monitored_chat_id" in raw:
        monitored_ids = _parse_int_list(raw["monitored_chat_id"])
    elif "monitored_chat_ids" in raw:
        monitored_ids = _parse_int_list(raw["monitored_chat_ids"])

    use_topics: bool | None = None
    if "use_topics" in raw:
        use_topics = _to_bool(raw["use_topics"])

    rules = None
    if "tags_for_topics" in raw:
        rules = parse_topic_rules(raw.get("tags_for_topics") or {})

    return (monitored_ids, rules, use_topics)


def _load_sidecar_routes() -> list[TopicRule]:
    """Если рядом лежит routes.json — читаем правила из него (для .env-сценария)."""
    path = app_dir() / ROUTES_FILE_NAME
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Не удалось прочитать %s: %s", path, exc)
        return []
    return parse_topic_rules(raw if isinstance(raw, dict) else {})


def _prompt(key: str, is_numeric: bool) -> str:
    while True:
        value = input(f"Введите значение для '{key}': ").strip()
        if _is_missing(value):
            print("Значение не может быть пустым. Попробуйте снова.")
            continue
        if is_numeric and not value.lstrip("-").isdigit():
            print(f"Значение для '{key}' должно быть числом. Попробуйте снова.")
            continue
        return value


def _prompt_missing(
    env_path: Path,
    layer: dict[str, str],
    monitored_ids: tuple[int, ...],
) -> tuple[dict[str, str], tuple[int, ...]]:
    """Запрашивает у пользователя недостающие обязательные параметры."""
    filled = dict(layer)
    for key in REQUIRED_STRING + REQUIRED_NUMERIC:
        if _is_missing(filled.get(key)):
            value = _prompt(key, is_numeric=key in REQUIRED_NUMERIC)
            filled[key] = value
            _write_env(env_path, {key: value})
            os.environ[key] = value

    if not monitored_ids:
        value = _prompt("MONITORED_CHAT_IDS (через запятую или один id)", is_numeric=False)
        monitored_ids = _parse_int_list(value)
        _write_env(env_path, {"MONITORED_CHAT_IDS": value})
        os.environ["MONITORED_CHAT_IDS"] = value

    return filled, monitored_ids


def load_settings(interactive: bool = True) -> Settings:
    """Главная точка входа: применяет слои конфигурации в порядке приоритета."""
    env_path = path_for(ENV_FILE)
    json_path = path_for(CONFIG_JSON)
    example_path = app_dir() / ENV_EXAMPLE_NAME

    layer: dict[str, str] = dict(DEFAULTS)
    _layer_dotenv(layer, example_path)
    _layer_dotenv(layer, env_path)
    _layer_environ(layer)

    if env_path.exists():
        load_dotenv(env_path, override=False)

    monitored_ids = _parse_int_list(layer.get("MONITORED_CHAT_IDS") or layer.get("MONITORED_CHAT_ID"))

    json_monitored, json_rules, json_use_topics = _layer_json(layer, json_path)
    if json_monitored is not None:
        monitored_ids = json_monitored

    needs = {k: layer.get(k) for k in REQUIRED_STRING + REQUIRED_NUMERIC}
    if any(_is_missing(v) for v in needs.values()) or not monitored_ids:
        if not interactive:
            missing = [k for k, v in needs.items() if _is_missing(v)]
            if not monitored_ids:
                missing.append("MONITORED_CHAT_IDS")
            raise RuntimeError(f"Не заданы обязательные параметры: {', '.join(missing)}")
        layer, monitored_ids = _prompt_missing(env_path, layer, monitored_ids)

    use_topics = _to_bool(layer.get("USE_TOPICS")) if json_use_topics is None else json_use_topics
    rules = json_rules if json_rules is not None else _load_sidecar_routes()

    return Settings(
        api_id=_to_int(layer["API_ID"], "API_ID"),
        api_hash=str(layer["API_HASH"]).strip(),
        monitored_chat_ids=monitored_ids,
        chat_id_to_redirect_messages=_to_int(
            layer["CHAT_ID_TO_REDIRECT_MESSAGES"], "CHAT_ID_TO_REDIRECT_MESSAGES"
        ),
        use_topics=use_topics,
        topic_rules=tuple(rules),
        device_model=layer.get("DEVICE_MODEL", DEFAULTS["DEVICE_MODEL"]),
        system_version=layer.get("SYSTEM_VERSION", DEFAULTS["SYSTEM_VERSION"]),
        app_version=layer.get("APP_VERSION", DEFAULTS["APP_VERSION"]),
        temp_files_dir=layer.get("TEMP_FILES_DIR", DEFAULTS["TEMP_FILES_DIR"]),
        session_name=layer.get("SESSION_NAME", DEFAULTS["SESSION_NAME"]),
        log_level=(layer.get("LOG_LEVEL", DEFAULTS["LOG_LEVEL"]) or "INFO").upper(),
    )

"""Определение рабочей директории приложения.

Гарантирует портативность: при запуске из PyInstaller onefile-EXE все пользовательские
файлы (.env, config.json, proxies.txt, *.session, temp_files/, telethon_log.log)
располагаются рядом с исполняемым файлом, а не в AppData или во временной папке.
"""

from __future__ import annotations

import sys
from pathlib import Path


def app_dir() -> Path:
    """Директория, в которой хранятся пользовательские файлы приложения.

    Для frozen-сборки PyInstaller — папка рядом с .exe.
    Для запуска из исходников — корень репозитория (на два уровня выше этого файла).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resolve(name: str) -> Path:
    """Полный путь к файлу/папке внутри app_dir()."""
    return app_dir() / name


ENV_FILE = "ENV_FILE"
CONFIG_JSON = "CONFIG_JSON"
CONFIG_BAK = "CONFIG_BAK"
PROXIES_FILE = "PROXIES_FILE"
LOG_FILE = "LOG_FILE"

_NAMES = {
    ENV_FILE: ".env",
    CONFIG_JSON: "config.json",
    CONFIG_BAK: "config.json.bak",
    PROXIES_FILE: "proxies.txt",
    LOG_FILE: "telethon_log.log",
}


def path_for(kind: str) -> Path:
    """Зарезервированные имена стандартных файлов."""
    return resolve(_NAMES[kind])

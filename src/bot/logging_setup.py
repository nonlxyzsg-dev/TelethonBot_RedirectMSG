"""Настройка логирования: файл рядом с приложением + консоль."""

from __future__ import annotations

import logging
from pathlib import Path

LOG_LEVELS = {
    "1": "INFO",
    "2": "DEBUG",
    "3": "WARNING",
    "4": "ERROR",
    "5": "CRITICAL",
}


def setup_logging(level_name: str, log_file: Path) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)


def prompt_log_level(default: str = "INFO") -> str:
    """Интерактивный выбор уровня логирования. Возвращает имя уровня."""
    print("Выберите уровень логирования (Enter — оставить по умолчанию):")
    for num, name in LOG_LEVELS.items():
        marker = " (по умолчанию)" if name == default else ""
        print(f"  {num}. {name}{marker}")
    print("  6. Выход")

    while True:
        choice = input("Ваш выбор: ").strip()
        if not choice:
            return default
        if choice in LOG_LEVELS:
            return LOG_LEVELS[choice]
        if choice == "6":
            raise SystemExit(0)
        print("Некорректный ввод. Введите число от 1 до 6.")

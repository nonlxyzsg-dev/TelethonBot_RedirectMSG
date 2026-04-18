"""Определение и миграция пути к файлу сессии Telethon.

Для портативности .session всегда кладётся рядом с приложением (в app_dir()).
Для обратной совместимости: если старый .session лежит в CWD (как было
раньше, когда TelegramClient('telethon', ...) использовал CWD), а в
app_dir() его ещё нет — переносим в app_dir().
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from bot.paths import app_dir

log = logging.getLogger(__name__)


def session_path(session_name: str) -> str:
    """Возвращает путь к .session БЕЗ расширения — Telethon дописывает сам."""
    return str(app_dir() / session_name)


def migrate_legacy_session(session_name: str) -> bool:
    """Переносит старый session-файл из CWD в app_dir(), если нужно.

    Возвращает True, если миграция была выполнена. Никогда не удаляет исходник
    и не перетирает целевой файл — только копирует при отсутствии целевого.
    """
    target = app_dir() / f"{session_name}.session"
    if target.exists():
        return False

    legacy = Path.cwd() / f"{session_name}.session"
    if not legacy.exists():
        return False

    try:
        legacy.resolve() == target.resolve()
    except OSError:
        pass
    else:
        if legacy.resolve() == target.resolve():
            return False

    try:
        shutil.copy2(legacy, target)
        log.warning(
            "Старая сессия перенесена: %s → %s. Оригинал оставлен нетронутым.",
            legacy, target,
        )
        # Перенесём и journal-файл, если есть (важно для целостности sqlite)
        legacy_journal = legacy.with_suffix(".session-journal")
        if legacy_journal.exists():
            shutil.copy2(legacy_journal, target.with_suffix(".session-journal"))
        return True
    except OSError as exc:
        log.warning("Не удалось перенести сессию из %s: %s", legacy, exc)
        return False

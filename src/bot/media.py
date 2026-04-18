"""Утилиты для работы с медиа: правильные имена файлов, скачивание, отправка."""

from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path

from telethon.tl.types import DocumentAttributeFilename

log = logging.getLogger(__name__)

_EXT_BY_KIND = {
    "photo": ".jpg",
    "video": ".mp4",
    "voice": ".ogg",
    "audio": ".mp3",
    "sticker": ".webp",
    "gif": ".mp4",
}


def _kind_of(message) -> str:
    if getattr(message, "photo", None):
        return "photo"
    if getattr(message, "video", None):
        return "video"
    if getattr(message, "voice", None):
        return "voice"
    if getattr(message, "audio", None):
        return "audio"
    if getattr(message, "sticker", None):
        return "sticker"
    if getattr(message, "gif", None):
        return "gif"
    return "file"


def guess_ext(message) -> str:
    """Определяет расширение файла на основе метаданных сообщения Telethon."""
    file = getattr(message, "file", None)
    if file is not None:
        ext = getattr(file, "ext", None)
        if ext:
            return ext
        mime = getattr(file, "mime_type", None)
        if mime:
            guessed = mimetypes.guess_extension(mime)
            if guessed:
                return guessed

    media = getattr(message, "media", None)
    doc = getattr(media, "document", None)
    if doc is not None:
        for attr in getattr(doc, "attributes", ()):
            if isinstance(attr, DocumentAttributeFilename):
                _, ext = os.path.splitext(attr.file_name)
                if ext:
                    return ext

    return _EXT_BY_KIND.get(_kind_of(message), ".bin")


def make_temp_name(message, temp_dir: Path) -> Path:
    """Имя для временного файла: сохраняет оригинальное имя, если есть, иначе
    генерирует на основе id сообщения и корректного расширения."""
    file = getattr(message, "file", None)
    if file is not None:
        name = getattr(file, "name", None)
        if name:
            return temp_dir / f"{message.id}_{name}"
    return temp_dir / f"temp_{_kind_of(message)}_{message.id}{guess_ext(message)}"


async def download_message_media(message, temp_dir: Path) -> Path | None:
    """Скачивает медиа сообщения в temp_dir. Возвращает путь или None."""
    if not getattr(message, "media", None):
        return None
    target = make_temp_name(message, temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    downloaded = await message.download_media(file=str(target))
    if downloaded is None:
        return None
    return Path(downloaded)


def pick_caption(messages) -> str | None:
    """Из списка сообщений альбома выбирает первый непустой текст — это caption."""
    for m in messages:
        text = getattr(m, "text", None) or getattr(m, "message", None)
        if text:
            return text
    return None


def cleanup(paths) -> None:
    """Безопасно удаляет список временных файлов."""
    for p in paths:
        try:
            Path(p).unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Не удалось удалить temp-файл %s: %s", p, exc)


def cleanup_temp_dir(temp_dir: Path) -> None:
    """Удаляет все файлы из temp_dir (оставшиеся после падений прошлых запусков)."""
    if not temp_dir.exists():
        return
    for item in temp_dir.iterdir():
        if item.is_file():
            try:
                item.unlink()
            except OSError as exc:
                log.warning("Не удалось очистить %s: %s", item, exc)

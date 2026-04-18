"""Обработчик входящих сообщений и логика пересылки."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.types import MessageMediaWebPage

from bot.media import cleanup, download_message_media, pick_caption
from bot.ttlset import TTLSet

log = logging.getLogger(__name__)

_processed_groups: TTLSet[int] = TTLSet(maxsize=1024, ttl_seconds=600.0)

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 2.0


async def _with_retry(coro_factory, description: str):
    """Выполняет асинхронную операцию с ретраями и обработкой FloodWait."""
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return await coro_factory()
        except FloodWaitError as exc:
            wait = exc.seconds + 1
            log.warning("FloodWait %d с на '%s', ждём...", wait, description)
            await asyncio.sleep(wait)
        except (RPCError, ConnectionError, OSError) as exc:
            last_exc = exc
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            log.warning(
                "Попытка %d/%d '%s' упала: %s. Повтор через %.1f с",
                attempt, RETRY_ATTEMPTS, description, exc, delay,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


def register_handler(
    client: TelegramClient,
    monitored_chat_id: int,
    redirect_chat_id: int,
    temp_dir: Path,
) -> None:
    """Регистрирует NewMessage-хэндлер с пересылкой и обработкой всех типов медиа."""

    @client.on(events.NewMessage(chats=monitored_chat_id))
    async def handler(event):
        message = event.message
        log.info("Зафиксировано сообщение id=%s от chat=%s", message.id, event.chat_id)

        try:
            if message.grouped_id:
                await _handle_album(client, event, redirect_chat_id, temp_dir)
            elif isinstance(message.media, MessageMediaWebPage):
                await _handle_webpage(client, message, redirect_chat_id)
            elif message.media:
                await _handle_media(client, message, redirect_chat_id, temp_dir)
            elif message.text:
                await _with_retry(
                    lambda: client.send_message(redirect_chat_id, message.text),
                    "send_message(text)",
                )
        except Exception:
            log.exception("Ошибка при обработке сообщения id=%s", message.id)


async def _handle_album(
    client: TelegramClient, event, redirect_chat_id: int, temp_dir: Path
) -> None:
    grouped_id = event.message.grouped_id
    if not await _processed_groups.add_if_absent(grouped_id):
        return

    log.info("Обработка альбома grouped_id=%s", grouped_id)

    collected = []
    async for msg in client.iter_messages(event.chat_id, limit=20):
        if msg.grouped_id == grouped_id:
            collected.append(msg)

    # Telethon выдаёт сообщения от новых к старым — разворачиваем для правильного порядка.
    collected.reverse()

    caption = pick_caption(collected)
    files: list[Path] = []
    try:
        for msg in collected:
            path = await _with_retry(
                lambda m=msg: download_message_media(m, temp_dir),
                f"download_media(id={msg.id})",
            )
            if path is not None:
                files.append(path)
        if files:
            await _with_retry(
                lambda: client.send_file(
                    redirect_chat_id, [str(p) for p in files], caption=caption
                ),
                "send_file(album)",
            )
    finally:
        cleanup(files)


async def _handle_media(
    client: TelegramClient, message, redirect_chat_id: int, temp_dir: Path
) -> None:
    caption = message.text or None
    path = await _with_retry(
        lambda: download_message_media(message, temp_dir), f"download_media(id={message.id})"
    )
    if path is None:
        return
    try:
        await _with_retry(
            lambda: client.send_file(redirect_chat_id, str(path), caption=caption),
            "send_file(media)",
        )
    finally:
        cleanup([path])


async def _handle_webpage(client: TelegramClient, message, redirect_chat_id: int) -> None:
    url = getattr(message.media.webpage, "url", None) if message.media.webpage else None
    text = message.text
    if text and url and url not in text:
        payload = f"{text}\n{url}"
    else:
        payload = text or url
    if not payload:
        return
    await _with_retry(
        lambda: client.send_message(redirect_chat_id, payload),
        "send_message(webpage)",
    )

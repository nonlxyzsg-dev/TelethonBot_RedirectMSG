"""Обработчик входящих сообщений и логика пересылки.

Поддерживает:
- Несколько источников (events.NewMessage(chats=[...]))
- Маршрутизацию в темы форума по правилам tags_for_topics
  (use_topics=True) — копия отправляется в каждую тему, чьи правила
  пропустили сообщение
- Простую 1→1 пересылку (use_topics=False)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from pathlib import Path

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.types import MessageMediaWebPage

from bot.media import cleanup, download_message_media, pick_caption
from bot.routing import (
    TopicRule,
    collect_hashtags,
    extract_hashtags,
    matching_topics,
    reply_to_for_topic,
)
from bot.ttlset import TTLSet

log = logging.getLogger(__name__)

_processed_groups: TTLSet[int] = TTLSet(maxsize=1024, ttl_seconds=600.0)

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 2.0


async def _with_retry(coro_factory, description: str):
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
    monitored_chat_ids: Iterable[int],
    redirect_chat_id: int,
    temp_dir: Path,
    use_topics: bool = False,
    topic_rules: Iterable[TopicRule] = (),
) -> None:
    """Регистрирует NewMessage-хэндлер на список источников.

    Если use_topics=True и есть правила — сообщение копируется во все
    темы, чьи правила сработали по хэштегам сообщения.
    Иначе — обычная пересылка одного сообщения в redirect_chat_id.
    """
    monitored = list(monitored_chat_ids)
    rules = list(topic_rules) if use_topics else []

    @client.on(events.NewMessage(chats=monitored))
    async def handler(event):
        message = event.message
        log.info(
            "Сообщение id=%s из chat=%s (grouped_id=%s)",
            message.id, event.chat_id, message.grouped_id,
        )
        try:
            if message.grouped_id:
                await _handle_album(
                    client, event, redirect_chat_id, temp_dir, rules, use_topics
                )
            elif isinstance(message.media, MessageMediaWebPage):
                await _handle_webpage(
                    client, message, redirect_chat_id, rules, use_topics
                )
            elif message.media:
                await _handle_media(
                    client, message, redirect_chat_id, temp_dir, rules, use_topics
                )
            elif message.text:
                await _handle_text(
                    client, message, redirect_chat_id, rules, use_topics
                )
        except Exception:
            log.exception("Ошибка при обработке сообщения id=%s", message.id)


def _resolve_targets(
    tags: set[str], rules: list[TopicRule], use_topics: bool
) -> list[int | None]:
    """Возвращает список reply_to для каждой целевой темы.

    Если use_topics=False — один None (просто отправка в чат без темы).
    Если use_topics=True — по reply_to для каждой совпавшей темы;
    если ни одно правило не сработало — None (всё равно отправляем
    в General, чтобы сообщение не потерялось).
    """
    if not use_topics or not rules:
        return [None]

    topic_ids = matching_topics(tags, rules)
    if not topic_ids:
        log.warning("Ни одно правило не сработало для тегов %s — шлю в General", tags)
        return [None]
    return [reply_to_for_topic(t) for t in topic_ids]


async def _handle_album(
    client, event, redirect_chat_id, temp_dir, rules, use_topics
) -> None:
    grouped_id = event.message.grouped_id
    if not await _processed_groups.add_if_absent(grouped_id):
        return

    log.info("Обработка альбома grouped_id=%s", grouped_id)

    collected = []
    async for msg in client.iter_messages(event.chat_id, limit=20):
        if msg.grouped_id == grouped_id:
            collected.append(msg)
    collected.reverse()

    caption = pick_caption(collected)
    tags = collect_hashtags(collected)
    targets = _resolve_targets(tags, rules, use_topics)

    files: list[Path] = []
    try:
        for msg in collected:
            path = await _with_retry(
                lambda m=msg: download_message_media(m, temp_dir),
                f"download_media(id={msg.id})",
            )
            if path is not None:
                files.append(path)
        if not files:
            return
        for reply_to in targets:
            await _with_retry(
                lambda rt=reply_to: client.send_file(
                    redirect_chat_id,
                    [str(p) for p in files],
                    caption=caption,
                    reply_to=rt,
                ),
                f"send_file(album, reply_to={reply_to})",
            )
    finally:
        cleanup(files)


async def _handle_media(
    client, message, redirect_chat_id, temp_dir, rules, use_topics
) -> None:
    caption = message.text or None
    tags = extract_hashtags(caption)
    targets = _resolve_targets(tags, rules, use_topics)

    path = await _with_retry(
        lambda: download_message_media(message, temp_dir),
        f"download_media(id={message.id})",
    )
    if path is None:
        return
    try:
        for reply_to in targets:
            await _with_retry(
                lambda rt=reply_to: client.send_file(
                    redirect_chat_id, str(path), caption=caption, reply_to=rt
                ),
                f"send_file(media, reply_to={reply_to})",
            )
    finally:
        cleanup([path])


async def _handle_webpage(
    client, message, redirect_chat_id, rules, use_topics
) -> None:
    url = getattr(message.media.webpage, "url", None) if message.media.webpage else None
    text = message.text
    payload = f"{text}\n{url}" if text and url and url not in text else (text or url)
    if not payload:
        return
    tags = extract_hashtags(text)
    targets = _resolve_targets(tags, rules, use_topics)
    for reply_to in targets:
        await _with_retry(
            lambda rt=reply_to: client.send_message(
                redirect_chat_id, payload, reply_to=rt
            ),
            f"send_message(webpage, reply_to={reply_to})",
        )


async def _handle_text(client, message, redirect_chat_id, rules, use_topics) -> None:
    tags = extract_hashtags(message.text)
    targets = _resolve_targets(tags, rules, use_topics)
    for reply_to in targets:
        await _with_retry(
            lambda rt=reply_to: client.send_message(
                redirect_chat_id, message.text, reply_to=rt
            ),
            f"send_message(text, reply_to={reply_to})",
        )

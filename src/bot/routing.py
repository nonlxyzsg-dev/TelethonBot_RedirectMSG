"""Маршрутизация сообщений по темам форума на основе хэштегов.

Поддерживает include/exclude правила с операторами and/or:
- include.or:[#X, #Y] — пропускает, если есть ХОТЯ БЫ ОДИН из тегов
- include.and:[#X, #Y] — пропускает, только если есть ВСЕ теги
- exclude.or:[#X] — отбрасывает, если есть ХОТЯ БЫ ОДИН тег
- exclude.and:[#X, #Y] — отбрасывает, только если есть ВСЕ
- Пустой include = "фильтр не задан, проходит всё"
- Пустой exclude = "фильтр не задан, не отбрасываем"

Сообщение копируется во ВСЕ темы, чьи правила сработали.
Тема с id=1 — это General в Telegram-форумах: при отправке туда
параметр reply_to не используется.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# \w в Python 3 учитывает Unicode (включая кириллицу), так что #трейд распознаётся.
_HASHTAG_RE = re.compile(r"#\w+")

GENERAL_TOPIC_ID = 1


@dataclass(frozen=True)
class TopicRule:
    topic_id: int
    include_or: tuple[str, ...] = ()
    include_and: tuple[str, ...] = ()
    exclude_or: tuple[str, ...] = ()
    exclude_and: tuple[str, ...] = ()

    def matches(self, tags: set[str]) -> bool:
        return _matches(tags, self)


def _norm(items) -> set[str]:
    return {t.lower() for t in items}


def _matches(tags: set[str], rule: TopicRule) -> bool:
    inc_or = _norm(rule.include_or)
    inc_and = _norm(rule.include_and)
    exc_or = _norm(rule.exclude_or)
    exc_and = _norm(rule.exclude_and)

    if inc_or and not (tags & inc_or):
        return False
    if inc_and and not inc_and.issubset(tags):
        return False
    if exc_or and (tags & exc_or):
        return False
    if exc_and and exc_and.issubset(tags):
        return False
    return True


def extract_hashtags(text: str | None) -> set[str]:
    """Извлекает хэштеги из текста, нормализует к нижнему регистру."""
    if not text:
        return set()
    return {m.lower() for m in _HASHTAG_RE.findall(text)}


def collect_hashtags(messages) -> set[str]:
    """Собирает хэштеги со всех сообщений (для альбомов).

    Учитывает и текстовое сообщение, и подпись медиа — в Telethon оба
    доступны через `message.text` / `message.message`.
    """
    tags: set[str] = set()
    for m in messages:
        tags |= extract_hashtags(getattr(m, "text", None))
        tags |= extract_hashtags(getattr(m, "message", None))
    return tags


def parse_topic_rules(raw) -> list[TopicRule]:
    """Парсит секцию `tags_for_topics` из конфига в список TopicRule."""
    if not raw:
        return []
    rules: list[TopicRule] = []
    for topic_id_str, body in raw.items():
        try:
            topic_id = int(topic_id_str)
        except (TypeError, ValueError):
            continue
        body = body or {}
        include = body.get("include") or {}
        exclude = body.get("exclude") or {}
        rules.append(
            TopicRule(
                topic_id=topic_id,
                include_or=tuple(include.get("or") or ()),
                include_and=tuple(include.get("and") or ()),
                exclude_or=tuple(exclude.get("or") or ()),
                exclude_and=tuple(exclude.get("and") or ()),
            )
        )
    return rules


def matching_topics(tags: set[str], rules) -> list[int]:
    """Возвращает id всех тем, чьи правила пропустили это сообщение."""
    return [r.topic_id for r in rules if r.matches(tags)]


def reply_to_for_topic(topic_id: int) -> int | None:
    """Telegram-форум: тема с id=1 — это General, отправляется без reply_to."""
    return None if topic_id == GENERAL_TOPIC_ID else topic_id

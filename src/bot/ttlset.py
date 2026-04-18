"""Bounded set с TTL для дедупликации обработанных событий.

Нужен в обработчике альбомов: Telethon доставляет каждый элемент медиа-группы
как отдельное событие, и без дедупликации мы бы скачивали/отправляли группу
столько раз, сколько в ней элементов.

Старая реализация использовала безразмерный set как атрибут функции —
память росла бесконечно. TTLSet решает это:
- лимитом maxsize (LRU-вытеснение)
- TTL (элементы старше ttl_seconds считаются истёкшими)
- asyncio.Lock закрывает TOCTOU-гонку между check и add
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import Generic, Hashable, TypeVar

T = TypeVar("T", bound=Hashable)


class TTLSet(Generic[T]):
    """Асинхронно-безопасный набор с ограничением размера и TTL."""

    def __init__(self, maxsize: int = 1024, ttl_seconds: float = 600.0):
        if maxsize <= 0:
            raise ValueError("maxsize должен быть положительным")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds должен быть положительным")
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._data: OrderedDict[T, float] = OrderedDict()
        self._lock = asyncio.Lock()

    def _now(self) -> float:
        return time.monotonic()

    def _evict_expired(self) -> None:
        now = self._now()
        expired = [k for k, ts in self._data.items() if now - ts > self._ttl]
        for k in expired:
            self._data.pop(k, None)

    async def add_if_absent(self, key: T) -> bool:
        """Атомарно: если ключа нет — добавить и вернуть True. Иначе False."""
        async with self._lock:
            self._evict_expired()
            if key in self._data:
                self._data.move_to_end(key)
                return False
            self._data[key] = self._now()
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)
            return True

    async def __contains__(self, key: T) -> bool:  # pragma: no cover
        async with self._lock:
            self._evict_expired()
            return key in self._data

    def __len__(self) -> int:
        return len(self._data)

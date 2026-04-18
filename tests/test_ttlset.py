"""Тесты TTLSet."""

from __future__ import annotations

import asyncio

import pytest

from bot.ttlset import TTLSet


async def test_add_first_time_returns_true():
    s = TTLSet[int](maxsize=10, ttl_seconds=60.0)
    assert await s.add_if_absent(1) is True


async def test_add_duplicate_returns_false():
    s = TTLSet[int](maxsize=10, ttl_seconds=60.0)
    await s.add_if_absent(1)
    assert await s.add_if_absent(1) is False


async def test_eviction_on_overflow():
    s = TTLSet[int](maxsize=2, ttl_seconds=60.0)
    await s.add_if_absent(1)
    await s.add_if_absent(2)
    await s.add_if_absent(3)
    assert len(s) == 2
    # После вытеснения 1 можно добавить снова
    assert await s.add_if_absent(1) is True


async def test_ttl_expiration():
    s = TTLSet[int](maxsize=10, ttl_seconds=0.05)
    await s.add_if_absent(42)
    await asyncio.sleep(0.1)
    assert await s.add_if_absent(42) is True


async def test_concurrent_add_deduplicates():
    """Критичный тест: TOCTOU. Два одновременных add_if_absent на один ключ —
    только один должен вернуть True."""
    s = TTLSet[int](maxsize=10, ttl_seconds=60.0)
    results = await asyncio.gather(*(s.add_if_absent(99) for _ in range(20)))
    assert sum(results) == 1


def test_invalid_maxsize():
    with pytest.raises(ValueError):
        TTLSet[int](maxsize=0, ttl_seconds=1.0)


def test_invalid_ttl():
    with pytest.raises(ValueError):
        TTLSet[int](maxsize=1, ttl_seconds=0)

"""Поддержка MTProto-прокси для Telethon.

Используется, когда прямое подключение к серверам Telegram блокируется.
Прокси читаются из файла proxies.txt (по одному URI на строку, комментарии #).

Формат URI: tg://proxy?server=HOST&port=PORT&secret=HEX
Пример: tg://proxy?server=194.87.57.180&port=443&secret=ddb7c4685b50c48b91a64412b63408dc2c

Стратегия подключения: сначала пробуем прямое соединение с таймаутом,
затем последовательно перебираем прокси из файла. Первый рабочий —
тот и используется на всё время работы бота.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

log = logging.getLogger(__name__)

DEFAULT_CONNECT_TIMEOUT = 10.0


@dataclass(frozen=True)
class MTProxy:
    """Разобранный MTProto-прокси, готовый к передаче в TelegramClient."""

    host: str
    port: int
    secret: str  # hex-строка

    def as_tuple(self) -> tuple[str, int, str]:
        """Формат, который принимает Telethon в параметре proxy=."""
        return (self.host, self.port, self.secret)

    def masked(self) -> str:
        """Безопасное представление для логов (без секрета)."""
        return f"{self.host}:{self.port}"


def parse_mtproxy_uri(uri: str) -> MTProxy:
    """Парсит строку вида tg://proxy?server=...&port=...&secret=... в MTProxy.

    Raises ValueError, если формат некорректный.
    """
    if not isinstance(uri, str):
        raise ValueError(f"Ожидалась строка URI, получено {type(uri).__name__}")

    uri = uri.strip()
    if not uri:
        raise ValueError("Пустая строка URI")

    parsed = urlparse(uri)
    if parsed.scheme != "tg" or parsed.netloc != "proxy":
        raise ValueError(f"Ожидался URI tg://proxy?..., получено: {uri!r}")

    params = parse_qs(parsed.query)

    def single(name: str) -> str:
        values = params.get(name)
        if not values or not values[0]:
            raise ValueError(f"В URI отсутствует обязательный параметр '{name}': {uri!r}")
        return values[0]

    host = single("server").strip()
    secret = single("secret").strip()

    try:
        port = int(single("port"))
    except ValueError as exc:
        raise ValueError(f"Параметр 'port' должен быть числом: {uri!r}") from exc

    if port <= 0 or port > 65535:
        raise ValueError(f"Некорректный порт {port} в {uri!r}")

    # Валидация секрета (hex). Telethon примет hex-строку и сам её декодирует.
    try:
        bytes.fromhex(secret)
    except ValueError as exc:
        raise ValueError(f"Секрет должен быть hex-строкой: {uri!r}") from exc

    return MTProxy(host=host, port=port, secret=secret)


def load_proxies(path: Path) -> list[MTProxy]:
    """Читает файл прокси. Пустые строки и комментарии (#) игнорируются.

    Некорректные строки логируются, но не прерывают загрузку.
    Если файла нет — возвращает пустой список.
    """
    if not path.exists():
        log.info("Файл прокси не найден: %s (прокси не используются)", path)
        return []

    proxies: list[MTProxy] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            proxies.append(parse_mtproxy_uri(line))
        except ValueError as exc:
            log.warning("Строка %d в %s пропущена: %s", lineno, path.name, exc)

    log.info("Загружено прокси: %d из %s", len(proxies), path.name)
    return proxies


async def connect_with_fallback(
    client_factory: Callable[[MTProxy | None], object],
    proxies: list[MTProxy],
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
) -> object:
    """Пытается подключиться сначала напрямую, затем через прокси по очереди.

    client_factory(proxy) должен создавать НОВЫЙ TelegramClient и возвращать
    уже подключённый клиент (обычно через `await client.connect()`).
    Функция возвращает первый клиент, которому удалось подключиться.
    Если ни один вариант не сработал — бросает RuntimeError.
    """
    attempts: list[MTProxy | None] = [None, *proxies]
    last_error: Exception | None = None

    for proxy in attempts:
        label = "прямое подключение" if proxy is None else f"прокси {proxy.masked()}"
        try:
            log.info("Пробую %s...", label)
            client = await asyncio.wait_for(
                _call_factory(client_factory, proxy), timeout=connect_timeout
            )
            log.info("Успешное подключение: %s", label)
            return client
        except asyncio.TimeoutError as exc:
            last_error = exc
            log.warning("Таймаут (%.1f с): %s", connect_timeout, label)
        except (ConnectionError, OSError) as exc:
            last_error = exc
            log.warning("Сетевая ошибка (%s): %s", label, exc)
        except Exception as exc:
            last_error = exc
            log.warning("Ошибка подключения (%s): %s", label, exc)

    raise RuntimeError(
        f"Не удалось подключиться ни напрямую, ни через {len(proxies)} прокси. "
        f"Последняя ошибка: {last_error}"
    )


async def _call_factory(
    factory: Callable[[MTProxy | None], object], proxy: MTProxy | None
) -> object:
    """Вызывает factory и, если результат — корутина, ожидает её."""
    result = factory(proxy)
    if asyncio.iscoroutine(result):
        return await result
    return result

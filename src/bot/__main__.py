"""Точка входа приложения.

Поддерживает два способа запуска:
    python -m bot                # из исходников
    ./TelethonBot.exe            # после сборки PyInstaller
"""

from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

from bot.config import Settings, load_settings
from bot.handler import register_handler
from bot.logging_setup import prompt_log_level, setup_logging
from bot.media import cleanup_temp_dir
from bot.paths import LOG_FILE, PROXIES_FILE, app_dir, path_for
from bot.proxy import MTProxy, connect_with_fallback, load_proxies
from bot.session import migrate_legacy_session, session_path

log = logging.getLogger(__name__)

STARTUP_HELP = """\
TelethonBot_RedirectMSG — пересылка сообщений Telegram.

Все пользовательские файлы (.env, proxies.txt, *.session, temp_files/, лог)
располагаются рядом с этим исполняемым файлом — его можно свободно переносить.

Если это первый запуск:
  1. Получите api_id и api_hash на https://my.telegram.org
  2. Узнайте id чатов через @userinfobot в Telegram
  3. Ответьте на запрошенные поля — будет создан .env рядом с программой
  4. При первом логине Telegram пришлёт код — введите его в консоль

Для корректного завершения используйте Ctrl+C.
"""


def _make_client(settings: Settings, proxy: MTProxy | None) -> TelegramClient:
    kwargs = {
        "device_model": settings.device_model,
        "system_version": settings.system_version,
        "app_version": settings.app_version,
    }
    if proxy is not None:
        kwargs["proxy"] = proxy.as_tuple()
        kwargs["connection"] = ConnectionTcpMTProxyRandomizedIntermediate

    return TelegramClient(
        session_path(settings.session_name),
        settings.api_id,
        settings.api_hash,
        **kwargs,
    )


async def _factory_connect(settings: Settings, proxy: MTProxy | None) -> TelegramClient:
    """Создаёт TelegramClient и пытается установить соединение (без авторизации)."""
    client = _make_client(settings, proxy)
    await client.connect()
    return client


async def _start_client(settings: Settings) -> TelegramClient:
    """Устанавливает соединение — напрямую или через прокси из proxies.txt.

    Возвращает подключённый (но, возможно, ещё не авторизованный) клиент.
    """
    proxies = load_proxies(path_for(PROXIES_FILE))

    client = await connect_with_fallback(
        lambda proxy: _factory_connect(settings, proxy),
        proxies,
    )
    return client


async def _authorize_if_needed(client: TelegramClient, settings: Settings) -> None:
    """Выполняет start() для запроса кода входа, если пользователь ещё не авторизован."""
    if not await client.is_user_authorized():
        log.warning("Требуется авторизация. Введите код из Telegram когда попросят.")
        await client.start()


async def _confirm_chats(client: TelegramClient, settings: Settings) -> tuple[int, int]:
    """Подтверждает доступ к monitored_chat_id и redirect_chat_id. Возвращает финальную пару."""
    monitored = settings.monitored_chat_id
    redirect = settings.chat_id_to_redirect_messages

    await client.get_dialogs()

    while True:
        try:
            m_entity = await client.get_entity(monitored)
            r_entity = await client.get_entity(redirect)
        except ValueError as exc:
            log.error("Не удалось найти чат: %s", exc)
            new_id = input("Введите корректный ID чата для мониторинга или 'exit': ").strip()
            if new_id.lower() == "exit":
                raise SystemExit(0) from exc
            try:
                monitored = int(new_id)
            except ValueError:
                print("ID должен быть числом.")
            continue

        m_name = getattr(m_entity, "title", None) or getattr(m_entity, "username", str(monitored))
        r_name = getattr(r_entity, "title", None) or getattr(r_entity, "username", str(redirect))

        answer = input(
            f"Пересылать из '{m_name}' в '{r_name}'? [Y/n]: "
        ).strip().lower()
        if answer in ("", "y", "yes", "да"):
            log.warning("Мониторим '%s' (%s) → '%s' (%s)", m_name, m_entity.id, r_name, r_entity.id)
            return monitored, redirect
        if answer in ("n", "no", "нет"):
            try:
                monitored = int(input("Новый monitored_chat_id: ").strip())
                redirect = int(input("Новый chat_id_to_redirect_messages: ").strip())
            except ValueError:
                print("ID должны быть числами, повтор.")
                continue
        elif answer in ("exit", "выход"):
            raise SystemExit(0)


async def run_async() -> None:
    print(STARTUP_HELP)

    settings = load_settings()

    log_file = path_for(LOG_FILE)
    log_level = prompt_log_level(default=settings.log_level)
    setup_logging(log_level, log_file)

    log.info("app_dir: %s", app_dir())
    log.info("log_file: %s", log_file)

    migrate_legacy_session(settings.session_name)

    temp_dir = app_dir() / settings.temp_files_dir
    temp_dir.mkdir(parents=True, exist_ok=True)
    cleanup_temp_dir(temp_dir)

    client: TelegramClient | None = None
    try:
        client = await _start_client(settings)
        await _authorize_if_needed(client, settings)
        monitored, redirect = await _confirm_chats(client, settings)
        register_handler(client, monitored, redirect, temp_dir)
        log.warning("Клиент запущен и слушает новые сообщения. Ctrl+C для остановки.")
        await client.run_until_disconnected()
    finally:
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                log.exception("Ошибка при disconnect()")
        log.warning("Клиент отключён.")


def run() -> None:
    try:
        asyncio.run(run_async())
    except KeyboardInterrupt:
        print("\nЗавершение по Ctrl+C.")


if __name__ == "__main__":
    run()

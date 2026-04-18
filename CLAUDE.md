# CLAUDE.md

Инструкции для Claude Code и других ассистентов, работающих с этим
репозиторием. Язык коммуникации — русский.

## Что это

Telegram-бот на Telethon: мониторит один чат, пересылает сообщения
(текст, фото, видео, файлы, альбомы, web-страницы) в другой чат.
Поставляется как портативный Windows EXE и как Python-скрипт.

## Команды разработки

| Действие | Команда |
|---|---|
| Установка зависимостей | `pip install -r requirements-dev.txt` |
| Запуск из исходников | `python -m bot` или `python main.py` |
| Линт | `ruff check src tests` |
| Тесты | `pytest -q` |
| Ручная сборка EXE | `pyinstaller bot.spec` |
| Проверка миграции конфига | положить `config.json` рядом → запустить |

## Архитектура

```
main.py             тонкий launcher (добавляет src/ в sys.path)
src/bot/
    __main__.py     точка входа: загружает Settings, стартует клиент
    paths.py        app_dir() — портативность (frozen-aware)
    config.py       Settings, .env → config.json → prompt
    session.py      путь к .session и миграция из CWD
    proxy.py        MTProxy, парсер tg://proxy, connect_with_fallback
    logging_setup.py
    ttlset.py       bounded LRU + TTL для дедупа grouped_id
    media.py        guess_ext, pick_caption, download, cleanup
    handler.py      NewMessage, альбомы, webpage, ретраи
```

Поток запуска: `load_settings` → `setup_logging` → `migrate_legacy_session`
→ `cleanup_temp_dir` → `connect_with_fallback` (прямое/прокси) →
`is_user_authorized` / `start` → `_confirm_chats` → `register_handler` →
`run_until_disconnected`.

## Принципы, которые нельзя нарушать

### Портативность
Все пользовательские файлы резолвятся через `paths.app_dir()`. Никаких
обращений к AppData / `%USERPROFILE%` / `os.getcwd()`. Если добавляете
новый файл конфигурации или данных — используйте `paths.resolve(name)`.

### Стабильность Telegram-сессии
`device_model`, `system_version`, `app_version` — стабильные значения
из `.env`. Никогда не генерируйте их рандомно и не зависьте от
версии ОС/Python. Смена этих полей вызывает у Telegram подозрение
на новое устройство и может привести к завершению других сессий
пользователя. Путь к `.session` — всегда `app_dir() / session_name`,
никогда `Path.cwd()`.

### Секреты
`API_HASH` и session-файлы — только в `.env` и рядом с приложением.
Оба в `.gitignore`. Никогда не логируйте `api_hash` и содержимое
`.session`. Для прокси — `MTProxy.masked()` в логах, не `as_tuple()`.

### Обратная совместимость
Старые пользователи могут иметь `config.json` и `.session` в CWD. При
обновлении они должны продолжать работать без ручных действий:
`migrate_legacy_if_needed` (config) и `migrate_legacy_session`
выполняются автоматически.

## Конвенции коммитов

Conventional Commits: английский префикс + двоеточие + пробел +
русский текст. Примеры:

- `feat: добавлен MTProxy-фолбэк из proxies.txt`
- `fix: корректные расширения файлов альбома`
- `feat!: миграция config.json на .env` — breaking change, мажорный bump
- `refactor: выделен модуль config`
- `docs: обновлён раздел про прокси`
- `ci: линт и тесты`
- `chore: добавлены requirements`
- `test: покрытие TTLSet`

Префикс → bump:
- `feat!:` / `BREAKING CHANGE:` в footer → major
- `feat:` → minor
- `fix:`, `perf:` → patch
- `refactor:`, `docs:`, `style:`, `test:`, `chore:`, `ci:`, `build:` →
  без релиза (но попадают в changelog)

## Release-процесс

`push origin main` → `.github/workflows/release.yml`:
1. `python-semantic-release` читает историю с прошлого тега,
   определяет bump, обновляет `pyproject.toml:project.version`,
   коммитит `CHANGELOG.md`, создаёт тег `vX.Y.Z`, пушит.
2. `windows-latest` собирает `TelethonBot-vX.Y.Z.exe` через
   PyInstaller (`bot.spec`).
3. Публикуется GitHub Release с EXE, `.env.example`, `proxies.txt`,
   `README.md` в ассетах.

Ручного вмешательства для релиза не требуется. Если нужно избежать
релиза при push — используйте префиксы `chore:`, `docs:`, `ci:`,
`refactor:`, `test:`, `style:` (semantic-release их не релизит).

## Что не делать

- Писать комментарии в коде, объясняющие WHAT. Код сам себя
  документирует хорошими именами. Комментарии — только для WHY
  (неочевидный инвариант, workaround с объяснением).
- Создавать MD-файлы (планы, анализы, доки) без явной просьбы
  пользователя — документацию пишем только в README/CLAUDE.md.
- Использовать `print()` для отладки в модулях `bot/` — только
  `logging` через `log = logging.getLogger(__name__)`.
- Комитить `.env`, `config.json`, `*.session`, `temp_files/`, логи.
- Менять `device_model` без явной просьбы пользователя.
- Амендить опубликованные коммиты или force-push в main.

## GitHub MCP scope

Доступ только к `nonlxyzsg-dev/telethonbot_redirectmsg`. Для PR и
issues используем `mcp__github__*`, а не `gh`.

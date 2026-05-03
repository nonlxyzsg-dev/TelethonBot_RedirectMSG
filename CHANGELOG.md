# CHANGELOG


## v1.1.0 (2026-05-03)

### Documentation

- Разделы про темы форума, Linux-сборку и слои настроек
  ([`1ae4c36`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/1ae4c36e40c5b43dda5ad812dd44672146661626))

README.md обновлён под новые возможности:

- Шапка: упомянуто "из нескольких чатов" и раскладка по темам форума - Быстрый старт: добавлен
  Linux-вариант (chmod +x + ./binary), вариант с готовым config.json (положить рядом — само
  заработает) - MONITORED_CHAT_IDS: csv-формат для нескольких источников - Новый раздел
  "Маршрутизация по темам форума": * Формат правил с примером из реального конфига * Семантика:
  пустой include = всё, пустой exclude = ничего не отбрасываем, регистр не важен, копируется во ВСЕ
  совпавшие темы * Таблица "Где хранить правила": config.json vs routes.json vs отключить через
  USE_TOPICS=false * Схема слоёв: .env.example ← .env ← environ ← config.json - FAQ: добавлен пункт
  про неверный id темы - Раздел Dev: pyinstaller bot.spec собирает под текущую ОС

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

### Features

- Layered конфиг, список источников, use_topics, чтение JSON поверх .env
  ([`e04cc63`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/e04cc63f24810d13d47d6ce5ecf689419f3b02a2))

Стратегия загрузки настроек переписана на слои (каждый следующий перетирает предыдущий): 1.
  Хардкод-дефолты 2. Шаблонный .env.example рядом с приложением 3. Пользовательский .env 4.
  Переменные окружения (os.environ) 5. config.json — поверх всего

Это значит: можно просто положить рядом config.json (как у пользователей со старой расширенной
  версии — с массивом monitored_chat_id, флагом use_topics и секцией tags_for_topics) — и всё
  заработает без миграции, без ручных правок .env. JSON — последний слой, перебивает всё.

Изменения в Settings: - monitored_chat_id (int) → monitored_chat_ids (tuple[int, ...]) - Новые поля:
  use_topics: bool, topic_rules: tuple[TopicRule, ...]

Парсинг чисел: - _parse_int_list принимает list[int], int или csv-строку - _to_bool понимает
  true/yes/1/on/да + bool

Источники правил тем: - config.json → секция tags_for_topics (как в проекте пользователя) -
  routes.json (сайдкар рядом с .env) — если нет config.json - иначе пустые правила

Удалено: - migrate_legacy_if_needed() — больше не нужно: JSON и так читается напрямую и поверх .env,
  ничего никуда переносить не надо

Тесты (16 шт.): - Хелперы: _parse_int_list, _to_bool, _is_missing(0) - Загрузка из .env (одиночный
  id и csv) - JSON перетирает .env (api_id, hash, монитор, редирект) - Реальный конфиг пользователя
  (массив + use_topics + tags_for_topics) - Сайдкар routes.json рядом с .env

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

- Маршрутизация в темы форума и пересылка с нескольких источников
  ([`6231bfa`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/6231bfa482d4773c6c35a2fe1d16d90dbee88171))

handler.py: - register_handler принимает monitored_chat_ids (Iterable), use_topics, topic_rules —
  Telethon NewMessage с chats=list слушает все источники одним обработчиком - Новая функция
  _resolve_targets: возвращает список reply_to для каждой темы, чьи правила сработали по хэштегам
  сообщения. Если правил нет или ни одно не подошло — отправляем в General (None). - _handle_album:
  collect_hashtags по всем сообщениям группы, затем цикл send_file по каждому совпавшему reply_to с
  одним и тем же набором файлов и caption (Telegram-форум: id=1 это General, reply_to=None ↔ General
  через reply_to_for_topic) - _handle_media/_handle_text/_handle_webpage: те же правила, теги берём
  из caption или message.text

__main__.py: - _confirm_chats работает со списком источников: проверяет каждый, убирает недоступные
  (с подтверждением), позволяет переопределить список через csv-ввод - register_handler вызывается с
  use_topics и topic_rules из Settings

.env.example: - Раздел про слои настроек (.env.example → .env → environ → config.json) -
  MONITORED_CHAT_IDS вместо MONITORED_CHAT_ID, поддержка csv - Раздел про USE_TOPICS и routes.json
  sidecar

routing.py: - Минорный refactor по замечанию ruff (return not (...))

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

- Модуль routing с парсингом хэштегов и матчингом тем форума
  ([`cd5ef3f`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/cd5ef3f442961d04a99c747ec74d037d12f96625))

src/bot/routing.py: - TopicRule(dataclass): include_or/and, exclude_or/and для одной темы -
  extract_hashtags(): достаёт #теги из текста (Unicode \w, поддержка кириллицы), нормализует в
  нижний регистр - collect_hashtags(): объединяет теги по списку сообщений (для альбомов) -
  parse_topic_rules(): преобразует секцию tags_for_topics из конфига в список TopicRule -
  matching_topics(): возвращает все темы, чьи правила пропустили сообщение (slать копию во ВСЕ
  совпавшие темы) - reply_to_for_topic(): тема id=1 это General в Telegram-форумах, для неё reply_to
  не передаётся

Семантика правил: - Пустой include or:[] = "фильтра нет, проходит всё" - include or:[#X, #Y] = хотя
  бы один тег - include and:[#X, #Y] = все теги одновременно - Аналогично для exclude - Регистр
  игнорируется: #Трейд == #трейд

Тесты (27 шт., все зелёные): - Парсинг хэштегов: латиница, кириллица, регистр, пунктуация - Матчинг
  правил: пустые, or, and, комбинации include+exclude - Реальный конфиг пользователя: 8 тем, разные
  комбинации тегов (#Indiana_jones+#трейд → 1, 9233, 9211; без тегов → 1, 9278; и т.д.)

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

- Сборка Linux-бинарника в авторелизе
  ([`7842c96`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/7842c96255d9c880d7e8af1a715f5803a33a4eab))

Раньше релиз содержал только Windows EXE — теперь к нему добавлен Linux onefile-бинарник, собранный
  через PyInstaller на ubuntu-latest.

Изменения в release.yml: - Новый job build-linux работает параллельно с build-windows (оба зависят
  только от semantic-release) - Артефакты переименованы: * TelethonBot-vX.Y.Z-windows (содержит
  .exe) * TelethonBot-vX.Y.Z-linux (содержит исполняемый бинарник) - publish зависит от обоих билдов
  и аплоадит в Release оба файла - chmod +x на Linux-бинарнике после download (artifact теряет
  permissions при упаковке)

Использование: - Windows: скачать TelethonBot-vX.Y.Z.exe, запустить - Linux: скачать
  TelethonBot-vX.Y.Z-linux, ./TelethonBot-vX.Y.Z-linux (chmod +x уже установлен в самом релизе)

В обоих случаях рядом можно положить .env, config.json, proxies.txt — работает портативно одинаково.

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5


## v1.0.0 (2026-04-18)

### Bug Fixes

- Корректные расширения медиа и caption альбомов
  ([`39c662f`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/39c662f37660ee84a99b7415d4bbb28cfd809602))

Проблемы в старом main.py: - 198-203: все файлы альбома сохранялись как temp_photo_*.jpg независимо
  от типа (видео/документ/голос получали неправильное расширение) - 198: caption брался из
  event.message.text, хотя в альбоме подпись обычно в ДРУГОМ сообщении группы — часто caption
  терялся - limit=10 обрезал альбомы (в Telegram до 10 элементов, но граница без запаса) - Нет
  ретраев на сетевые/FloodWait ошибки

Решение: - src/bot/media.py: guess_ext() определяет расширение по file.ext → mime_type →
  DocumentAttributeFilename → типу (photo/video/etc) - src/bot/media.py: pick_caption() выбирает
  первый непустой text из группы - src/bot/handler.py: вынесен обработчик событий * _handle_album:
  собирает все сообщения группы (limit=20), переворачивает порядок (Telethon выдаёт от новых к
  старым), выбирает caption из нужного сообщения, скачивает файлы с правильными расширениями,
  отправляет одним send_file, чистит в finally * _handle_webpage: избегает дубля URL если он уже в
  тексте * _with_retry: 3 попытки с экспоненциальной задержкой, FloodWait-aware - TTLSet
  используется для дедупликации grouped_id

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

- Устранена утечка processed_groups через TTLSet
  ([`9065f82`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/9065f824eb204847877947cc79a9891d7234b927))

Старая реализация использовала handler.processed_groups = set() без ограничения размера и без
  очистки — на длинной дистанции потребление памяти росло неограниченно. Также между проверкой 'in
  processed_groups' и добавлением стоял await, то есть две параллельные обработки одного grouped_id
  могли обе пройти проверку и обе начать скачивание (TOCTOU).

Модуль src/bot/ttlset.py: - TTLSet[T]: bounded (LRU-вытеснение) + TTL - asyncio.Lock делает
  add_if_absent атомарным — гонка закрыта - Возврат True/False сразу говорит, была ли группа уже
  обработана

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

### Chores

- Добавлены .gitignore, requirements и pyproject
  ([`695235b`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/695235b3758f7646cf8eccda4089b81d9e4d9f94))

- .gitignore исключает секреты (.env, *.session, config.json), temp-файлы и артефакты сборки -
  requirements.txt с pinned версиями (telethon, python-dotenv, python-socks, cryptg) -
  requirements-dev.txt с pytest, ruff, pyinstaller, python-semantic-release - pyproject.toml:
  метаданные проекта, конфиг ruff, pytest, semantic-release

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

- Исключение proxies.txt из .gitignore
  ([`ded7de8`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/ded7de81fcddd176bf76cf51c6e260e615b7c8b1))

Файл поставляется с 4 шаблонными MTProto-прокси как часть проекта, его нужно трекать. Пользователи
  могут редактировать его локально — конфликт при git pull для dev-пользователей лучше, чем
  отсутствие файла у exe-пользователей.

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

### Continuous Integration

- Линт и тесты в GitHub Actions
  ([`fc3148f`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/fc3148f578b69edb4fb96236f2b27dbe00fdd9b4))

- .github/workflows/ci.yml запускает ruff и pytest на каждый push/PR в main - Python 3.11,
  ubuntu-latest, кэш pip - concurrency-группа отменяет старые прогоны при новых коммитах - Попутно
  исправлены мелкие замечания ruff в исходниках: * удалены неиспользуемые импорты в __main__.py *
  raise SystemExit with chained 'from exc' * упрощена логика webpage payload через тернарный
  оператор * asyncio.TimeoutError → TimeoutError (Py3.11) * удалён bogus-код в session.py *
  typing.Hashable → collections.abc.Hashable

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

### Documentation

- Добавлен CLAUDE.md и обновлён README
  ([`2e9541a`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/2e9541abbcc0407c3c7b84e9f5751b0b97d24104))

README.md полностью переписан под новый формат: - Быстрый старт на простом русском: скачал exe →
  положил .env и proxies.txt рядом → запустил - Пошаговая инструкция, где брать API_ID/API_HASH и ID
  чатов - Раздел про MTProto-прокси с форматом, примерами и ссылками на каналы со свежими прокси -
  FAQ по частым ошибкам (invalid api_id, peer not found, flood wait, "выкинуло из Telegram" —
  причины и решения) - Отдельный раздел для dev-пользователей (запуск из исходников, тесты, сборка)
  - Миграция для старых пользователей: автоматическая, ручных действий не требуется

CLAUDE.md — инструкции для будущих сессий Claude Code: - команды разработки (pytest, ruff,
  pyinstaller) - описание архитектуры и потока запуска - принципы, которые нельзя нарушать:
  портативность через app_dir(), стабильность session/device-полей (иначе Telegram инвалидирует
  сессии), секреты только в .env, обратная совместимость - конвенции коммитов Conventional Commits с
  английским префиксом и русским текстом, таблица bump-ов - release-процесс через semantic-release -
  scope MCP GitHub

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

### Features

- Авторелиз EXE через semantic-release и PyInstaller
  ([`581ce29`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/581ce291abf001df4e76263aad2f1d107461d4d7))

При push в main автоматически: 1. python-semantic-release читает коммиты с прошлого тега, определяет
  bump по префиксам (feat!→major, feat→minor, fix/perf→patch), создаёт тег vX.Y.Z, коммитит
  CHANGELOG и версию в pyproject.toml. 2. Job build-windows собирает портативный onefile EXE на
  windows-latest через PyInstaller (bot.spec), имя файла включает тег: TelethonBot-vX.Y.Z.exe. 3.
  Job publish создаёт GitHub Release с приложенными: EXE, .env.example, proxies.txt, README.md —
  всё, что нужно положить рядом с exe для работы.

bot.spec: - onefile, console=True (нужен для интерактивного ввода при первом логине) - hiddenimports
  для telethon.network.connection.tcpmtproxy и python_socks (иначе PyInstaller не найдёт их
  динамически) - имя exe берётся из env PYI_EXE_NAME, чтобы CI мог встроить номер версии - upx=False
  (упаковка сломает интерактивный режим Windows)

В pyproject.toml (уже есть) настроен angular commit parser:
  [tool.semantic_release.commit_parser_options] minor_tags = ["feat"] patch_tags = ["fix", "perf"]

Первый релиз после мержа этих коммитов: из-за feat!: в истории (миграция config.json → .env) версия
  пойдёт 0.1.0 → 1.0.0.

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

- Миграция конфигурации с config.json на .env
  ([`fdf3c09`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/fdf3c093f0aa22aa2d8f682044170b49e48efc7a))

BREAKING CHANGE: формат конфигурации изменён с config.json на .env. Для старых пользователей
  выполняется автоматическая миграция при первом запуске: значения из config.json переносятся в
  .env, старый файл сохраняется как config.json.bak. Никаких действий от пользователя не требуется.

Что сделано: - src/bot/config.py: Settings dataclass, load_settings() с приоритетом .env →
  config.json → интерактивный ввод - Автоматическая миграция legacy config.json в .env -
  .env.example с подробными комментариями по каждому параметру - Предупреждение про
  device_model/system_version/app_version: менять их между запусками нельзя — Telegram может
  посчитать это новым устройством и завершить другие сессии пользователя - Исправлены баги валидации
  из старого кода: * _is_missing() корректно обрабатывает 0 (раньше not value ломался) * _to_int()
  даёт понятную ошибку с указанием поля * поддержка отрицательных chat_id (для супергрупп -100...)

Безопасность: api_hash теперь в .env, а .env в .gitignore — секрет не попадёт в репозиторий.

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

- Поддержка MTProxy-фолбэка из proxies.txt
  ([`29c60e0`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/29c60e0c75505d04f53e744277bd1584d0f2cbc8))

Добавлен модуль src/bot/proxy.py с: - parse_mtproxy_uri(): парсинг URI вида
  tg://proxy?server=&port=&secret= - load_proxies(): чтение файла proxies.txt, игнорирование
  комментариев (#) и пустых строк, валидация каждой записи - connect_with_fallback(): стратегия
  подключения — сначала напрямую с таймаутом, затем последовательный перебор прокси из списка до
  первого рабочего

Создан proxies.txt с 4 боевыми MTProto-прокси в качестве шаблона. Пользователи могут редактировать
  файл локально — он в .gitignore, поэтому git pull не будет его перезаписывать.

Зачем: Telegram периодически блокируется провайдерами, и прямое подключение перестаёт работать. При
  наличии рабочих MTProxy в файле бот автоматически переключается на них, не требуя ручного
  вмешательства.

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

### Refactoring

- Выделен модуль paths для портативной работы
  ([`52fb8ac`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/52fb8acc492b1efa678ab55d1ba9e6b66055a32a))

Модуль src/bot/paths.py определяет app_dir() — директорию приложения, которая для PyInstaller
  onefile-EXE соответствует папке рядом с .exe, а для запуска из исходников — корню репозитория.

Все пользовательские файлы (.env, config.json, proxies.txt, session, temp_files/, логи) будут
  резолвиться через эту функцию, что обеспечивает портативность: запустил exe в любой папке — там же
  и создадутся данные.

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

- Перезапуск из модульного main с портативным session
  ([`4dbce3f`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/4dbce3f2166e75443ecd7421c893b7f82e7fa174))

Старый main.py (336 строк монолита) заменён на тонкий launcher, вся логика живёт в src/bot/. Особое
  внимание — стабильности сессии Telethon, чтобы не "выкидывало" из других клиентов Telegram:

1. src/bot/session.py: session_path() всегда возвращает путь рядом с приложением (app_dir() /
  session_name) — независимо от CWD. Это важно для EXE: раньше двойной клик и запуск через ярлык
  давали разные CWD → разные .session-файлы → новый логин → Telegram считал это новым устройством.

2. Обратная совместимость: migrate_legacy_session() проверяет, нет ли старого .session в текущей
  директории, и копирует его в app_dir() (без удаления оригинала). Существующие пользователи не
  потеряют авторизацию после обновления — достаточно положить .session рядом с exe.

3. src/bot/logging_setup.py: логи пишутся в telethon_log.log рядом с приложением (не в CWD). Выбор
  уровня вынесен в prompt_log_level().

4. src/bot/__main__.py: разделил этапы запуска: - connect через connect_with_fallback
  (прокси-фолбэк) - start/is_user_authorized отдельно (прозрачнее) - подтверждение чатов через
  get_entity с retry-ввода - register_handler ставит обработчик - run_until_disconnected, disconnect
  в finally

5. device_model/system_version/app_version всегда берутся из .env — при их смене между запусками
  Telegram будет подозревать новое устройство и может завершить другие сессии, это поведение
  Telegram. README предупреждает об этом явно.

6. main.py становится launcher'ом на 16 строк: добавляет src/ в sys.path и зовёт bot.__main__.run().
  Годится и для python main.py, и для PyInstaller.

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

### Testing

- Покрытие парсера прокси, конфига, TTLSet и paths
  ([`42de4e0`](https://github.com/nonlxyzsg-dev/TelethonBot_RedirectMSG/commit/42de4e0be79bc52b0f1f24349d8323d529810a52))

Добавлено 39 юнит-тестов (все зелёные):

- tests/test_proxy.py — парсинг tg://proxy URI, валидация ошибок (пустая строка, чужая схема,
  отсутствие secret, нечисловой port, порт вне диапазона, не-hex secret), загрузка файла
  (комментарии, пропуск невалидных строк), проверка всех 4 боевых примеров из проекта proxies.txt.

- tests/test_config.py — хелперы (_is_missing корректно обрабатывает 0 — регрессионный тест на баг
  старого кода), _to_int с указанием поля в ошибке, миграция из config.json в .env (успех, пропуск
  если есть .env, пропуск пустых полей), load_settings (чтение .env, приоритет os.environ над
  файлом, ошибка при отсутствии обязательных полей в non-interactive режиме).

- tests/test_ttlset.py — add_if_absent (первый раз True, повтор False), LRU-вытеснение при
  переполнении, TTL-истечение, ТЕСТ НА TOCTOU: 20 параллельных add на один ключ — ровно один
  возвращает True.

- tests/test_paths.py — app_dir в dev и frozen-режимах, резолвинг стандартных имён, комбинирование с
  произвольным name.

https://claude.ai/code/session_012MpDrwPvqg932vuAhYpdn5

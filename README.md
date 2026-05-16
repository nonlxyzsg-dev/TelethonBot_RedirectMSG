# TelethonBot_RedirectMSG

Telegram-бот, который пересылает сообщения (текст, фото, видео, файлы,
альбомы, ссылки) **из нескольких чатов** в другой чат. Можно раскладывать
сообщения по темам форума по правилам с хэштегами. Работает от вашего
аккаунта через Telethon. Есть MTProto-прокси для обхода блокировок.

Поставляется как готовые бинарники (Windows и Linux) и как Python-скрипт.

---

## Быстрый старт

1. **Скачайте последний релиз**
   На странице [Releases](../../releases) выберите подходящую сборку:
   - `TelethonBot-vX.Y.Z.exe` — для Windows
   - `TelethonBot-vX.Y.Z-linux` — для Linux (любой современный дистрибутив)
   - Также скачайте: `.env.example` или `default.env.example` (зависит
     от того, как GitHub переименовал файл при загрузке)

2. **Положите в одну папку** бинарник и файл настроек.
   Программа портативная: всё хранит только в этой папке (.session,
   логи, временные файлы), никуда больше не лезет.

3. **Настройте**: один из двух способов:

   **a)** Самый простой — переименуйте `*.env.example` в `.env`, откройте
   в Блокноте/любом редакторе и впишите свои значения.

   **b)** Если у вас уже есть рабочий `config.json` (например, со списком
   `monitored_chat_id` и секцией `tags_for_topics`) — просто положите
   его рядом с бинарником. JSON перетирает `.env`, ничего больше не
   надо.

4. **Запустите**:
   - Windows: двойной клик по `.exe`
   - Linux: `chmod +x TelethonBot-vX.Y.Z-linux && ./TelethonBot-vX.Y.Z-linux`

   Откроется консоль. При первом запуске Telegram пришлёт код — введите
   его в консоли. Дальше бот сам подхватит `.session` и работает.

5. **Не закрывайте консоль** — пока окно открыто, бот пересылает
   сообщения. Для остановки нажмите `Ctrl+C`.

---

## Где взять значения для `.env`

### `API_ID` и `API_HASH`
1. https://my.telegram.org → войти своим номером.
2. "API development tools" → создать приложение (название любое).
3. Скопируйте `api_id` (число) и `api_hash` (строка).

### `MONITORED_CHAT_IDS` (откуда забираем) и `CHAT_ID_TO_REDIRECT_MESSAGES` (куда)
1. Откройте `@userinfobot` или `@getmyid_bot`.
2. Перешлите ему сообщение из нужного чата — он пришлёт ID.
3. **Несколько источников**: пишите через запятую:
   `MONITORED_CHAT_IDS=-1001234567890,738212658,4122528496`
4. Для супергрупп/каналов ID начинается с `-100…`.
5. Ваш аккаунт должен состоять во всех этих чатах.

### Параметры устройства (`DEVICE_MODEL`, `SYSTEM_VERSION`, `APP_VERSION`)
**Не меняйте после первого логина.** Telegram запоминает их в сессии,
и смена воспринимается как новый вход с другого устройства — может
привести к уведомлениям в ваш Telegram и к завершению других ваших
сессий.

---

## Маршрутизация по темам форума

Если получатель — это форум-группа (где есть темы), и нужно складывать
сообщения с разными хэштегами в разные темы — используйте либо
`config.json` (с секцией `tags_for_topics`), либо `routes.json` рядом
с `.env` плюс `USE_TOPICS=true`.

### Формат правил

Каждая тема описывается двумя блоками — `include` (что пропустить)
и `exclude` (что отбросить). У каждого свой оператор: `or` (любой
из тегов) или `and` (все теги одновременно).

```jsonc
{
  "1": {                                 // тема "General" (id=1) —
    "include": {"or": []},               //   пустые правила = всё подряд
    "exclude": {"or": []}
  },
  "9233": {                              // тема "Indiana_jones"
    "include": {"or": ["#Indiana_jones"]},
    "exclude": {"or": []}
  },
  "9211": {                              // подтема "Indiana_jones — трейд"
    "include": {"and": ["#Indiana_jones", "#трейд"]},
    "exclude": {"or": []}
  },
  "9278": {                              // "общая лента без трейдов"
    "include": {"or": []},               //   пропускаем всё...
    "exclude": {"or": ["#трейд"]}        //   ...кроме сообщений с #трейд
  }
}
```

### Семантика

- Пустой `include: or:[]` или `and:[]` = **"фильтра нет, проходит всё"**.
- Пустой `exclude` = **"ничего не отбрасываем"**.
- Регистр **не важен**: `#Трейд` и `#трейд` — одно и то же.
- Хэштеги ищутся и в тексте, и в подписи медиа. Для альбомов —
  по всем сообщениям группы.
- Сообщение копируется во **все темы**, чьи правила сработали.
  Например, пост `#Indiana_jones #трейд` уйдёт в темы `1`, `9233`
  и `9211` (три копии).

### Где хранить правила

| Источник | Когда использовать |
|---|---|
| `config.json` (секция `tags_for_topics`) | У вас уже есть готовый `config.json` — просто положите рядом, JSON перетирает `.env`. |
| `routes.json` рядом с `.env` | Чистый сценарий с `.env` + сайдкар. Установите `USE_TOPICS=true`. |
| Не нужна маршрутизация | `USE_TOPICS=false` — тогда всё пересылается в `CHAT_ID_TO_REDIRECT_MESSAGES` без `reply_to`. |

### Слои настроек (что чем перетирается)

```
.env.example  ←  .env  ←  переменные окружения  ←  config.json
   (низ)                                              (верх — побеждает)
```

То есть `config.json` всегда выигрывает, если положить его рядом.

---

## Прокси (`proxies.txt`)

Если Telegram блокируется провайдером, бот переберёт MTProto-прокси
из `proxies.txt` и будет использовать первый рабочий.

Формат: одна строка — один прокси, `tg://proxy?server=HOST&port=PORT&secret=HEX`.
Строки с `#` — комментарии.

Свежие прокси: каналы `@MTProtoProxies`, `@mtpro_xy`, боты `@mtproto_bot`,
`@MTProxyBot`. В Telegram: тап по прокси → "Поделиться" → копируется
ссылка нужного формата.

Если прокси не нужны — оставьте файл с примерами, не помешает.

---

## FAQ

### "Invalid api_id/api_hash"
Скопированы не те значения или с пробелами. Перепроверьте.

### "Peer not found"
Ваш аккаунт не состоит в чате. Зайдите в чат, отправьте туда
сообщение, перезапустите бот.

### Меня выкинуло из Telegram после запуска
Изменился `DEVICE_MODEL/SYSTEM_VERSION/APP_VERSION` или потерян
`telethon.session`. Решение: не меняйте поля устройства, держите
`.session` рядом с бинарником.

### "Flood wait"
Telegram попросил подождать N секунд — бот сам ждёт и продолжает.

### Не пересылается в правильную тему
Проверьте id темы (это id корневого сообщения темы в форуме —
видно в ссылке на тему). Тема General всегда имеет id=1.

---

## Запуск на VPS (Linux)

Шаги ниже — для свежей Ubuntu/Debian VPS. На других дистрибутивах
поменяется только пакетный менеджер.

### 1. Подключиться и подготовить папку

```bash
ssh user@<ip-вашей-vps>
mkdir -p ~/telethonbot && cd ~/telethonbot
```

Все файлы бота держим в одной папке — он портативный, в системные
каталоги ничего не пишет.

### 2. Скачать релиз

Зайдите на страницу [Releases](../../releases), скопируйте ссылки на
`TelethonBot-vX.Y.Z-linux` и `.env.example` (правый клик по ассету →
"Копировать адрес ссылки"), затем на VPS:

```bash
curl -L -o telethonbot   "https://github.com/<owner>/<repo>/releases/download/vX.Y.Z/TelethonBot-vX.Y.Z-linux"
curl -L -o .env.example  "https://github.com/<owner>/<repo>/releases/download/vX.Y.Z/.env.example"
chmod +x telethonbot
```

### 3. Заполнить `.env`

```bash
cp .env.example .env
nano .env
```

Минимум, что нужно вписать — `API_ID`, `API_HASH`,
`MONITORED_CHAT_IDS`, `CHAT_ID_TO_REDIRECT_MESSAGES` (как их получить —
см. раздел "Где взять значения для `.env`" выше). Сохранить:
`Ctrl+O`, `Enter`, `Ctrl+X`.

### 4. Первый запуск — авторизация

При первом запуске Telegram пришлёт код в приложение, его нужно
ввести вручную. Поэтому первый запуск делаем интерактивно, прямо
в SSH:

```bash
./telethonbot
```

Бот спросит номер телефона → код из Telegram → если включён
двухфакторный пароль, ещё и его. После успешного входа рядом
появится файл `telethon.session` — это и есть авторизация. Дальше
бот сам пересылает сообщения.

Убедитесь, что всё работает (отправьте тестовое сообщение в
исходный чат), и остановите бот: `Ctrl+C`.

### 5. Фоновый запуск через `systemd` (рекомендуется)

`systemd` сам перезапустит бот после падения и после ребута VPS.

Создайте unit-файл:

```bash
sudo nano /etc/systemd/system/telethonbot.service
```

Вставьте (замените `user` на вашего пользователя и проверьте
`WorkingDirectory`):

```ini
[Unit]
Description=TelethonBot RedirectMSG
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/telethonbot
ExecStart=/home/user/telethonbot/telethonbot
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Включить и запустить:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now telethonbot
sudo systemctl status telethonbot
```

Логи:

```bash
journalctl -u telethonbot -f          # живой хвост
journalctl -u telethonbot --since today
```

Управление:

```bash
sudo systemctl restart telethonbot
sudo systemctl stop telethonbot
```

### Альтернатива: `tmux` / `screen` (без systemd)

Если не хочется возиться с `systemd`:

```bash
sudo apt install -y tmux
tmux new -s bot
./telethonbot
# отсоединиться, оставив бот работать: Ctrl+B, потом D
# вернуться в сессию: tmux attach -t bot
```

Минус: после ребута VPS бот сам не поднимется.

### 6. Обновление до новой версии

```bash
sudo systemctl stop telethonbot         # если через systemd
curl -L -o telethonbot.new "https://github.com/<owner>/<repo>/releases/download/vX.Y.Z/TelethonBot-vX.Y.Z-linux"
chmod +x telethonbot.new
mv telethonbot.new telethonbot
sudo systemctl start telethonbot
```

`.env` и `telethon.session` трогать не нужно — повторная авторизация
не потребуется.

### Частые проблемы на VPS

- **`Permission denied` при запуске** — забыли `chmod +x telethonbot`.
- **`./telethonbot: cannot execute binary file`** — скачали Windows
  `.exe` вместо `-linux`. Перекачайте нужный ассет.
- **`GLIBC_X.YZ not found`** — слишком старый дистрибутив (например,
  Ubuntu 18.04). Поднимите версию ОС или запускайте из исходников
  (см. ниже).
- **Бот пишет "code"** в systemd-логах и стоит — это первый запуск,
  нужен интерактивный ввод. Остановите сервис, авторизуйтесь руками
  (`./telethonbot`), потом снова запускайте через systemd.
- **MTProxy** — если провайдер VPS режет Telegram, положите рядом
  `proxies.txt` (см. раздел "Прокси").

---

## Запуск из исходников (для разработчиков)

```bash
git clone <url>
cd TelethonBot_RedirectMSG
pip install -r requirements-dev.txt

python -m bot                # или python main.py

ruff check src tests
pytest -q

pyinstaller bot.spec         # сборка бинарника под текущую ОС
```

Архитектура и конвенции коммитов — в `CLAUDE.md`.

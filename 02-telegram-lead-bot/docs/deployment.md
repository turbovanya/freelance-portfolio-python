# Развёртывание

## 1. Создать бота

1. Напишите [@BotFather](https://t.me/BotFather) команду `/newbot`, придумайте имя и адрес.
2. Скопируйте токен в `BOT_TOKEN` в файле `.env`.
3. Узнайте свой Telegram ID у [@userinfobot](https://t.me/userinfobot) и впишите в `ADMIN_IDS`. Несколько менеджеров перечисляются через запятую.
4. Каждый менеджер нажимает `/start` у бота.

## 2. Запуск на сервере через Docker (рекомендуется)

Подойдёт любой VPS с 512 МБ памяти.

```bash
git clone <репозиторий> && cd 02-telegram-lead-bot
cp .env.example .env && nano .env
docker compose up -d --build
```

Поднимаются два контейнера: бот и PostgreSQL. Данные базы лежат в томе `pgdata` и переживают перезапуск. Бот перезапускается автоматически после сбоя или перезагрузки сервера.

Полезные команды:

```bash
docker compose logs -f bot          # логи
docker compose restart bot          # перезапуск после правки faq.json
docker compose exec db pg_dump -U bot leads > backup.sql   # резервная копия
```

`faq.json` подключён в контейнер как файл, поэтому вопросы можно править без пересборки: отредактировать и перезапустить бота.

## 3. Запуск без Docker (systemd)

```bash
python3 -m venv /opt/lead-bot/.venv
/opt/lead-bot/.venv/bin/pip install /opt/lead-bot
```

`/etc/systemd/system/lead-bot.service`:

```ini
[Unit]
Description=Lead bot
After=network-online.target

[Service]
WorkingDirectory=/opt/lead-bot
ExecStart=/opt/lead-bot/.venv/bin/lead-bot
Restart=always
User=leadbot

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now lead-bot
journalctl -u lead-bot -f
```

По умолчанию используется SQLite в `data/leads.db`. Для резервной копии достаточно копировать этот файл.

## Переменные окружения

| Переменная | Обязательна | По умолчанию | Описание |
|---|---|---|---|
| `BOT_TOKEN` | да | | токен от @BotFather |
| `ADMIN_IDS` | да | | ID менеджеров через запятую |
| `BUSINESS_NAME` | | Студия «Пример» | название в приветствии |
| `TIMEZONE` | | Europe/Moscow | часовой пояс для дат в карточках и выгрузке |
| `MAX_LEADS_PER_DAY` | | 3 | лимит заявок от одного человека за сутки |
| `FAQ_PATH` | | faq.json | файл с вопросами |
| `DATABASE_URL` | | SQLite | для PostgreSQL: `postgresql+asyncpg://...` |

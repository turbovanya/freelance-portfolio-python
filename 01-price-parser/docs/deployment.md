# Развёртывание и запуск по расписанию

## Вариант 1. Компьютер с Windows

1. Установите Python 3.11 или новее с [python.org](https://www.python.org/downloads/), отметьте «Add Python to PATH».
2. В папке проекта:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install .
copy .env.example .env
price-parser run
```

3. Чтобы запускать каждый день: «Планировщик заданий» → «Создать простую задачу» → «Ежедневно» → «Запустить программу»:
   - программа: `C:\путь\к\проекту\.venv\Scripts\price-parser.exe`
   - аргументы: `run --max-pages 0`
   - рабочая папка: `C:\путь\к\проекту`

## Вариант 2. Linux-сервер, cron

```bash
python3 -m venv .venv && .venv/bin/pip install .
cp .env.example .env && nano .env
crontab -e
```

```cron
# каждый день в 9:00, лог в файл
0 9 * * * cd /opt/price-parser && .venv/bin/price-parser run --max-pages 0 >> output/cron.log 2>&1
```

## Вариант 3. Docker

```bash
docker build -t price-parser .
docker run --rm --env-file .env -v /opt/price-parser/output:/app/output price-parser run --max-pages 0
```

Свои профили можно подключить без пересборки образа:

```bash
docker run --rm --env-file .env \
  -v /opt/price-parser/output:/app/output \
  -v /opt/price-parser/profiles:/app/profiles:ro \
  price-parser run -p my-shop
```

Для расписания эту же команду можно поставить в cron на хосте.

## Уведомления в Telegram

1. Создайте бота у [@BotFather](https://t.me/BotFather), скопируйте токен в `TELEGRAM_BOT_TOKEN`.
2. Напишите боту что угодно (или добавьте его в группу).
3. Узнайте ID чата, например у [@userinfobot](https://t.me/userinfobot), и впишите в `TELEGRAM_CHAT_ID`.
4. `NOTIFY_THRESHOLD_PERCENT=5` пришлёт сообщение, только если цена изменилась больше чем на 5%.

## Где лежат данные

| Файл | Что в нём |
|---|---|
| `output/products.xlsx` | последняя выгрузка в Excel |
| `output/products.csv` | то же в CSV |
| `output/products.html` | отчёт для браузера |
| `output/prices.db` | история всех запусков (SQLite). Не удаляйте, иначе сравнивать будет не с чем |

Для резервной копии достаточно сохранять `prices.db`.

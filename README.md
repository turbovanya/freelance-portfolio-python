# Python: парсеры, Telegram-боты, интеграции

[![tests](https://github.com/turbovanya/freelance-portfolio-python/actions/workflows/tests.yml/badge.svg)](https://github.com/turbovanya/freelance-portfolio-python/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

Меня зовут Иван, пишу на Python. Здесь три небольших проекта под типовые задачи: собрать данные с сайта в таблицу, сделать бота для заявок, связать форму на сайте с Telegram. Каждый запускается отдельно, настраивается через `.env` и покрыт тестами.

## Проекты

### [Парсер цен → Excel / CSV](01-price-parser)
Обходит каталог, фильтрует товары, выгружает в XLSX и CSV. Хранит историю цен в SQLite и при повторном запуске показывает, что подорожало и подешевело.
`requests` · `BeautifulSoup` · `openpyxl` · `SQLite`

### [Telegram-бот: FAQ и заявки](02-telegram-lead-bot)
Отвечает на частые вопросы, собирает заявку (имя → телефон → комментарий) и сразу присылает её админу. Для админа есть `/stats` и `/export` в CSV.
`aiogram 3` · `SQLite`

### [Заявки с сайта → Telegram](03-webhook-lead-notifier)
Небольшой API: принимает форму с сайта, проверяет данные, сохраняет и отправляет в Telegram. Если Telegram недоступен, заявка не теряется и будет дослана позже.
`FastAPI` · `httpx` · `SQLite`

## Запуск

Как запустить каждый проект, написано в его README. Тесты:

```bash
cd 01-price-parser          # или любой другой
pip install -r requirements.txt
pytest
```

Для тестов не нужны ни токены, ни интернет: Telegram и сайт подменяются заглушками.

## Что общего у всех трёх

- секреты только в `.env`, в репозитории лежит `.env.example`
- ввод пользователя проверяется: телефон приводится к `+7XXXXXXXXXX`, мусор отсекается
- сетевые ошибки не роняют программу: повторы в парсере, сохранение заявки до отправки в боте и API
- выгрузки открываются в Excel без «кракозябр», а формулы из пользовательского ввода экранируются

Лицензия — MIT.

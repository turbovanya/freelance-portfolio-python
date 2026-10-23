# 03 · Приём заявок с сайта → Telegram + база + CSV (webhook-сервис)

**Задача клиента:** «заявки с формы на сайте должны приходить мне в Telegram и сохраняться в таблицу». Типичная автоматизация/интеграция (сайт, Tilda, CRM-формы → мессенджер).

## Возможности
- `POST /webhook/lead` (JSON), защита ключом в заголовке `X-API-Key`
- Валидация: имя, телефон (нормализуется в `+7…`), email
- Защита от ботов: honeypot-поле `website`
- Сохранение в SQLite; если Telegram недоступен — заявка не теряется, помечается `notified=0`
- `GET /leads.csv` — выгрузка для Excel, `GET /health` — проверка
- CORS настраивается для домена сайта

## Запуск за 5 минут
```bash
pip install -r requirements.txt
cp .env.example .env     # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, API_KEY
uvicorn app.main:get_app --factory --port 8000
pytest
```

## Пример запроса
```bash
curl -X POST http://localhost:8000/webhook/lead \
  -H "X-API-Key: change-me" -H "Content-Type: application/json" \
  -d '{"name":"Иван Петров","phone":"8 912 345-67-89","message":"Нужен бот"}'
# {"ok":true,"id":1}
```
В Telegram придёт:
```
🔔 Заявка №1 (website)
👤 Иван Петров
📞 +79123456789
✉️ —
💬 Нужен бот
```

## Тесты (8)
Сохранение и отправка, ключ API, ошибки валидации, honeypot, сбой Telegram, CSV. Telegram подменяется заглушкой — токен не нужен.

> Честно: реальная отправка в Telegram здесь не проверялась (нет токена), покрыта заглушкой.

## Стек
Python 3, FastAPI, httpx, SQLite, pytest.

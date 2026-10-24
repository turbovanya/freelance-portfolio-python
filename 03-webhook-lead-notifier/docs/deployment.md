# Развёртывание с HTTPS

Формы сайтов отправляют данные только на `https://`, поэтому сервису нужен домен (например, `leads.example.ru`) и сертификат.

## 1. Сервер и Docker

Подойдёт любой VPS с 1 ГБ памяти и Docker.

```bash
git clone <репозиторий> && cd 03-webhook-lead-notifier
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # это API_KEY
nano .env           # API_KEY, TELEGRAM_*, ADMIN_PASSWORD, ALLOWED_ORIGINS
docker compose up -d --build
curl localhost:8000/health
```

Сервис слушает только `127.0.0.1:8000`, наружу его выставляет nginx.

## 2. nginx и сертификат

```nginx
server {
    server_name leads.example.ru;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo certbot --nginx -d leads.example.ru
```

Uvicorn в контейнере запущен с `--proxy-headers`, чтобы видеть настоящий IP клиента. Если nginx работает не на том же хосте, добавьте его адрес через `--forwarded-allow-ips`.

## 3. Проверка

```bash
curl -X POST https://leads.example.ru/api/v1/leads \
  -H "X-API-Key: <API_KEY>" -H "Content-Type: application/json" \
  -d '{"name": "Проверка", "phone": "+79990000000", "message": "тест"}'
```

Заявка должна прийти в Telegram и появиться в панели `https://leads.example.ru/admin`.

## Переменные окружения

| Переменная | Обязательна | По умолчанию | Описание |
|---|---|---|---|
| `API_KEY` | да | | секрет для сайта, не короче 16 символов |
| `TELEGRAM_BOT_TOKEN` | | | токен бота |
| `TELEGRAM_CHAT_ID` | | | ID чата или группы (у группы с минусом) |
| `ADMIN_USER` | | admin | логин в панель |
| `ADMIN_PASSWORD` | | | без пароля панель отключена |
| `ALLOWED_ORIGINS` | | `*` | домены сайта для CORS |
| `RATE_LIMIT_PER_MINUTE` | | 10 | заявок в минуту с одного IP |
| `RESEND_INTERVAL_SECONDS` | | 60 | как часто досылать недоставленное |
| `TIMEZONE` | | Europe/Moscow | для дат в уведомлениях и выгрузке |
| `DEMO_FORM` | | false | показать демо-форму на `/demo` |
| `DATABASE_URL` | | SQLite | в docker-compose уже PostgreSQL |

## Резервные копии

```bash
docker compose exec db pg_dump -U leads leads > leads_$(date +%F).sql
```

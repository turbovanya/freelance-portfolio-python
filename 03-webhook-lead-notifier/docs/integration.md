# Подключение формы сайта

Во всех вариантах нужен адрес сервиса (например, `https://leads.example.ru`) и ключ `API_KEY` из `.env`.

## Tilda

1. «Настройки сайта» → «Формы» → «Webhook».
2. Адрес: `https://leads.example.ru/api/v1/leads?key=<API_KEY>`
3. Сохраните. Tilda отправит проверочный запрос `test=test`, сервис ответит `ok`, и подключение будет подтверждено.
4. В нужных блоках формы отметьте галочку Webhook.

Поля Tilda `Name`, `Phone`, `Email`, `Comments` и название формы `formname` распознаются автоматически. UTM-метки Tilda передаёт сама, если они включены в настройках форм.

## WordPress (Contact Form 7)

Через плагин «CF7 to Webhook» или аналог:

- URL: `https://leads.example.ru/api/v1/leads`
- заголовок: `X-API-Key: <API_KEY>`
- поля: `your-name` → `name`, `your-phone` → `phone`, `your-email` → `email`, `your-message` → `message`

## Своя форма на JavaScript

Если форма отправляется прямо из браузера, ключ будет виден в коде страницы. Поэтому в этом режиме ограничьте домены в `ALLOWED_ORIGINS` и держите включённым rate limit. Лучший вариант: отправлять заявку со своего бэкенда, тогда ключ остаётся на сервере.

```html
<form id="lead">
  <input name="name" required>
  <input name="phone" required>
  <textarea name="message"></textarea>
  <!-- ловушка для ботов, человек её не видит -->
  <input name="website" style="position:absolute;left:-9999px" tabindex="-1" autocomplete="off">
  <button>Отправить</button>
</form>
<script>
document.getElementById("lead").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  const utm = new URLSearchParams(location.search);
  for (const k of ["utm_source", "utm_medium", "utm_campaign"]) if (utm.get(k)) data[k] = utm.get(k);
  const resp = await fetch("https://leads.example.ru/api/v1/leads", {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-API-Key": "<API_KEY>"},
    body: JSON.stringify(data),
  });
  const body = await resp.json();
  alert(resp.ok ? "Спасибо, заявка отправлена!" : body.errors.map((x) => x.message).join("\n"));
});
</script>
```

Полный рабочий пример: [`src/lead_hub/static/demo-form.html`](../src/lead_hub/static/demo-form.html).

## Поля

| Поле | Обязательно | Также принимается как |
|---|---|---|
| `name` | да | `fio`, `fullname`, `first_name`, `имя` |
| `phone` | да | `tel`, `telephone`, `phone_number`, `телефон` |
| `email` | | `e-mail`, `mail`, `почта` |
| `message` | | `comment`, `comments`, `text`, `question`, `комментарий` |
| `source` | | `formname`, `form_name`, `form` |
| `page_url` | | `referer`, `page`; если не передано, берётся заголовок Referer |
| `utm_source`, `utm_medium`, `utm_campaign` | | |
| `website` | | ловушка для ботов: должно быть пустым |

Регистр имён полей не важен.

## Ответы

| Код | Когда |
|---|---|
| `201` | заявка принята: `{"ok": true, "id": 12, "duplicate": false}` |
| `201` с `id: null` | сработала ловушка или это повтор той же заявки за 10 минут |
| `401` | неверный ключ |
| `422` | ошибка в полях, список в `errors` |
| `429` | слишком много запросов с одного IP |

"""Все тексты бота в одном месте: заказчик может поправить формулировки, не разбираясь в логике."""

from html import escape
from zoneinfo import ZoneInfo

from .db import Lead

BTN_LEAD = "📝 Оставить заявку"
BTN_FAQ = "❓ Частые вопросы"
BTN_CONTACTS = "📞 Контакты"
BTN_CANCEL = "Отмена"
BTN_SHARE_PHONE = "📱 Отправить мой номер"
BTN_SKIP = "Пропустить"

START = (
    "Здравствуйте! Это бот <b>{business}</b>.\n\n"
    "Здесь можно задать вопрос или оставить заявку. Выберите, что нужно:"
)
CONTACTS = (
    "Пишите прямо сюда в бот или оставьте заявку, менеджер перезвонит.\n"
    "Работаем Пн-Пт с 10:00 до 19:00 (МСК)."
)
CANCELLED = "Хорошо, отменил. Возвращаю в меню."
FAQ_INTRO = "Напишите вопрос своими словами, я постараюсь ответить. Частые темы:\n\n{topics}"
UNKNOWN_COMMAND = "Не знаю такой команды. Воспользуйтесь меню ниже."
FAQ_NOT_FOUND = "Не нашёл готового ответа. Оставьте заявку, и менеджер ответит лично."

ASK_NAME = "Как к вам обращаться?"
BAD_NAME = "Похоже, это не имя. Напишите, пожалуйста, имя буквами (от 2 до 50 символов)."
ASK_PHONE = "Приятно познакомиться, {name}! Оставьте номер телефона или нажмите кнопку ниже."
BAD_PHONE = "Не получилось распознать номер. Пример: <code>+7 912 345-67-89</code>"
ASK_COMMENT = "Коротко опишите задачу. Можно нажать «Пропустить»."
LEAD_ACCEPTED = "Спасибо! Заявка <b>№{id}</b> принята. Менеджер свяжется с вами в ближайшее время."
TOO_MANY_LEADS = (
    "Вы уже оставили несколько заявок за сутки. Менеджер скоро свяжется, повторно отправлять не нужно."
)

STATUS_FOR_CLIENT = {
    "in_work": "Ваша заявка №{id} взята в работу. Скоро с вами свяжутся.",
    "done": "Заявка №{id} выполнена. Спасибо, что обратились!",
}


def admin_card(lead: Lead, tz: ZoneInfo) -> str:
    who = (
        f"@{escape(lead.username)}" if lead.username else f'<a href="tg://user?id={lead.user_id}">профиль</a>'
    )
    return (
        f"🔔 <b>Заявка №{lead.id}</b> · {lead.status.label}\n\n"
        f"👤 {escape(lead.name)}\n"
        f"📞 <code>{lead.phone}</code>\n"
        f"💬 {escape(lead.comment) or '<i>без комментария</i>'}\n"
        f"✈️ {who}\n"
        f"🕒 {lead.created_local(tz):%d.%m.%Y %H:%M}"
    )


def stats_text(s: dict[str, int]) -> str:
    closed = s["done"] + s["rejected"]
    conversion = f"{s['done'] / closed:.0%}" if closed else "нет данных"
    return (
        "📊 <b>Статистика</b>\n\n"
        f"За сутки: <b>{s['last_day']}</b>\n"
        f"За неделю: <b>{s['last_week']}</b>\n"
        f"Всего: <b>{s['total']}</b>\n\n"
        f"🆕 Новые: {s['new']}\n🔧 В работе: {s['in_work']}\n✅ Выполнены: {s['done']}\n"
        f"🚫 Отклонены: {s['rejected']}\n\nДоля успешных среди закрытых: {conversion}"
    )


ADMIN_HELP = (
    "<b>Команды администратора</b>\n"
    "/stats: статистика по заявкам\n"
    "/leads: последние заявки\n"
    "/new: необработанные заявки\n"
    "/export: все заявки в CSV для Excel"
)

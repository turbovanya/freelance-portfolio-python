import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (BufferedInputFile, KeyboardButton, Message,
                           ReplyKeyboardMarkup, ReplyKeyboardRemove)

from .config import Config
from .db import LeadStorage
from .faq import find_answer
from .validators import clean_comment, normalize_phone, validate_name

log = logging.getLogger(__name__)

BTN_LEAD = "📝 Оставить заявку"
BTN_FAQ = "❓ Частые вопросы"
BTN_CANCEL = "Отмена"

MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_LEAD), KeyboardButton(text=BTN_FAQ)]], resize_keyboard=True
)
CANCEL_KB = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)
PHONE_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Отправить мой номер", request_contact=True)], [KeyboardButton(text=BTN_CANCEL)]],
    resize_keyboard=True,
)


class LeadForm(StatesGroup):
    name = State()
    phone = State()
    comment = State()


def format_lead_for_admin(lead_id: int, message: Message, name: str, phone: str, comment: str) -> str:
    user = message.from_user
    handle = f"@{user.username}" if user.username else f"id {user.id}"
    return (f"🔔 Новая заявка №{lead_id}\n"
            f"Имя: {name}\nТелефон: {phone}\nКомментарий: {comment or '—'}\nTelegram: {handle}")


def build_router(config: Config, storage: LeadStorage, faq: list) -> Router:
    router = Router()

    def is_admin(message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in config.admin_ids)

    @router.message(CommandStart())
    async def start(message: Message, state: FSMContext):
        await state.clear()
        await message.answer(
            f"Здравствуйте! Это бот «{config.business_name}».\nВыберите действие:", reply_markup=MENU
        )

    @router.message(Command("cancel"))
    @router.message(F.text == BTN_CANCEL)
    async def cancel(message: Message, state: FSMContext):
        await state.clear()
        await message.answer("Отменено. Возвращаю меню.", reply_markup=MENU)

    @router.message(F.text == BTN_FAQ)
    async def faq_list(message: Message):
        lines = "\n".join(f"• {item['question']}" for item in faq)
        await message.answer(f"Напишите вопрос своими словами — отвечу.\n\nТемы:\n{lines}")

    @router.message(F.text == BTN_LEAD)
    async def lead_start(message: Message, state: FSMContext):
        await state.set_state(LeadForm.name)
        await message.answer("Как к вам обращаться?", reply_markup=CANCEL_KB)

    @router.message(LeadForm.name)
    async def lead_name(message: Message, state: FSMContext):
        name = validate_name(message.text or "")
        if not name:
            await message.answer("Введите имя (2–50 символов, без цифр).")
            return
        await state.update_data(name=name)
        await state.set_state(LeadForm.phone)
        await message.answer("Укажите телефон или нажмите кнопку ниже:", reply_markup=PHONE_KB)

    @router.message(LeadForm.phone)
    async def lead_phone(message: Message, state: FSMContext):
        raw = message.contact.phone_number if message.contact else (message.text or "")
        phone = normalize_phone(raw)
        if not phone:
            await message.answer("Не похоже на российский номер. Пример: +7 912 345-67-89")
            return
        await state.update_data(phone=phone)
        await state.set_state(LeadForm.comment)
        await message.answer("Коротко опишите задачу (или напишите «-», чтобы пропустить):", reply_markup=CANCEL_KB)

    @router.message(LeadForm.comment)
    async def lead_comment(message: Message, state: FSMContext, bot: Bot):
        comment = clean_comment(message.text or "")
        comment = "" if comment == "-" else comment
        data = await state.get_data()
        await state.clear()
        lead_id = storage.add(message.from_user.id, message.from_user.username, data["name"], data["phone"], comment)
        text = format_lead_for_admin(lead_id, message, data["name"], data["phone"], comment)
        for admin_id in config.admin_ids:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                # чаще всего админ не нажал /start у бота; заявка уже в базе, так что просто пишем в лог
                log.exception("Не удалось отправить заявку №%s админу %s", lead_id, admin_id)
        await message.answer(f"Спасибо! Заявка №{lead_id} принята, скоро свяжемся.", reply_markup=MENU)

    @router.message(Command("stats"))
    async def stats(message: Message):
        if not is_admin(message):
            return
        s = storage.stats()
        await message.answer(f"Заявок всего: {s['total']}\nЗа последние сутки: {s['last_day']}")

    @router.message(Command("export"))
    async def export(message: Message):
        if not is_admin(message):
            return
        await message.answer_document(BufferedInputFile(storage.export_csv(), filename="leads.csv"))

    @router.message(F.text)
    async def free_text(message: Message):
        item = find_answer(faq, message.text)
        if item:
            await message.answer(item["answer"])
        else:
            await message.answer("Не нашёл ответ. Нажмите «Оставить заявку» — менеджер свяжется с вами.", reply_markup=MENU)

    return router

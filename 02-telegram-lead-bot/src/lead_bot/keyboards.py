from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import texts
from .db import LeadStatus


class LeadAction(CallbackData, prefix="lead"):
    id: int
    status: LeadStatus


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_LEAD)],
            [KeyboardButton(text=texts.BTN_FAQ), KeyboardButton(text=texts.BTN_CONTACTS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Задайте вопрос или выберите действие",
    )


def cancel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=texts.BTN_CANCEL)]], resize_keyboard=True)


def phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_SHARE_PHONE, request_contact=True)],
            [KeyboardButton(text=texts.BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def comment() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.BTN_SKIP), KeyboardButton(text=texts.BTN_CANCEL)]],
        resize_keyboard=True,
    )


# какие кнопки показывать менеджеру в зависимости от текущего статуса
_NEXT: dict[LeadStatus, list[tuple[str, LeadStatus]]] = {
    LeadStatus.NEW: [("🔧 Взять в работу", LeadStatus.IN_WORK), ("🚫 Отклонить", LeadStatus.REJECTED)],
    LeadStatus.IN_WORK: [("✅ Выполнена", LeadStatus.DONE), ("🚫 Отклонить", LeadStatus.REJECTED)],
    LeadStatus.DONE: [("↩️ Вернуть в работу", LeadStatus.IN_WORK)],
    LeadStatus.REJECTED: [("↩️ Вернуть в работу", LeadStatus.IN_WORK)],
}


def lead_actions(lead_id: int, status: LeadStatus) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for text, new_status in _NEXT[status]:
        kb.button(text=text, callback_data=LeadAction(id=lead_id, status=new_status))
    kb.adjust(2)
    return kb.as_markup()

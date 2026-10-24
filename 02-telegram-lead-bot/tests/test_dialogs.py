"""Сценарии целиком: от сообщения клиента до карточки у менеджера и смены статуса."""

import csv
import io

from conftest import ADMIN, CLIENT, submit_lead

from lead_bot.db import LeadStatus


async def test_lead_flow_saves_and_notifies_admin(h):
    await h.say("/start")
    assert "Студия «Пример»" in h.tg.texts(CLIENT)[-1]

    await submit_lead(h)

    leads = await h.repo.all()
    assert len(leads) == 1
    lead = leads[0]
    assert (lead.name, lead.phone, lead.comment, lead.status) == ("Иван", "+79123456789", "Нужен бот", "new")
    assert "№1" in h.tg.texts(CLIENT)[-1]

    card = h.tg.last(ADMIN)
    assert "Заявка №1" in card.text and "@client" in card.text and "+79123456789" in card.text
    buttons = [b.text for row in card.reply_markup.inline_keyboard for b in row]
    assert buttons == ["🔧 Взять в работу", "🚫 Отклонить"]


async def test_phone_from_contact_button_and_skip_comment(h):
    await h.say("📝 Оставить заявку")
    await h.say("Мария")
    await h.say(None, contact="+79990001122")
    await h.say("Пропустить")
    lead = (await h.repo.all())[0]
    assert (lead.phone, lead.comment) == ("+79990001122", "")


async def test_invalid_input_keeps_form_on_same_step(h):
    await h.say("📝 Оставить заявку")
    await h.say("12345")
    assert "не имя" in h.tg.texts(CLIENT)[-1]
    await h.say("Мария")
    await h.say("не телефон")
    assert "распознать номер" in h.tg.texts(CLIENT)[-1]
    assert await h.repo.all() == []
    await h.say("+7 999 000 11 22")
    await h.say("Пропустить")
    assert len(await h.repo.all()) == 1


async def test_cancel_by_button_and_command(h):
    await h.say("📝 Оставить заявку")
    await h.say("Отмена")
    await h.say("Иван")  # уже не в форме: это обычный текст, а не имя
    await h.say("📝 Оставить заявку")
    await h.say("/cancel")
    assert "отменил" in h.tg.texts(CLIENT)[-1]
    assert await h.repo.all() == []


async def test_daily_limit_against_spam(h):
    for _ in range(3):
        await submit_lead(h)
    await h.say("📝 Оставить заявку")
    assert "несколько заявок" in h.tg.texts(CLIENT)[-1]
    assert len(await h.repo.all()) == 3


async def test_manager_moves_lead_through_statuses_and_client_is_informed(h):
    await submit_lead(h)
    await h.press(h.tg.last(ADMIN), "🔧 Взять в работу")

    lead = (await h.repo.all())[0]
    assert lead.status == LeadStatus.IN_WORK and lead.manager_id == ADMIN
    edited = h.tg.last(ADMIN)
    assert edited.edited and "В работе" in edited.text
    assert "взята в работу" in h.tg.texts(CLIENT)[-1]

    await h.press(edited, "✅ Выполнена")
    assert (await h.repo.all())[0].status == LeadStatus.DONE
    assert "выполнена" in h.tg.texts(CLIENT)[-1]


async def test_lead_is_saved_even_if_admin_blocked_bot(h):
    h.tg.fail_for.add(ADMIN)
    await submit_lead(h)
    assert len(await h.repo.all()) == 1
    assert "принята" in h.tg.texts(CLIENT)[-1]


async def test_faq_answers_and_fallback(h):
    await h.say("а какая у вас стоимость?")
    assert "рассчитаем" in h.tg.texts(CLIENT)[-1]
    await h.say("ывапывап")
    assert "Не нашёл" in h.tg.texts(CLIENT)[-1]
    await h.say("❓ Частые вопросы")
    assert "Есть ли гарантия?" in h.tg.texts(CLIENT)[-1]


async def test_admin_commands_are_hidden_from_clients(h):
    await submit_lead(h)
    await h.say("/stats", user_id=CLIENT)
    assert "Не знаю такой команды" in h.tg.texts(CLIENT)[-1]

    await h.say("/stats", user_id=ADMIN)
    assert "Всего: <b>1</b>" in h.tg.texts(ADMIN)[-1]


async def test_admin_lists_and_export(h):
    await submit_lead(h, name="Иван")
    await submit_lead(h, name="Пётр", user_id=8)
    await h.press(h.tg.last(ADMIN), "🚫 Отклонить")

    before = len(h.tg.messages)
    await h.say("/new", user_id=ADMIN)
    new_cards = h.tg.messages[before:]
    assert len(new_cards) == 1 and "Иван" in new_cards[0].text

    await h.say("/export", user_id=ADMIN)
    doc = h.tg.last(ADMIN)
    assert doc.document.startswith("leads_") and "Заявок в файле: 2" in doc.text
    rows = list(csv.reader(io.StringIO(doc.raw.decode("utf-8-sig")), delimiter=";"))
    assert [r[2] for r in rows[1:]] == ["Иван", "Пётр"] and rows[2][6] == "Отклонена"


async def test_stats_counts_by_status(h):
    await submit_lead(h)
    await submit_lead(h, user_id=8)
    await h.press(h.tg.last(ADMIN), "🔧 Взять в работу")
    stats = await h.repo.stats()
    assert (stats["total"], stats["new"], stats["in_work"], stats["last_day"]) == (2, 1, 1, 2)

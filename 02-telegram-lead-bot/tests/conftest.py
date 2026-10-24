import pytest
from harness import BotHarness

ADMIN = 100
CLIENT = 7


@pytest.fixture
async def h():
    harness = await BotHarness.create(admin_ids=[ADMIN])
    yield harness
    await harness.close()


async def submit_lead(h, name="Иван", phone="8 (912) 345-67-89", comment="Нужен бот", user_id=CLIENT):
    for text in ("📝 Оставить заявку", name, phone, comment):
        await h.say(text, user_id=user_id)

"""Прогоняет демонстрационный сценарий через настоящий код бота и сохраняет переписку в HTML.

Telegram не нужен: апдейты подаются прямо в Dispatcher, ответы бота перехватываются.
Запуск из папки проекта:  python scripts/render_demo.py docs/demo
Получатся client.html (переписка клиента), manager.html (что видит менеджер) и overview.html (обе рядом).
"""

import asyncio
import html
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from harness import BotHarness

CLIENT, MANAGER = 7, 100


@dataclass
class Bubble:
    outgoing: bool  # True: пишет человек, False: отвечает бот
    text: str
    message_id: int | None = None
    inline: list[list[str]] = field(default_factory=list)


@dataclass
class Chat:
    title: str
    bubbles: list[Bubble] = field(default_factory=list)
    keyboard: list[list[str]] = field(default_factory=list)


def _inline(markup: Any) -> list[list[str]]:
    rows = getattr(markup, "inline_keyboard", None) or []
    return [[b.text for b in row] for row in rows]


async def scenario() -> dict[int, Chat]:
    h = await BotHarness.create(admin_ids=[MANAGER], business_name="Студия «Пример»")
    chats = {CLIENT: Chat("Студия «Пример»"), MANAGER: Chat("Студия «Пример» · менеджер")}
    seen = 0

    def collect() -> None:
        nonlocal seen
        for out in h.tg.messages[seen:]:
            chat = chats[out.chat_id]
            if out.edited:
                for b in chat.bubbles:
                    if b.message_id == out.message_id:
                        b.text, b.inline = out.text, _inline(out.reply_markup)
                continue
            text = out.text if not out.document else f"📄 <b>{out.document}</b><br>{out.text}"
            chat.bubbles.append(Bubble(False, text, out.message_id, _inline(out.reply_markup)))
            rows = getattr(out.reply_markup, "keyboard", None)
            if rows is not None:
                chat.keyboard = [[b.text for b in row] for row in rows]
        seen = len(h.tg.messages)

    async def say(text: str | None, user: int = CLIENT, contact: str | None = None) -> None:
        chats[user].bubbles.append(Bubble(True, html.escape(text) if text else f"📱 {contact}"))
        await h.say(text, user_id=user, contact=contact)
        collect()

    await say("/start")
    await say("Сколько стоит сделать бота?")
    await say("📝 Оставить заявку")
    await say("Иван")
    await say(None, contact="+79123456789")
    await say("Нужен бот для записи клиентов на услуги")

    card = h.tg.last(MANAGER)
    await h.press(card, "🔧 Взять в работу", user_id=MANAGER)
    collect()
    await say("/stats", user=MANAGER)
    await h.close()
    return chats


CSS = """
* { box-sizing: border-box; }
body { margin: 0; background: #fff; font: 15px/1.4 -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }
.pair { display: flex; gap: 28px; justify-content: center; align-items: flex-start; padding: 8px 20px 20px; }
.pair h3 { margin: 6px 0 10px; font-size: 16px; color: #5b6576; font-weight: 600; text-align: center; }
.phone { width: 420px; margin: 0 auto; border-radius: 18px; overflow: hidden; box-shadow: 0 6px 24px rgba(30,50,80,.18); background: #c8d9e6; display: flex; flex-direction: column; }
.head { background: #517da2; color: #fff; padding: 12px 16px; display: flex; gap: 12px; align-items: center; }
.ava { width: 38px; height: 38px; border-radius: 50%; background: #f5a623; display: grid; place-items: center;
       font-weight: 700; }
.head b { display: block; } .head span { font-size: 13px; opacity: .8; }
.feed { padding: 12px 10px; display: flex; flex-direction: column; gap: 6px; }
.msg { max-width: 82%; padding: 7px 11px; border-radius: 12px; white-space: pre-wrap; word-wrap: break-word;
       box-shadow: 0 1px 1px rgba(0,0,0,.12); }
.in { background: #fff; align-self: flex-start; border-bottom-left-radius: 4px; }
.out { background: #e1ffc7; align-self: flex-end; border-bottom-right-radius: 4px; }
.msg code { background: rgba(0,0,0,.06); padding: 0 3px; border-radius: 3px; font-size: 14px; }
.msg a { color: #2a6ebb; text-decoration: none; }
.inline { align-self: flex-start; width: 82%; display: flex; flex-direction: column; gap: 4px; margin-top: -2px; }
.inline div { display: flex; gap: 4px; }
.inline span { flex: 1; text-align: center; background: rgba(81,125,162,.55); color: #fff; padding: 7px; border-radius: 8px;
               font-size: 14px; }
.kb { background: #eef1f4; padding: 8px; display: flex; flex-direction: column; gap: 6px; border-top: 1px solid #d5dbe1; }
.kb div { display: flex; gap: 6px; }
.kb span { flex: 1; text-align: center; background: #fff; padding: 10px 6px; border-radius: 8px; font-size: 14px;
           box-shadow: 0 1px 1px rgba(0,0,0,.1); }
"""


def render_phone(chat: Chat) -> str:
    parts = ['<div class="phone">',
             f'<div class="head"><div class="ava">С</div><div><b>{html.escape(chat.title)}</b>'
             "<span>бот</span></div></div><div class=\"feed\">"]  # fmt: skip
    for b in chat.bubbles:
        parts.append(f'<div class="msg {"out" if b.outgoing else "in"}">{b.text}</div>')
        if b.inline:
            rows = "".join("<div>" + "".join(f"<span>{t}</span>" for t in row) + "</div>" for row in b.inline)
            parts.append(f'<div class="inline">{rows}</div>')
    parts.append("</div>")
    if chat.keyboard:
        rows = "".join(
            "<div>" + "".join(f"<span>{t}</span>" for t in row) + "</div>" for row in chat.keyboard
        )
        parts.append(f'<div class="kb">{rows}</div>')
    parts.append("</div>")
    return "".join(parts)


def page(body: str) -> str:
    return f'<!doctype html><meta charset="utf-8"><style>{CSS}</style>{body}'


def overview(client: Chat, manager: Chat) -> str:
    """Обе стороны рядом: что видит клиент и что видит менеджер."""
    return page(
        '<div class="pair">'
        f"<div><h3>Клиент</h3>{render_phone(client)}</div>"
        f"<div><h3>Менеджер</h3>{render_phone(manager)}</div>"
        "</div>"
    )


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/demo")
    out_dir.mkdir(parents=True, exist_ok=True)
    chats = asyncio.run(scenario())
    (out_dir / "client.html").write_text(page(render_phone(chats[CLIENT])), encoding="utf-8")
    (out_dir / "manager.html").write_text(page(render_phone(chats[MANAGER])), encoding="utf-8")
    (out_dir / "overview.html").write_text(overview(chats[CLIENT], chats[MANAGER]), encoding="utf-8")
    print(f"Готово: {out_dir.resolve()}")


if __name__ == "__main__":
    main()

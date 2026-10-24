from aiogram import Router

from . import admin, common, faq, lead_form


def build_router() -> Router:
    root = Router(name="root")
    # порядок важен: свободный текст (FAQ) обрабатывается последним
    root.include_routers(
        common.make_router(), admin.make_router(), lead_form.make_router(), faq.make_router()
    )
    return root

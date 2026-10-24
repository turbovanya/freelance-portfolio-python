"""Понятные ошибки на русском: их можно показать посетителю сайта прямо под формой."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

FIELDS = {"name": "Имя", "phone": "Телефон", "email": "Email", "message": "Сообщение", "source": "Источник"}

MESSAGES = {
    "missing": "обязательное поле",
    "string_too_short": "слишком короткое значение",
    "string_too_long": "слишком длинное значение",
    "string_type": "ожидается текст",
    "int_parsing": "ожидается число",
}


def _message(error: dict[str, Any]) -> str:
    field = str(error["loc"][-1]) if error.get("loc") else ""
    if field == "email":
        return "некорректный email"
    if error.get("type") == "value_error":
        # наши валидаторы уже пишут по-русски, pydantic добавляет префикс
        return str(error.get("msg", "")).removeprefix("Value error, ")
    return MESSAGES.get(str(error.get("type")), "некорректное значение")


def readable_errors(errors: list[dict[str, Any]]) -> list[dict[str, str]]:
    result = []
    for error in errors:
        field = str(error["loc"][-1]) if error.get("loc") else ""
        label = FIELDS.get(field, field)
        result.append(
            {"field": field, "message": f"{label}: {_message(error)}" if label else _message(error)}
        )
    return result


async def validation_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return JSONResponse(
        {"detail": "Проверьте поля формы", "errors": readable_errors(list(exc.errors()))},
        status_code=422,
    )


def install(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_handler)

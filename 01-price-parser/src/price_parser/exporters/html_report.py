from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from ..models import Product, RunResult

_env = Environment(
    loader=PackageLoader("price_parser", "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


_env.filters["money"] = _money


def export_html(result: RunResult, products: list[Product], path: Path) -> Path:
    """Отчёт, который можно открыть в браузере или отправить заказчику одним файлом."""
    path = path.with_suffix(".html")
    path.parent.mkdir(parents=True, exist_ok=True)
    html = _env.get_template("report.html.j2").render(result=result, products=products)
    path.write_text(html, encoding="utf-8")
    return path

"""Командная строка: price-parser run | history | runs | profiles."""

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from . import __version__
from .config import Settings
from .filters import ProductFilter
from .http import FetchError, HttpClient
from .notify import build_message, send_telegram
from .pipeline import RunOptions, run
from .profile import find_profile, list_profiles
from .storage import PriceStore

app = typer.Typer(help="Мониторинг цен: выгрузка каталога в Excel, CSV и HTML-отчёт.", no_args_is_help=True)
console = Console()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False, rich_tracebacks=True)],
    )


def _formats(value: str) -> tuple[str, ...]:
    formats = tuple(f.strip() for f in value.split(",") if f.strip())
    bad = [f for f in formats if f not in ("xlsx", "csv", "html")]
    if bad or not formats:
        raise typer.BadParameter("допустимо: xlsx, csv, html через запятую")
    return formats


@app.command("run")
def run_command(
    profile: Annotated[str, typer.Option("--profile", "-p", help="имя профиля из папки profiles/")] = "books",
    max_pages: Annotated[int | None, typer.Option(help="сколько страниц обойти, 0 = все")] = None,
    min_price: Annotated[float | None, typer.Option(help="минимальная цена")] = None,
    max_price: Annotated[float | None, typer.Option(help="максимальная цена")] = None,
    min_rating: Annotated[int | None, typer.Option(min=1, max=5, help="минимальный рейтинг")] = None,
    in_stock: Annotated[bool, typer.Option("--in-stock", help="только товары в наличии")] = False,
    formats: Annotated[str, typer.Option("--format", "-f", help="xlsx,csv,html")] = "xlsx,csv,html",
    notify: Annotated[bool, typer.Option(help="отправить сводку в Telegram")] = True,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Собрать каталог, сравнить с прошлым запуском и сохранить выгрузки."""
    _setup_logging(verbose)
    settings = Settings()
    site = find_profile(settings.profiles_dir, profile)
    options = RunOptions(
        max_pages=settings.max_pages if max_pages is None else max_pages,
        formats=_formats(formats),
        product_filter=ProductFilter(min_price, max_price, min_rating, in_stock),
    )

    console.print(f"[bold]price-parser {__version__}[/]  профиль [cyan]{site.name}[/]  {site.start_url}")
    try:
        with (
            HttpClient(settings) as client,
            PriceStore(settings.db_path) as store,
        ):
            result, selected, files = run(
                settings,
                site,
                options,
                client,
                store,
                on_page=lambda n, url, count: console.print(f"  [green]✓[/] страница {n}: {count} товаров"),
            )
    except FetchError as exc:
        console.print(f"[red]Ошибка загрузки:[/] {exc}")
        raise typer.Exit(1) from exc

    table = Table(title="Итог", show_header=False, title_justify="left", min_width=44)
    table.add_row("Собрано товаров", str(len(result.products)))
    table.add_row("В выгрузке после фильтров", str(len(selected)))
    table.add_row("Подорожало", f"[red]{len(result.increased)}[/]")
    table.add_row("Подешевело", f"[green]{len(result.decreased)}[/]")
    table.add_row("Новых товаров", str(len(result.new_products)))
    table.add_row("Пропало из каталога", str(len(result.removed)))
    console.print(table)

    if result.changes:
        changes = Table(title="Крупнейшие изменения", title_justify="left")
        changes.add_column("Товар", max_width=44, overflow="ellipsis", no_wrap=True)
        changes.add_column("Было", justify="right")
        changes.add_column("Стало", justify="right")
        changes.add_column("%", justify="right")
        for c in result.changes[:8]:
            color = "red" if c.is_increase else "green"
            changes.add_row(
                c.title, f"{c.old_price:.2f}", f"{c.new_price:.2f}", f"[{color}]{c.percent:+.1f}%[/]"
            )
        console.print(changes)
    elif result.first_run:
        console.print("[dim]Первый запуск: изменения появятся со следующего.[/]")

    for fmt, path in files.items():
        console.print(f"  {fmt.upper():<5} {path}")

    message = build_message(result, settings.notify_threshold_percent)
    if notify and message and settings.telegram_enabled:
        sent = send_telegram(settings, message)
        console.print("  Telegram: сводка отправлена" if sent else "  [red]Telegram: не удалось отправить[/]")


@app.command()
def history(
    url: Annotated[str, typer.Argument(help="ссылка на товар")],
    limit: Annotated[int, typer.Option(help="сколько последних точек показать")] = 20,
) -> None:
    """История цены одного товара."""
    with PriceStore(Settings().db_path) as store:
        points = store.history(url, limit)
    if not points:
        console.print("Нет данных по этому товару.")
        raise typer.Exit(1)
    table = Table("Дата", "Цена")
    for p in points:
        table.add_row(p.seen_at.replace("T", " ")[:16], f"{p.price:.2f} {p.currency}")
    console.print(table)


@app.command()
def runs(limit: Annotated[int, typer.Option()] = 10) -> None:
    """Последние запуски."""
    with PriceStore(Settings().db_path) as store:
        rows = store.runs(limit)
    table = Table("№", "Профиль", "Дата", "Товаров")
    for run_id, profile, started_at, items in rows:
        table.add_row(str(run_id), profile, started_at.replace("T", " ")[:16], str(items))
    console.print(table)


@app.command()
def profiles(
    directory: Annotated[Path | None, typer.Option(help="папка с профилями")] = None,
) -> None:
    """Список настроенных сайтов."""
    table = Table("Имя", "Сайт", "Стартовая страница")
    for p in list_profiles(directory or Settings().profiles_dir):
        table.add_row(p.name, p.title, p.start_url)
    console.print(table)


if __name__ == "__main__":
    app()

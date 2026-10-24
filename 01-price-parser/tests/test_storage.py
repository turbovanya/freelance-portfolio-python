from datetime import timedelta

from conftest import NOW, product
from price_parser.filters import ProductFilter


def test_first_run_has_nothing_to_compare(store):
    diff = store.save_run("books", NOW, [product("a"), product("b")])
    assert diff.first_run
    assert diff.changes == [] and diff.new_products == [] and diff.removed == []


def test_detects_changes_new_and_removed(store):
    store.save_run("books", NOW, [product("a", 10), product("b", 20), product("c", 30, title="Старая")])
    diff = store.save_run(
        "books",
        NOW + timedelta(days=1),
        [product("a", 12.5), product("b", 20), product("d", 5, title="Новая")],
    )
    assert not diff.first_run
    assert [(c.url, c.delta, c.percent) for c in diff.changes] == [("a", 2.5, 25.0)]
    assert [p.title for p in diff.new_products] == ["Новая"]
    assert diff.removed == ["Старая"]


def test_profiles_have_separate_history(store):
    store.save_run("books", NOW, [product("a", 10)])
    diff = store.save_run("other", NOW, [product("a", 99)])
    assert diff.first_run and diff.changes == []


def test_changes_sorted_by_magnitude(store):
    store.save_run("books", NOW, [product("a", 100), product("b", 100)])
    diff = store.save_run("books", NOW, [product("a", 101), product("b", 50)])
    assert [c.url for c in diff.changes] == ["b", "a"]
    assert diff.changes[0].is_increase is False


def test_history_and_runs(store):
    for i, price in enumerate([10, 11, 12]):
        store.save_run("books", NOW + timedelta(days=i), [product("a", price)])
    assert [p.price for p in store.history("a")] == [12, 11, 10]
    assert [r[3] for r in store.runs()] == [1, 1, 1]


def test_filter():
    items = [product("a", 5, 1), product("b", 20, 4, in_stock=False), product("c", 50, 5)]
    assert [p.url for p in ProductFilter(min_price=10).apply(items)] == ["b", "c"]
    assert [p.url for p in ProductFilter(max_price=20, min_rating=4).apply(items)] == ["b"]
    assert [p.url for p in ProductFilter(in_stock_only=True).apply(items)] == ["a", "c"]

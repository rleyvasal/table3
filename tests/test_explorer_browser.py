"""The explorer's script, driven in headless Chromium (docs/explorer.md §6).

Needs Playwright and its Chromium: pip install pytest-playwright, then
python -m playwright install chromium. Skipped without them.
"""

import datetime as dt
import random

import polars as pl
import pytest

from table3._explore import explorer_html

sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # no Chromium installed for Playwright
            pytest.skip(f"no headless Chromium: {e}")
        yield b
        b.close()


@pytest.fixture
def explore(browser):
    pages = []

    def _open(df, total=None, **options):
        page = browser.new_page()
        pages.append(page)
        html = explorer_html(
            df, df.height if total is None else total, None,
            n=options.get("n", 10_000), height=options.get("height", 400),
            digits=options.get("digits"),
        )
        page.set_content(f"<!doctype html><html><body>{html}</body></html>")
        return page

    yield _open
    for page in pages:
        page.close()


def _rows(page) -> list[int]:
    return [int(r) for r in page.eval_on_selector_all(
        "[data-grid] tbody tr[data-row]", "trs => trs.map(t => t.dataset.row)")]


def _cells(page, row: int) -> list[str]:
    return page.eval_on_selector_all(
        f"tbody tr[data-row='{row}'] td", "tds => tds.map(t => t.textContent)")


def _status(page) -> str:
    return page.eval_on_selector("[data-status]", "s => s.textContent")


def _wait_status(page, start: str) -> None:
    page.wait_for_function(
        "start => document.querySelector('[data-status]').textContent.startsWith(start)",
        arg=start)


def _header(page, name: str):
    return page.locator(f"[data-grid] td[title='Click to sort by {name}']")


random.seed(1)
FRAME = pl.DataFrame({
    "x": random.sample(range(300), 300),
    "species": [["Adelie", "Gentoo", "Chinstrap", None][i % 4] for i in range(300)],
    "note": [f"item {i}" for i in range(300)],
    "day": [dt.date(2007 + i % 3, 1 + i % 12, 1) for i in range(300)],
    "mass": [None if i % 10 == 0 else 3000.0 + i for i in range(300)],
})


def test_grid_replaces_the_fallback(explore):
    page = explore(FRAME)
    assert page.eval_on_selector("[data-fallback]", "f => f.style.display") == "none"
    assert _status(page) == "300 of 300 rows | 5 columns"
    assert _rows(page)[:3] == [1, 2, 3]
    assert _cells(page, 1)[:3] == ["1", str(FRAME["x"][0]), "Adelie"]
    assert _cells(page, 1)[5] == "null"  # mass of row 1


def test_sort_cycles_and_keeps_row_numbers(explore):
    page = explore(FRAME)
    first = FRAME["x"].arg_min() + 1
    _header(page, "x").click()
    assert _rows(page)[0] == first
    assert _cells(page, first)[1] == "0"
    _header(page, "x").click()
    assert _cells(page, _rows(page)[0])[1] == "299"
    _header(page, "x").click()
    assert _rows(page)[:3] == [1, 2, 3]


def _arrows(page) -> list[str]:
    return [t.strip() for t in page.eval_on_selector_all(
        "[data-grid] thead tr:first-child td span", "ss => ss.map(s => s.textContent)")]


def test_every_header_shows_it_sorts(explore):
    page = explore(FRAME)
    assert _arrows(page) == ["↕"] * 5  # before any click
    _header(page, "species").click()
    assert _arrows(page) == ["↕", "▲", "↕", "↕", "↕"]
    _header(page, "species").click()
    assert _arrows(page)[1] == "▼"
    _header(page, "species").click()
    assert _arrows(page) == ["↕"] * 5


def test_nulls_sort_last_both_ways(explore):
    page = explore(FRAME)
    for _ in range(2):
        _header(page, "mass").click()
        page.eval_on_selector("[data-grid]", "b => { b.scrollTop = b.scrollHeight }")
        page.wait_for_timeout(100)
        assert _cells(page, _rows(page)[-1])[5] == "null"


def test_number_filter(explore):
    page = explore(FRAME)
    page.locator("input[placeholder='from']").first.fill("10")
    page.locator("input[placeholder='to']").first.fill("19")
    _wait_status(page, "10 of 300")
    assert sorted(int(_cells(page, r)[1]) for r in _rows(page)) == list(range(10, 20))


def test_choice_filter_and_null_choice(explore):
    page = explore(FRAME)
    select = page.locator("select").first
    select.select_option(label="Gentoo")
    _wait_status(page, "75 of 300")
    select.select_option(label="null")
    _wait_status(page, "75 of 300")
    assert _cells(page, _rows(page)[0])[2] == "null"
    select.select_option(label="All")
    _wait_status(page, "300 of 300")


def test_text_filter_search_and_date_prefix(explore):
    page = explore(FRAME)
    page.locator("[data-grid] input[placeholder='contains']").fill("item 2")  # 2, 20-29, 200-299
    _wait_status(page, "111 of 300")
    page.locator("input[type='search']").fill("adelie")
    _wait_status(page, "28 of 300")
    page.locator("[data-grid] input[placeholder='contains']").fill("")
    _wait_status(page, "75 of 300")
    page.locator("input[type='search']").fill("")
    page.locator("input[placeholder='from']").nth(1).fill("2008")
    page.locator("input[placeholder='to']").nth(1).fill("2008")
    _wait_status(page, "100 of 300")


def test_ten_thousand_rows_scroll_virtually(explore):
    page = explore(pl.DataFrame({"x": range(10_000)}), total=52_341)
    assert _status(page) == "10,000 of 10,000 rows | 1 columns (first 10,000 of 52,341)"
    assert len(_rows(page)) < 60  # only the rows in view, plus a buffer
    page.eval_on_selector("[data-grid]", "b => { b.scrollTop = b.scrollHeight }")
    page.wait_for_timeout(100)
    assert _rows(page)[-1] == 10_000
    assert _cells(page, 10_000)[1] == "9999"


def test_values_show_as_text_never_markup(explore):
    page = explore(pl.DataFrame({"s": ["</script><b>bold</b>", "y" * 100]}))
    assert _cells(page, 1)[1] == "</script><b>bold</b>"
    assert page.locator("[data-grid] tbody b").count() == 0
    cut = page.locator("[data-grid] tbody tr[data-row='2'] td").nth(1)
    assert cut.text_content() == "y" * 39 + "…"
    assert cut.get_attribute("title") == "y" * 100


def test_digits_in_the_grid(explore):
    df = pl.DataFrame({"r": [0.000123456789, 1.9015544041450778]})
    assert _cells(explore(df), 1)[1] == "0.000123"
    assert _cells(explore(df, digits=6), 1)[1] == "0.000123457"

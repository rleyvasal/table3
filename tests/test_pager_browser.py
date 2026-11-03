"""The paged table's script, driven in headless Chromium: rows past the first
page arrive as JSON and are drawn before paging. Skipped without Playwright."""

import polars as pl
import pytest

import table3

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
def show(browser):
    pages = []

    def _open(df, width=900, **options):
        page = browser.new_page(viewport={"width": width, "height": 700})
        pages.append(page)
        page.set_content(f"<!doctype html><html><body>{table3.html(df, **options)}</body></html>")
        return page

    yield _open
    for page in pages:
        page.close()


def _visible(page) -> list[list[str]]:
    return page.eval_on_selector_all(
        "tbody tr", "trs => trs.filter(t => t.style.display !== 'none')"
        ".map(t => [...t.cells].filter(c => c.style.display !== 'none').map(c => c.textContent))")


def _foot(page) -> str:
    return page.eval_on_selector("[data-foot]", "f => f.textContent")


def _click(page, text: str) -> None:
    page.locator("[data-pager] button", has_text=text).first.click()


FRAME = pl.DataFrame({"i": range(35), "s": [f"row {k}" for k in range(35)]})


def test_pages_drawn_from_json(show):
    page = show(FRAME)
    assert page.eval_on_selector_all("tbody tr", "trs => trs.length") == 35
    assert _foot(page) == "1–10 of 35 rows"
    assert [r[0] for r in _visible(page)] == [str(k) for k in range(10)]
    _click(page, "Next")
    assert _foot(page) == "11–20 of 35 rows"
    assert _visible(page)[0] == ["10", "row 10"]
    _click(page, "4")
    assert [r[0] for r in _visible(page)] == ["30", "31", "32", "33", "34"]


def test_drawn_rows_keep_the_formatting(show):
    df = pl.DataFrame({"f": [1.0] * 10 + [3.3000000000000003, None],
                       "s": ["x"] * 10 + ["<b>" + "y" * 60, "ok"]})
    page = show(df)
    _click(page, "Next")
    assert _visible(page) == [["3.3", "<b>" + "y" * 36 + "…"], ["null", "ok"]]
    cut = page.locator("tbody tr").nth(10).locator("td").nth(1)
    assert cut.get_attribute("title") == "<b>" + "y" * 60
    assert cut.get_attribute("style") == page.locator("tbody td").first.get_attribute("style")
    assert page.locator("tbody b").count() == 0


def test_column_pages_over_drawn_rows(show):
    wide = pl.DataFrame({f"column_{c}": [f"value {r}-{c}" for r in range(25)] for c in range(12)})
    page = show(wide, width=600)
    foot = _foot(page)
    assert foot.startswith("1–10 of 25 rows | 1–") and foot.endswith(" of 12 columns")
    shown = len(_visible(page)[0])
    _click(page, "columns ▸")
    assert _visible(page)[0][0] == f"value 0-{shown}"
    _click(page, "Next")
    assert _visible(page)[0][0] == f"value 10-{shown}"

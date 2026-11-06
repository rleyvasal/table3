"""The live explorer's grid in headless Chromium, its pages answered by ``Source``.

The page holds the grid's script (``EXPLORER_CORE``) as the widget runs it;
each request goes to a ``Source`` through Playwright, as the widget's go
through the kernel. Skipped without Playwright and its Chromium.
"""

import json
import random

import polars as pl
import pytest

from table3._explorer_js import EXPLORER_CORE
from table3._format import json_for_script
from table3._live import BLOCK
from table3._source import Source

sync_api = pytest.importorskip("playwright.sync_api")

random.seed(3)
N = 1000
FRAME = pl.DataFrame({
    "x": random.sample(range(N), N),
    "species": [["Adelie", "Gentoo", "Chinstrap", None][i % 4] for i in range(N)],
    "note": [f"item {i}" for i in range(N)],
    "mass": [None if i % 10 == 0 else 3000.0 + i for i in range(N)],
})


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
def live(browser):
    pages = []

    def _open(df, *, slow_search=None):
        source = Source(df)
        page = browser.new_page()
        pages.append(page)
        asked = []

        def query(request):
            asked.append(request)
            return source.query(request)

        page.expose_function("t3query", query)

        def export(request):  # the widget's answer to an export: a file, as base64
            import base64

            request = dict(request)
            kind = request.pop("export")
            if request.pop("save", False):
                return {"saved": f"/kernel/folder/table3-export.{kind}"}
            return {"download": {"name": f"table3-export.{kind}"},
                    "b64": base64.b64encode(source.export(request, kind)).decode()}

        page.expose_function("t3export", export)
        meta = {"columns": source.columns, "total": source.total, "block": BLOCK,
                "layouts": source.layouts,
                "first": source.query({"offset": 0, "limit": BLOCK, "profile": True})}
        # slow_search: requests for that search answer late, as a busy kernel would.
        page.set_content(
            "<!doctype html><html><body><div id='root' data-height='300'></div><script>"
            + EXPLORER_CORE
            + f"\nvar meta = {json_for_script(meta)}, slow = {json.dumps(slow_search)};\n"
            + """table3Explorer(document.getElementById('root'), meta, {block: meta.block,
              fetch: function (req) {
                if (req.export) return window.t3export(req).then(function (msg) {
                  if (msg.b64) msg.buffers = [Uint8Array.from(atob(msg.b64), function (ch) { return ch.charCodeAt(0); })];
                  return msg;
                });
                var answer = window.t3query(req);
                if (req.search !== slow) return answer;
                return answer.then(function (page) {
                  return new Promise(function (ok) { setTimeout(function () { ok(page); }, 600); });
                });
              }});
            </script></body></html>""")
        page.asked = asked
        page.source = source
        return page

    yield _open
    for page in pages:
        page.close()


def _rows(page):
    return [int(r) for r in page.eval_on_selector_all(
        "tbody tr[data-row]", "trs => trs.map(t => t.dataset.row)")]


def _cells(page, row):
    return page.eval_on_selector_all(
        f"tbody tr[data-row='{row}'] td", "tds => tds.map(t => t.textContent)")


def _status(page):
    return page.eval_on_selector("[data-status]", "s => s.textContent")


def _settle(page):
    page.wait_for_function(
        "() => !document.querySelector('[data-status]').dataset.loading"
        " && !document.querySelector('tbody tr[data-pending]')")


def test_first_block_comes_with_the_widget(live):
    page = live(FRAME)
    assert _status(page) == f"{N:,} of {N:,} rows | 4 columns"
    assert _rows(page)[:3] == [1, 2, 3]
    assert _cells(page, 1)[:3] == ["1", str(FRAME["x"][0]), "Adelie"]
    assert page.asked == []  # nothing fetched until a scroll or a change


def test_scrolling_fetches_the_block_in_view(live):
    page = live(FRAME)
    page.eval_on_selector("[data-grid]", "b => { b.scrollTop = b.scrollHeight }")
    page.wait_for_selector(f"tbody tr[data-row='{N}']")
    _settle(page)
    assert _rows(page)[-1] == N
    assert {r["offset"] for r in page.asked} == {BLOCK * (N // BLOCK - 1)}
    assert _cells(page, N)[3] == f"item {N - 1}"


def test_sort_and_search_run_over_every_row(live):
    page = live(FRAME)
    page.locator("td[title='Click to sort by x']").click()
    _settle(page)
    top = FRAME["x"].arg_min() + 1
    assert _rows(page)[0] == top and _cells(page, top)[1] == "0"
    assert page.asked[-1]["sort"] == {"column": "x", "desc": False}
    page.fill("input[type=search]", "item 99")
    page.wait_for_function("() => document.querySelector('[data-status]').textContent.startsWith('11 of')")
    _settle(page)
    want = page.source.order({"search": "item 99", "sort": {"column": "x", "desc": False}})
    assert _rows(page) == [i + 1 for i in want.to_list()]


def test_filters_go_to_the_kernel(live):
    page = live(FRAME)
    page.locator("[data-filter-toggle]").click()
    page.locator("[data-chip='mass']").click()
    page.locator("td:has([data-chip='mass']) input").first.fill("3990")
    page.keyboard.press("Enter")
    page.wait_for_function("() => document.querySelector('[data-status]').textContent.startsWith('9 of')")
    assert page.asked[-1]["filters"] == {"mass": {"from": 3990, "to": None}}


def test_an_answer_for_an_older_search_is_dropped(live):
    page = live(FRAME, slow_search="item 1")
    page.fill("input[type=search]", "item 1")
    page.wait_for_timeout(250)  # past the 150 ms pause: "item 1" is asked, slowly
    page.fill("input[type=search]", "item 12")
    page.wait_for_timeout(1000)  # the slow answer has come back by now
    _settle(page)
    assert _status(page).startswith("11 of")
    assert all("12" in _cells(page, r)[3] for r in _rows(page))


def test_an_error_shows_in_the_status_line(live):
    page = live(FRAME)
    page.evaluate("""() => { window.t3query = function () {
        return Promise.resolve({error: "no column 'gone' to sort"}); }; }""")
    page.locator("td[title='Click to sort by x']").click()
    page.wait_for_function("() => document.querySelector('[data-status]').textContent.startsWith('Error')")
    assert "gone" in _status(page)


def test_profiles_come_from_the_kernel(live):
    from test_explorer_browser import _check_profiles

    page = live(FRAME)
    _check_profiles(page, page.source, {})
    page.fill("input[type=search]", "item 99")
    page.wait_for_function("() => document.querySelector('[data-status]').textContent.startsWith('11 of')")
    _settle(page)
    assert page.asked[-1]["profile"] is True
    _check_profiles(page, page.source, {"search": "item 99"})
    assert page.eval_on_selector("[data-profile-basis]", "s => s.textContent") == "Profiles: all 11 rows"


def test_export_writes_every_kept_row(live):
    page = live(FRAME)
    page.fill("input[type=search]", "item 9")  # 9, 90-99, 900-999: 111 rows, past the first block
    page.wait_for_function("() => document.querySelector('[data-status]').textContent.startsWith('111 of')")
    page.locator("[data-columns-menu]").click()
    page.locator("[data-column-toggle='species']").uncheck()
    page.keyboard.press("Escape")
    page.locator("[data-export-menu]").click()
    assert page.eval_on_selector("[data-export-scope]", "s => s.textContent") == "111 rows × 3 columns, as sorted"
    with page.expect_download() as info:
        page.locator("[data-export='parquet']").click()
    got = pl.read_parquet(info.value.path())
    want = page.source.kept({"search": "item 9", "columns": ["x", "note", "mass"]})
    assert got.equals(want, null_equal=True) and got.height == 111
    page.locator("[data-export='save-csv']").click()
    page.wait_for_function("() => document.querySelector('[data-export-note]').textContent.startsWith('Saved')")
    assert page.asked == [r for r in page.asked if "export" not in r]  # exports don't touch the pages

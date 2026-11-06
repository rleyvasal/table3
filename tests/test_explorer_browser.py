"""The explorer's script, driven in headless Chromium (docs/explorer.md §6).

Needs Playwright and its Chromium: pip install pytest-playwright, then
python -m playwright install chromium. Skipped without them.
"""

import datetime as dt
import math
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


def _filters_on(page) -> None:
    toggle = page.locator("[data-filter-toggle]")
    if toggle.get_attribute("aria-pressed") != "true":
        toggle.click()


def _edit(page, name: str):
    """Open the filter on column *name*: the cell holding its editor."""
    _filters_on(page)
    page.locator(f"[data-chip='{name}']").click()
    return page.locator(f"[data-grid] thead td:has([data-chip='{name}'])")


def _chip(page, name: str) -> str:
    return page.locator(f"[data-chip='{name}']").text_content()


def test_number_filter(explore):
    page = explore(FRAME)
    cell = _edit(page, "x")
    cell.locator("input[placeholder='from']").fill("10")
    cell.locator("input[placeholder='to']").fill("19")
    _wait_status(page, "10 of 300")
    assert sorted(int(_cells(page, r)[1]) for r in _rows(page)) == list(range(10, 20))


def test_choice_filter_and_null_choice(explore):
    page = explore(FRAME)
    select = _edit(page, "species").locator("select")
    select.select_option(label="Gentoo")
    _wait_status(page, "75 of 300")
    assert _chip(page, "species") == "Gentoo"
    select = _edit(page, "species").locator("select")
    select.select_option(label="null")
    _wait_status(page, "75 of 300")
    assert _cells(page, _rows(page)[0])[2] == "null"
    select = _edit(page, "species").locator("select")
    select.select_option(label="All")
    _wait_status(page, "300 of 300")
    assert _chip(page, "species") == "All"


def test_text_filter_search_and_date_prefix(explore):
    page = explore(FRAME)
    note = _edit(page, "note").locator("input[placeholder='contains']")
    note.fill("item 2")  # 2, 20-29, 200-299
    _wait_status(page, "111 of 300")
    page.locator("input[type='search']").fill("adelie")
    _wait_status(page, "28 of 300")
    assert _chip(page, "note") == '"item 2"'
    page.locator("[data-clear='note']").click()
    _wait_status(page, "75 of 300")
    page.locator("input[type='search']").fill("")
    day = _edit(page, "day")
    day.locator("input[placeholder='from']").fill("2008")
    day.locator("input[placeholder='to']").fill("2008")
    _wait_status(page, "100 of 300")


def _shown(page, selector: str) -> int:
    return page.locator(selector).filter(visible=True).count()


def test_filters_hide_until_asked_for(explore):
    page = explore(FRAME)
    assert _shown(page, "[data-grid] thead input, [data-grid] thead select") == 0
    assert _shown(page, "[data-chip]") == 0
    _filters_on(page)
    assert [page.locator(f"[data-chip='{c}']").text_content() for c in FRAME.columns] == ["All"] * 5
    assert _shown(page, "[data-grid] thead input, [data-grid] thead select") == 0
    assert _shown(page, "[data-clear]") == 0
    _edit(page, "x")
    assert _shown(page, "[data-grid] thead input") == 2  # from and to, for x only


def test_a_range_reads_as_a_label_and_clears(explore):
    page = explore(FRAME)
    cell = _edit(page, "x")
    cell.locator("input[placeholder='from']").fill("10")
    cell.locator("input[placeholder='to']").fill("50")
    cell.locator("input[placeholder='to']").press("Enter")
    assert _chip(page, "x") == "10–50"
    assert _shown(page, "[data-grid] thead input") == 0
    assert _status(page).startswith("41 of 300")
    cell = _edit(page, "mass")
    cell.locator("input[placeholder='from']").fill("3100")
    page.locator("input[type='search']").click()  # a click elsewhere closes it
    assert _chip(page, "mass") == "≥ 3100"
    page.locator("[data-clear='x']").click()
    assert _chip(page, "x") == "All"
    assert _shown(page, "[data-clear]") == 1
    _wait_status(page, str(FRAME.filter(pl.col("mass") >= 3100).height) + " of 300")


def test_hiding_the_filters_clears_them(explore):
    page = explore(FRAME)
    _edit(page, "species").locator("select").select_option(label="Gentoo")
    _wait_status(page, "75 of 300")
    page.locator("[data-filter-toggle]").click()
    _wait_status(page, "300 of 300")
    _filters_on(page)
    assert _chip(page, "species") == "All"


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


def test_alignment_matches_the_paged_table(explore):
    """view() lines values up as the paged table does: numbers, dates and
    times right; text and booleans left, names and types with them."""
    from table3._html import right_aligned

    df = pl.DataFrame({"s": ["a", "b"], "n": [1, 2], "f": [1.5, 2.5],
                       "d": [dt.date(2020, 1, 1)] * 2, "t": [dt.datetime(2020, 1, 1)] * 2,
                       "b": [True, False], "c": pl.Series(["x", "y"], dtype=pl.Categorical)})
    want = ["right" if right_aligned(t) else "left" for t in df.dtypes]
    assert want == ["left", "right", "right", "right", "right", "left", "left"]
    page = explore(df)
    rows = page.evaluate("""() => [...document.querySelectorAll(
        '[data-grid] thead tr:nth-child(-n+2), [data-grid] tbody tr[data-row]')]
      .map(tr => [...tr.cells].slice(1).map(td => getComputedStyle(td).textAlign))""")
    assert len(rows) == 4 and all(r == want for r in rows)  # name, type, two rows


# -- profiles -----------------------------------------------------------------

PROFILED = pl.DataFrame({
    "x": [i % 37 if i % 11 else None for i in range(400)],
    "f": [[0.5, float("nan"), float("inf"), -2.5, None, 1e8, 3.3][i % 7] for i in range(400)],
    "species": [["Adelie", "Gentoo", "Chinstrap", None, "Adelie"][i % 5] for i in range(400)],
    "note": [f"item {i % 90}" for i in range(400)],
    "ok": [[True, False, None][i % 3] for i in range(400)],
    "day": [dt.date(2000 + i % 9, 1 + i % 12, 1) if i % 13 else None for i in range(400)],
})

PROFILE_DOM = """() => [...document.querySelectorAll('[data-grid] td[data-profile]')].map(td => ({
  name: td.dataset.profile,
  stats: (td.querySelector('[data-stats]') || {}).textContent,
  missing: (td.querySelector('[data-missing]') || {}).textContent,
  title: td.title,
  bars: Object.fromEntries([...td.querySelectorAll('rect[data-bin]')].map(
    r => [r.dataset.bin, +r.getAttribute('height')]))}))"""


def expected_profiles(source, request):
    """What the profile row should show for *request*, from Python's counts."""
    base, now = source.profile({}), source.profile(request)
    out = {}
    for col, lay, b, p in zip(source.columns, source.layouts, base["columns"], now["columns"]):
        stats = (f"{'≈' if p['approx'] else ''}{p['distinct']:,} distinct",
                 f"{p['missing']:,} missing" if p["missing"] else "\u00a0")
        if lay["type"] == "hist":
            most = max([1] + b["bins"])
            bars = {str(i): n / most for i, n in enumerate(p["bins"]) if n}
            out[col["name"]] = (stats, bars, None)
        else:
            total = sum(p["top"]) + p["other"]
            # Math.round: halves up, where Python's round() goes to even.
            tops = [f"{v}: {n:,} ({math.floor(100 * n / max(total, 1) + 0.5)}%)"
                    for v, n in zip(lay["values"], p["top"])]
            out[col["name"]] = (stats, {}, tops)
    return out


def _check_profiles(page, source, request):
    want = expected_profiles(source, request)
    for got in page.evaluate(PROFILE_DOM):
        stats, bars, tops = want[got["name"]]
        assert (got["stats"], got["missing"]) == stats, got["name"]
        assert got["bars"].keys() == bars.keys(), got["name"]
        assert all(abs(got["bars"][k] - bars[k]) < 1e-9 for k in bars), got["name"]
        if tops:
            assert got["title"].split("\n")[: len(tops)] == tops, got["name"]


def test_the_snapshot_profiles_match_python(explore):
    """The browser's recount of each column, as filters change, is Python's."""
    from table3._source import Source

    page = explore(PROFILED)
    source = Source(PROFILED)
    assert page.eval_on_selector("[data-profile-basis]", "s => s.textContent") == "Profiles: all 400 rows"
    _check_profiles(page, source, {})
    for q in ("item 1", "adelie", "2003", "null", "nan"):
        page.fill("input[type=search]", q)
        n = len(source.order({"search": q}))
        _wait_status(page, f"{n} of 400")
        _check_profiles(page, source, {"search": q})
    page.fill("input[type=search]", "")
    cell = _edit(page, "x")
    cell.locator("input[placeholder='from']").fill("5")
    cell.locator("input[placeholder='to']").fill("9")
    request = {"filters": {"x": {"from": 5, "to": 9}}}
    _wait_status(page, f"{len(source.order(request))} of 400")
    _check_profiles(page, source, request)


def test_the_profile_row_hides(explore):
    page = explore(PROFILED.head(20), total=1000)
    basis = page.eval_on_selector("[data-profile-basis]", "s => s.textContent")
    assert basis == "Profiles: these 20 snapshot rows"
    page.locator("[data-profile-toggle]").click()
    assert page.eval_on_selector("[data-grid] td[data-profile]", "td => td.offsetParent") is None
    page.locator("[data-profile-toggle]").click()
    assert page.eval_on_selector("[data-grid] td[data-profile]", "td => !!td.offsetParent")


# -- columns and export --------------------------------------------------------

EXPORTED = pl.DataFrame({
    "x": [5, 3, None, 1, 4, 2],
    "f": [0.1 + 0.2, float("nan"), float("inf"), -float("inf"), 2.0, None],
    "s": ["a,b", 'say "hi"', "line\nbreak", None, "plain", "x"],
    "ok": [True, False, None, True, True, False],
    "day": [dt.date(2020, 1, d) for d in range(1, 7)],
    "big": [2**60 + 1, 1, 2, 3, 4, 5],
})


def _download_csv(page) -> str:
    page.locator("[data-export-menu]").click()
    with page.expect_download() as info:
        page.locator("[data-export='csv']").click()
    return open(info.value.path()).read()


def test_snapshot_csv_is_polars_csv_of_the_kept_rows(explore):
    page = explore(EXPORTED)
    assert _download_csv(page) == EXPORTED.write_csv()
    page.keyboard.press("Escape")
    _header(page, "x").click()
    _header(page, "x").click()  # descending
    cell = _edit(page, "x")
    cell.locator("input[placeholder='from']").fill("2")
    _wait_status(page, "4 of 6")
    want = EXPORTED.filter(pl.col("x") >= 2).sort("x", descending=True)
    assert _download_csv(page) == want.write_csv()
    assert page.eval_on_selector("[data-export-scope]", "s => s.textContent") == \
        "4 rows × 6 columns, as sorted"


def test_hidden_columns_leave_the_grid_and_the_export(explore):
    page = explore(EXPORTED)
    page.locator("[data-columns-menu]").click()
    page.locator("[data-column-toggle='f']").uncheck()
    page.locator("[data-column-toggle='s']").uncheck()
    assert page.locator("[data-columns-menu]").text_content() == "Columns 4/6"
    assert len(_cells(page, 1)) == 5  # row number and four columns
    assert not page.locator("td[title='Click to sort by f']").is_visible()
    page.keyboard.press("Escape")
    assert _download_csv(page) == EXPORTED.drop("f", "s").write_csv()
    # The last column can't be hidden.
    page.keyboard.press("Escape")
    page.locator("[data-columns-menu]").click()
    for name in ("x", "ok", "day"):
        page.locator(f"[data-column-toggle='{name}']").uncheck()
    page.locator("[data-column-toggle='big']").click()
    assert page.locator("[data-column-toggle='big']").is_checked()
    assert page.locator("[data-columns-menu]").text_content() == "Columns 1/6"


def test_a_cut_snapshot_says_what_it_exports(explore):
    page = explore(EXPORTED.head(3), total=100)
    page.locator("[data-export-menu]").click()
    assert "3 snapshot rows" in page.eval_on_selector("[data-export-scope]", "s => s.textContent")
    assert "run the cell to export every row" in page.eval_on_selector("[data-export-note]", "s => s.textContent")

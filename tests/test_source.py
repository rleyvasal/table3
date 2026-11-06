"""The live explorer's backend: search, filters and sort over every row, then a page."""

import datetime as dt
import functools
import random

import polars as pl
import pytest

from table3._explore import payload
from table3._source import CACHE_ORDERS, Source, can_query, display_text, frame

MIXED = pl.DataFrame({
    "species": ["Adelie", "Gentoo", None, "Chinstrap", "Adelie", "Gentoo"],
    "mass": [3750, None, 4100, 3200, 3750, 5000],
    "ratio": [0.000123456789, float("nan"), float("inf"), -2.5, None, 1e8],
    "ok": [True, False, None, True, False, True],
    "day": [dt.date(2008, 5, 1), None, dt.date(2009, 1, 2), dt.date(2008, 12, 31),
            dt.date(2007, 1, 1), dt.date(2009, 6, 6)],
    "at": [dt.datetime(2020, 1, 1), dt.datetime(2020, 1, 1, 0, 0, 0, 500), None,
           dt.datetime(2019, 5, 5, 12), dt.datetime(2021, 1, 1), dt.datetime(2020, 1, 1)],
    "note": ["first note", "Second", "third", None, "null", "x" * 50],
})


def _ids(source, **request):
    return [i - 1 for i in source.query({"limit": 10_000, **request})["index"]]


# -- the browser's rules, as _explorer_js.py writes them ---------------------

def _js_string(v):
    if v is True:
        return "true"
    if v is False:
        return "false"
    return str(v)


class Browser:
    """The embedded explorer's passes() and compare(), over the same payload."""

    def __init__(self, df, digits=None):
        self.data = payload(df, df.height, df.height, digits)
        self.cols = self.data["columns"]
        self.rows = self.data["rows"]
        self.lower = []
        for r, row in enumerate(self.rows):
            out = []
            for c, v in enumerate(row):
                shown = self.data["shown"][c] and self.data["shown"][c][r]
                out.append((shown if shown is not None else "null" if v is None else _js_string(v)).lower())
            self.lower.append(out)

    def passes(self, r, filters, query):
        for c, col in enumerate(self.cols):
            f = filters.get(col["name"])
            if not f:
                continue
            v = self.rows[r][c]
            if "is" in f:
                if v != f["is"] or (v is None) != (f["is"] is None) or type(v) is not type(f["is"]):
                    return False
                continue
            if "has" in f:
                if f["has"] not in self.lower[r][c]:
                    return False
                continue
            if v is None:
                return False
            date = col["kind"] == "date"
            key = str(v) if date else v
            if f["from"] is not None and ((key[: len(f["from"])] < f["from"]) if date else key < f["from"]):
                return False
            if f["to"] is not None and ((key[: len(f["to"])] > f["to"]) if date else key > f["to"]):
                return False
        if query:
            return any(query in t for t in self.lower[r])
        return True

    def order(self, filters=None, search="", sort=None):
        filters = filters or {}
        query = search.strip().lower()
        out = [r for r in range(len(self.rows)) if self.passes(r, filters, query)]
        if sort:
            c = [col["name"] for col in self.cols].index(sort["column"])
            d = -1 if sort["desc"] else 1

            def compare(a, b):
                x, y = self.rows[a][c], self.rows[b][c]
                if x == y and type(x) is type(y):
                    return a - b
                if x is None:
                    return 1
                if y is None:
                    return -1
                diff = -1 if x < y else 1 if x > y else 0
                return diff * d if diff else a - b

            out.sort(key=functools.cmp_to_key(compare))
        return out


def _random_state(rng, df, browser):
    filters = {}
    for col in rng.sample(browser.cols, rng.randint(0, 2)):
        values = [v for v in df[col["name"]].to_list()]
        kind = col["kind"]
        if kind in ("choice", "bool"):
            pick = rng.choice((col.get("choices") or [True, False]) + [None])
            filters[col["name"]] = {"is": pick}
        elif kind == "number":
            nums = sorted(x for x in values if x is not None and x == x and abs(x) != float("inf"))
            a, b = rng.choice(nums + [None]), rng.choice(nums + [None])
            filters[col["name"]] = {"from": a, "to": b}
        elif kind == "date":
            texts = sorted(str(v) for v in values if v is not None)
            a, b = rng.choice(texts), rng.choice(texts)
            a, b = a[: rng.choice([4, 7, len(a)])], b[: rng.choice([4, 7, len(b)])]
            filters[col["name"]] = {"from": rng.choice([a, None]), "to": rng.choice([b, None])}
        else:
            text = rng.choice([v for v in values if v is not None] or ["x"])
            start = rng.randint(0, max(0, len(text) - 2))
            filters[col["name"]] = {"has": text[start:start + 2].lower()}
    search = rng.choice(["", "", "a", "20", "1", "null", "e8", " GEN ", "true", "nan"])
    sort = None
    if rng.random() < 0.7:
        sort = {"column": rng.choice(browser.cols)["name"], "desc": rng.random() < 0.5}
    return filters, search, sort


def _mixed_big(rows=300, seed=1):
    rng = random.Random(seed)
    pick = lambda xs: [rng.choice(xs) for _ in range(rows)]  # noqa: E731
    return pl.DataFrame({
        "species": pick(["Adelie", "Gentoo", "Chinstrap", None]),
        "island": [f"isle {rng.randint(0, 80)}" if rng.random() > 0.1 else None for _ in range(rows)],
        "mass": pick([3200, 3750, 4100, None, 5000, -1, 0]),
        "ratio": pick([0.000123456789, float("nan"), float("inf"), -2.5, None, 1e8, 3.3, 2.0]),
        "ok": pick([True, False, None]),
        "day": pick([dt.date(2008, 5, 1), None, dt.date(2009, 1, 2), dt.date(2008, 12, 31)]),
        "at": pick([dt.datetime(2020, 1, 1), dt.datetime(2020, 1, 1, 0, 0, 0, 500), None,
                    dt.datetime(2019, 5, 5, 12)]),
        "big": pick([2**60, -(2**60), 7, None]),
    })


@pytest.mark.parametrize("digits", [None, 3])
def test_same_rows_as_the_browser(digits):
    """Random searches, filters and sorts keep the rows the embedded explorer keeps, in its order."""
    df = _mixed_big()
    source, browser = Source(df, digits=digits), Browser(df, digits)
    rng = random.Random(7)
    for _ in range(400):
        filters, search, sort = _random_state(rng, df, browser)
        want = browser.order(filters, search, sort)
        got = _ids(source, filters=filters, search=search, sort=sort)
        assert got == want, (filters, search, sort)


def test_display_text_is_what_the_browser_shows():
    df = _mixed_big(60)
    browser = Browser(df)
    for c, name in enumerate(df.columns):
        text = display_text(df[name], None).str.to_lowercase().to_list()
        assert text == [row[c] for row in browser.lower], name


def test_header_matches_the_embedded_one():
    assert Source(MIXED).columns == payload(MIXED, 6, 6, None)["columns"]


# -- pages -------------------------------------------------------------------

def test_a_page_has_the_embedded_shape():
    source = Source(MIXED)
    page = source.query({"id": 1, "offset": 0, "limit": 6})
    whole = payload(MIXED, 6, 6, None)
    assert page["rows"] == whole["rows"] and page["shown"] == whole["shown"]
    assert page["index"] == [1, 2, 3, 4, 5, 6]
    assert (page["id"], page["total"], page["filtered"], page["offset"]) == (1, 6, 6, 0)


def test_pages_come_after_the_filter_and_sort():
    df = pl.DataFrame({"x": list(range(100)), "even": [i % 2 == 0 for i in range(100)]})
    source = Source(df)
    state = {"filters": {"even": {"is": True}}, "sort": {"column": "x", "desc": True}}
    page = source.query({**state, "offset": 10, "limit": 5})
    assert page["filtered"] == 50
    assert [r[0] for r in page["rows"]] == [78, 76, 74, 72, 70]
    assert page["index"] == [79, 77, 75, 73, 71]  # each row's place in the data


def test_page_past_the_end_and_selected_columns():
    source = Source(MIXED)
    assert source.query({"offset": 100, "limit": 10})["rows"] == []
    page = source.query({"limit": 2, "columns": ["mass", "species"]})
    assert page["columns"] == ["mass", "species"] and page["rows"] == [[3750, "Adelie"], [None, "Gentoo"]]


def test_stale_requests_get_no_answer():
    source = Source(MIXED)
    assert source.query({"id": 5, "search": "gen"})["filtered"] == 2
    assert source.query({"id": 4, "search": "g"}) is None
    assert source.query({"id": 6})["filtered"] == 6


def test_orders_are_cached_and_bounded():
    df = pl.DataFrame({"x": list(range(50))})
    source = Source(df)
    first = source.order({"filters": {"x": {"from": 10, "to": None}}})
    assert source.order({"filters": {"x": {"from": 10, "to": None}}, "offset": 5}) is first
    for i in range(CACHE_ORDERS + 3):
        source.order({"filters": {"x": {"from": i, "to": None}}})
    assert len(source._orders) == CACHE_ORDERS


def test_bad_requests():
    source = Source(MIXED)
    for request in ({"filters": {"nope": {"has": "a"}}}, {"sort": {"column": "nope"}},
                    {"columns": ["nope"]}):
        with pytest.raises(ValueError, match="nope"):
            source.query(request)


def test_the_text_null_and_a_missing_value():
    source = Source(MIXED)
    assert _ids(source, filters={"species": {"is": None}}) == [2]
    assert _ids(source, filters={"note": {"has": "null"}}) == [3, 4]  # missing reads "null" too
    assert _ids(source, sort={"column": "note", "desc": False}) == [1, 0, 4, 2, 5, 3]  # by code point, as the browser: "S" < "f"


def test_dates_compare_by_their_leading_characters():
    source = Source(MIXED)
    assert _ids(source, filters={"day": {"from": "2008", "to": "2008"}}) == [0, 3]
    assert _ids(source, filters={"at": {"from": "2020-01-01", "to": "2020-01-01"}}) == [0, 1, 5]


# -- what it reads -----------------------------------------------------------

def test_every_kind_of_input():
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    df = pl.DataFrame({"x": [3, 1, 2]})
    for data in (df, df.lazy(), df["x"], df.to_pandas(), df.to_pandas()["x"]):
        assert can_query(data)
        assert _ids(Source(data), sort={"column": "x", "desc": False}) == [1, 2, 0]
    assert not can_query([1, 2])
    with pytest.raises(TypeError, match="list"):
        frame([1, 2])
    assert isinstance(pd, object)


def test_a_package_frame_gives_its_data():
    class Wrapped:
        def __init__(self, lf):
            self._lf = lf

        def __table3__(self, n):  # the preview: not what the live explorer reads
            return self._lf.head(1).collect(), None, "Wrapped"

        def __table3_source__(self):
            return self._lf

    lf = pl.LazyFrame({"x": list(range(1000))}).filter(pl.col("x") % 3 == 0)
    source = Source(Wrapped(lf))
    assert source.total == 334
    assert source.query({"filters": {"x": {"from": 990, "to": None}}})["filtered"] == 4

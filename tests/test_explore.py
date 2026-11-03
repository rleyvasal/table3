import datetime as dt
import json
import re

import polars as pl
import pytest

import table3
from table3._explore import explorer_html, payload


def _data(html: str) -> dict:
    block = re.search(r"<script type='application/json'>(.*?)</script>", html, re.S).group(1)
    return json.loads(block)


@pytest.fixture
def notebook(monkeypatch):
    """Pretend to run in a notebook; collect what view() displays."""
    import IPython
    import IPython.display

    shown = []
    monkeypatch.setattr(IPython, "get_ipython", lambda: object())
    monkeypatch.setattr(IPython.display, "display", lambda obj: shown.append(obj.data))
    return shown


MIXED = pl.DataFrame({
    "species": ["Adelie", "Gentoo", None],
    "mass": [3750, None, 4100],
    "ratio": [0.000123456789, float("nan"), float("inf")],
    "ok": [True, False, None],
    "day": [dt.date(2008, 5, 1), None, dt.date(2009, 1, 2)],
    "note": [f"note {i}" for i in range(3)],
})


def test_kinds_and_choices():
    cols = payload(MIXED, 3, 10, None)["columns"]
    assert [c["kind"] for c in cols] == ["choice", "number", "number", "bool", "date", "choice"]
    assert cols[0]["choices"] == ["Adelie", "Gentoo"]
    assert [c["type"] for c in cols[:3]] == ["str", "i64", "f64"]
    many = pl.DataFrame({"s": [f"v{i}" for i in range(51)]})
    assert payload(many, 51, 100, None)["columns"][0]["kind"] == "text"


def test_raw_values_sort_and_shown_values_display():
    data = payload(MIXED, 3, 10, None)
    rows = data["rows"]
    assert rows[0] == ["Adelie", 3750, 0.000123456789, True, "2008-05-01", "note 0"]
    assert rows[1][1] is None and rows[1][2] is None  # null, and NaN as null
    assert rows[2][2] == 1.7976931348623157e308  # inf sorts last
    assert data["shown"][2] == ["0.000123", "NaN", "inf"]
    assert data["shown"][0] is None and data["shown"][1] is None
    assert payload(MIXED, 3, 10, 6)["shown"][2][0] == "0.000123457"


def test_big_integers_keep_their_digits():
    data = payload(pl.DataFrame({"id": [2**60 + 1, 5]}), 2, 10, None)
    assert data["shown"][0] == [str(2**60 + 1), "5"]


def test_script_end_in_a_value_is_escaped():
    html = explorer_html(
        pl.DataFrame({"s": ["</script><b>x"]}), 1, None, n=10, height=500, digits=None
    )
    assert "</script><b>x" not in html
    assert _data(html)["rows"] == [["</script><b>x"]]


def test_n_cut_and_counts():
    df = pl.DataFrame({"x": range(2500)})
    data = _data(explorer_html(df.head(1000), 2500, None, n=1000, height=500, digits=None))
    assert len(data["rows"]) == 1000 and data["total"] == 2500 and data["n"] == 1000


def test_fallback_without_scripts():
    df = pl.DataFrame({"x": range(250)})
    html = explorer_html(df, 250, "Frame", n=10_000, height=400, digits=None)
    fallback = html.split("<div data-fallback>")[1].split("<script type='application/json'>")[0]
    assert "the first 100 rows show here instead" in fallback
    assert fallback.split("<tbody>")[1].count("<tr") == 100
    assert "<script" not in fallback  # the fallback table needs no script
    assert "data-height='400'" in html and ">Frame<" in html


def test_view_shows_the_explorer_and_returns_data(notebook):
    df = pl.DataFrame({"x": range(30)})
    assert table3.view(df, n=20, height=300) is df
    (html,) = notebook
    assert "table3-explore-" in html and "data-height='300'" in html
    data = _data(html)
    assert len(data["rows"]) == 20 and data["total"] == 30


def test_view_takes_lazy_pandas_and_hooks(notebook):
    class Frame:
        def __table3__(self, n):
            return pl.DataFrame({"x": [1, 2]}), 2, "Frame (view)"

    table3.view(pl.LazyFrame({"x": [1, 2]}))
    table3.view(Frame())
    pd = pytest.importorskip("pandas")
    table3.view(pd.DataFrame({"x": [1.5, None]}))
    lazy, hooked, pandas = notebook
    assert _data(lazy)["total"] == 2
    assert ">Frame (view)<" in hooked
    assert _data(pandas)["shown"][0] == ["1.5", None]


def test_view_outside_a_notebook_prints(capsys):
    df = pl.DataFrame({"x": range(50)})
    assert table3.view(df) is df
    out = capsys.readouterr().out
    assert out.startswith("shape: (50, 1)") and "… first 20 rows" in out


def test_view_arguments_checked():
    df = pl.DataFrame({"x": [1]})
    for bad in ({"n": -1}, {"height": 0}, {"height": None}, {"digits": 0}):
        with pytest.raises(ValueError):
            table3.view(df, **bad)

"""Column profiles: bins and top values over all rows, counts over the rows kept."""

import datetime as dt

import polars as pl
import pytest

from table3 import _profile
from table3._source import Source

DF = pl.DataFrame({
    "small": [1, 2, 2, 3, None, 3, 3, 1],
    "wide": [0.5, float("nan"), 100.0, float("inf"), 25.0, None, -float("inf"), 50.0],
    "species": ["Adelie", "Gentoo", "Adelie", None, "Chinstrap", "Adelie", "Gentoo", "x"],
    "ok": [True, False, True, None, True, True, False, True],
    "day": [dt.date(2008, 1, d) for d in (1, 2, 2, 5, 9, 9, 9, 3)],
    "none": pl.Series([None] * 8, dtype=pl.Float64),
})


def _by(profile, source):
    return {c["name"]: p for c, p in zip(source.columns, profile["columns"])}


def test_layouts():
    lay = {c["name"]: x for c, x in zip(Source(DF).columns, Source(DF).layouts)}
    # Few integers or days: a bin per value.
    assert lay["small"] == {"type": "hist", "bins": 3, "lo": 0.5, "width": 1.0, "from": "1", "to": "3"}
    assert lay["day"]["bins"] == 9 and (lay["day"]["from"], lay["day"]["to"]) == ("2008-01-01", "2008-01-09")
    # Floats: BINS equal bins over the finite values, labelled as printed.
    assert lay["wide"]["bins"] == _profile.BINS and lay["wide"]["lo"] == 0.5
    assert (lay["wide"]["from"], lay["wide"]["to"]) == ("0.5", "100.0")
    # Text and booleans: the most common values, ties by value.
    assert lay["species"] == {"type": "top", "values": ["Adelie", "Gentoo", "Chinstrap"]}
    assert lay["ok"] == {"type": "top", "values": ["true", "false"]}
    assert lay["none"]["bins"] == 0


def test_counts_over_every_row():
    source = Source(DF)
    p = _by(source.profile({}), source)
    assert source.profile({})["basis"] == "full"
    assert p["small"] == {"missing": 1, "distinct": 3, "approx": False, "bins": [2, 2, 3]}
    # NaN is missing; ±inf fall in the end bins.
    assert p["wide"]["missing"] == 2 and sum(p["wide"]["bins"]) == 6
    assert p["wide"]["bins"][0] == 2 and p["wide"]["bins"][-1] == 2
    assert p["species"]["top"] == [3, 2, 1] and p["species"]["other"] == 1
    assert p["species"]["missing"] == 1 and p["species"]["distinct"] == 4
    assert p["ok"]["top"] == [5, 2] and p["ok"]["other"] == 0
    assert p["none"] == {"missing": 8, "distinct": 0, "approx": False, "bins": []}


def test_counts_follow_the_filters_not_the_sort():
    source = Source(DF)
    request = {"filters": {"species": {"is": "Adelie"}}}
    p = _by(source.profile(request), source)
    assert p["small"]["bins"] == [1, 1, 1] and p["species"]["top"] == [3, 0, 0]
    assert source.profile({**request, "sort": {"column": "small", "desc": True}}) is source.profile(request)
    # The same counts as profiling the kept rows on their own, in the whole data's bins.
    kept = DF.filter(pl.col("species") == "Adelie")
    lay = source.layouts[0]
    direct = _profile.counts(kept["small"], "number", lay, None, lambda s: s.cast(pl.String))
    assert direct == p["small"]


def test_a_page_brings_its_profile_when_asked():
    source = Source(DF)
    assert "profile" not in source.query({"limit": 2})
    page = source.query({"limit": 2, "search": "gentoo", "profile": True})
    assert page["profile"]["of"] == 2 == page["filtered"]


def test_many_rows_are_sampled(monkeypatch):
    monkeypatch.setattr(_profile, "SAMPLE_ROWS", 300)
    n = 1000
    df = pl.DataFrame({
        "x": [None if i % 10 == 0 else i % 50 for i in range(n)],
        "s": [f"v{i % 7}" for i in range(n)],
    })
    source = Source(df)
    p = source.profile({})
    assert (p["basis"], p["rows"], p["of"]) == ("sampled", 300, 1000)
    x = p["columns"][0]
    assert x["missing"] == 100  # counted over every row, not the sample
    assert x["approx"] and 45 <= x["distinct"] <= 50  # estimated, never above the rows
    sample = df["x"].gather(source.order({}).sample(300, seed=0))
    assert sum(x["bins"]) == sample.drop_nulls().len()  # bars are the sample's
    small = source.profile({"filters": {"x": {"from": 0, "to": 5}}})
    assert small["basis"] == "full" and not small["columns"][0]["approx"]


@pytest.mark.parametrize("digits", [None, 2])
def test_top_values_are_display_text(digits):
    df = pl.DataFrame({"c": pl.Series(["a", "b", "b", None], dtype=pl.Categorical)})
    source = Source(df, digits=digits)
    assert source.layouts[0] == {"type": "top", "values": ["b", "a"]}
    assert source.profile({})["columns"][0]["top"] == [2, 1]

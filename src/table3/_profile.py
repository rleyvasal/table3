"""Column profiles: what each column holds, over the rows the explorer keeps.

Each column gets a layout once, over all its rows, so its bars stay put as
filters change and a filtered profile can be drawn over the whole one:

- numbers, dates and times: a histogram of up to ``BINS`` equal bins from
  the smallest to the largest finite value (one bin per value for integers
  and dates spanning fewer than ``BINS``), labelled with those two values as
  the grid prints them; ±inf count in the end bins;
- everything else (text, pick-list values, booleans): its ``TOP`` most
  common values by display text, and the rest as "other".

Then, for the rows a request keeps (``Source.order``), ``counts`` gives per
column: the missing values (null, and NaN for floats), the distinct
non-missing values, and the bin or top-value counts. Up to ``SAMPLE_ROWS``
rows are profiled whole ("full"); past that a fixed random sample of them
("sampled"), with distinct values estimated over every kept row
(HyperLogLog, "approx") rather than counted on the sample.

The snapshot explorer recounts the same bins in the browser as its filters
change: numbers from their values, dates from the bin each row's value
falls in (sent with the rows, ``date_bins``), top values by display text.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from table3._format import float_text

BINS = 20
TOP = 3
SAMPLE_ROWS = 1_000_000  # rows profiled whole; past this, a sample
EXACT_DISTINCT = 1_000_000  # rows whose distinct values are counted, not estimated


def _hist_key(s: pl.Series) -> pl.Series:
    """What a histogram bins: numbers as floats (NaN missing), temporal values
    as their underlying integers."""
    if s.dtype.is_temporal():
        return s.to_physical().cast(pl.Float64)
    return s.cast(pl.Float64).fill_nan(None)


def _missing(s: pl.Series) -> int:
    n = s.null_count()
    if s.dtype.is_float():
        n += int(s.is_nan().sum() or 0)
    return n


def _label(s: pl.Series, i: int, digits: int | str | None, text: Any) -> str:
    v = s[i]
    if s.dtype.is_float():
        return str(float_text(pl.Series([v]), digits)[0])
    return str(text(s.slice(i, 1))[0])


def layout(s: pl.Series, kind: str, digits: int | str | None, text: Any) -> dict:
    """Column *s*'s bins or top values, over all its rows. *text* gives a
    Series' display text, missing kept missing."""
    if kind in ("number", "date"):
        key = _hist_key(s)
        finite = key.filter(key.is_finite())
        if finite.len() == 0:
            return {"type": "hist", "bins": 0, "lo": 0.0, "width": 1.0, "from": "", "to": ""}
        lo, hi = float(finite.min()), float(finite.max())
        whole = s.dtype.is_integer() or s.dtype == pl.Date
        if (whole and hi - lo < BINS) or hi == lo:
            bins, start, width = int(hi - lo) + 1, lo - 0.5, 1.0
        else:
            bins, start, width = BINS, lo, (hi - lo) / BINS
        finite_only = pl.select(pl.when(key.is_finite()).then(key)).to_series()
        imin, imax = int(finite_only.arg_min()), int(finite_only.arg_max())
        return {"type": "hist", "bins": bins, "lo": start, "width": width,
                "from": _label(s, imin, digits, text), "to": _label(s, imax, digits, text)}
    t = text(s).drop_nulls()
    top = (
        t.value_counts(sort=False, name="n")
        .sort(["n", t.name], descending=[True, False])
        .head(TOP)
        .get_column(t.name)
        .to_list()
    )
    return {"type": "top", "values": top}


def bin_of(s: pl.Series, lay: dict) -> pl.Series:
    """Each value's bin (null where missing): what the browser recounts for dates."""
    key = _hist_key(s)
    k = max(lay["bins"], 1)
    return ((key - lay["lo"]) / lay["width"]).floor().clip(0, k - 1).cast(pl.Int32)


def counts(s: pl.Series, kind: str, lay: dict, digits: int | str | None, text: Any,
           whole: pl.Series | None = None) -> dict:
    """Column *s*'s profile over its rows as given: missing, distinct, and the
    counts of *lay*'s bins or top values. When *s* is a sample, *whole* is
    every row it was drawn from: missing values are counted on it, and its
    distinct values estimated."""
    distinct = None
    if whole is not None:
        missing = _missing(whole)
        distinct = estimate_distinct(whole)
        distinct = (min(distinct[0], whole.len() - missing), True)
    out: dict[str, Any] = {"missing": _missing(s) if whole is None else missing}
    if distinct is None:
        clean = _hist_key(s) if s.dtype.is_float() else s
        clean = clean.drop_nulls()
        distinct = (clean.n_unique(), False) if clean.len() <= EXACT_DISTINCT else (
            min(clean.approx_n_unique(), clean.len()), True)
    out["distinct"], out["approx"] = int(distinct[0]), bool(distinct[1])
    if lay["type"] == "hist":
        k = lay["bins"]
        if k == 0:
            out["bins"] = []
            return out
        b = bin_of(s, lay).drop_nulls()
        found = b.value_counts(sort=False, name="n")
        bins = [0] * k
        for i, n in zip(found.get_column(b.name).to_list(), found.get_column("n").to_list()):
            bins[i] = int(n)
        out["bins"] = bins
        return out
    t = text(s).drop_nulls()
    found = dict(zip(*t.value_counts(sort=False, name="n").to_dict(as_series=False).values()))
    top = [int(found.get(v, 0)) for v in lay["values"]]
    out["top"] = top
    out["other"] = t.len() - sum(top)
    return out


def estimate_distinct(s: pl.Series) -> tuple[int, bool]:
    """Distinct non-missing values of all of *s*, estimated (HyperLogLog)."""
    clean = (_hist_key(s) if s.dtype.is_float() else s).drop_nulls()
    return int(clean.approx_n_unique()), True

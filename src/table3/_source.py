"""The explorer's data on the Python side: every row, queried a page at a time.

``Source(data)`` holds the whole of *data* as one polars DataFrame and
answers the explorer's requests: search, per-column filters and one sort
column, run over every row before the page is cut, then the page's rows in
the shape the embedded explorer already reads (``_explore.cells``). The
rules are the browser's (``passes()`` and ``compare()`` in
``_explorer_js.py``), so a live explorer and a saved snapshot of it keep the
same rows for the same filters:

- search and "contains" match the cell's display text, lowercased, the
  floats as printed (``digits=``), ``null`` for a missing value;
- a from-to filter keeps values inside both bounds and drops missing ones;
  for dates and times a bound compares with as many leading characters of
  the value's text ("2008" keeps all of 2008 under "to");
- a pick-list keeps one value, or ``null``;
- the sort is stable, missing values (NaN too) last in either direction.

A request is a dict, as it comes from the browser::

    {"id": 7, "search": "gentoo",
     "filters": {"mass": {"from": 3000, "to": null}, "species": {"is": "Adelie"},
                 "island": {"has": "dream"}},
     "sort": {"column": "mass", "desc": true},
     "offset": 0, "limit": 50, "columns": ["species", "mass"]}

and the answer carries the same id, the matching row count and the page.
Each distinct search, filter and sort keeps its row order (a few, most
recent first), so turning pages costs only the page.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

import polars as pl

from table3 import _profile
from table3._explore import _kind, cells
from table3._format import dtype_short, float_text

CACHE_ORDERS = 8  # distinct search/filter/sort states kept
EXPORT_FORMATS = ("csv", "parquet")
MAX_DOWNLOAD = 256 * 2**20  # bytes sent to the browser at most; past this, save in the kernel
MAX_LIMIT = 10_000  # the most rows one page may ask for


def frame(data: Any) -> pl.DataFrame:
    """*data* whole, as one polars DataFrame.

    A ``__table3_source__()`` method gives the data behind a package's own
    frames (a polars DataFrame or LazyFrame), as ``__table3__(n)`` gives
    their preview; a LazyFrame is collected once, here.
    """
    if hasattr(type(data), "__table3_source__"):
        data = data.__table3_source__()
    if isinstance(data, pl.Series):
        return data.to_frame()
    if isinstance(data, pl.LazyFrame):
        return data.collect()
    if isinstance(data, pl.DataFrame):
        return data
    # pandas, duck-typed so table3 never imports it
    if hasattr(data, "to_frame") and hasattr(data, "iloc") and not hasattr(data, "columns"):
        data = data.to_frame()
    if hasattr(data, "columns") and hasattr(data, "iloc"):
        from table3 import _from_pandas

        return _from_pandas(data)
    raise TypeError(
        f"table3 can't explore a {type(data).__name__} live: pass a polars or "
        "pandas DataFrame or Series, or an object with a __table3_source__ method"
    )


def eager(data: Any) -> bool:
    """Whether *data* is already in memory: a polars or pandas DataFrame or
    Series. Lazy data (a LazyFrame, a ``__table3_source__`` object) isn't."""
    if hasattr(type(data), "__table3_source__") or isinstance(data, pl.LazyFrame):
        return False
    return can_query(data)


def can_query(data: Any) -> bool:
    """Whether *data* can be explored whole (``frame()`` takes it)."""
    if hasattr(type(data), "__table3_source__"):
        return True
    if isinstance(data, (pl.DataFrame, pl.LazyFrame, pl.Series)):
        return True
    return hasattr(data, "iloc") and (hasattr(data, "columns") or hasattr(data, "to_frame"))


_SECONDS = "%H:%M:%S"


def _clock_text(s: pl.Series, date: str) -> pl.Series:
    """Datetimes and times as Python prints them: microseconds only when not zero."""
    fmt = date + _SECONDS
    tz = "%:z" if getattr(s.dtype, "time_zone", None) else ""
    out = pl.select(
        pl.when(s.dt.nanosecond() // 1000 != 0)
        .then(s.dt.to_string(fmt + "%.6f" + tz))
        .otherwise(s.dt.to_string(fmt + tz))
    ).to_series()
    return out.alias(s.name)


def _text_or_null(s: pl.Series, digits: int | str | None) -> pl.Series:
    """*s* as the explorer prints it, missing values left missing."""
    t = s.dtype
    if t.is_float():
        return pl.Series(s.name, float_text(s, digits), dtype=pl.String)
    if t == pl.Datetime:
        return _clock_text(s, "%Y-%m-%d ")
    if t == pl.Time:
        return _clock_text(s, "")
    if t.is_numeric() or t in (pl.Boolean, pl.String, pl.Date, pl.Categorical) or isinstance(t, pl.Enum):
        return s.cast(pl.String)
    # durations, lists, structs, binary, objects: as Python prints them
    return pl.Series(s.name, [None if v is None else str(v) for v in s.to_list()], dtype=pl.String)


def display_text(s: pl.Series, digits: int | str | None) -> pl.Series:
    """*s* as the explorer shows it, ``null`` for missing: what search reads."""
    return _text_or_null(s, digits).fill_null("null")


def _as_float(s: pl.Series) -> pl.Series:
    out = s.cast(pl.Float64)
    return out.fill_nan(None)


class Source:
    """Every row of *data*, and the explorer's queries over them."""

    def __init__(self, data: Any, *, digits: int | str | None = None) -> None:
        self.df = frame(data)
        self.digits = digits
        self.total = self.df.height
        self.columns = []
        self._kinds: dict[str, str] = {}
        for s in self.df.get_columns():
            kind = _kind(s)
            head = {"name": s.name, "type": dtype_short(s.dtype), "kind": kind}
            if kind == "choice":
                raw, _ = cells(s.unique().drop_nulls(), kind, digits)
                head["choices"] = sorted(raw)
            self.columns.append(head)
            self._kinds[s.name] = kind
        self._texts: dict[str, pl.Series] = {}
        self._orders: OrderedDict[Any, pl.Series] = OrderedDict()
        self._profiles: OrderedDict[Any, dict] = OrderedDict()
        self._layouts: list[dict] | None = None
        self._latest = None

    # -- the rows a state keeps, in its order --------------------------------

    def _text(self, name: str) -> pl.Series:
        """The column's lowercased display text, made on first use."""
        if name not in self._texts:
            self._texts[name] = display_text(self.df[name], self.digits).str.to_lowercase()
        return self._texts[name]

    def _keep(self, name: str, f: dict) -> pl.Series:
        """The rows column *name* keeps under filter *f*, as a boolean Series."""
        s, kind = self.df[name], self._kinds[name]
        if "is" in f:
            v = f["is"]
            if v is None:
                return s.is_null()
            if kind == "bool":
                return (s == bool(v)).fill_null(False)
            return (s.cast(pl.String) == str(v)).fill_null(False)
        if "has" in f:
            return self._text(name).str.contains(str(f["has"]).lower(), literal=True)
        lo, hi = f.get("from"), f.get("to")
        if kind == "date":
            key = display_text(s, None)
            keep = s.is_not_null()
            if lo not in (None, ""):
                keep &= key.str.slice(0, len(str(lo))) >= str(lo)
            if hi not in (None, ""):
                keep &= key.str.slice(0, len(str(hi))) <= str(hi)
            return keep
        if kind == "number":
            x = _as_float(s)
            keep = x.is_not_null()
            if lo is not None:
                keep &= (x >= float(lo)).fill_null(False)
            if hi is not None:
                keep &= (x <= float(hi)).fill_null(False)
            return keep
        raise ValueError(f"table3: can't apply filter {f!r} to {name!r}")

    def _sort_key(self, name: str) -> pl.Series:
        """What column *name* sorts by: numbers as numbers (NaN missing),
        dates, times and booleans as themselves, the rest by their text."""
        s, kind = self.df[name], self._kinds[name]
        if kind == "number":
            return _as_float(s)
        if kind in ("bool", "date"):
            return s
        return _text_or_null(s, None)

    @staticmethod
    def _state(request: dict) -> tuple:
        filters = request.get("filters") or {}
        sort = request.get("sort") or None
        return (
            (request.get("search") or "").strip().lower(),
            tuple(sorted((k, tuple(sorted(v.items()))) for k, v in filters.items() if v)),
            (sort["column"], bool(sort.get("desc"))) if sort and sort.get("column") is not None else None,
        )

    def order(self, request: dict) -> pl.Series:
        """The row indexes (0-based, into *data*) a request keeps, in its order.

        Filters, search and sort only; ``offset`` and ``limit`` are the page's.
        Profiles and exports read the same rows through this.
        """
        state = self._state(request)
        if state in self._orders:
            self._orders.move_to_end(state)
            return self._orders[state]
        search, filters, sort = state
        for name, _ in filters:
            if name not in self._kinds:
                raise ValueError(f"table3: no column {name!r} to filter")
        keep = pl.Series([True] * self.total, dtype=pl.Boolean)
        for name, items in filters:
            keep &= self._keep(name, dict(items))
        if search:
            hit = pl.Series([False] * self.total, dtype=pl.Boolean)
            for name in self._kinds:
                hit |= self._text(name).str.contains(search, literal=True)
            keep &= hit
        idx = pl.int_range(0, self.total, dtype=pl.UInt32 if self.total < 2**32 else pl.UInt64, eager=True)
        idx = idx.filter(keep)
        if sort is not None:
            name, desc = sort
            if name not in self._kinds:
                raise ValueError(f"table3: no column {name!r} to sort")
            key = self._sort_key(name).gather(idx)
            idx = (
                pl.DataFrame({"k": key, "i": idx})
                .sort("k", descending=desc, nulls_last=True, maintain_order=True)
                .get_column("i")
            )
        self._orders[state] = idx
        while len(self._orders) > CACHE_ORDERS:
            self._orders.popitem(last=False)
        return idx

    # -- profiles ------------------------------------------------------------

    @property
    def layouts(self) -> list[dict]:
        """Each column's bins or top values, over all rows (``_profile.layout``)."""
        if self._layouts is None:
            text = lambda s: _text_or_null(s, self.digits)  # noqa: E731
            self._layouts = [
                _profile.layout(self.df[name], kind, self.digits, text)
                for name, kind in self._kinds.items()
            ]
        return self._layouts

    def profile(self, request: dict) -> dict:
        """Every column's profile over the rows *request* keeps.

        ``basis`` says what it covers: "full" (every kept row) or "sampled":
        bars from a fixed random ``_profile.SAMPLE_ROWS`` of them, missing
        values still counted over every kept row and distinct values
        estimated over them (each column's ``approx``).
        """
        state = self._state(request)[:2]  # the sort doesn't change a profile
        if state in self._profiles:
            self._profiles.move_to_end(state)
            return self._profiles[state]
        idx = self.order(request)
        kept = len(idx)
        sampled = kept > _profile.SAMPLE_ROWS
        rows = idx.sample(_profile.SAMPLE_ROWS, seed=0) if sampled else idx
        whole = kept == self.total
        text = lambda s: _text_or_null(s, self.digits)  # noqa: E731
        columns = []
        for (name, kind), lay in zip(self._kinds.items(), self.layouts):
            s = self.df[name]
            kept_s = s if whole else s.gather(idx)
            if sampled:
                columns.append(_profile.counts(s.gather(rows), kind, lay, self.digits, text, kept_s))
            else:
                columns.append(_profile.counts(kept_s, kind, lay, self.digits, text))
        out = {"basis": "sampled" if sampled else "full", "rows": len(rows), "of": kept,
               "columns": columns}
        self._profiles[state] = out
        while len(self._profiles) > CACHE_ORDERS:
            self._profiles.popitem(last=False)
        return out

    def date_bins(self) -> list[list | None]:
        """Each row's bin, for date columns (None for the rest): the snapshot
        recounts its date histograms from these as its filters change."""
        return [
            _profile.bin_of(self.df[name], lay).to_list() if kind == "date" else None
            for (name, kind), lay in zip(self._kinds.items(), self.layouts)
        ]

    # -- export --------------------------------------------------------------

    def _names(self, request: dict) -> list[str]:
        names = request.get("columns") or list(self._kinds)
        missing = [c for c in names if c not in self._kinds]
        if missing:
            raise ValueError(f"table3: no column {missing[0]!r} to show")
        return names

    def kept(self, request: dict) -> pl.DataFrame:
        """Every row *request* keeps, in its order, its columns only: what an
        export writes, whatever page the grid is on."""
        return self.df.select(pl.col(self._names(request)).gather(self.order(request)))

    def export(self, request: dict, fmt: str) -> bytes:
        """The kept rows as a file: "csv" (polars' CSV, every stored digit) or
        "parquet" (the original types and values)."""
        if fmt not in EXPORT_FORMATS:
            raise ValueError(f"table3: can't export as {fmt!r}; use one of {EXPORT_FORMATS}")
        import io

        buf = io.BytesIO()
        df = self.kept(request)
        if fmt == "csv":
            df.write_csv(buf)
        else:
            df.write_parquet(buf)
        return buf.getvalue()

    def save(self, request: dict, fmt: str, folder: str | None = None) -> str:
        """Write the export into *folder* (the kernel's working folder) under a
        new name; its path."""
        import datetime as _dt
        import os

        folder = folder or os.getcwd()
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(folder, f"table3-export-{stamp}.{fmt}")
        n = 1
        while os.path.exists(path):
            n += 1
            path = os.path.join(folder, f"table3-export-{stamp}-{n}.{fmt}")
        data = self.export(request, fmt)
        with open(path, "xb") as f:
            f.write(data)
        return path

    # -- one page ------------------------------------------------------------

    def query(self, request: dict) -> dict | None:
        """The page *request* asks for, or None when a later request already came.

        Requests carry increasing ids; one that arrives after a later one was
        answered is stale (the user typed on) and gets no answer.
        """
        rid = request.get("id")
        if rid is not None:
            if self._latest is not None and rid < self._latest:
                return None
            self._latest = rid
        idx = self.order(request)
        offset = max(0, int(request.get("offset") or 0))
        limit = min(MAX_LIMIT, max(0, int(request.get("limit") or 50)))
        names = self._names(request)
        page_idx = idx.slice(offset, limit)
        page = self.df.select(pl.col(names).gather(page_idx))
        rows_by_col, shown = [], []
        for s in page.get_columns():
            raw, text = cells(s, self._kinds[s.name], self.digits)
            rows_by_col.append(raw)
            shown.append(text)
        out = {
            "id": rid,
            "total": self.total,
            "filtered": len(idx),
            "offset": offset,
            "columns": names,
            "index": [i + 1 for i in page_idx.to_list()],
            "rows": [list(r) for r in zip(*rows_by_col)] if rows_by_col else [],
            "shown": shown,
        }
        if request.get("profile"):
            out["profile"] = self.profile(request)
        return out

"""The explorer's output: its rows as JSON, a script that draws the grid, and a
plain table for notebooks that don't run output scripts (docs/explorer.md)."""

from __future__ import annotations

import html as _html
import math
import uuid

import polars as pl

from table3._explorer_js import EXPLORER_JS
from table3._format import dtype_short, float_text, json_for_script
from table3._html import MONO, table_html

CHOICES_MAX = 50  # a text column with at most this many values filters by pick-list
FALLBACK_ROWS = 100
_MAX_FLOAT = 1.7976931348623157e308  # inf's stand-in: JSON has no infinity
_SAFE_INT = 2**53  # beyond this a JavaScript number loses digits


def _kind(s: pl.Series) -> str:
    t = s.dtype
    if t == pl.Boolean:
        return "bool"
    if t.is_numeric():
        return "number"
    if t.is_temporal():
        return "date"
    if t in (pl.String, pl.Categorical) or isinstance(t, pl.Enum):
        return "choice" if s.n_unique() <= CHOICES_MAX else "text"
    return "text"


def _float_raw(v: float | None) -> float | None:
    if v is None or math.isnan(v):
        return None
    if math.isinf(v):
        return _MAX_FLOAT if v > 0 else -_MAX_FLOAT
    return v


def _column(s: pl.Series, digits: int | str | None) -> tuple[dict, list, list | None]:
    """The column's header entry, its raw values, and its display text where it differs."""
    kind = _kind(s)
    head = {"name": s.name, "type": dtype_short(s.dtype), "kind": kind}
    values = s.to_list()
    shown = None
    if s.dtype.is_float():
        raw = [_float_raw(v) for v in values]
        shown = float_text(s, digits)
    elif s.dtype.is_integer():
        raw = values
        if any(v is not None and abs(v) > _SAFE_INT for v in values):
            raw = [None if v is None else float(v) for v in values]
            shown = [None if v is None else str(v) for v in values]
    elif s.dtype.is_decimal():
        raw = [None if v is None else float(v) for v in values]
        shown = [None if v is None else str(v) for v in values]
    elif kind == "bool":
        raw = values
    else:
        raw = [None if v is None else str(v) for v in values]
    if kind == "choice":
        head["choices"] = sorted({v for v in raw if v is not None})
    return head, raw, shown


def payload(df: pl.DataFrame, total: int | None, n: int, digits: int | str | None) -> dict:
    """What the script needs: columns, rows of raw values, display text, counts."""
    columns, raws, shown = [], [], []
    for s in df.get_columns():
        head, raw, text = _column(s, digits)
        columns.append(head)
        raws.append(raw)
        shown.append(text)
    return {
        "columns": columns,
        "rows": [list(r) for r in zip(*raws)] if raws else [],
        "shown": shown,
        "total": total,
        "n": n,
    }


def explorer_html(
    df: pl.DataFrame,
    total: int | None,
    caption: str | None,
    *,
    n: int,
    height: int,
    digits: int | str | None,
) -> str:
    uid = f"table3-explore-{uuid.uuid4().hex}"
    fallback = table_html(
        df.head(FALLBACK_ROWS), total, None, pages=False, page_size=10,
        height=300, digits=digits,
    )
    note = (
        f"<div style='font:{MONO};opacity:.65;margin:0 0 4px 0'>The explorer needs "
        f"the notebook to run output scripts; the first {min(df.height, FALLBACK_ROWS):,} "
        "rows show here instead.</div>"
    )
    cap = ""
    if caption:
        cap = (
            f"<div style='font:{MONO};opacity:.85;margin:0 0 4px 0'>"
            f"{_html.escape(caption)}</div>"
        )
    data = json_for_script(payload(df, total, n, digits))
    return (
        f"<div id='{uid}' data-height='{height}' style='font:{MONO}'>"
        + cap
        + f"<div data-fallback>{note}{fallback}</div>"
        + f"<script type='application/json'>{data}</script>"
        + "</div>"
        + f"<script>{EXPLORER_JS.replace('__ID__', uid)}</script>"
    )

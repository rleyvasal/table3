"""The table's HTML: inline styles only.

CRAFT republishes remote output through ``display_pub.publish``, which drops
``<style>`` blocks, so every element carries its own style (as in tidy3's
``display.py``). The pinned header needs a solid background: SolveIt's card
colour (``--card``, an HSL triplet) is drawn as a gradient over a plain colour
taken from VS Code, then JupyterLab, then the browser. Where ``--card`` is
undefined the gradient drops out alone.

A paged table writes only its first page as styled cells, and every row
as compact JSON beside it, which the paging script turns into the other
pages: styled cells cost about 100 bytes each, and SolveIt sends a cell's
output to its AI. Where output scripts don't run, the first page shows in a
box that scrolls sideways under pinned names and types. ``pages=False``
writes every row as styled cells, in a box of fixed height that scrolls.
"""

from __future__ import annotations

import html as _html
import uuid

import polars as pl

from table3._format import cell, display_rows, dtype_short, escape, json_for_script
from table3._pager import PAGER_JS

MONO = "12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
RULE = "border-bottom:1px solid rgba(127,127,127,.45)"
# The font is set once on the table: a cell's style repeats on up to
# n x columns cells, and the font list is half its length.
CELL = "font:inherit;padding:3px 10px;white-space:pre;border:0"
HEAD_BG = (
    "background-color:var(--vscode-editor-background,"
    "var(--jp-layout-color0,Canvas));"
    "background-image:linear-gradient(hsl(var(--card)),hsl(var(--card)))"
)
ZEBRA = "background:rgba(127,127,127,.08)"
SCROLLBAR = "scrollbar-color:rgba(127,127,127,.5) transparent"


def _plural(k: int) -> str:
    return f"{k:,} row" + ("s" if k != 1 else "")


def rows_label(shown: int, total: int | None) -> str:
    """Footer for the scroll box: "35 rows", or how many of how many show."""
    if total is not None and total <= shown:
        return _plural(total)
    of = "more" if total is None else f"{total:,}"
    return f"showing first {shown:,} of {of} rows"


def right_aligned(dtype: pl.DataType) -> bool:
    """Numbers, dates and times line up on the right; text and the rest on the left."""
    return dtype.is_numeric() or dtype.is_temporal()


def table_html(
    df: pl.DataFrame,
    total: int | None,
    caption: str | None,
    *,
    pages: bool,
    page_size: int,
    height: int | None,
    digits: int | str | None = None,
) -> str:
    """*df* is the first rows; *total* the whole row count, None if not counted."""

    align = [
        f"{CELL};text-align:{'right' if right_aligned(t) else 'left'}" for t in df.dtypes
    ]

    def _tr(cells: list[str], extra: str = "", row_style: str = "") -> str:
        tds = "".join(f"<td style='{a}{extra}'>{c}</td>" for a, c in zip(align, cells))
        return f"<tr style='{row_style}'>{tds}</tr>"

    head = _tr([f"<b>{escape(c)}</b>" for c in df.columns], f";{RULE}")
    types = _tr([escape(dtype_short(t)) for t in df.dtypes], f";opacity:.55;{RULE}")
    rows = display_rows(df, digits)
    written = rows[:page_size] if pages else rows
    body = [
        _tr([cell(v) for v in row], "", ZEBRA if i % 2 else "")
        for i, row in enumerate(written)
    ]

    shape = f"shape: ({'?' if total is None else total}, {df.width})"
    box = f"overflow:auto;{SCROLLBAR}"
    if height is not None:
        box = f"max-height:{height}px;{box}"
    small = f"font:{MONO};opacity:.65"
    cap = ""
    if caption:
        cap = (
            f"<div style='font:{MONO};opacity:.85;margin:0 0 2px 0'>"
            f"{_html.escape(caption)}</div>"
        )

    root = "<div>"
    foot = f"<small data-foot style='{small}'>{rows_label(len(written), total)}</small>"
    script = data = ""
    if pages:
        uid = f"table3-{uuid.uuid4().hex}"
        counted = "" if total is None else str(total)
        root = (
            f"<div id='{uid}' data-page-size='{page_size}' data-total='{counted}'>"
        )
        # The row and column counts on the left, the pager on the right.
        foot = (
            "<div data-bar style='display:flex;flex-wrap:wrap;align-items:center;"
            "gap:4px 12px;margin:2px 0 0 0'>"
            + foot
            + f"<div data-pager style='font:{MONO};margin-left:auto;display:none'>"
            "</div></div>"
        )
        script = f"<script>{PAGER_JS.replace('__ID__', uid)}</script>"
        if len(written) < len(rows):
            text = [[None if v is None else str(v) for v in row] for row in rows]
            data = f"<script type='application/json'>{json_for_script(text)}</script>"
    return (
        root
        + cap
        + f"<small style='{small}'>{shape}</small>"
        f"<div data-box style='{box}'>"
        "<table style='border-collapse:separate;border-spacing:0;margin:2px 0;"
        f"font:{MONO}'>"
        f"<thead style='position:sticky;top:0;z-index:1;{HEAD_BG}'>"
        + head
        + types
        + "</thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
        + foot
        + data
        + "</div>"
        + script
    )

"""The table's HTML: inline styles only.

CRAFT republishes remote output through ``display_pub.publish``, which drops
``<style>`` blocks, so every element carries its own style (as in tidy3's
``display.py``). The pinned header needs a solid background: SolveIt's card
colour (``--card``, an HSL triplet) is drawn as a gradient over a plain colour
taken from VS Code, then JupyterLab, then the browser. Where ``--card`` is
undefined the gradient drops out alone.

Paging is a script over this table. Where output scripts don't run, the
table stays a box of fixed height that scrolls down and sideways, with the
column names and types pinned at the top.
"""

from __future__ import annotations

import html as _html
import uuid

import polars as pl

from view3._format import cell, display_rows, dtype_short, escape
from view3._pager import PAGER_JS

MONO = "12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
RULE = "border-bottom:1px solid rgba(127,127,127,.45)"
# The font is set once on the table: a cell's style repeats on up to
# n x columns cells, and the font list is half its length.
CELL = "font:inherit;padding:3px 10px;text-align:right;white-space:pre;border:0"
HEAD_BG = (
    "background-color:var(--vscode-editor-background,"
    "var(--jp-layout-color0,Canvas));"
    "background-image:linear-gradient(hsl(var(--card)),hsl(var(--card)))"
)
ZEBRA = "background:rgba(127,127,127,.08)"
SCROLLBAR = "scrollbar-color:rgba(127,127,127,.5) transparent"


def _plural(k: int) -> str:
    return f"{k:,} row" + ("s" if k != 1 else "")


def rows_label(shown: int, total: int | None, n: int) -> str:
    """Footer for the scroll box: "35 rows", or how the n limit cut them."""
    if total is not None and total <= shown:
        return _plural(total)
    of = "more" if total is None else f"{total:,}"
    return f"showing first {shown:,} of {of} rows (n={n:,})"


def pages_label(shown: int, total: int | None, n: int) -> str:
    """What the pager counts rows of: "344 rows", or the first n of more."""
    if total is not None and total <= shown:
        return _plural(shown)
    of = "more" if total is None else f"{total:,}"
    return f"{_plural(shown)} (first {shown:,} of {of}, n={n:,})"


def table_html(
    df: pl.DataFrame,
    total: int | None,
    caption: str | None,
    *,
    n: int,
    pages: bool,
    page_size: int,
    height: int | None,
    digits: int | str | None = None,
) -> str:
    """*df* is the first rows; *total* the whole row count, None if not counted."""

    def _tr(cells: list[str], style: str, row_style: str = "") -> str:
        tds = "".join(f"<td style='{style}'>{c}</td>" for c in cells)
        return f"<tr style='{row_style}'>{tds}</tr>"

    head = _tr([f"<b>{escape(c)}</b>" for c in df.columns], f"{CELL};{RULE}")
    types = _tr(
        [escape(dtype_short(t)) for t in df.dtypes], f"{CELL};opacity:.55;{RULE}"
    )
    body = [
        _tr([cell(v) for v in row], CELL, ZEBRA if i % 2 else "")
        for i, row in enumerate(display_rows(df, digits))
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
    pager = script = ""
    if pages:
        uid = f"view3-{uuid.uuid4().hex}"
        label = _html.escape(pages_label(df.height, total, n))
        root = f"<div id='{uid}' data-page-size='{page_size}' data-label='{label}'>"
        pager = (
            f"<div data-pager style='font:{MONO};margin:4px 0 0 0;display:none'>"
            "</div>"
        )
        script = f"<script>{PAGER_JS.replace('__ID__', uid)}</script>"
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
        f"<small data-foot style='{small}'>"
        f"{rows_label(df.height, total, n)}</small>"
        + pager
        + "</div>"
        + script
    )

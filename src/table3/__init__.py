"""Paged, theme-aware tables in notebook output.

``table3.html(data)`` is a table of up to *n* rows shown ten at a time, with
Previous / page / Next buttons, scrolling sideways when wide data doesn't
fit the cell: what a package returns from its frames'
``_repr_html_`` so they print as R notebooks print data frames.
``table3.show(data)`` displays the same table and returns *data* unchanged.
``table3.view(data)`` opens a data explorer instead, as R's ``View()``: a
grid of up to 10,000 rows to search, sort and filter.

*data* is a polars DataFrame, LazyFrame or Series, a pandas DataFrame or
Series, or any object with a ``__table3__`` method::

    def __table3__(self, n: int) -> tuple[polars.DataFrame, int | None, str | None]:
        # the first n rows, the whole row count (None if not counted),
        # and a caption shown above the table (None for none)

so a package's own frames show without table3 importing that package.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from table3.__version__ import __version__
from table3._html import table_html
from table3 import _quiet, _solveit
from table3._solveit import autohide

__all__ = ["__version__", "autohide", "html", "show", "view"]


def _from_pandas(df: Any) -> pl.DataFrame:
    try:
        return pl.from_pandas(df)
    except Exception:  # no pyarrow, or a dtype polars can't take: show the text
        return pl.DataFrame({str(c): df[c].astype(str).tolist() for c in df.columns})


def _parts(data: Any, n: int) -> tuple[pl.DataFrame, int | None, str | None]:
    if hasattr(type(data), "__table3__"):
        return data.__table3__(n)
    if isinstance(data, pl.Series):
        data = data.to_frame()
    if isinstance(data, pl.LazyFrame):
        head, count = pl.collect_all([data.head(n), data.select(pl.len())])
        return head, int(count.item()), None
    if isinstance(data, pl.DataFrame):
        return data.head(n), data.height, None
    # pandas, duck-typed so table3 never imports it
    if hasattr(data, "to_frame") and hasattr(data, "iloc") and not hasattr(data, "columns"):
        data = data.to_frame()
    if hasattr(data, "columns") and hasattr(data, "iloc"):
        return _from_pandas(data.head(n)), len(data), None
    raise TypeError(
        f"table3 can't show a {type(data).__name__}: pass a polars or pandas "
        "DataFrame or Series, or an object with a __table3__ method"
    )


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _check(n: Any, pages: Any, page_size: Any, height: Any, digits: Any) -> None:
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("table3: n must be a non-negative integer")
    if not isinstance(pages, bool):
        raise TypeError("table3: pages must be True or False")
    if not _positive_int(page_size):
        raise ValueError("table3: page_size must be a positive integer")
    if height is not None and not _positive_int(height):
        raise ValueError("table3: height must be a positive integer or None")
    if digits is not None and digits != "full" and not _positive_int(digits):
        raise ValueError('table3: digits must be a positive integer, "full", or None')


def html(
    data: Any,
    *,
    n: int = 1000,
    pages: bool = True,
    page_size: int = 10,
    height: int | None = 300,
    digits: int | str | None = None,
    caption: str | None = None,
) -> str:
    """The table's HTML for the first *n* rows of *data*.

    *page_size* rows show per page. ``pages=False``, or a notebook that
    doesn't run output scripts, shows every row instead in a box *height*
    pixels tall that scrolls; ``height=None`` grows it to fit.

    Floats print as polars' text preview prints them (up to six decimals,
    following ``pl.Config(float_precision=)``) unless *digits* says
    otherwise: ``digits=6`` keeps six significant digits, as R's
    ``signif()`` does, so small numbers keep their precision (0.000123457);
    ``digits="full"`` shows every stored digit. *caption* replaces the one
    ``__table3__`` gives.
    """
    _check(n, pages, page_size, height, digits)
    df, total, own_caption = _parts(data, n)
    return table_html(
        df,
        total,
        own_caption if caption is None else caption,
        pages=pages,
        page_size=page_size,
        height=height,
        digits=digits,
    )


def _display(html_text: str) -> bool:
    """Show *html_text* in a notebook; False outside one."""
    try:
        from IPython import get_ipython
        from IPython.display import HTML, display
    except ImportError:
        return False
    if get_ipython() is None:
        return False
    display(HTML(html_text))
    return True


def _text(data: Any, n: int, digits: int | str | None = None) -> str:
    df, total, caption = _parts(data, n)
    # Polars prints no significant digits; digits=k applies to the table only.
    full = {"fmt_float": "full"} if digits == "full" else {}
    with pl.Config(tbl_rows=max(df.height, 1), tbl_hide_dataframe_shape=True, **full):
        lines = [f"shape: ({'?' if total is None else total}, {df.width})", repr(df)]
    if caption:
        lines.insert(0, caption)
    if total is None or total > df.height:
        lines.append(f"… first {df.height:,} rows")
    return "\n".join(lines)


def show(
    data: Any,
    *,
    n: int = 1000,
    pages: bool = True,
    page_size: int = 10,
    height: int | None = 300,
    digits: int | str | None = None,
    caption: str | None = None,
) -> Any:
    """Show up to *n* rows of *data* in a paged table and return *data*.

    Arguments as in ``html()``. Outside a notebook it prints the rows as
    text. As a cell's last line the notebook also prints *data* itself; end
    the line with ``;`` to hide it.
    """
    _check(n, pages, page_size, height, digits)
    options = {"n": n, "pages": pages, "page_size": page_size, "height": height}
    if not _display(html(data, digits=digits, caption=caption, **options)):
        print(_text(data, n, digits))
    return data


def view(
    data: Any,
    *,
    n: int = 10_000,
    height: int = 500,
    digits: int | str | None = None,
    caption: str | None = None,
    hide: bool | None = None,
    live: bool | None = None,
) -> Any:
    """Open a data explorer over the first *n* rows of *data*, and return *data*.

    As R's ``View()``: one grid to scroll, a search box, headers that sort
    on a click, and a filter under each column (from-to for numbers and
    dates, "contains" for text, a pick-list for columns of few values).
    The rows go into the notebook's output, so the explorer works in a saved
    notebook, about 1 MB for 10,000 rows of a dozen columns. *height* is the
    grid's height in pixels; *digits* and *caption* as in ``html()``. Where
    output scripts don't run, it shows the first 100 rows as ``show()``.
    Outside a notebook it prints the first rows.

    A cell that ends in ``view()`` shows the explorer alone, not *data* a
    second time, as R's ``View()`` returns invisibly. *data* is still
    returned: piped on, assigned, or on a later line or in a later cell, it
    displays as usual.

    In SolveIt, which sends every cell's code and output to its AI, the
    cell is then hidden from the AI (SolveIt's red eye), so the rows don't
    fill its context. *hide* says whether to, for this call: ``True`` or
    ``False``; ``None`` follows ``table3.autohide()``, on by default.
    SolveIt hides the cell's code with its output.

    *live* explores every row instead, through the kernel: search, filters
    and sort run in Python over all of *data* and the grid fetches the rows
    it scrolls to. It needs anywidget (``pip install table3[live]``) and a
    notebook that draws Jupyter widgets (JupyterLab, Notebook 7, VS Code).
    The first *n* rows are still written as a snapshot, which shows when
    the notebook is reopened without its kernel. ``None`` (the default) is
    live where it can be, for data already in memory (a polars or pandas
    DataFrame or Series), but never in SolveIt, which draws no widgets;
    lazy data, a polars LazyFrame or a package's frame that gives its data
    through ``__table3_source__()`` (tidy3's), stays a snapshot, as live
    mode would run its whole query. ``True`` insists (lazy data is then
    collected once); ``False`` writes the snapshot alone.
    """
    _check(n, True, 10, height, digits)
    if hide is not None and not isinstance(hide, bool):
        raise TypeError("table3: hide must be True, False or None")
    if height is None:
        raise ValueError("table3: view() height must be a positive integer")
    if live is not None and not isinstance(live, bool):
        raise TypeError("table3: live must be True, False or None")
    from table3 import _live, _source
    from table3._explore import explorer_html, new_uid

    if live is None:
        # Lazy data (a LazyFrame, or a package's frame through
        # __table3_source__) stays a snapshot unless asked: live would run
        # the whole query (a large scan, say) where the snapshot collects n rows.
        live = _source.eager(data) and _live.available()
    elif live and not _live.available():
        raise RuntimeError(
            "table3: view(live=True) needs anywidget (pip install table3[live]) "
            "and a Jupyter kernel outside SolveIt"
        )
    df, total, own_caption = _parts(data, n)
    cap = own_caption if caption is None else caption
    uid = new_uid()
    page = explorer_html(df, total, cap, n=n, height=height, digits=digits, uid=uid, live=live)
    widget = None
    if live:
        widget = _live.live_explorer(data, height=height, digits=digits, caption=cap, snapshot=uid)
    if not _display(page):
        print(_text(data, min(n, 20), digits))
    else:
        if widget is not None:
            from IPython.display import display

            display(widget)
        if _solveit.AUTOHIDE if hide is None else hide:
            _solveit.hide_calling_cell()
    _quiet.return_quietly(data)
    return data


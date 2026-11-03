"""Paged, theme-aware tables in notebook output.

``view3.view(data)`` shows up to *n* rows ten at a time, with Previous /
page / Next buttons and, for wide data, as many columns as fit the cell plus
arrows to the rest. It returns *data* unchanged. ``view3.html(data)`` returns
the same HTML without showing it.

*data* is a polars DataFrame, LazyFrame or Series, a pandas DataFrame or
Series, or any object with a ``__view3__`` method::

    def __view3__(self, n: int) -> tuple[polars.DataFrame, int | None, str | None]:
        # the first n rows, the whole row count (None if not counted),
        # and a caption shown above the table (None for none)

so a package's own frames show without view3 importing that package.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from view3.__version__ import __version__
from view3._html import table_html

__all__ = ["__version__", "html", "view"]


def _from_pandas(df: Any) -> pl.DataFrame:
    try:
        return pl.from_pandas(df)
    except Exception:  # no pyarrow, or a dtype polars can't take: show the text
        return pl.DataFrame({str(c): df[c].astype(str).tolist() for c in df.columns})


def _parts(data: Any, n: int) -> tuple[pl.DataFrame, int | None, str | None]:
    if hasattr(type(data), "__view3__"):
        return data.__view3__(n)
    if isinstance(data, pl.Series):
        data = data.to_frame()
    if isinstance(data, pl.LazyFrame):
        head, count = pl.collect_all([data.head(n), data.select(pl.len())])
        return head, int(count.item()), None
    if isinstance(data, pl.DataFrame):
        return data.head(n), data.height, None
    # pandas, duck-typed so view3 never imports it
    if hasattr(data, "to_frame") and hasattr(data, "iloc") and not hasattr(data, "columns"):
        data = data.to_frame()
    if hasattr(data, "columns") and hasattr(data, "iloc"):
        return _from_pandas(data.head(n)), len(data), None
    raise TypeError(
        f"view3 can't show a {type(data).__name__}: pass a polars or pandas "
        "DataFrame or Series, or an object with a __view3__ method"
    )


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _check(n: Any, pages: Any, page_size: Any, height: Any, digits: Any) -> None:
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("view3: n must be a non-negative integer")
    if not isinstance(pages, bool):
        raise TypeError("view3: pages must be True or False")
    if not _positive_int(page_size):
        raise ValueError("view3: page_size must be a positive integer")
    if height is not None and not _positive_int(height):
        raise ValueError("view3: height must be a positive integer or None")
    if digits is not None and digits != "full" and not _positive_int(digits):
        raise ValueError('view3: digits must be a positive integer, "full", or None')


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
    ``__view3__`` gives.
    """
    _check(n, pages, page_size, height, digits)
    df, total, own_caption = _parts(data, n)
    return table_html(
        df,
        total,
        own_caption if caption is None else caption,
        n=n,
        pages=pages,
        page_size=page_size,
        height=height,
        digits=digits,
    )


def _text(data: Any, n: int, digits: int | str | None = None) -> str:
    df, total, caption = _parts(data, n)
    # Polars prints no significant digits; digits=k applies to the table only.
    full = {"fmt_float": "full"} if digits == "full" else {}
    with pl.Config(tbl_rows=max(df.height, 1), tbl_hide_dataframe_shape=True, **full):
        lines = [f"shape: ({'?' if total is None else total}, {df.width})", repr(df)]
    if caption:
        lines.insert(0, caption)
    if total is None or total > df.height:
        lines.append(f"… first {df.height:,} rows (n={n:,})")
    return "\n".join(lines)


def view(
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
    try:
        from IPython import get_ipython
        from IPython.display import HTML, display
    except ImportError:
        get_ipython = None
    if get_ipython is not None and get_ipython() is not None:
        options = {"n": n, "pages": pages, "page_size": page_size, "height": height}
        display(HTML(html(data, digits=digits, caption=caption, **options)))
    else:
        print(_text(data, n, digits))
    return data

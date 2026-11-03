"""Cell text: values, types and floats as polars' text preview prints them."""

from __future__ import annotations

import html as _html

import polars as pl

MAX_CHARS = 40  # longer values are cut, with the full value on hover


def escape(v: object) -> str:
    if v is None:
        return "null"
    return _html.escape(str(v))


def cell(v: object) -> str:
    text = "null" if v is None else str(v)
    if len(text) <= MAX_CHARS:
        return escape(v)
    short = _html.escape(text[: MAX_CHARS - 1]) + "…"
    return f"<span title='{_html.escape(text)}'>{short}</span>"


def dtype_short(t: pl.DataType) -> str:
    """Polars-style short dtype name ("i64"); falls back to str(t)."""
    try:
        from polars._plr import dtype_str_repr

        return dtype_str_repr(t)
    except Exception:
        return str(t)


def significant(v: float, digits: int) -> str:
    """*v* to *digits* significant digits, as R's ``signif()`` keeps them.

    Written as polars writes floats: "2.0" not "2", "1.5e-7" not "1.5e-07".
    """
    if v != v:
        return "NaN"
    if v in (float("inf"), float("-inf")):
        return "inf" if v > 0 else "-inf"
    text = format(v, f".{digits}g")
    if "e" in text:
        mantissa, exponent = text.split("e")
        return f"{mantissa}e{int(exponent)}"
    return text if "." in text else text + ".0"


def float_text(s: pl.Series, digits: int | str | None = None) -> list[object]:
    """Floats as polars' text preview prints them ("3.3", "1.2346e8").

    Read off polars' own printer, so ``pl.Config(float_precision=)`` applies.
    *digits* = k keeps k significant digits instead; "full" every stored digit.
    """
    if isinstance(digits, int):
        return [None if v is None else significant(v, digits) for v in s.to_list()]
    full = {"fmt_float": "full"} if digits == "full" else {}
    with pl.Config(
        tbl_formatting="NOTHING",
        tbl_hide_column_names=True,
        tbl_hide_column_data_types=True,
        tbl_hide_dataframe_shape=True,
        tbl_rows=-1,
        tbl_width_chars=10_000,
        **full,
    ):
        lines = [line.strip() for line in repr(s.to_frame()).splitlines()]
    if len(lines) != len(s):
        return s.to_list()
    return [None if v is None else t for v, t in zip(s.to_list(), lines)]


def display_rows(df: pl.DataFrame, digits: int | str | None = None) -> list[tuple]:
    cols = [
        float_text(s, digits) if s.dtype.is_float() else s.to_list()
        for s in df.get_columns()
    ]
    return list(zip(*cols))

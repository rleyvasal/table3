# Changelog

## 0.4.1 — unreleased

### Fixed

- The explorer's headers show that they sort before the first click: a
  faint ↕ beside each name, which turns into ▲ or ▼ on the sorted column,
  and "Click to sort by …" on hover.

## 0.4.0 — 2026-11-03

### Added

- `table3.view(data)` opens a data explorer over the first 10,000 rows, as
  R's `View()`: one grid to scroll, with row numbers, a search box, headers
  that sort on a click (ascending, descending, off; nulls last), and a filter
  under each column: from–to for numbers and dates (`2008` matches a year),
  "contains" for text, and a pick-list for booleans and columns of at most
  50 values. The status line counts the rows that pass ("120 of 344 rows").
  It runs in the notebook's browser, so it works in saved notebooks; the
  rows are JSON drawn a screen at a time, about 1 MB for 10,000 rows of a
  dozen columns. Where output scripts don't run, it shows the first 100
  rows as `show()` does. [docs/explorer.md](docs/explorer.md) has the design.

## 0.3.0 — 2026-11-02

table3 is view3 renamed: the table is how a frame prints in a notebook, as
R's `print()`, and `view` is kept for a data explorer, as R's `View()`. Its
versions continue view3's, whose entries are below; this is table3's first
release on PyPI.

### Changed from view3 0.2.0

- `view3.view()` is `table3.show()`, and there is no `view()`. Nothing used
  `view()` yet.
- The hook is `__table3__`, not `__view3__`.
- The footer no longer names `n=`: "1–10 of 100 rows (first 100 of 344)".
  A package showing the table as its frames' notebook display sets *n*
  itself.

## view3 0.2.0 — 2026-11-02

### Added

- `digits=` chooses how floats print. `digits=6` keeps six significant
  digits, as R's `signif()` does, so small numbers keep their precision
  (`0.000123457`, `1.5e-7`) where the default shows `0.000123`;
  `digits="full"` shows every stored digit. The default, `None`, prints as
  polars' text preview does, as before.

## view3 0.1.0 — 2026-11-02

Phase 1 of [the design](docs/design.md).

### Added

- `view3.view(data)` shows up to `n` rows in a paged table and returns
  `data`; `view3.html(data)` returns the HTML. Ten rows a page
  (`page_size=`), column pages for wide tables, and a scroll box with pinned
  names and types where output scripts don't run or with `pages=False`.
- polars DataFrames, LazyFrames and Series, pandas DataFrames and Series, and
  any object with a `__view3__(n)` method.

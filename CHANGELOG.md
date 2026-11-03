# Changelog

## 0.3.0 — unreleased

### Changed

- `view3.view()` is `view3.show()`, and `view()` is removed: the name is
  kept for a data explorer, as R's `View()` opens one, while this table is
  how R notebooks print a data frame. Nothing used `view()` yet.
- The footer no longer names `n=`: "1–10 of 100 rows (first 100 of 344)".
  A package showing the table as its frames' notebook display sets *n*
  itself.

## 0.2.0 — 2026-11-02

### Added

- `digits=` chooses how floats print. `digits=6` keeps six significant
  digits, as R's `signif()` does, so small numbers keep their precision
  (`0.000123457`, `1.5e-7`) where the default shows `0.000123`;
  `digits="full"` shows every stored digit. The default, `None`, prints as
  polars' text preview does, as before.

## 0.1.0 — 2026-11-02

Phase 1 of [the design](docs/design.md).

### Added

- `view3.view(data)` shows up to `n` rows in a paged table and returns
  `data`; `view3.html(data)` returns the HTML. Ten rows a page
  (`page_size=`), column pages for wide tables, and a scroll box with pinned
  names and types where output scripts don't run or with `pages=False`.
- polars DataFrames, LazyFrames and Series, pandas DataFrames and Series, and
  any object with a `__view3__(n)` method.

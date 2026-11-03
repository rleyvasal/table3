# Changelog

## 0.2.0 — unreleased

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

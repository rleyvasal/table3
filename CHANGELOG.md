# Changelog

## Unreleased

### Fixed

- A wide table's scrollbar shows from the start, under the paged table
  and the explorer, where macOS's overlay scrollbars stayed hidden until a
  scroll, so a mouse had nothing to drag (VS Code, Chrome, Edge, Safari;
  Firefox keeps its own). Clicking a table to scroll it with the keys no
  longer draws a focus ring round it; moving to it with Tab still does.

## 0.8.0 — 2026-11-06

### Changed

- A paged table wider than its cell scrolls sideways, as marimo's table
  and VS Code's Data Wrangler do, instead of paging through groups of
  columns with ◂ and ▸: drag the scrollbar, swipe, or Shift+scroll to any
  column, and see any columns side by side. A shadow at an edge says there
  are more columns past it, and the footer names those in view ("Columns
  4–9 of 24"), updated as it scrolls. Turning a row page keeps the columns
  scrolled to.

## 0.7.1 — 2026-11-06

### Fixed

- A column's profile shows its missing count on a line of its own, under
  the distinct count, where narrow columns cut it short before; text
  columns are wide enough for both.

## 0.7.0 — 2026-11-05

### Added

- `view()` explores every row, not only the first *n*, where anywidget is
  installed (`pip install table3[live]`) and the notebook draws Jupyter
  widgets (JupyterLab, Notebook 7, VS Code): search, sort and filters run in
  polars over the whole data, and the grid fetches the rows it scrolls to.
  The first *n* rows are still saved with the notebook, so it reopens
  without its kernel showing them, with a note that search and filters
  cover only those. `view(live=False)` saves the rows alone, as before;
  SolveIt, which draws no widgets, always gets them, and so does lazy
  data unless `live=True` (live mode runs its whole query once): a polars
  LazyFrame, or a package's frame that gives its whole data through a new
  `__table3_source__()` method (a polars DataFrame or LazyFrame), as
  tidy3's frames do.
- The explorer profiles each column under its name and type, as marimo's
  table does: a histogram for numbers, dates and times; the most common
  values for text and booleans; and the distinct and missing counts. Faint
  bars show all rows and solid bars the rows the search and filters keep,
  updated as they change. The toolbar says what the profiles cover (every
  row, the snapshot's rows, or a sample past a million rows, with
  estimated distinct counts marked "≈"); the new Profile button hides them.
- A Columns menu hides columns from the explorer and its exports, and an
  Export menu writes every row the search and filters keep, in the grid's
  order, whatever is in view: CSV with every stored digit, or, when live,
  Parquet with the original types, downloaded or saved in the kernel's
  folder.

### Fixed

- In SolveIt, `view()` hides its cell from the AI again, where SolveIt
  tells it which cell is running: SolveIt no longer puts `__msg_id` in the
  namespace, so `view()` now also asks dialoghelper for the current
  message (`read_msg(n=0)`, as plot3 does), the request's `cellId`, and
  SolveIt's gateway. When none of them says, it reports that
  once a session rather than under every explorer. SolveIt is recognised
  by the dialoghelper it loads into every kernel, so live mode stays off
  there. Hiding needs SolveIt's own dialoghelper: a newer one installed
  with `pip` shadows it and can't find the running cell, so remove that
  copy rather than upgrading (docs/explorer.md §8).

## 0.6.1 — 2026-11-03

### Fixed

- A cell that ends in `view()` shows the explorer alone. `view()` returns
  its data, and Jupyter printed that data again under the explorer, as a
  paged table; now, as R's `View()` returns invisibly, the notebook skips
  printing it. The data is still returned: assigned, piped on, or on a
  later line or in a later cell, it prints as usual. This covers
  `table3.view(df)` for polars and pandas and every package that passes
  its data through `table3.view()`, including tidy3's `view()` before
  tidy3 0.20.3.

## 0.6.0 — 2026-11-03

### Changed

- The explorer's filters stay hidden until the new Filter button beside
  Search is pressed, as in RStudio's viewer. Each column then shows a
  compact `All`; clicking it opens that column's filter (from and to for
  numbers and dates, contains for text, a pick-list for few values), and
  once applied it reads as a label such as `10–50 ×`, where × clears it.
  Turning Filter off clears every filter.
- The paged table lines text up on the left and numbers, dates and times
  on the right, names and types with them, as `view()` does; before,
  every column was on the right.
- The paged table's controls move to RStudio's places: ◂ and ▸ for the
  columns before and after sit at the header's edges, the row and column
  counts at the bottom left, and Previous / pages / Next at the bottom
  right. When *n* cut the rows the counts say so plainly: "Rows 1–10 of
  1,000 previewed (52,341 total)", instead of "1–10 of 1,000 rows (first
  1,000 of 52,341)".

## 0.5.1 — 2026-11-03

### Fixed

- A paged table's Next button stays where it is from the first page to the
  last, so it can be clicked over and over: the page links fill a fixed
  number of fixed-width slots, each column keeps the width measured over
  all rows, and blank rows pad a short last page. A control that can't act
  is dimmed rather than disabled, so it keeps keyboard focus (pressing Enter
  on Next walks every page).

## 0.5.0 — 2026-11-03

### Added

- In SolveIt, `view()` hides its cell from the AI (SolveIt's red eye), as
  plot3 does for plots, so the explorer's rows don't fill the model's
  context. SolveIt hides the cell's code with its output. `view(hide=False)`
  keeps one cell visible, and `table3.autohide(False)` turns it off for the
  session. `show()` and printed tables are not hidden. Outside SolveIt
  nothing changes.

### Changed

- A paged table writes only its first page as styled cells, and every row
  as compact JSON its script draws into the other pages: about a quarter
  of the size (a printed 8-column frame of 100 rows, 23 KB instead of
  86 KB), which matters in SolveIt, where a cell's output goes to the AI.
  Where scripts don't run, the first page shows. `pages=False` is
  unchanged.

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

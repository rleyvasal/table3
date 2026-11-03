# A shared package for viewing tables in notebooks

Status: accepted 2026-11-02; phase 1 (§6) released in view3 0.1.0.

tidy3 previews show ten rows. To see more, a notebook user had to `pull()` a
column and call `.to_list()` on the parenthesized pipe, losing column names,
types and the table. view3 shows up to *n* rows in the cell's output as a
paged table, like RStudio's paged data frames, with tidy3's formatting. It is
its own package because tidy3, tidy3a and stats3 all produce tables to look
at, and none of them should depend on another to do it.

## 1. Precedents

- R splits printing from the table packages: tibble prints through
  [pillar](https://pillar.r-lib.org), which other packages share, and
  RStudio's paged table lives in rmarkdown (`paged_table()`), not dplyr.
- tidy3syntax already shares notebook syntax among tidy3, tidy3a, plot3 and
  stats3 the same way: one small package, a version range in each.
- tidy3a reaches tidy3 through `TidyArray.__tidy__` and never imports it.
  view3 reaches its callers' objects through `__view3__` the same way.

## 2. What it shows

- A table of the first *n* rows (default 1,000), names and types in the
  header, as tidy3's notebook table prints them; `null` for missing values;
  floats as polars' text preview prints them (`3.3`, `1.2346e8`), following
  `pl.Config(float_precision=)`; values longer than 40 characters cut with
  "…", the full value on hover.
- Ten rows a page (`page_size=`), Previous / page numbers / Next, and as many
  columns as fit the cell with `◂ columns` / `columns ▸` for the rest. Column
  groups are measured once over all *n* rows, so they don't shift between
  pages, and they are regrouped when the cell's width changes.
- The footer counts rows and columns ("21–30 of 344 rows | 10–12 of 12
  columns") and says when *n* cut the rows ("1,000 rows (first 1,000 of
  52,341, n=1,000)").

## 3. Where it runs

- **Inline styles only.** CRAFT republishes remote output through
  `display_pub.publish`, which drops `<style>` blocks; tidy3's `display.py`
  is inline-only for the same reason.
- **Theme.** Text inherits the notebook's colour; rules, stripes and
  scrollbars are translucent grey, which reads on dark and light. The pinned
  header needs a solid background: SolveIt's `--card` (an HSL triplet, so
  `hsl(var(--card))`) drawn as a gradient over `var(--vscode-editor-background,
  var(--jp-layout-color0, Canvas))`. An undefined `--card` makes only the
  gradient invalid, so the colour under it shows. Checked in SolveIt's dark
  theme on 2026-11-02 (card `rgb(23,23,23)`).
- **Paging is a script over a plain table.** SolveIt runs output scripts and
  inline handlers, and runs them again when a dialog is reloaded (probed
  2026-11-02); VS Code and trusted Jupyter notebooks run them too. Where
  scripts don't run, the table stays a box `height` pixels tall (default
  300) that scrolls both ways under a pinned header. `pages=False` asks for
  that box everywhere.
- **Size.** Every cell carries its style, about 100 bytes a cell: 1,000 rows
  of 12 columns add about 1.2 MB to a saved notebook. The font is set once
  on the table to halve that.

## 4. Interface

```python
view3.view(data, *, n=1000, pages=True, page_size=10, height=300, caption=None)  # shows, returns data
view3.html(data, *, n=1000, pages=True, page_size=10, height=300, caption=None)  # the HTML
```

*data* is a polars DataFrame, LazyFrame or Series (a LazyFrame's first *n*
rows and row count are collected together), a pandas DataFrame or Series
(read without importing pandas), or any object with

```python
def __view3__(self, n: int) -> tuple[polars.DataFrame, int | None, str | None]:
    """The first n rows, the whole row count (None if not counted), and a caption."""
```

Outside a notebook `view()` prints the rows as text. As a cell's last line
the notebook also prints what `view()` returns; `;` hides it.

## 5. Each package's part

| Package | Change | Dependency |
|---|---|---|
| tidy3 | `TidyFrame.__view3__` from `_preview_parts` (respects `preview_count`), caption `TidyFrame (view groups=[…])`; a `view()` verb that calls `view3.view` and passes the frame through | `view3>=0.1,<0.2` |
| stats3 | Result tables are polars, so `view3.view(table)` works as is; `report.py` may later use `view3.html` | optional at first |
| tidy3a | `TidyArray.__view3__` through `as_table` | extra `tidy3a[view]` (tidy3a has no polars) |
| plot3, tidy3syntax | none | none |

Only tidy3 exports a bare `view`; stats3 and tidy3a document `view3.view(x)`,
so `from … import *` in any order leaves one `view`.

## 6. Phases

1. view3 0.1.0: the prototype's code without tidy3, tests, CI, release.
2. tidy3: dependency, `__view3__`, `view()` verb, reference docs, release.
3. stats3 and tidy3a: hooks and docs.
4. Later: tidy3's ordinary notebook table formats through view3 (its floats
   print in full today); loading further rows while paging.

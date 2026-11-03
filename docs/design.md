# A shared package for notebook tables

Status: accepted 2026-11-02. Released first as view3 (0.1.0 phase 1 of §6,
0.2.0 `digits=` of §2.1); renamed table3 for 0.3.0, with `show()` and the
table as tidy3's notebook display (§5).

tidy3 previews showed ten rows. To see more, a notebook user had to `pull()`
a column and call `.to_list()` on the parenthesized pipe, losing column
names, types and the table. R notebooks print every data frame as a paged
table (R Markdown's `df_print: paged`, `rmarkdown::paged_table()`): ten rows
a page, up to `max.print` rows to page through. table3 is that table, with
tidy3's formatting, for any package's `_repr_html_`. It is its own package
because tidy3, tidy3a and stats3 all produce tables to look at, and none of
them should depend on another to do it.

The name `view` is kept for a data explorer: in R, `View(df)` opens
RStudio's viewer, where you search, sort and filter as in a spreadsheet.
That is not this table, so the package is table3 (what it makes), its
functions `html()` and `show()` (R's `print()`), and a later `table3.view()`
can be the explorer. view3 0.1 and 0.2 called `show()` `view()`; nothing
used it yet, so it is gone rather than deprecated.

## 1. Precedents

- R splits printing from the table packages: tibble prints through
  [pillar](https://pillar.r-lib.org), which other packages share, and
  RStudio's paged table lives in rmarkdown (`paged_table()`), not dplyr.
- tidy3syntax already shares notebook syntax among tidy3, tidy3a, plot3 and
  stats3 the same way: one small package, a version range in each.
- tidy3a reaches tidy3 through `TidyArray.__tidy__` and never imports it.
  table3 reaches its callers' objects through `__table3__` the same way.

## 2. What it shows

- A table of the first *n* rows (default 1,000), names and types in the
  header, as tidy3's notebook table prints them; `null` for missing values;
  floats as polars' text preview prints them (`3.3`, `1.2346e8`), following
  `pl.Config(float_precision=)`, unless `digits=` asks for significant
  digits (§2.1); values longer than 40 characters cut with
  "…", the full value on hover.
- Ten rows a page (`page_size=`), Previous / page numbers / Next, and as many
  columns as fit the cell with `◂ columns` / `columns ▸` for the rest. Column
  groups are measured once over all *n* rows, so they don't shift between
  pages, and they are regrouped when the cell's width changes.
- The footer counts rows and columns ("21–30 of 344 rows | 10–12 of 12
  columns") and says when *n* cut the rows ("1–10 of 100 rows (first 100 of
  52,341)").

### 2.1 Float digits

Polars' preview keeps up to six decimal places, so `0.000123456789` shows as
`0.000123`, and its `float_precision` counts decimal places, which turns
small numbers into `0.00`. `digits=k` instead keeps *k* significant digits,
as R's `signif()` and tibble's `pillar.sigfig` count them: `0.000123457`,
`1.5e-7`, `1.23457e8` for `digits=6`, written as polars writes floats (`2.0`,
an exponent without `+` or a leading zero). `digits="full"` is polars'
`fmt_float="full"`: every stored digit, float noise included. Text output
outside a notebook takes `"full"` but not *k*, since polars prints no
significant digits and converting the column would print its type as `str`.

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
table3.show(data, *, n=1000, pages=True, page_size=10, height=300, digits=None, caption=None)  # shows, returns data
table3.html(data, *, n=1000, pages=True, page_size=10, height=300, digits=None, caption=None)  # the HTML
```

*data* is a polars DataFrame, LazyFrame or Series (a LazyFrame's first *n*
rows and row count are collected together), a pandas DataFrame or Series
(read without importing pandas), or any object with

```python
def __table3__(self, n: int) -> tuple[polars.DataFrame, int | None, str | None]:
    """The first n rows, the whole row count (None if not counted), and a caption."""
```

Outside a notebook `show()` prints the rows as text. As a cell's last line
the notebook also prints what `show()` returns; `;` hides it. A package
prints its frames as this table by returning `table3.html(self, n=…)` from
`_repr_html_`.

## 5. Each package's part

| Package | Change | Dependency |
|---|---|---|
| tidy3 | `TidyFrame._repr_html_` returns `table3.html(self, n=preview_max, page_size=preview_rows, digits=preview_digits)` from `options()`; `TidyFrame.__table3__` from `_preview_parts` (respects `preview_count`), caption `TidyFrame (preview groups=[…])`. No verb: every frame in a cell prints this way | `table3>=0.3,<0.4` |
| stats3 | Result tables are polars, so `table3.show(table)` works as is; its own result objects may return `table3.html` from `_repr_html_` | optional at first |
| tidy3a | `TidyArray.__table3__` through `as_table` | extra `tidy3a[view]` (tidy3a has no polars) |
| plot3, tidy3syntax | none | none |

None of them exports `show` or `view` bare, so `from … import *` in any order
leaves the names alone.

## 6. Phases

1. view3 0.1.0: the prototype's code without tidy3, tests, CI, release.
2. tidy3: dependency, `__table3__`, the table as `_repr_html_`, reference docs,
   release.
3. stats3 and tidy3a: hooks and docs.
4. Later: tidy3's ordinary notebook table formats through table3 (its floats
   print in full today); loading further rows while paging.

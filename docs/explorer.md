# A data explorer: `table3.view()`

Status: accepted 2026-11-03; phase 1 released in table3 0.4.0.

A printed frame shows as a paged table (design.md). R has a second way to
look at data: `View(df)` opens RStudio's data viewer, a spreadsheet-like
grid where you search, sort and filter without writing code. This document
plans that viewer for table3: `table3.view(data)`, and a `view()` verb in
tidy3.

## 1. What R's `View()` does

- One grid of every row, scrolled rather than paged, with row numbers and a
  pinned header.
- **Search** across every column in one box.
- **Sort** by clicking a column header: ascending, descending, off.
- **Filter** per column: a range for numbers and dates, text match for
  strings, a pick-list for factors.
- A status line: "Showing 1 to 120 of 344 entries, 8 total columns".
- It reads only what it shows from the R session, so millions of rows work.

## 2. Where filtering runs

**Phase 1: in the browser.** `view()` writes the first *n* rows into the
output once, as compact JSON, and a script draws the grid and runs search,
sort and filters on them.

- It works where the paged table works: SolveIt runs output scripts and runs
  them again when a dialog is reloaded (probed 2026-11-02); VS Code and
  trusted Jupyter notebooks run them too. A saved notebook reopens with the
  explorer working.
- No new dependency, no kernel connection.
- It explores only the rows it was given: `n=10_000` by default, about 1 MB
  for a dozen columns. The status line says when *n* cut the rows ("120 of
  10,000 rows (first 10,000 of 52,341)").
- Rows are JSON, not HTML: 10,000 rows of HTML table cells with inline
  styles would be about 12 MB. The script draws only the rows in view
  (virtual scrolling), so the grid stays fast at 10,000 rows.

**Phase 3 (later, if needed): through the kernel.** A live widget (anywidget)
sends each search, sort or filter to polars and gets one screen of rows
back, so it explores any number of rows lazily. It needs a live kernel and
shows nothing in a saved notebook, and SolveIt's and CRAFT's support for
widgets was unknown. It would be an optional extra (`table3[explore]`), and a
probe like the script probe decided whether to build it.

Probed 2026-11-03: SolveIt does not draw Jupyter widgets. An anywidget whose
button sends a click to the kernel printed as its text,
`<__main__.Probe object at 0x…>`, with no button, so a widget has no kernel
connection there. The kernel-backed mode is not built: the in-browser
explorer is the only one, and `n=` is how to explore more rows. A widget
mode for VS Code and Jupyter alone would split the explorer by notebook, so
it waits for a need that `n=` can't meet.

**Revisited 2026-11-05: a live mode beside the snapshot.** Exploring every
row (as marimo's table and VS Code's Data Wrangler do) is now planned as a
second mode, not a replacement: a widget whose output also carries today's
explorer as HTML, so a notebook that draws widgets gets the live grid and one
that doesn't (SolveIt, a saved notebook without a kernel) gets the snapshot.
Steps: (1) a Python backend that runs search, filters and sort over every
row and returns one page; (2) the widget and its fallback, with probes in
SolveIt and in saved JupyterLab and VS Code notebooks; (3) column profiles;
(4) export of the filtered rows; (5) tidy3's hook.

Step 1 is `table3/_source.py`. `Source(data)` collects *data* whole once
(a LazyFrame is collected; pandas converted once) and answers requests
`{id, search, filters, sort, offset, limit, columns}` with the matching row
count and that page in the embedded explorer's shape. Its rules are the
browser's, checked against a Python copy of `passes()` and `compare()` on
random states (`tests/test_source.py`), so live and snapshot keep the same
rows. A package exposes its whole data with
`__table3_source__(self) -> polars.DataFrame | polars.LazyFrame`, beside
`__table3__(n)` for the preview. Each search/filter/sort state keeps its row
order (8 most recent), so paging costs only the page, and a request older
than one already answered gets no answer. On 5 million rows a filtered,
sorted page takes about 0.05 s; the first search formats each float column
as displayed once (about 4 s for 5 million floats), later ones about 0.2 s.

Step 2 (`table3/_live.py`, `view(live=None)`): the grid's script is now one
function, `table3Explorer(root, data, remote)`, over either the snapshot's
rows or a kernel's (`_explorer_js.EXPLORER_CORE`). The widget (anywidget,
extra `table3[live]`) sends the state with an offset and fetches blocks of
200 rows as the grid scrolls; the first block comes with the widget, so it
draws at once. A change of search, filter or sort starts a new version and
an answer for an older one is dropped, while the old rows stay, dimmed,
until the new ones come.

Probed in JupyterLab 4.6 with ipywidgets 8.1 (2026-11-05): a widget output
that also carries `text/html` shows "Error displaying widget: model not
found" once the notebook is reopened without its kernel, never the HTML.
So `view()` displays two outputs: the snapshot explorer (first *n* rows, as
before), then the widget. The widget hides the snapshot when it draws, and
the snapshot hides itself if the widget is already there. Without a kernel
the snapshot shows, its status line saying it covers the first *n* rows
only, and it hides JupyterLab's "model not found" line in its cell.
`scripts/check_lab.py` checks this in JupyterLab end to end. `live=None`
is live where anywidget imports in a Jupyter kernel, never in SolveIt
(found by its `__msg_id`), and only for data `Source` can read whole; a
`__table3__`-only object stays a snapshot. A polars LazyFrame also stays a
snapshot unless `live=True` (decided 2026-11-05): live mode holds the whole
data in memory, so it would run the whole query, a large scan say, where the
snapshot collects *n* rows. The same goes for any `__table3_source__`
object (decided 2026-11-05, step 5): tidy3's frames are lazy queries, so
`penguins >> view()` is a snapshot and `view(live=True)` explores every row.
`_source.eager(data)` is the test: a polars or pandas DataFrame or Series.

Step 3 (`table3/_profile.py`): a profile row under the types, as marimo's
table shows one. Numbers, dates and times get a histogram of up to 20
equal bins (a bin per value for integers and dates spanning fewer),
labelled with the smallest and largest value as printed; text, pick-list
values and booleans get a bar of their three most common values and the
rest. Every column says how many distinct and missing (null, or NaN)
values it holds. The bins and top values are laid out once over all rows,
so they stay put as filters change: faint bars are all rows, solid blue
bars the rows the search and filters keep. A Profile button beside Filter
hides the row. The toolbar says what the profiles cover: "Profiles: all
120 rows", "these 1,000 snapshot rows" (the snapshot when *n* cut the
data), or "a sample of 1,000,000 of 5,000,000 rows". Past 1,000,000 kept
rows the bars come from a fixed random sample, missing values are still
counted on every kept row, and distinct values are estimated (HyperLogLog,
shown "≈"); about 0.3 s for 5 million rows.

Python computes every profile in the live explorer, with the first block
of each new search, filter or sort (the sort alone reuses the last one).
The snapshot gets the layouts from Python and recounts in the browser as
its filters change, dates from each row's bin (sent with the rows),
numbers from their values, top values by display text; a browser test
checks that its counts are Python's.

Step 4: a **Columns** menu (a checkbox per column; one always stays) hides
columns from the grid and from exports, and an **Export** menu writes every
row the search and filters keep, in the grid's order, the shown columns,
whatever part of the grid is in view. Its first line says so: "111 rows × 3
columns, as sorted".

- Live: Python writes the file from the same rows the grid shows
  (`Source.kept`, `Source.export`): CSV as polars writes it (every stored
  digit, `inf`, `NaN`, empty for null) or Parquet (the original types).
  "Download" sends the bytes to the browser as a binary widget message (a
  2,000,000-row, 67 MB CSV took 0.4 s in JupyterLab), refused past 256 MB;
  "Save … in the kernel's folder" writes `table3-export-<time>.csv` or
  `.parquet` where the kernel runs (useful when it runs on another machine)
  and shows the path.
- Snapshot: the browser writes the CSV of its kept rows, the same text as
  polars' CSV (a browser test compares them byte for byte), except that
  datetimes and times are written as the grid shows them
  (`2020-01-01 00:00:00`, where polars writes `2020-01-01T00:00:00.000000`).
  When *n* cut the data, the menu says the snapshot holds the first *n* rows
  and that running the cell exports every row. No Parquet: the browser has
  only JSON values.

Not checked: whether VS Code's notebook outputs allow a download link's
click (its outputs run in a webview); saving in the kernel's folder works
there either way. Not yet checked by hand: VS
Code (`docs/check.ipynb` has a live case) and the widget's text in viewers
without widgets (it is empty, so only the snapshot shows).

## 3. Interface

```python
table3.view(data, *, n=10_000, height=500, digits=None, caption=None, hide=None)  # shows, returns data
table3.autohide(on=True)  # whether view() hides its cell from SolveIt's AI
```

*data* is anything `html()` and `show()` take, `__table3__` objects
included. It returns *data* unchanged, like `show()`, but a cell that ends
in `view()` doesn't print it under the explorer, as R's `View()` returns
invisibly (0.6.1): `view()` wraps IPython's `sys.displayhook` until the cell
ends and skips *data* when it is printed as the value of the statement
that called `view()`. `view(df); df`, a value piped on from `view()`, and
*data* in a later cell print as usual. Outside a notebook it prints the first rows as
`show()` does.

In SolveIt, which sends each cell's code and output to its AI, `view()`
then marks its cell hidden from the AI (`dialoghelper.update_msg(skipped=1)`,
SolveIt's red eye), as plot3 does for plots: the rows would fill the
model's context. SolveIt has no flag for an output alone, so the cell's code
is hidden too; a `view()` cell is usually one line. `show()` and printed
tables are not hidden, since most analysis cells end in a frame and hiding
those would hide their code. `hide=False`, or `autohide(False)` for the
session, keeps cells visible. Added in 0.5.0.

tidy3 adds `view()` as a verb and method, as `glimpse()`: `penguins >> view()`,
`view(penguins)`, `penguins.view()`, passing the frame through. It is the
only bare `view` in the family; tidy3a and stats3 document `table3.view(x)`.

## 4. The grid

- **Header**, pinned: name, type (`i64`, `str`), and a sort arrow; clicking
  cycles ascending, descending, off. One sort column at a time, as R.
- **Filters**, as RStudio shows them: hidden until the **Filter** button
  beside the search box is pressed, then a compact `All` under each
  column. Clicking it opens that column's editor in its place:
  - numbers and dates: two boxes, from and to, either blank;
  - strings: contains, case-insensitive;
  - strings with at most 50 distinct values, booleans and categoricals: a
    pick-list of their values, with `null` as one choice.
  Enter, Escape or a click elsewhere closes the editor, and a column with a
  filter then reads it in words, `10–50 ×`, `≥ 2008 ×`, `Gentoo ×` or
  `"item 2" ×`, where × clears it. Turning Filter off clears every filter,
  so no row is ever filtered out of sight. The editor is the chip's height,
  so opening it moves nothing. (0.5.1 and before showed every column's
  boxes at once: two inputs under each number column, mostly unused.)
- **Search box** above: rows where any cell's text contains it.
- **Row numbers** on the left: the row's place in *data*, kept through sorts
  and filters, as R shows them.
- **Status line**: "120 of 344 rows | 8 columns", plus the *n* note.
- **Cells** as the table formats them: `null`, floats by `digits=`, long
  values cut with the full value on hover. Sorting and filters use the raw
  values, so numbers sort as numbers and nulls go last.
- **Wide frames** scroll sideways with the row numbers pinned at the left.
- **Theme**: table3's colours and translucent greys, every style inline (set
  by the script), no `<style>` block.

**Without scripts** (an untrusted Jupyter notebook, perhaps CRAFT's
republish) the output is `show()`'s table of the first 100 rows, with a line
saying the explorer needs output scripts.

## 5. Data in the output

```json
{"columns": [{"name": "species", "type": "str", "kind": "text", "choices": ["Adelie", "Chinstrap", "Gentoo"]},
             {"name": "body_mass_g", "type": "i64", "kind": "number"}],
 "rows": [["Adelie", 3750], ["Adelie", null]],
 "shown": [null, ["3750"]],
 "total": 344, "n": 10000}
```

- `rows` holds raw values for sorting and filtering: numbers as numbers,
  dates and times as ISO text (which sorts in order), everything else as
  text, `null` for missing.
- `shown` holds a column's display text only where it differs from the raw
  value: floats (`digits=`) and values cut at 40 characters. Other columns
  show their raw text.
- `kind` picks the filter: `number`, `date`, `text`, `choice`, `bool`.
- The JSON goes in a `<script type="application/json">` element beside the
  grid, escaped so a value holding `</script>` can't end it.

## 6. Tests

- **pytest**: the JSON (kinds, choices, raw and shown values, escaping, the
  *n* cut, `__table3__` objects, pandas), `view()` returning its input, the
  no-script fallback.
- **pytest with Playwright** (headless Chromium): load the output in a page
  and drive it: sort cycles, each filter kind, search, row numbers kept,
  status line counts, virtual scrolling at 10,000 rows, a value holding
  `</script>`. Its own CI job (`pip install pytest-playwright`, `playwright
  install chromium`) and a `scripts/check.sh` step, as neither the Mac nor
  gpudev has a headless browser installed.
- **By eye**: `docs/check.ipynb` cells for the explorer, in SolveIt (dark
  theme) and VS Code.

## 7. Phases

1. table3 0.4.0: `table3.view()` in the browser (§2, §4–§6).
2. tidy3: the `view()` verb and method, reference docs, release.
3. Probe SolveIt and CRAFT for widgets; if they work and in-browser limits
   bite, a kernel-backed mode as `table3[explore]`. Done 2026-11-03: SolveIt
   does not draw widgets (§2), so there is no kernel-backed mode.
4. tidy3a and stats3: document `table3.view(x)`.

## 8. SolveIt and dialoghelper (fragile)

Two things in table3 depend on SolveIt's private helpers, dialoghelper, and
may break when SolveIt updates:

- **Hiding a `view()` cell from the AI** (`_solveit.hide_calling_cell`)
  needs the running cell's id, which SolveIt has exposed differently over
  time:
  1. `__msg_id` in the notebook namespace: older SolveIt; gone by
     2026-11-05.
  2. `dialoghelper.core.read_msg(n=0, relative=True)`, answered by
     SolveIt's server: dialoghelper 0.2.41, the version SolveIt ships in
     `/usr/local` as of 2026-11-05. This is what works today (plot3 uses it
     too).
  3. `update_msg(skipped=1)` with no id, dialoghelper 0.2.45 and later,
     which asks SolveIt's gateway through a comm. It needs
     `RUSTYGATE_KERNEL_ID`, which the 2026-11-05 SolveIt doesn't set, so it
     fails there.
  `_hide` tries 1 (both id forms) when `__msg_id` is there, else 3; then
  2, the request's `cellId`, and the gateway's caller route; and reports a
  failure once a session.
- **Knowing it's SolveIt** (so live mode stays off: SolveIt draws no
  widgets): `dialoghelper` loaded in `sys.modules` (SolveIt loads it into
  every kernel), `RUSTYGATE_KERNEL_ID`, or `__msg_id`. SolveIt also sets
  `IN_SOLVEIT` and `__DIALOG_NAME`.

**A trap found on 2026-11-05.** A newer dialoghelper installed with `pip`
lands in the user's `~/.local` (`/app/data/.local`) and shadows SolveIt's
own copy in `/usr/local`, along with newer dependencies (toolslm and
others). A dialoghelper newer than the SolveIt server can't find the
running cell, and SolveIt's own dialoghelper then fails to import against
the newer dependencies (`No module named 'toolslm.funccall'`). The fix was
to `pip uninstall` the `~/.local` copies of SolveIt's packages so SolveIt's
matching versions load. Don't tell users to upgrade dialoghelper.

**When SolveIt updates**, check in a SolveIt cell: `import dialoghelper;
print(dialoghelper.__file__, dialoghelper.__version__)`, whether
`await dialoghelper.core.update_msg(skipped=1)` hides the cell by itself,
and whether `table3.view(df)` hides its cell without a warning. Then adjust
`_hide`'s order and this section.


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
widgets is unknown. It would be an optional extra (`table3[explore]`), and a
probe like the script probe decides whether to build it.

## 3. Interface

```python
table3.view(data, *, n=10_000, height=500, digits=None, caption=None)  # shows, returns data
```

*data* is anything `html()` and `show()` take, `__table3__` objects
included. It returns *data* unchanged, like `show()`; `;` hides the
notebook's own print of it. Outside a notebook it prints the first rows as
`show()` does.

tidy3 adds `view()` as a verb and method, as `glimpse()`: `penguins >> view()`,
`view(penguins)`, `penguins.view()`, passing the frame through. It is the
only bare `view` in the family; tidy3a and stats3 document `table3.view(x)`.

## 4. The grid

- **Header**, pinned: name, type (`i64`, `str`), and a sort arrow; clicking
  cycles ascending, descending, off. One sort column at a time, as R.
- **Filter row** under the header, one control per column by type:
  - numbers and dates: two boxes, from and to, either blank;
  - strings: contains, case-insensitive;
  - strings with at most 50 distinct values, booleans and categoricals: a
    pick-list of their values, with `null` as one choice.
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
   bite, a kernel-backed mode as `table3[explore]`.
4. tidy3a and stats3: document `table3.view(x)`.

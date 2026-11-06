"""Write docs/check.ipynb: the cases to look at by eye in VS Code and SolveIt.

    python scripts/check_notebook.py
"""

from pathlib import Path

import nbformat as nbf

PENGUINS = (
    '"https://raw.githubusercontent.com/allisonhorst/palmerpenguins/main/'
    'inst/extdata/penguins.csv"'
)

cells = [
    ("md", "# table3 check\nRun all, then page through each table in your "
           "notebook's dark and light themes."),
    ("code", "import polars as pl\nimport table3\n\n"
             f"penguins = pl.read_csv({PENGUINS}, null_values=\"NA\")"),
    ("md", "## Every distinct value, paged"),
    ("code", 'table3.show(penguins.select("body_mass_g").unique().sort("body_mass_g"));'),
    ("md", "## The same as a scroll box (`pages=False`)"),
    ("code", 'table3.show(penguins.select("body_mass_g").unique().sort("body_mass_g"), '
             "pages=False, height=300);"),
    ("md", "## Wide: scroll sideways"),
    ("code", "table3.show(penguins.with_columns(\n"
             '    bill_ratio=pl.col("bill_length_mm") / pl.col("bill_depth_mm"),\n'
             '    mass_kg=pl.col("body_mass_g") / 1000,\n'
             '    label=pl.concat_str("species", "island", "sex", separator=" / "),\n'
             '    note=pl.lit("a long note that goes past forty characters, cut with a hover"),\n'
             "));"),
    ("md", "## Row limit, bigger pages, empty"),
    ("code", "table3.show(penguins, n=100, page_size=25);"),
    ("code", 'table3.show(penguins.filter(pl.col("body_mass_g") > 99999));'),
    ("md", "## Explorer: search, click a header to sort, filter under each column"),
    ("code", "dated = penguins.with_columns(\n"
             '    day=pl.date(2007, 1, 1) + pl.duration(days=pl.int_range(pl.len()) * 3),\n'
             ")\n"
             "table3.view(dated);"),
    ("code", "table3.view(pl.DataFrame({\"x\": range(10_000)}), height=300);"),
    ("md", "## Live explorer (pip install table3[live]): every row, through the kernel\n"
           "Search, sort and filter cover all 2,000,000 rows. Reopen the notebook without its "
           "kernel: the first 1,000 rows show instead, and the status line says so."),
    ("code", "big = pl.DataFrame({\"x\": range(2_000_000)}).with_columns(\n"
             "    s=pl.format(\"item {}\", \"x\"), half=pl.col(\"x\") / 2)\n"
             "table3.view(big, n=1000);"),
    ("md", "## Viewing returns the data unchanged"),
    ("code", "before = penguins.clone()\ntable3.show(penguins).equals(before)"),
]

nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(s) if kind == "md" else nbf.v4.new_code_cell(s)
    for kind, s in cells
]
nbf.write(nb, Path(__file__).resolve().parent.parent / "docs" / "check.ipynb")

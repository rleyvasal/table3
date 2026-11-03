# view3

Paged, theme-aware tables in notebook output. It is the shared viewer of
[tidy3](https://github.com/rleyvasal/tidy3),
[tidy3a](https://github.com/rleyvasal/tidy3a) and
[stats3](https://github.com/rleyvasal/stats3), released on its own so each
can show tables without depending on the others. It needs only polars.

```python
import polars as pl
import view3

penguins = pl.read_csv(
    "https://raw.githubusercontent.com/allisonhorst/palmerpenguins/main/inst/extdata/penguins.csv",
    null_values="NA",
)
view3.view(penguins);                           # ten rows a page, every row up to n=1000
view3.view(penguins, page_size=25);             # bigger pages
view3.view(penguins, pages=False, height=300);  # one box that scrolls
```

Column names and types sit in the header, missing values show as `null`,
floats print as polars' text preview prints them, and long values are cut
with the full value on hover. Wide tables show as many columns as fit, with
arrows to the rest. The table follows the notebook's light or dark theme in
VS Code, JupyterLab and SolveIt.

`view()` returns what it was given, so it can sit in the middle of a pipe.
As a cell's last line the notebook also prints that value; end the line with
`;` to hide it.

## Your own objects

An object with a `__view3__` method shows without view3 importing its
package:

```python
def __view3__(self, n):
    return first_n_rows_as_polars, total_rows_or_None, "caption or None"
```

## More

[docs/design.md](docs/design.md) records the design and what each package
adds.

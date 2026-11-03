# table3

Paged, theme-aware tables in notebook output, the way R notebooks print a
data frame. It is the shared table display of
[tidy3](https://github.com/rleyvasal/tidy3),
[tidy3a](https://github.com/rleyvasal/tidy3a) and
[stats3](https://github.com/rleyvasal/stats3), released on its own so each
can show tables without depending on the others. It needs only polars.

```python
import polars as pl
import table3

penguins = pl.read_csv(
    "https://raw.githubusercontent.com/allisonhorst/palmerpenguins/main/inst/extdata/penguins.csv",
    null_values="NA",
)
table3.show(penguins);                           # ten rows a page, every row up to n=1000
table3.show(penguins, page_size=25);             # bigger pages
table3.show(penguins, pages=False, height=300);  # one box that scrolls
table3.show(penguins, digits=4);                 # four significant digits
```

Column names and types sit in the header, missing values show as `null`,
floats print as polars' text preview prints them (or to `digits=`
significant digits, or `digits="full"`), and long values are cut with the
full value on hover. Wide tables show as many columns as fit, with
arrows to the rest. The table follows the notebook's light or dark theme in
VS Code, JupyterLab and SolveIt.

## Explore

`table3.view(penguins)` opens a data explorer, as R's `View()` does: one
grid of up to 10,000 rows with a search box, headers that sort on a click,
and a filter under each column (from–to for numbers and dates, "contains"
for text, a pick-list for columns of few values).

```python
table3.view(penguins);
table3.view(penguins, n=50_000, height=600);  # more rows, a taller grid
```

`show()` and `view()` return what they were given, so they can sit in the
middle of a pipe.
As a cell's last line the notebook also prints that value; end the line with
`;` to hide it.

## Your own frames

A package makes its frames print this way by returning `table3.html(self)`
from `_repr_html_`. An object with a `__table3__` method shows without table3
importing its package:

```python
def __table3__(self, n):
    return first_n_rows_as_polars, total_rows_or_None, "caption or None"

def _repr_html_(self):
    return table3.html(self, n=100)
```

## More

[docs/design.md](docs/design.md) records the design and what each package
adds, and [docs/explorer.md](docs/explorer.md) the explorer's. table3 was
first released as view3 0.1 and 0.2, where `show()` was `view()`; its
versions continue from them, and `view()` is now the explorer.

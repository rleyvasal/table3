import re

import polars as pl
import pytest

import view3


def _body_rows(html: str) -> int:
    return html.split("<tbody>")[1].count("<tr")


@pytest.fixture
def islands():
    # 29 distinct values, like a distinct() over one column
    return pl.DataFrame({"island": [f"island {i:02d}" for i in range(29)]})


class Frame:
    """A package's own frame: shown through __view3__ without view3 knowing it."""

    def __init__(self, df, counted=True):
        self.df, self.counted, self.asked = df, counted, []

    def __view3__(self, n):
        self.asked.append(n)
        return self.df.head(n), self.df.height if self.counted else None, "Frame (view)"


def test_all_rows_shown(islands):
    html = view3.html(islands)
    assert _body_rows(html) == 29
    assert "island 28" in html
    assert "max-height:300px" in html
    assert ">29 rows<" in html


def test_header_and_types_pinned(islands):
    thead = view3.html(islands).split("<thead")[1].split("</thead>")[0]
    assert "position:sticky;top:0" in thead
    assert "<b>island</b>" in thead and ">str<" in thead


def test_row_limit_labelled():
    html = view3.html(pl.DataFrame({"x": range(2500)}), n=1000)
    assert _body_rows(html) == 1000
    assert "showing first 1,000 of 2,500 rows (n=1,000)" in html
    assert "data-label='1,000 rows (first 1,000 of 2,500, n=1,000)'" in html
    assert "shape: (2500, 1)" in html


def test_lazy_frame_counted():
    html = view3.html(pl.LazyFrame({"x": range(50)}), n=10)
    assert _body_rows(html) == 10 and "shape: (50, 1)" in html


def test_view3_hook_gives_rows_count_and_caption():
    frame = Frame(pl.DataFrame({"x": range(50)}), counted=False)
    html = view3.html(frame, n=10)
    assert frame.asked == [10]
    assert ">Frame (view)<" in html
    assert "shape: (?, 1)" in html
    assert "showing first 10 of more rows" in html
    assert "(first 10 of more, n=10)" in html
    assert ">Mine<" in view3.html(frame, caption="Mine")


def test_nulls_mixed_types_and_long_strings():
    df = pl.DataFrame(
        {"n": [1, None, 3], "s": ["short", None, "<b>" + "y" * 100], "d": [1.5, 2.0, None]}
    )
    html = view3.html(df)
    assert html.split("<tbody>")[1].count(">null<") == 3
    assert ">i64<" in html and ">f64<" in html
    assert "<b>yyy" not in html  # escaped, never live markup
    assert "title='&lt;b&gt;" + "y" * 100 + "'" in html
    assert re.search(r"&lt;b&gt;y{36}…</span>", html)


def test_floats_as_text_preview():
    df = pl.DataFrame(
        {"x": [3.3000000000000003, 1.9015544041450778, None, 123456789.123, 2.0],
         "y": [1, 2, 3, 4, 5]}
    )
    body = view3.html(df).split("<tbody>")[1]
    cells = re.findall(r"<td style='[^']*'>([^<]*)</td>", body)
    assert cells[0::2] == ["3.3", "1.901554", "null", "1.2346e8", "2.0"]
    assert cells[1::2] == ["1", "2", "3", "4", "5"]
    with pl.Config(float_precision=2):
        assert ">1.90<" in view3.html(df)


def _float_cells(html: str) -> list[str]:
    return re.findall(r"<td style='[^']*'>([^<]*)</td>", html.split("<tbody>")[1])


SMALL = pl.DataFrame(
    {"x": [0.000123456789, 1.5e-7, 2.5e-12, 1.9015544041450778, 123456789.123,
           2.0, -0.5, float("nan"), float("inf"), None]}
)


def test_digits_significant_keeps_small_numbers():
    assert _float_cells(view3.html(SMALL, digits=6)) == [
        "0.000123457", "1.5e-7", "2.5e-12", "1.90155", "1.23457e8",
        "2.0", "-0.5", "NaN", "inf", "null",
    ]
    assert _float_cells(view3.html(SMALL, digits=2))[:4] == [
        "0.00012", "1.5e-7", "2.5e-12", "1.9",
    ]


def test_digits_default_and_full():
    default = _float_cells(view3.html(SMALL))
    assert default[:2] == ["0.000123", "1.5000e-7"]
    full = _float_cells(view3.html(SMALL, digits="full"))
    assert full[:5] == [
        "0.000123456789", "0.00000015", "0.0000000000025", "1.9015544041450778",
        "123456789.123",
    ]


def test_digits_leave_other_columns_and_float32():
    df = pl.DataFrame({"i": [123456789], "s": ["0.123456789"],
                       "f": pl.Series([0.1], dtype=pl.Float32)})
    assert _float_cells(view3.html(df, digits=3)) == ["123456789", "0.123456789", "0.1"]


def test_digits_in_text_output(capsys):
    view3.view(SMALL.head(1), digits="full")
    assert "0.000123456789" in capsys.readouterr().out
    view3.view(SMALL.head(1), digits=3)  # polars prints its own floats
    assert "f64" in capsys.readouterr().out


def test_empty():
    html = view3.html(pl.DataFrame({"x": []}, schema={"x": pl.Int64}))
    assert _body_rows(html) == 0
    assert "<b>x</b>" in html and ">0 rows<" in html


def test_wide_table_keeps_every_column():
    html = view3.html(pl.DataFrame({f"c{i}": [i] for i in range(45)}))
    assert [i for i in range(45) if f"<b>c{i}</b>" not in html] == []
    assert "…</td>" not in html


def test_series_and_pandas():
    assert "<b>x</b>" in view3.html(pl.Series("x", [1, 2]))
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"a": [1.5, None], "b": ["p", "q"]})
    html = view3.html(df)
    assert "<b>a</b>" in html and ">1.5<" in html and ">null<" in html
    assert "<b>a</b>" in view3.html(df["a"])


def test_unknown_data_refused():
    with pytest.raises(TypeError, match="can't show a list"):
        view3.html([1, 2])


def test_pages_script_targets_its_table(islands):
    html = view3.html(islands, page_size=5)
    uid = re.search(r"<div id='(view3-[0-9a-f]{32})'", html).group(1)
    assert f'document.getElementById("{uid}")' in html
    assert "data-page-size='5'" in html and "data-label='29 rows'" in html
    assert html.count("<script>") == 1 and html.endswith("</script>")
    assert uid not in view3.html(islands)  # each output pages its own table


def test_pages_off_is_the_scroll_box(islands):
    html = view3.html(islands, pages=False)
    assert "<script" not in html and "data-pager" not in html
    assert "max-height:300px" in html


def test_view_returns_data_unchanged(capsys):
    df = pl.DataFrame({"x": [3, 1, 2], "y": ["a", "b", None]})
    before = df.clone()
    assert view3.view(df) is df
    assert df.equals(before)
    out = capsys.readouterr().out  # text outside a notebook
    assert "shape: (3, 2)" in out and "│ 3" in out


def test_view_text_labels_the_limit(capsys):
    frame = Frame(pl.DataFrame({"x": range(50)}))
    assert view3.view(frame, n=5) is frame
    out = capsys.readouterr().out
    assert out.startswith("Frame (view)\nshape: (50, 1)")
    assert "… first 5 rows (n=5)" in out


def test_arguments_checked():
    with pytest.raises(ValueError):
        view3.html(pl.DataFrame({"x": [1]}), n=-1)
    with pytest.raises(ValueError):
        view3.view(pl.DataFrame({"x": [1]}), page_size=0)
    with pytest.raises(ValueError):
        view3.view(pl.DataFrame({"x": [1]}), height=0)
    with pytest.raises(TypeError):
        view3.view(pl.DataFrame({"x": [1]}), pages="yes")
    for bad in (0, True, 2.5, "all"):
        with pytest.raises(ValueError, match="digits"):
            view3.html(pl.DataFrame({"x": [1.0]}), digits=bad)

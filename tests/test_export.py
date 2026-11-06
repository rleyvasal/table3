"""Export: every row a search, filters and sort keep, the shown columns, any page."""

import io
import os

import polars as pl
import pytest

from table3 import _live
from table3._source import Source

DF = pl.DataFrame({
    "x": [5, 3, None, 1, 4],
    "f": [0.1 + 0.2, float("nan"), float("inf"), 1e-7, 2.0],
    "s": ["a,b", 'say "hi"', "line\nbreak", None, ""],
    "big": [2**60 + 1, 1, 2, 3, 4],
})
STATE = {"filters": {"x": {"from": 2, "to": None}}, "sort": {"column": "x", "desc": True}}


def test_kept_rows_in_order_and_columns():
    kept = Source(DF).kept({**STATE, "columns": ["s", "x"], "offset": 1, "limit": 1})
    assert kept.columns == ["s", "x"]
    assert kept["x"].to_list() == [5, 4, 3]  # every kept row, not the page


def test_csv_keeps_every_digit():
    source = Source(DF)
    csv = source.export({}, "csv").decode()
    assert csv == DF.write_csv()
    assert "0.30000000000000004" in csv and str(2**60 + 1) in csv


def test_parquet_keeps_types_and_values():
    data = Source(DF).export(STATE, "parquet")
    back = pl.read_parquet(io.BytesIO(data))
    want = DF.filter(pl.col("x") >= 2).sort("x", descending=True)
    assert back.schema == DF.schema and back.equals(want, null_equal=True)


def test_bad_format():
    with pytest.raises(ValueError, match="xlsx"):
        Source(DF).export({}, "xlsx")


def test_save_in_a_folder(tmp_path):
    source = Source(DF)
    first = source.save(STATE, "csv", str(tmp_path))
    second = source.save(STATE, "csv", str(tmp_path))
    assert first != second and os.path.dirname(first) == str(tmp_path)
    assert pl.read_csv(first)["x"].to_list() == [5, 4, 3]


def test_the_widget_sends_the_file_or_saves_it(monkeypatch, tmp_path):
    pytest.importorskip("anywidget")
    widget = _live.live_explorer(DF, height=300, digits=None, caption=None, snapshot=None)
    sent = []
    monkeypatch.setattr(widget, "send", lambda msg, buffers=None: sent.append((msg, buffers)))
    widget._answer(widget, {"id": "v:1", **STATE, "columns": ["x"], "export": "csv"}, [])
    msg, buffers = sent[-1]
    assert msg["id"] == "v:1" and msg["download"]["name"].endswith(".csv")
    assert bytes(buffers[0]).decode() == "x\n5\n4\n3\n"
    monkeypatch.chdir(tmp_path)
    widget._answer(widget, {"id": "v:2", "export": "parquet", "save": True}, [])
    msg, buffers = sent[-1]
    assert buffers is None and msg["saved"].startswith(str(tmp_path))
    assert pl.read_parquet(msg["saved"]).height == 5
    monkeypatch.setattr(_live, "MAX_DOWNLOAD", 10)
    widget._answer(widget, {"id": "v:3", "export": "csv"}, [])
    assert "too large" in sent[-1][0]["error"] and sent[-1][1] is None

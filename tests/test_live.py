"""view()'s live mode: when it is chosen, what it displays, and the widget's answers."""

import json
import sys
import re

import polars as pl
import pytest

import table3
from table3 import _live

DF = pl.DataFrame({"x": list(range(500)), "s": [f"v{i % 7}" for i in range(500)]})


@pytest.fixture
def notebook(monkeypatch):
    """A notebook: collect what view() displays, HTML or widget."""
    import IPython
    import IPython.display

    shown = []
    monkeypatch.setattr(IPython, "get_ipython", lambda: object())
    monkeypatch.setattr(IPython.display, "display", lambda obj: shown.append(obj))
    return shown


def test_snapshot_alone_without_a_kernel(notebook):
    table3.view(DF)  # get_ipython() has no kernel: no widget can draw
    assert len(notebook) == 1 and '"live"' not in notebook[0].data
    with pytest.raises(RuntimeError, match="anywidget"):
        table3.view(DF, live=True)
    with pytest.raises(TypeError, match="live"):
        table3.view(DF, live="yes")


def test_not_live_in_solveit(monkeypatch):
    pytest.importorskip("anywidget")
    import IPython

    class Shell:
        kernel = object()
        user_ns = {"__msg_id": "_abc"}

    monkeypatch.setattr(IPython, "get_ipython", lambda: Shell())
    monkeypatch.delenv("RUSTYGATE_KERNEL_ID", raising=False)
    monkeypatch.delitem(sys.modules, "dialoghelper", raising=False)
    assert not _live.available()
    Shell.user_ns = {}
    assert _live.available()
    monkeypatch.setenv("RUSTYGATE_KERNEL_ID", "k1")  # today's SolveIt: no __msg_id
    assert not _live.available()


def test_live_shows_the_snapshot_then_the_widget(notebook, monkeypatch):
    pytest.importorskip("anywidget")
    monkeypatch.setattr(_live, "available", lambda: True)
    table3.view(DF, n=100, hide=False)
    snapshot, widget = notebook
    uid = re.search(r"id='(table3-explore-[0-9a-f]+)'", snapshot.data).group(1)
    block = re.search(r"<script type='application/json'>(.*?)</script>", snapshot.data, re.S).group(1)
    assert json.loads(block)["live"] is True and len(json.loads(block)["rows"]) == 100
    assert widget.meta["snapshot"] == uid
    assert widget.meta["total"] == 500 and widget.meta["first"]["filtered"] == 500
    assert len(widget.meta["first"]["rows"]) == _live.BLOCK
    table3.view(DF, live=False)
    assert len(notebook) == 3  # the snapshot alone


def test_a_lazyframe_is_live_only_when_asked(notebook, monkeypatch):
    pytest.importorskip("anywidget")
    monkeypatch.setattr(_live, "available", lambda: True)
    table3.view(DF.lazy(), hide=False)
    assert len(notebook) == 1  # the snapshot alone: the query isn't run whole
    table3.view(DF.lazy(), live=True, hide=False)
    assert len(notebook) == 3 and notebook[2].meta["total"] == 500


def test_a_package_frame_is_live_only_when_asked(notebook, monkeypatch):
    pytest.importorskip("anywidget")
    monkeypatch.setattr(_live, "available", lambda: True)

    class Frame:  # as tidy3's TidyFrame: a lazy query behind a preview
        def __table3__(self, n):
            return DF.head(n), 500, "Frame"

        def __table3_source__(self):
            return DF.lazy()

    table3.view(Frame(), hide=False)
    assert len(notebook) == 1
    table3.view(Frame(), live=True, hide=False)
    assert len(notebook) == 3 and notebook[2].meta["caption"] == "Frame"


def test_unqueryable_data_stays_a_snapshot(notebook, monkeypatch):
    monkeypatch.setattr(_live, "available", lambda: True)

    class Preview:  # __table3__ only: a preview, no whole data
        def __table3__(self, n):
            return DF.head(n), None, None

    table3.view(Preview())
    assert len(notebook) == 1


def test_the_widget_answers_each_request(monkeypatch):
    pytest.importorskip("anywidget")
    widget = _live.live_explorer(DF, height=300, digits=None, caption="c", snapshot="id")
    sent = []
    monkeypatch.setattr(widget, "send", lambda msg, buffers=None: sent.append(msg))
    widget._answer(widget, {"id": "v:2", "search": "v3", "offset": 0, "limit": 5}, [])
    widget._answer(widget, {"id": "v:1", "sort": {"column": "nope"}}, [])
    assert sent[0]["id"] == "v:2" and sent[0]["filtered"] == 71 and len(sent[0]["rows"]) == 5
    # Ids are the views' own; an earlier one from another view still gets its answer.
    assert sent[1]["id"] == "v:1" and "nope" in sent[1]["error"]
    bundle = widget._repr_mimebundle_()
    data = bundle[0] if isinstance(bundle, tuple) else bundle
    assert data["text/plain"] == "" and "application/vnd.jupyter.widget-view+json" in data

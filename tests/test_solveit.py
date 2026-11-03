"""view() hides its cell from SolveIt's AI, through a stand-in dialoghelper."""

import sys
import types

import polars as pl
import pytest

import table3

DF = pl.DataFrame({"x": range(5)})


class Shell:
    def __init__(self, user_ns):
        self.user_ns = user_ns


@pytest.fixture
def solveit(monkeypatch):
    """A notebook with SolveIt's dialoghelper: records each update_msg call."""
    import IPython
    import IPython.display

    calls, user_ns = [], {"__msg_id": "_abc123"}

    async def update_msg(id=None, **fields):
        calls.append((id, fields))

    core = types.ModuleType("dialoghelper.core")
    core.update_msg = update_msg
    package = types.ModuleType("dialoghelper")
    package.core = core
    monkeypatch.setitem(sys.modules, "dialoghelper", package)
    monkeypatch.setitem(sys.modules, "dialoghelper.core", core)
    monkeypatch.setattr(IPython, "get_ipython", lambda: Shell(user_ns))
    monkeypatch.setattr(IPython.display, "display", lambda obj: None)
    monkeypatch.setattr(table3._solveit, "AUTOHIDE", True)
    return types.SimpleNamespace(calls=calls, user_ns=user_ns, core=core)


def test_view_hides_its_cell(solveit):
    assert table3.view(DF) is DF
    assert solveit.calls == [("_abc123", {"skipped": 1})]


def test_without_an_id_solveit_finds_the_cell(solveit):
    del solveit.user_ns["__msg_id"]
    table3.view(DF)
    assert solveit.calls == [(None, {"skipped": 1})]


def test_a_plain_update_msg_works_too(solveit):
    solveit.core.update_msg = lambda id=None, **fields: solveit.calls.append((id, fields))
    table3.view(DF)
    assert solveit.calls == [("_abc123", {"skipped": 1})]


def test_the_other_id_form_is_tried(solveit):
    async def update_msg(id=None, **fields):
        if id.startswith("_"):
            raise KeyError(id)
        solveit.calls.append((id, fields))

    solveit.core.update_msg = update_msg
    table3.view(DF)
    assert solveit.calls == [("abc123", {"skipped": 1})]


def test_hide_and_autohide(solveit):
    table3.view(DF, hide=False)
    assert solveit.calls == []
    table3.autohide(False)
    try:
        table3.view(DF)
        assert solveit.calls == []
        table3.view(DF, hide=True)
        assert len(solveit.calls) == 1
    finally:
        table3.autohide(True)


def test_show_never_hides(solveit):
    table3.show(DF)
    assert solveit.calls == []


def test_a_failure_is_reported_not_raised(solveit, capsys):
    async def update_msg(id=None, **fields):
        raise ConnectionError("no SolveIt")

    solveit.core.update_msg = update_msg
    assert table3.view(DF) is DF
    assert "could not hide this cell" in capsys.readouterr().out


def test_nothing_outside_solveit(monkeypatch, capsys):
    import IPython
    import IPython.display

    monkeypatch.setitem(sys.modules, "dialoghelper", None)  # import fails
    monkeypatch.setattr(IPython, "get_ipython", lambda: Shell({}))
    monkeypatch.setattr(IPython.display, "display", lambda obj: None)
    assert table3.view(DF) is DF
    assert capsys.readouterr().out == ""


def test_hide_checked():
    with pytest.raises(TypeError, match="hide"):
        table3.view(DF, hide="yes")

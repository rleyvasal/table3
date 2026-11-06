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


def test_a_failure_is_reported_not_raised(solveit, capsys, monkeypatch):
    monkeypatch.setattr(table3._solveit, "_WARNED", False)
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


def test_an_old_dialoghelper_asks_the_gateway(solveit, monkeypatch):
    """dialoghelper 0.2.44 can't find the running cell; SolveIt's gateway can."""
    del solveit.user_ns["__msg_id"]

    async def update_msg(id=None, **fields):
        if not id:
            raise TypeError("update_msg needs either a dict message with and id, or `id=`")
        solveit.calls.append((id, fields))

    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {"cell": "_running"}

    asked = []
    solveit.core.update_msg = update_msg
    solveit.core.dh_settings = {"kid": "k1"}
    solveit.core._gateway_url = lambda: "http://gateway"
    solveit.core.xget = lambda url: asked.append(url) or Reply()
    table3.view(DF)
    assert asked == ["http://gateway/api/kernels/k1/caller"]
    assert solveit.calls == [("_running", {"skipped": 1})]


def test_without_a_way_to_the_cell_it_says_so_once(solveit, capsys, monkeypatch):
    del solveit.user_ns["__msg_id"]
    monkeypatch.setattr(table3._solveit, "_WARNED", False)

    async def update_msg(id=None, **fields):
        raise TypeError("update_msg needs `id=`, a message dict with an id, or a current message")

    solveit.core.update_msg = update_msg
    table3.view(DF)
    table3.view(DF)
    out = capsys.readouterr().out
    assert out.count("could not hide") == 1 and "tell which cell is running" in out


def test_the_running_requests_cell_id_is_tried(solveit, monkeypatch):
    del solveit.user_ns["__msg_id"]

    async def update_msg(id=None, **fields):
        if not id:
            raise TypeError("update_msg needs `id=`")
        solveit.calls.append((id, fields))

    class Kernel:
        def get_parent(self):
            return {"metadata": {"cellId": "_cell9"}}

    solveit.core.update_msg = update_msg
    import IPython

    shell = Shell(solveit.user_ns)
    shell.kernel = Kernel()
    monkeypatch.setattr(IPython, "get_ipython", lambda: shell)
    table3.view(DF)
    assert solveit.calls == [("_cell9", {"skipped": 1})]


def test_solveit_is_known_by_its_kernel_id(monkeypatch):
    import IPython

    monkeypatch.setattr(IPython, "get_ipython", lambda: Shell({}))
    monkeypatch.delenv("RUSTYGATE_KERNEL_ID", raising=False)
    monkeypatch.delitem(sys.modules, "dialoghelper", raising=False)
    assert not table3._solveit.in_solveit()
    monkeypatch.setenv("RUSTYGATE_KERNEL_ID", "k1")
    assert table3._solveit.in_solveit()
    monkeypatch.delenv("RUSTYGATE_KERNEL_ID")
    monkeypatch.setitem(sys.modules, "dialoghelper", object())  # SolveIt loads it at start
    assert table3._solveit.in_solveit()


def test_solveits_own_dialoghelper_reads_the_current_message(solveit):
    """dialoghelper 0.2.41, as SolveIt ships it: update_msg needs an id, and
    read_msg(n=0) gives the running cell's."""
    del solveit.user_ns["__msg_id"]

    async def update_msg(id=None, **fields):
        if not id:
            raise TypeError("update_msg needs either a dict message with and id, or `id=`")
        solveit.calls.append((id, fields))

    async def read_msg(n=-1, relative=True, **kw):
        assert (n, relative) == (0, True)
        return {"id": "_current", "content": "table3.view(DF)"}

    solveit.core.update_msg = update_msg
    solveit.core.read_msg = read_msg
    table3.view(DF)
    assert solveit.calls == [("_current", {"skipped": 1})]

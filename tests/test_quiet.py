"""A cell that ends in view() shows the explorer alone (R's View() returns
invisibly): IPython doesn't print view()'s returned data a second time."""

import polars as pl
import pytest

pytest.importorskip("IPython")

SETUP = """
import polars as pl, pandas as pd, table3
df = pl.DataFrame({"x": [3, 1, 2]})
pdf = pd.DataFrame({"x": [3, 1, 2]})
class Piped:
    # A package's pipe step that calls table3.view() and passes the data on,
    # as tidy3's view() verb does.
    def __rrshift__(self, data):
        return table3.view(data)
"""


@pytest.fixture
def run(capsys):
    from IPython.core.interactiveshell import InteractiveShell

    shell = InteractiveShell.instance()

    def _run(code: str) -> str:
        capsys.readouterr()
        result = shell.run_cell(code)
        assert result.success, result.error_before_exec or result.error_in_exec
        return capsys.readouterr().out

    _run(SETUP)
    yield _run
    # Later tests must not find a running IPython: they'd see a notebook.
    InteractiveShell.clear_instance()


def printed(out: str) -> bool:
    """Whether the cell printed the frame as its value (polars' or pandas' text)."""
    return "shape: (3, 1)" in out or "   x\n0  3" in out


def test_a_cell_ending_in_view_prints_only_the_explorer(run):
    assert printed(run("df"))  # the check sees a printed frame
    assert not printed(run("table3.view(df)"))
    assert not printed(run("table3.view(pdf)"))
    assert not printed(run("df >> Piped()"))
    assert not printed(run("x = 1\ntable3.view(df)"))


def test_view_still_returns_the_data(run):
    assert not printed(run("v = table3.view(df)"))
    assert printed(run("v"))
    assert printed(run("v"))  # quiet only in the cell that viewed it


def test_other_values_in_the_cell_print_as_usual(run):
    assert printed(run("table3.view(df)\ndf"))  # df is its own statement
    assert printed(run("table3.view(df); df"))
    assert "[3, 1, 2]" in run("table3.view(df)['x'].to_list()")
    assert printed(run("table3.view(df).sort('x')"))
    assert printed(run("df"))  # the next cell prints it again


def test_the_notebook_hook_is_restored(run):
    import sys

    before = sys.displayhook
    run("table3.view(df)")
    assert sys.displayhook is before


def test_a_real_kernel_sends_no_result_for_view():
    """In Jupyter (ipykernel), the cell's result message is what draws the
    frame; a cell ending in view() sends display data only."""
    pytest.importorskip("ipykernel")
    manager = pytest.importorskip("jupyter_client.manager")
    km, kc = manager.start_new_kernel(kernel_name="python3")
    try:
        def outputs(code: str) -> list[str]:
            msg_id = kc.execute(code)
            kinds = []
            while True:
                msg = kc.get_iopub_msg(timeout=60)
                if msg["parent_header"].get("msg_id") != msg_id:
                    continue
                kind = msg["msg_type"]
                if kind == "status" and msg["content"]["execution_state"] == "idle":
                    return kinds
                if kind == "error":
                    raise AssertionError("\n".join(msg["content"]["traceback"]))
                if kind in ("execute_result", "display_data", "stream"):
                    kinds.append(kind)

        outputs(SETUP)
        assert outputs("df") == ["execute_result"]
        assert outputs("table3.view(df)") == ["display_data"]
        assert outputs("df >> Piped()") == ["display_data"]
        assert outputs("table3.view(df); df") == ["display_data", "execute_result"]
        assert outputs("df") == ["execute_result"]
    finally:
        kc.stop_channels()
        km.shutdown_kernel(now=True)


def test_outside_ipython_view_returns_the_data(monkeypatch, capsys):
    import IPython

    import table3

    monkeypatch.setattr(IPython, "get_ipython", lambda: None)
    df = pl.DataFrame({"x": [1]})
    assert table3.view(df) is df

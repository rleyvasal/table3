"""The live explorer: the grid as a Jupyter widget whose rows come from the kernel.

``view()`` displays two outputs: the snapshot explorer (``_explore``), then
this widget. Where the widget draws (JupyterLab, Notebook 7, VS Code, with
a running kernel), it hides the snapshot and asks ``_source.Source`` for
each block of rows it scrolls to, so search, filters and sort cover every
row. Where it can't (a saved notebook reopened without its kernel, a viewer
without widgets), the snapshot stays: JupyterLab shows such a widget as
"model not found" rather than any fallback it carries, so the snapshot must
be an output of its own (probed 2026-11-05).

Needs anywidget (``pip install table3[live]``).
"""

from __future__ import annotations

from typing import Any

from table3._explorer_js import WIDGET_ESM
from table3._html import MONO
from table3._source import MAX_DOWNLOAD, Source

BLOCK = 200  # rows per request; the first block goes with the widget


def available() -> bool:
    """Whether a live explorer can be shown here: anywidget, in a Jupyter kernel,
    and not SolveIt (which draws no widgets: docs/explorer.md §2), known by
    its gateway's ``RUSTYGATE_KERNEL_ID`` or an older SolveIt's ``__msg_id``."""
    try:
        import anywidget  # noqa: F401
        from IPython import get_ipython
    except ImportError:
        return False
    shell = get_ipython()
    if shell is None or getattr(shell, "kernel", None) is None:
        return False
    from table3 import _solveit

    return not _solveit.in_solveit()


def _widget_class() -> type:
    import anywidget
    import traitlets

    class LiveExplorer(anywidget.AnyWidget):
        """table3's explorer over every row of its data, a block at a time."""

        _esm = WIDGET_ESM
        meta = traitlets.Dict().tag(sync=True)

        def __init__(self, source: Source, meta: dict) -> None:
            super().__init__(meta=meta)
            self.source = source
            self.on_msg(self._answer)

        def _answer(self, _: Any, content: Any, buffers: Any) -> None:
            if not isinstance(content, dict):
                return
            request = dict(content)
            rid = request.pop("id", None)
            buffers = None
            try:
                if "export" in request:
                    page, buffers = self._export(request)
                else:
                    page = self.source.query(request) or {}
            except Exception as e:  # a bad request: say so in the status line
                page = {"error": str(e)}
            page["id"] = rid
            self.send(page, buffers)

        def _export(self, request: dict) -> tuple[dict, list | None]:
            """Every kept row as a file: saved in the kernel's folder, or its
            bytes sent to the browser to download."""
            fmt = request.pop("export")
            if request.pop("save", False):
                return {"saved": self.source.save(request, fmt)}, None
            data = self.source.export(request, fmt)
            if len(data) > MAX_DOWNLOAD:
                mb = len(data) / 2**20
                return {"error": f"the {fmt} file is {mb:,.0f} MB, too large to download "
                                 "through the notebook; save it in the kernel's folder"}, None
            import datetime as _dt

            name = f"table3-export-{_dt.datetime.now():%Y%m%d-%H%M%S}.{fmt}"
            return {"download": {"name": name, "bytes": len(data)}}, [data]

        def _repr_mimebundle_(self, **kwargs: Any) -> Any:
            # Where widgets don't draw, show nothing here: the snapshot above
            # is the explorer there.
            out = super()._repr_mimebundle_(**kwargs)
            data = out[0] if isinstance(out, tuple) else out
            if isinstance(data, dict):
                data["text/plain"] = ""
            return out

    return LiveExplorer


_CLASS: type | None = None


def live_explorer(
    data: Any, *, height: int, digits: int | str | None, caption: str | None,
    snapshot: str | None,
) -> Any:
    """The widget over every row of *data*; *snapshot* is the id of the
    snapshot explorer it hides when it draws."""
    global _CLASS
    if _CLASS is None:
        _CLASS = _widget_class()
    source = Source(data, digits=digits)
    first = source.query({"offset": 0, "limit": BLOCK, "profile": True})
    meta = {
        "columns": source.columns,
        "layouts": source.layouts,
        "total": source.total,
        "first": first,
        "block": BLOCK,
        "height": height,
        "caption": caption,
        "snapshot": snapshot,
        "font": MONO,
    }
    return _CLASS(source, meta)

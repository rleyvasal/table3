"""Hide the calling cell from SolveIt's AI (its red eye), as plot3 does for plots.

SolveIt sends every cell's code and output to the model. An explorer's rows
(about 1 MB for 10,000) would fill that context, so ``view()`` marks its
cell ``skipped``: SolveIt's "hide from prompt", which hides the cell's code
with its output, as there is no flag for the output alone. Outside SolveIt
(no dialoghelper) nothing happens. dialoghelper's calls are async in some
versions and plain in others, and the cell's id must be resolved while the
cell still runs, so the call completes before ``view()`` returns.

FRAGILE: this leans on dialoghelper internals that change with SolveIt
(docs/explorer.md §8). Finding the running cell has changed three times:
``__msg_id`` in the namespace (gone by 2026-11), ``read_msg(n=0)`` answered
by SolveIt's server (dialoghelper 0.2.41, what SolveIt ships as of
2026-11-05), and ``update_msg`` without an id through the gateway
(dialoghelper 0.2.45+, which needs ``RUSTYGATE_KERNEL_ID``, not set by that
SolveIt). ``_hide`` tries each; when SolveIt updates, check which still works.
"""

from __future__ import annotations

import inspect
import os
import sys
from typing import Any

AUTOHIDE = True
_WARNED = False  # a failure to hide is reported once a session


def autohide(on: bool = True) -> None:
    """Whether ``view()`` hides its cell from SolveIt's AI when *hide* isn't given."""
    global AUTOHIDE
    AUTOHIDE = bool(on)


def _msg_id() -> str | None:
    """The running cell's id where SolveIt puts it (``__msg_id``), or None."""
    frame = inspect.currentframe()
    try:
        f = frame.f_back if frame is not None else None
        while f is not None:
            for ns in (f.f_locals, f.f_globals):
                mid = ns.get("__msg_id") if isinstance(ns, dict) else None
                if mid:
                    return str(mid)
            f = f.f_back
    finally:
        del frame
    try:
        from IPython import get_ipython

        ns = getattr(get_ipython(), "user_ns", None) or {}
        mid = ns.get("__msg_id")
        return str(mid) if mid else None
    except Exception:
        return None


def in_solveit() -> bool:
    """Whether this kernel runs in SolveIt, which loads dialoghelper into every
    kernel as it starts; its gateway also names each kernel
    (``RUSTYGATE_KERNEL_ID``), and older SolveIt put ``__msg_id`` in the namespace."""
    return ("dialoghelper" in sys.modules or bool(os.environ.get("RUSTYGATE_KERNEL_ID"))
            or _msg_id() is not None)


async def _current_msg() -> str | None:
    """The running cell's id as SolveIt's server reports it: the message at
    offset 0 from the current one (dialoghelper's ``read_msg``), as plot3
    asks; SolveIt's own dialoghelper (0.2.41) has no other way."""
    try:
        from dialoghelper.core import read_msg

        msg = read_msg(n=0, relative=True)
        if inspect.iscoroutine(msg):
            msg = await msg
        mid = msg.get("id") if isinstance(msg, dict) else getattr(msg, "id", None)
        return str(mid) if mid else None
    except Exception:
        return None


def _parent_cell_id() -> str | None:
    """The cell id a frontend sends with the request that runs the cell
    (``metadata.cellId``, as JupyterLab and VS Code send it), if any."""
    try:
        from IPython import get_ipython

        meta = get_ipython().kernel.get_parent().get("metadata") or {}
    except Exception:
        return None
    for key in ("cellId", "cell_id", "msg_id", "msgId"):
        if meta.get(key):
            return str(meta[key])
    return None


def _gateway_caller() -> str | None:
    """The running cell's id from SolveIt's gateway, for a dialoghelper that
    can't find it itself (0.2.44 and before, once ``__msg_id`` was gone)."""
    try:
        from dialoghelper import core

        kid = core.dh_settings.get("kid")
        if not kid:
            return None
        res = core.xget(f"{core._gateway_url()}/api/kernels/{kid}/caller")
        res.raise_for_status()
        cell = res.json().get("cell")
        return str(cell) if cell else None
    except Exception:
        return None


async def _hide(update_msg: Any, mid: str | None) -> None:
    # Without an id, update_msg asks SolveIt for the running cell itself
    # (dialoghelper 0.2.45 and later); before that, the gateway is asked here.
    candidates = [mid, mid[1:] if mid.startswith("_") else "_" + mid] if mid else [None]
    error = None
    for cand in candidates:
        try:
            result = update_msg(id=cand, skipped=1) if cand else update_msg(skipped=1)
            if inspect.iscoroutine(result):
                await result
            return
        except Exception as e:  # a version that wants the other id form
            error = e
    if not mid:
        for found in (_current_msg, _parent_cell_id, _gateway_caller):
            cell = found()
            if inspect.iscoroutine(cell):
                cell = await cell
            if not cell:
                continue
            try:
                result = update_msg(id=cell, skipped=1)
                if inspect.iscoroutine(result):
                    await result
                return
            except Exception as e:
                error = e
    raise RuntimeError(error)


def _advice(error: Exception) -> str:
    """*error* in words: one that wants an id means no way to the running cell was found."""
    if "id" not in str(error):
        return f"({error})"
    return "(no way found to tell which cell is running)"


def hide_calling_cell() -> None:
    """Mark the running SolveIt cell hidden from the AI; a no-op elsewhere."""
    try:
        from dialoghelper.core import update_msg
    except Exception:
        return
    coro = _hide(update_msg, _msg_id())
    try:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is None:
            asyncio.run(coro)
            return
        try:
            import nest_asyncio

            nest_asyncio.apply()
            loop.run_until_complete(coro)
        except ImportError:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, coro).result()
    except Exception as e:
        global _WARNED
        if not _WARNED:
            _WARNED = True
            print(f"table3: could not hide this cell from SolveIt's AI {_advice(e)}; "
                  "view(hide=False) or table3.autohide(False) skips trying "
                  "(said once a session)")

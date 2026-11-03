"""Hide the calling cell from SolveIt's AI (its red eye), as plot3 does for plots.

SolveIt sends every cell's code and output to the model. An explorer's rows
(about 1 MB for 10,000) would fill that context, so ``view()`` marks its
cell ``skipped``: SolveIt's "hide from prompt", which hides the cell's code
with its output, as there is no flag for the output alone. Outside SolveIt
(no dialoghelper) nothing happens. dialoghelper's calls are async in some
versions and plain in others, and the cell's id must be resolved while the
cell still runs, so the call completes before ``view()`` returns.
"""

from __future__ import annotations

import inspect
from typing import Any

AUTOHIDE = True


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


async def _hide(update_msg: Any, mid: str | None) -> None:
    # Without an id, update_msg asks SolveIt for the running cell itself.
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
    raise RuntimeError(error)


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
        print(f"table3: could not hide this cell from SolveIt's AI ({e}); "
              "view(hide=False) or table3.autohide(False) skips trying")

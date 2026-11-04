"""Keep a notebook from printing what ``view()`` returned, as R's ``View()``
returns invisibly.

``view()`` displays the explorer and returns its data, so a cell ending in
``view(df)`` or ``df >> view()`` would print the data again under the
explorer. IPython prints a cell's last expression through
``sys.displayhook``, called from that expression's own frame. ``view()``
notes the frames it was called from and wraps the hook until the cell
ends: a value that is *data* itself, printed from one of those frames, is
not printed. Anything else prints as usual: ``view(df); df`` (``df`` is a
statement of its own, so another frame), ``df >> view() >> arrange("x")``
(another object), and *data* in any later cell. Outside IPython nothing
changes.
"""

from __future__ import annotations

import sys
from typing import Any


def return_quietly(data: Any) -> None:
    """Don't let the running cell print *data* as the value of this call."""
    try:
        from IPython import get_ipython

        shell = get_ipython()
        events = shell.events
    except Exception:  # not in IPython: no notebook to print it
        return
    frames = set()
    f = sys._getframe(1)
    while f is not None:
        frames.add(id(f))
        f = f.f_back
    inner = sys.displayhook

    def hook(value: Any) -> None:
        if value is data and id(sys._getframe(1)) in frames:
            return
        inner(value)

    def cell_done(*_: Any) -> None:
        events.unregister("post_run_cell", cell_done)
        if sys.displayhook is hook:
            sys.displayhook = inner

    sys.displayhook = hook
    events.register("post_run_cell", cell_done)

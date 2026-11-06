"""Scrollbars that show before the first scroll, for the paged table and the explorer.

macOS (and some Linux desktops) draw overlay scrollbars that stay hidden
until a scroll, so a mouse user doesn't see that a wide table goes on, or
where to drag. Blink and WebKit (VS Code, Chrome, Edge, Safari, SolveIt in
them) always draw a scrollbar styled through ``::-webkit-scrollbar``. Inline
styles can't reach that pseudo-element and CRAFT drops ``<style>`` blocks
from output HTML, so the table's script adds one ``<style>`` to the page as
it runs, for elements it marks ``data-t3-scroll``. Elsewhere (Firefox) the
thin standard scrollbar stays. Blink ignores ``::-webkit-scrollbar`` on an
element that sets ``scrollbar-color`` or ``scrollbar-width``, so those are
cleared on it; a click no longer rings the table, the keyboard's focus does.
"""

SCROLLBARS_JS = r"""
function table3Scrollbars(e) {
  var d = e.ownerDocument || document, c = d.defaultView && d.defaultView.CSS;
  if (!(c && c.supports && c.supports("selector(::-webkit-scrollbar)"))) return;
  e.setAttribute("data-t3-scroll", "");
  e.style.scrollbarColor = e.style.scrollbarWidth = "";
  if (d.getElementById("table3-scrollbars")) return;
  var s = d.createElement("style"), S = "[data-t3-scroll]";
  s.id = "table3-scrollbars";
  s.textContent = S + "::-webkit-scrollbar{width:10px;height:10px}" +
    S + "::-webkit-scrollbar-track{background:#7f7f7f1f;border-radius:5px}" +
    S + "::-webkit-scrollbar-thumb{background:#7f7f7f80;border-radius:5px}" +
    S + "::-webkit-scrollbar-corner{background:none}" +
    S + ":focus{outline:0}" + S + ":focus-visible{outline:1px solid #7f7f7f99}";
  (d.head || d.documentElement).appendChild(s);
}
"""

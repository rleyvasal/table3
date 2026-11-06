"""The script that pages a table3 table in place."""

# Column widths are measured once over all rows and pinned on the header, so
# every column keeps its width whichever row page is shown; blank rows pad a
# short last page, so the pager at the right of the footer never moves. A
# table wider than its cell scrolls sideways, as marimo's and Data Wrangler's
# do: a thin scrollbar under it, a shadow at an edge with more columns past
# it, and the footer naming the columns in view ("Columns 4–9 of 24"). The
# rows past the first page arrive as JSON and are drawn into the table
# first. __ID__ is the table's root element.
from table3._scrollbars import SCROLLBARS_JS

PAGER_JS = """
(function () {
""" + SCROLLBARS_JS + """
  var root = document.getElementById("__ID__");
  if (!root || root.dataset.paged) return;
  root.dataset.paged = "1";
  var box = root.querySelector("[data-box]");
  var table = box.querySelector("table");
  var head = [].slice.call(table.tHead.rows);
  // Only the first page is written as cells; the rest come as JSON text,
  // drawn here with the first page's cell styles, one per column, so text
  // stays left and numbers right ("null", cut at 40 as there).
  var tb0 = table.tBodies[0];
  var styles = tb0.rows[0] ? [].map.call(tb0.rows[0].cells, function (td) {
    return td.getAttribute("style");
  }) : [];
  var json = root.querySelector("script[type='application/json']");
  if (json) {
    var tb = tb0;
    var esc = function (t) {
      return t.replace(/[&<>"']/g, function (ch) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;" }[ch];
      });
    };
    var cells = "";
    JSON.parse(json.textContent).forEach(function (row) {
      cells += "<tr>";
      row.forEach(function (v, j) {
        var t = v === null ? "null" : v, cut = t.length > 40;
        cells += "<td style='" + styles[j] + "'" + (cut ? " title='" + esc(t) + "'" : "") + ">" +
          esc(cut ? t.slice(0, 39) + "…" : t) + "</td>";
      });
      cells += "</tr>";
    });
    tb.innerHTML = cells;
  }
  var body = [].slice.call(table.tBodies[0].rows);
  var foot = root.querySelector("[data-foot]");
  var pager = root.querySelector("[data-pager]");
  var size = +root.dataset.pageSize;
  var total = root.dataset.total === "" ? null : +root.dataset.total;
  var npages = Math.max(1, Math.ceil(body.length / size));
  // Every row is in the table now, so each column is as wide as its widest
  // value, name or type; pin it there, or hiding rows would narrow it.
  var widths = [].map.call(head[0].cells, function (c) {
    return Math.ceil(c.getBoundingClientRect().width);
  });
  [].forEach.call(head[0].cells, function (c, j) {
    c.style.boxSizing = "border-box";
    c.style.width = c.style.minWidth = widths[j] + "px";
  });
  // Blank rows fill a short last page, so the pager stays where it was.
  var pad = [], tb = table.tBodies[0];
  for (var k = 0; npages > 1 && k < size - 1; k++) {
    var tr = document.createElement("tr");
    tr.setAttribute("aria-hidden", "true");
    tr.dataset.pad = "1";
    widths.forEach(function (_, j) {
      var td = document.createElement("td");
      td.setAttribute("style", styles[j] || "");
      td.textContent = " ";
      tr.appendChild(td);
    });
    tb.appendChild(tr);
    pad.push(tr);
  }
  var page = 0;
  var BTN = "font:inherit;color:inherit;background:none;cursor:pointer;flex:none;" +
    "box-sizing:border-box;border:1px solid transparent;border-radius:4px;" +
    "padding:1px 7px;margin:0 1px";

  // Sideways scrolling: the box scrolls, a frame round it holds a shadow at
  // each edge that has columns past it, and the footer names those in view.
  var frame = document.createElement("div");
  frame.style.cssText = "position:relative;min-width:0";
  box.parentNode.insertBefore(frame, box);
  frame.appendChild(box);
  box.style.overflowX = "auto";
  box.style.scrollbarWidth = "thin";
  table3Scrollbars(box);  // shown before the first scroll
  function shade(side) {
    var s = document.createElement("div");
    s.dataset.shade = side;
    s.setAttribute("aria-hidden", "true");
    s.style.cssText = "position:absolute;top:0;bottom:0;width:18px;pointer-events:none;" +
      "transition:opacity .15s;opacity:0;" + side + ":0;background:linear-gradient(to " +
      (side === "left" ? "right" : "left") + ",rgba(127,127,127,.35),rgba(127,127,127,0))";
    frame.appendChild(s);
    return s;
  }
  var shadeLeft = shade("left"), shadeRight = shade("right");
  var lefts = [], acc = 0;
  widths.forEach(function (x) { lefts.push(acc); acc += x; });

  // The columns at least half in view, as "Columns 4–9 of 24".
  function columnsText() {
    var n = widths.length;
    if (box.scrollWidth <= box.clientWidth + 1) return n + (n === 1 ? " column" : " columns");
    var lo = box.scrollLeft, hi = lo + box.clientWidth, a = -1, z = -1;
    widths.forEach(function (x, j) {
      var seen = Math.min(hi, lefts[j] + x) - Math.max(lo, lefts[j]);
      if (seen >= Math.min(x, box.clientWidth) / 2) { if (a < 0) a = j; z = j; }
    });
    if (a < 0) { a = z = 0; }
    return a === z ? "Column " + (a + 1) + " of " + n
      : "Columns " + (a + 1) + "–" + (z + 1) + " of " + n;
  }
  function edges() {
    var wide = box.scrollWidth > box.clientWidth + 1;
    shadeLeft.style.opacity = wide && box.scrollLeft > 1 ? "1" : "0";
    shadeRight.style.opacity =
      wide && box.scrollLeft + box.clientWidth < box.scrollWidth - 1 ? "1" : "0";
    // A wide table takes keyboard focus, so arrow keys scroll it too.
    if (wide) { box.tabIndex = 0; box.setAttribute("aria-label", "Table: scroll sideways for more columns"); }
    else { box.removeAttribute("tabindex"); box.removeAttribute("aria-label"); }
  }

  // The controls are made once and only restyled, so a focused button keeps
  // focus. A button that can't act is aria-disabled, not disabled: it stays
  // in place, visible and focused, and its click does nothing.
  function button(parent, text, go) {
    var b = document.createElement("button");
    b.type = "button"; b.textContent = text; b.style.cssText = BTN;
    b.onclick = function () { if (b.getAttribute("aria-disabled") !== "true") go(b); };
    parent.appendChild(b);
    return b;
  }

  function state(b, on, current) {
    b.setAttribute("aria-disabled", on ? "false" : "true");
    b.style.opacity = on ? "" : ".35";
    b.style.cursor = on ? "pointer" : "default";
    b.style.borderColor = current ? "rgba(127,127,127,.6)" : "transparent";
    if (current) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }

  // Seven slots once there are more than seven pages: the first and last
  // page, the current one with its neighbours, and "…" for each run left
  // out. Near either end the slots fill with pages instead, so their count,
  // and every slot's width, stays the same on every page.
  function slotPages(n, cur) {
    var all = function (a, b) { var r = []; for (var i = a; i <= b; i++) r.push(i); return r; };
    if (n <= 7) return all(0, n - 1);
    if (cur <= 3) return all(0, 4).concat([-1, n - 1]);
    if (cur >= n - 4) return [0, -1].concat(all(n - 5, n - 1));
    return [0, -1, cur - 1, cur, cur + 1, -1, n - 1];
  }

  pager.style.alignItems = "center";
  pager.style.whiteSpace = "nowrap";
  var prev = button(pager, "Previous", function () { page--; render(); });
  var nums = document.createElement("span");
  nums.style.cssText = "display:flex;flex:none";
  pager.appendChild(nums);
  var slotWidth = "calc(" + String(npages).length + "ch + 16px)";
  var slots = slotPages(npages, 0).map(function () {
    var b = button(nums, "", function (b) { page = +b.dataset.page; render(); });
    b.style.width = slotWidth; b.style.textAlign = "center";
    b.style.paddingLeft = b.style.paddingRight = "0";
    return b;
  });
  var next = button(pager, "Next", function () { page++; render(); });

  // "Rows 11–20 of 344", and when n cut the rows, what was previewed of how
  // many: "Rows 11–20 of 1,000 previewed (52,341 total)".
  function count(k) { return k.toLocaleString("en-US"); }
  function rowsText(lo, hi) {
    var n = body.length;
    var text = n > size ? "Rows " + count(lo + 1) + "–" + count(hi) + " of " + count(n)
      : count(n) + (n === 1 ? " row" : " rows");
    if (total === null) return text + " previewed (total not counted)";
    if (total > n) return text + " previewed (" + count(total) + " total)";
    return text;
  }

  function render() {
    page = Math.min(page, npages - 1);
    var lo = page * size, hi = Math.min(lo + size, body.length);
    body.forEach(function (tr, i) {
      var on = i >= lo && i < hi;
      tr.style.display = on ? "" : "none";
      if (on) tr.style.background = (i - lo) % 2 ? "rgba(127,127,127,.08)" : "";
    });
    var blanks = npages > 1 ? size - (hi - lo) : 0;
    pad.forEach(function (tr, k) { tr.style.display = k < blanks ? "" : "none"; });
    rowsShown = rowsText(lo, hi);
    footer();

    var paged = npages > 1;
    [prev, nums, next].forEach(function (el) { el.style.display = paged ? "" : "none"; });
    nums.style.display = paged ? "flex" : "none";
    state(prev, page > 0);
    state(next, page < npages - 1);
    slotPages(npages, page).forEach(function (p, i) {
      var b = slots[i];
      if (p < 0) {
        b.textContent = "…"; b.tabIndex = -1; b.setAttribute("aria-hidden", "true");
        state(b, false); b.style.opacity = ".55";
      } else {
        b.textContent = String(p + 1); b.dataset.page = p;
        b.removeAttribute("tabindex"); b.removeAttribute("aria-hidden");
        state(b, p !== page, p === page);
      }
    });
    pager.style.display = paged ? "flex" : "none";
  }

  var rowsShown = "";
  function footer() {
    foot.textContent = rowsShown + " | " + columnsText();
    edges();
  }

  box.style.maxHeight = "none";
  render();
  var pending = false;
  box.addEventListener("scroll", function () {
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () { pending = false; footer(); });
  });
  if (window.ResizeObserver) new ResizeObserver(footer).observe(box);
})();
"""

# Every paged table carries this script, so its comment-only lines stay here.
PAGER_JS = "\n".join(line for line in PAGER_JS.splitlines() if not line.lstrip().startswith("//"))

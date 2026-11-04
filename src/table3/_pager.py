"""The script that pages a table3 table in place."""

# Column widths are measured once over all rows and pinned on the header, so
# a column page keeps its columns, and every column its width, whichever row
# page is shown; blank rows pad a short last page, and the page links fill a
# fixed number of fixed-width slots, so Next stays put from page to page. The rows past the first page arrive as
# JSON and are drawn into the table first. __ID__ is the table's root element.
PAGER_JS = """
(function () {
  var root = document.getElementById("__ID__");
  if (!root || root.dataset.paged) return;
  root.dataset.paged = "1";
  var box = root.querySelector("[data-box]");
  var table = box.querySelector("table");
  var head = [].slice.call(table.tHead.rows);
  // Only the first page is written as cells; the rest come as JSON text,
  // drawn here with the first page's cell style ("null", cut at 40 as there).
  var json = root.querySelector("script[type='application/json']");
  if (json) {
    var tb = table.tBodies[0], first = tb.rows[0] && tb.rows[0].cells[0];
    var style = first ? first.getAttribute("style") : "";
    var esc = function (t) {
      return t.replace(/[&<>"']/g, function (ch) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;" }[ch];
      });
    };
    var cells = "";
    JSON.parse(json.textContent).forEach(function (row) {
      cells += "<tr>";
      row.forEach(function (v) {
        var t = v === null ? "null" : v, cut = t.length > 40;
        cells += "<td style='" + style + "'" + (cut ? " title='" + esc(t) + "'" : "") + ">" +
          esc(cut ? t.slice(0, 39) + "…" : t) + "</td>";
      });
      cells += "</tr>";
    });
    tb.innerHTML = cells;
  }
  var body = [].slice.call(table.tBodies[0].rows);
  var foot = root.querySelector("[data-foot]");
  var pager = root.querySelector("[data-pager]");
  var size = +root.dataset.pageSize, label = root.dataset.label;
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
  var padStyle = body[0] && body[0].cells[0] ? body[0].cells[0].getAttribute("style") : "";
  for (var k = 0; npages > 1 && k < size - 1; k++) {
    var tr = document.createElement("tr");
    tr.setAttribute("aria-hidden", "true");
    tr.dataset.pad = "1";
    widths.forEach(function () {
      var td = document.createElement("td");
      td.setAttribute("style", padStyle);
      td.textContent = " ";
      tr.appendChild(td);
    });
    tb.appendChild(tr);
    pad.push(tr);
  }
  var page = 0, cpage = 0, groups = [], seenWidth = -1;
  var BTN = "font:inherit;color:inherit;background:none;cursor:pointer;flex:none;" +
    "box-sizing:border-box;border:1px solid transparent;border-radius:4px;" +
    "padding:1px 7px;margin:0 1px";

  function group() {
    var avail = box.clientWidth || Infinity, cur = [], w = 0;
    seenWidth = box.clientWidth;
    groups = [];
    widths.forEach(function (x, j) {
      if (cur.length && w + x > avail) { groups.push(cur); cur = []; w = 0; }
      cur.push(j); w += x;
    });
    groups.push(cur);
    cpage = Math.min(cpage, groups.length - 1);
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

  function span(parent, text) {
    var s = document.createElement("span");
    s.textContent = text; s.style.cssText = "opacity:.55;padding:0 4px;flex:none";
    parent.appendChild(s);
    return s;
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
  var colPrev = button(pager, "◂ columns", function () { cpage--; render(); });
  var colNext = button(pager, "columns ▸", function () { cpage++; render(); });
  var colSep = span(pager, "|");
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

  function render() {
    page = Math.min(page, npages - 1);
    var lo = page * size, hi = Math.min(lo + size, body.length);
    var cols = groups[cpage], keep = {};
    cols.forEach(function (j) { keep[j] = 1; });
    body.forEach(function (tr, i) {
      var on = i >= lo && i < hi;
      tr.style.display = on ? "" : "none";
      if (on) tr.style.background = (i - lo) % 2 ? "rgba(127,127,127,.08)" : "";
    });
    var blanks = npages > 1 ? size - (hi - lo) : 0;
    pad.forEach(function (tr, k) { tr.style.display = k < blanks ? "" : "none"; });
    head.concat(body.slice(lo, hi), pad.slice(0, blanks)).forEach(function (tr) {
      [].forEach.call(tr.cells, function (td, j) { td.style.display = keep[j] ? "" : "none"; });
    });

    var text = body.length > size ? (lo + 1) + "–" + hi + " of " + label : label;
    if (groups.length > 1)
      text += " | " + (cols[0] + 1) + "–" + (cols[cols.length - 1] + 1) +
        " of " + widths.length + " columns";
    foot.textContent = text;

    var wide = groups.length > 1, paged = npages > 1;
    colPrev.style.display = colNext.style.display = wide ? "" : "none";
    colSep.style.display = wide && paged ? "" : "none";
    state(colPrev, cpage > 0);
    state(colNext, cpage < groups.length - 1);
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
    pager.style.display = wide || paged ? "flex" : "none";
  }

  group();
  box.style.maxHeight = "none";
  render();
  if (window.ResizeObserver)
    new ResizeObserver(function () {
      if (box.clientWidth !== seenWidth) { group(); render(); }
    }).observe(box);
})();
"""

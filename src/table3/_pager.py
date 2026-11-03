"""The script that pages a table3 table in place."""

# Column widths are measured once over all rows, so a column page keeps its
# columns whichever row page is shown. The rows past the first page arrive as
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
  var widths = [].map.call(head[0].cells, function (c) { return c.offsetWidth; });
  var page = 0, cpage = 0, groups = [], seenWidth = -1;
  var BTN = "font:inherit;color:inherit;background:none;cursor:pointer;" +
    "border:1px solid transparent;border-radius:4px;padding:1px 7px;margin:0 1px";

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

  function button(text, on, go, current) {
    var b = document.createElement("button");
    b.type = "button"; b.textContent = text; b.style.cssText = BTN;
    if (current) b.style.borderColor = "rgba(127,127,127,.6)";
    if (!on) { b.disabled = true; b.style.opacity = ".35"; b.style.cursor = "default"; }
    else b.onclick = go;
    pager.appendChild(b);
  }

  function gap(text) {
    var s = document.createElement("span");
    s.textContent = text || "…"; s.style.cssText = "opacity:.55;padding:0 4px";
    pager.appendChild(s);
  }

  function pageList(n, cur) {
    if (n <= 7) return Array.from({ length: n }, function (_, i) { return i; });
    var keep = [0, n - 1, cur - 1, cur, cur + 1].filter(function (i) {
      return i >= 0 && i < n;
    });
    return keep.filter(function (v, i) { return keep.indexOf(v) === i; })
      .sort(function (a, b) { return a - b; });
  }

  function render() {
    var npages = Math.max(1, Math.ceil(body.length / size));
    page = Math.min(page, npages - 1);
    var lo = page * size, hi = Math.min(lo + size, body.length);
    var cols = groups[cpage], keep = {};
    cols.forEach(function (j) { keep[j] = 1; });
    body.forEach(function (tr, i) {
      var on = i >= lo && i < hi;
      tr.style.display = on ? "" : "none";
      if (on) tr.style.background = (i - lo) % 2 ? "rgba(127,127,127,.08)" : "";
    });
    head.concat(body.slice(lo, hi)).forEach(function (tr) {
      [].forEach.call(tr.cells, function (td, j) { td.style.display = keep[j] ? "" : "none"; });
    });

    var text = body.length > size ? (lo + 1) + "–" + hi + " of " + label : label;
    if (groups.length > 1)
      text += " | " + (cols[0] + 1) + "–" + (cols[cols.length - 1] + 1) +
        " of " + widths.length + " columns";
    foot.textContent = text;

    pager.textContent = "";
    if (groups.length > 1) {
      button("◂ columns", cpage > 0, function () { cpage--; render(); });
      button("columns ▸", cpage < groups.length - 1, function () { cpage++; render(); });
      if (npages > 1) gap("|");
    }
    if (npages > 1) {
      button("Previous", page > 0, function () { page--; render(); });
      var last = -1;
      pageList(npages, page).forEach(function (p) {
        if (p > last + 1) gap();
        button(String(p + 1), p !== page, function () { page = p; render(); }, p === page);
        last = p;
      });
      button("Next", page < npages - 1, function () { page++; render(); });
    }
    pager.style.display = pager.childNodes.length ? "" : "none";
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

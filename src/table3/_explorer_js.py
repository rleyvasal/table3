"""The script that turns a table3 explorer's JSON into a grid (docs/explorer.md §4).

Every style is set inline by the script: CRAFT's republish drops <style>
blocks. Only the rows in view are drawn, between two spacer rows, so 10,000
rows scroll as fast as ten. Sorts and filters read the raw values; the grid
shows the display text. __ID__ is the explorer's root element.
"""

EXPLORER_JS = r"""
(function () {
  var root = document.getElementById("__ID__");
  if (!root || root.dataset.explorer) return;
  root.dataset.explorer = "1";
  var data = JSON.parse(root.querySelector("script[type='application/json']").textContent);
  var fallback = root.querySelector("[data-fallback]");
  if (fallback) fallback.style.display = "none";

  var cols = data.columns, rows = data.rows, ncol = cols.length;
  var ROW = 22, BUFFER = 10, CUT = 40;
  var GREY = "rgba(127,127,127,.45)";
  var SOLID = "background-color:var(--vscode-editor-background,var(--jp-layout-color0,Canvas));" +
    "background-image:linear-gradient(hsl(var(--card)),hsl(var(--card)))";
  var NUMERIC = { number: 1, date: 1 };

  // Display text, and its lowercase for search, once per cell.
  var text = [], lower = [];
  rows.forEach(function (row, r) {
    var t = [], l = [];
    for (var c = 0; c < ncol; c++) {
      var shown = data.shown[c] && data.shown[c][r];
      var v = row[c];
      var s = shown != null ? shown : v === null ? "null" : String(v);
      t.push(s); l.push(s.toLowerCase());
    }
    text.push(t); lower.push(l);
  });

  function esc(s) {
    return s.replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  // Column widths in characters, from the widest text up to the cut.
  var widths = cols.map(function (col, c) {
    // Numbers and dates need room for their two filter boxes, from and to.
    var w = Math.max(col.name.length + 2, col.type.length, NUMERIC[col.kind] ? 12 : 6);
    for (var r = 0; r < rows.length && w < CUT; r++) w = Math.max(w, text[r][c].length);
    return Math.min(w, CUT);
  });
  var numWidth = String(rows.length).length;

  function cellStyle(c) {
    return "box-sizing:border-box;width:calc(" + widths[c] + "ch + 20px);" +
      "max-width:calc(" + widths[c] + "ch + 20px);padding:0 10px;height:" + ROW + "px;" +
      "line-height:" + ROW + "px;white-space:pre;overflow:hidden;border:0;" +
      "text-align:" + (NUMERIC[cols[c].kind] ? "right" : "left");
  }
  var NUM_STYLE = "box-sizing:border-box;width:calc(" + numWidth + "ch + 20px);padding:0 10px;" +
    "height:" + ROW + "px;line-height:" + ROW + "px;text-align:right;opacity:.55;border:0;" +
    "position:sticky;left:0;z-index:1;" + SOLID;

  // Toolbar: search and the status line.
  var bar = document.createElement("div");
  bar.style.cssText = "display:flex;gap:12px;align-items:center;margin:0 0 4px 0;flex-wrap:wrap";
  var search = document.createElement("input");
  search.type = "search"; search.placeholder = "Search";
  var INPUT = "font:inherit;color:inherit;background:transparent;border:1px solid " + GREY +
    ";border-radius:4px;padding:1px 6px;box-sizing:border-box";
  search.style.cssText = INPUT + ";width:16em";
  var status = document.createElement("span");
  status.dataset.status = "";
  status.style.cssText = "opacity:.65";
  bar.appendChild(search); bar.appendChild(status);
  root.appendChild(bar);

  var box = document.createElement("div");
  box.dataset.grid = "";
  box.style.cssText = "max-height:" + root.dataset.height + "px;overflow:auto;" +
    "scrollbar-color:rgba(127,127,127,.5) transparent;border-top:1px solid " + GREY;
  var table = document.createElement("table");
  table.style.cssText = "border-collapse:separate;border-spacing:0;table-layout:fixed;font:inherit";
  var thead = document.createElement("thead");
  thead.style.cssText = "position:sticky;top:0;z-index:2;" + SOLID;
  var tbody = document.createElement("tbody");
  table.appendChild(thead); table.appendChild(tbody);
  box.appendChild(table); root.appendChild(box);

  // State: one sort column, a filter per column, the search text.
  var sortCol = -1, sortDir = 0, filters = cols.map(function () { return null; });
  var order = [], query = "";

  // Header: names with sort arrows, types, filters.
  var nameRow = document.createElement("tr"), typeRow = document.createElement("tr"),
    filterRow = document.createElement("tr");
  function corner(tr, html) {
    var td = document.createElement("td");
    td.style.cssText = NUM_STYLE + ";z-index:3";
    td.innerHTML = html;
    tr.appendChild(td);
  }
  corner(nameRow, ""); corner(typeRow, ""); corner(filterRow, "");
  var arrows = [];
  cols.forEach(function (col, c) {
    var td = document.createElement("td");
    td.style.cssText = cellStyle(c) + ";cursor:pointer;user-select:none";
    td.title = "Sort by " + col.name;
    var arrow = document.createElement("span");
    arrow.style.cssText = "opacity:.55";
    var name = document.createElement("b");
    name.textContent = col.name;
    if (NUMERIC[col.kind]) { td.appendChild(arrow); td.appendChild(name); }
    else { td.appendChild(name); td.appendChild(arrow); }
    td.onclick = function () {
      if (sortCol !== c) { sortCol = c; sortDir = 1; }
      else if (sortDir === 1) sortDir = -1;
      else { sortCol = -1; sortDir = 0; }
      apply();
    };
    arrows.push(arrow);
    nameRow.appendChild(td);

    var ttd = document.createElement("td");
    ttd.style.cssText = cellStyle(c) + ";opacity:.55";
    ttd.textContent = col.type;
    typeRow.appendChild(ttd);

    var ftd = document.createElement("td");
    ftd.style.cssText = cellStyle(c) + ";height:auto;padding:2px 4px 4px 4px;border-bottom:1px solid " + GREY;
    ftd.appendChild(filterControl(col, c));
    filterRow.appendChild(ftd);
  });
  thead.appendChild(nameRow); thead.appendChild(typeRow); thead.appendChild(filterRow);

  function filterControl(col, c) {
    var timer = null;
    function later(fn) { clearTimeout(timer); timer = setTimeout(fn, 150); }
    if (col.kind === "choice" || col.kind === "bool") {
      var sel = document.createElement("select");
      sel.style.cssText = INPUT + ";width:100%;" + SOLID;
      var values = col.kind === "bool" ? [true, false] : col.choices;
      var opts = [["", "All"]].concat(values.map(function (v, i) { return ["v" + i, String(v)]; }))
        .concat([["null", "null"]]);
      opts.forEach(function (o) {
        var op = document.createElement("option");
        op.value = o[0]; op.textContent = o[1];
        sel.appendChild(op);
      });
      sel.onchange = function () {
        var v = sel.value;
        filters[c] = v === "" ? null : v === "null" ? { is: null } : { is: values[+v.slice(1)] };
        apply();
      };
      return sel;
    }
    if (NUMERIC[col.kind]) {
      var wrap = document.createElement("div");
      wrap.style.cssText = "display:flex;gap:2px";
      var lo = document.createElement("input"), hi = document.createElement("input");
      [lo, hi].forEach(function (inp, i) {
        inp.placeholder = i ? "to" : "from";
        inp.style.cssText = INPUT + ";width:50%;min-width:0";
        inp.oninput = function () {
          later(function () {
            var a = lo.value.trim(), b = hi.value.trim();
            if (col.kind === "number") {
              a = a === "" ? null : parseFloat(a); b = b === "" ? null : parseFloat(b);
              if (a !== null && isNaN(a)) a = null;
              if (b !== null && isNaN(b)) b = null;
            } else { a = a || null; b = b || null; }
            filters[c] = a === null && b === null ? null : { from: a, to: b };
            apply();
          });
        };
        wrap.appendChild(inp);
      });
      return wrap;
    }
    var inp = document.createElement("input");
    inp.placeholder = "contains";
    inp.style.cssText = INPUT + ";width:100%";
    inp.oninput = function () {
      later(function () {
        var q = inp.value.trim().toLowerCase();
        filters[c] = q ? { has: q } : null;
        apply();
      });
    };
    return inp;
  }

  function passes(r) {
    var row = rows[r];
    for (var c = 0; c < ncol; c++) {
      var f = filters[c];
      if (!f) continue;
      var v = row[c];
      if ("is" in f) { if (v !== f.is) return false; continue; }
      if ("has" in f) { if (lower[r][c].indexOf(f.has) < 0) return false; continue; }
      if (v === null) return false;
      // A date bound like "2008" or "2008-05" compares by its prefix.
      var key = cols[c].kind === "date" ? String(v) : v;
      if (f.from !== null && (cols[c].kind === "date" ? key.slice(0, f.from.length) < f.from : key < f.from)) return false;
      if (f.to !== null && (cols[c].kind === "date" ? key.slice(0, f.to.length) > f.to : key > f.to)) return false;
    }
    if (query) {
      var l = lower[r], hit = false;
      for (var k = 0; k < ncol && !hit; k++) hit = l[k].indexOf(query) >= 0;
      if (!hit) return false;
    }
    return true;
  }

  function compare(a, b) {
    var x = rows[a][sortCol], y = rows[b][sortCol];
    if (x === y) return a - b;
    if (x === null) return 1;  // nulls last, whichever way
    if (y === null) return -1;
    var d = x < y ? -1 : x > y ? 1 : 0;
    return d ? d * sortDir : a - b;
  }

  function apply() {
    query = search.value.trim().toLowerCase();
    order = [];
    for (var r = 0; r < rows.length; r++) if (passes(r)) order.push(r);
    if (sortCol >= 0) order.sort(compare);
    arrows.forEach(function (a, c) {
      a.textContent = c !== sortCol ? "" : sortDir > 0 ? " ▲ " : " ▼ ";
    });
    var label = order.length.toLocaleString("en-US") + " of " +
      rows.length.toLocaleString("en-US") + " rows | " + ncol + " columns";
    if (data.total === null || data.total > rows.length)
      label += " (first " + rows.length.toLocaleString("en-US") + " of " +
        (data.total === null ? "more" : data.total.toLocaleString("en-US")) + ")";
    status.textContent = label;
    box.scrollTop = 0;
    render(true);
  }

  var drawn = "";
  function render(force) {
    var first = Math.max(0, Math.floor(box.scrollTop / ROW) - BUFFER);
    var count = Math.ceil((box.clientHeight || +root.dataset.height) / ROW) + 2 * BUFFER;
    var last = Math.min(order.length, first + count);
    var key = first + ":" + last;
    if (key === drawn && !force) return;
    drawn = key;
    var html = "<tr style='height:" + first * ROW + "px'></tr>";
    for (var i = first; i < last; i++) {
      var r = order[i], t = text[r];
      html += "<tr data-row='" + (r + 1) + "' style='" + ((i % 2) ? "background:rgba(127,127,127,.08)" : "") + "'>";
      html += "<td style='" + NUM_STYLE + "'>" + (r + 1) + "</td>";
      for (var c = 0; c < ncol; c++) {
        var s = t[c], cut = s.length > CUT;
        html += "<td style='" + cellStyle(c) + "'" + (cut ? " title='" + esc(s) + "'" : "") + ">" +
          esc(cut ? s.slice(0, CUT - 1) + "…" : s) + "</td>";
      }
      html += "</tr>";
    }
    html += "<tr style='height:" + (order.length - last) * ROW + "px'></tr>";
    tbody.innerHTML = html;
  }

  var pending = false;
  box.addEventListener("scroll", function () {
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () { pending = false; render(); });
  });
  var searchTimer = null;
  search.oninput = function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(apply, 150);
  };
  apply();
})();
"""

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
    // Numbers and dates need room for their filter's from and to boxes.
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
  // Filters stay out of sight until asked for, as in RStudio's viewer.
  var filterBtn = document.createElement("button");
  filterBtn.type = "button"; filterBtn.textContent = "Filter";
  filterBtn.dataset.filterToggle = "";
  filterBtn.setAttribute("aria-pressed", "false");
  filterBtn.title = "Filter by column";
  filterBtn.style.cssText = INPUT + ";cursor:pointer";
  var status = document.createElement("span");
  status.dataset.status = "";
  status.style.cssText = "opacity:.65";
  bar.appendChild(search); bar.appendChild(filterBtn); bar.appendChild(status);
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

  // Header: names with sort arrows, types, and, under the Filter button, a
  // filter per column.
  var nameRow = document.createElement("tr"), typeRow = document.createElement("tr"),
    filterRow = document.createElement("tr");
  var RULE = "1px solid " + GREY, typeCells = [];
  var CHIP = "font:inherit;color:inherit;background:transparent;border:1px solid " + GREY +
    ";border-radius:9px;padding:0 6px;line-height:16px;cursor:pointer;white-space:pre;" +
    "overflow:hidden;text-overflow:ellipsis;min-width:0;max-width:100%";
  function corner(tr, html) {
    var td = document.createElement("td");
    td.style.cssText = NUM_STYLE + ";z-index:3";
    td.innerHTML = html;
    tr.appendChild(td);
    return td;
  }
  corner(nameRow, ""); typeCells.push(corner(typeRow, ""));
  corner(filterRow, "").style.borderBottom = RULE;
  var arrows = [], controls = [];
  cols.forEach(function (col, c) {
    var td = document.createElement("td");
    td.style.cssText = cellStyle(c) + ";cursor:pointer;user-select:none";
    td.title = "Click to sort by " + col.name;
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
    typeCells.push(ttd);

    var ftd = document.createElement("td");
    ftd.style.cssText = cellStyle(c) + ";height:auto;padding:2px 4px 4px 4px;" +
      "overflow:visible;border-bottom:" + RULE;
    var control = filterControl(col, c);
    ftd.appendChild(control.el);
    controls.push(control);
    filterRow.appendChild(ftd);
  });
  thead.appendChild(nameRow); thead.appendChild(typeRow); thead.appendChild(filterRow);

  function showFilters(on) {
    filterBtn.setAttribute("aria-pressed", String(on));
    filterBtn.style.borderColor = on ? "currentColor" : GREY;
    filterRow.style.display = on ? "" : "none";
    typeCells.forEach(function (td) { td.style.borderBottom = on ? "0" : RULE; });
  }
  showFilters(false);
  // Hiding the filters clears them, so no row is ever filtered out of sight.
  filterBtn.onclick = function () {
    var on = filterBtn.getAttribute("aria-pressed") !== "true";
    if (!on) controls.forEach(function (k) { k.clear(); });
    showFilters(on);
    if (!on) apply();
  };

  // One column's filter: a chip that reads "All", or the filter in words
  // ("10–50", "Gentoo") with × to clear it. Clicking the chip swaps it for
  // the column's editor until Enter, Escape or a click elsewhere.
  function filterControl(col, c) {
    var el = document.createElement("div");
    // The chip sits where the column's values do: right for numbers and dates.
    el.style.cssText = "display:flex;align-items:center;gap:2px;min-width:0;height:18px;" +
      "justify-content:" + (NUMERIC[col.kind] ? "flex-end" : "flex-start");
    var chip = document.createElement("button");
    chip.type = "button"; chip.dataset.chip = col.name;
    chip.style.cssText = CHIP + ";flex:0 1 auto";
    var clearBtn = document.createElement("button");
    clearBtn.type = "button"; clearBtn.dataset.clear = col.name; clearBtn.textContent = "×";
    clearBtn.title = "Clear the filter on " + col.name;
    clearBtn.style.cssText = CHIP + ";flex:none;padding:0 4px";
    var editor = document.createElement("div");
    editor.style.cssText = "display:none;gap:2px;width:100%;min-width:0";
    el.appendChild(chip); el.appendChild(clearBtn); el.appendChild(editor);

    // The editor's boxes are the chip's height, so opening one moves nothing.
    var SLIM = "height:18px;padding:0 4px;line-height:16px";
    var words = "", timer = null, inputs = [], commit;
    function later() { clearTimeout(timer); timer = setTimeout(function () { commit(); apply(); }, 150); }
    function input(placeholder, width) {
      var inp = document.createElement("input");
      inp.placeholder = placeholder;
      inp.style.cssText = INPUT + ";width:" + width + ";min-width:0;" + SLIM;
      inp.oninput = later;
      editor.appendChild(inp); inputs.push(inp);
      return inp;
    }

    if (col.kind === "choice" || col.kind === "bool") {
      var sel = document.createElement("select");
      sel.style.cssText = INPUT + ";width:100%;" + SLIM + ";" + SOLID;
      var values = col.kind === "bool" ? [true, false] : col.choices;
      [["", "All"]].concat(values.map(function (v, i) { return ["v" + i, String(v)]; }))
        .concat([["null", "null"]]).forEach(function (o) {
          var op = document.createElement("option");
          op.value = o[0]; op.textContent = o[1];
          sel.appendChild(op);
        });
      editor.appendChild(sel); inputs.push(sel);
      commit = function () {
        var v = sel.value;
        filters[c] = v === "" ? null : v === "null" ? { is: null } : { is: values[+v.slice(1)] };
        words = sel.options[sel.selectedIndex].textContent;
      };
      sel.onchange = function () { close(); chip.focus(); };
    } else if (NUMERIC[col.kind]) {
      var lo = input("from", "50%"), hi = input("to", "50%");
      commit = function () {
        var a = lo.value.trim(), b = hi.value.trim(), fa = a || null, fb = b || null;
        if (col.kind === "number") {
          fa = a === "" ? null : parseFloat(a); fb = b === "" ? null : parseFloat(b);
          if (fa !== null && isNaN(fa)) { fa = null; a = ""; }
          if (fb !== null && isNaN(fb)) { fb = null; b = ""; }
        }
        filters[c] = fa === null && fb === null ? null : { from: fa, to: fb };
        words = a && b ? (a === b ? a : a + "–" + b) : a ? "≥ " + a : "≤ " + b;
      };
    } else {
      var has = input("contains", "100%");
      commit = function () {
        var q = has.value.trim();
        filters[c] = q ? { has: q.toLowerCase() } : null;
        words = '"' + q + '"';
      };
    }

    function show() {
      var on = filters[c] !== null;
      chip.textContent = on ? words : "All";
      chip.title = on ? col.name + ": " + words + " (click to change)" : "Filter " + col.name;
      chip.style.opacity = on ? "1" : ".55";
      clearBtn.style.display = on ? "" : "none";
    }
    function open() {
      chip.style.display = clearBtn.style.display = "none";
      editor.style.display = "flex";
      inputs[0].focus();
    }
    function close() {
      if (editor.style.display === "none") return;
      clearTimeout(timer);
      commit(); apply();
      editor.style.display = "none"; chip.style.display = "";
      show();
    }
    function clear() {
      clearTimeout(timer);
      inputs.forEach(function (inp) { inp.value = ""; });
      commit();
      editor.style.display = "none"; chip.style.display = "";
      show();
    }
    chip.onclick = open;
    clearBtn.onclick = function () { clear(); apply(); chip.focus(); };
    editor.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === "Escape") { e.preventDefault(); close(); chip.focus(); }
    });
    editor.addEventListener("focusout", function (e) {
      if (!editor.contains(e.relatedTarget)) close();
    });
    show();
    return { el: el, clear: clear };
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
      // Every header shows it sorts: a faint ↕, and ▲ or ▼ on the sorted one.
      var on = c === sortCol;
      a.textContent = !on ? " ↕ " : sortDir > 0 ? " ▲ " : " ▼ ";
      a.style.opacity = on ? ".9" : ".5";
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

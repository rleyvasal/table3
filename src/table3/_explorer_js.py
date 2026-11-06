"""The script that turns a table3 explorer's JSON into a grid (docs/explorer.md §4).

Every style is set inline by the script: CRAFT's republish drops <style>
blocks. Only the rows in view are drawn, between two spacer rows, so 10,000
rows scroll as fast as ten. Sorts and filters read the raw values; the grid
shows the display text. __ID__ is the explorer's root element.

``EXPLORER_CORE`` is the grid itself, over either source of rows: the
snapshot's embedded rows, or a kernel's pages (``WIDGET_ESM``, the live
explorer's widget, docs/explorer.md §2).
"""

EXPLORER_CORE = r"""
// The grid over a snapshot (remote null: every row is in data.rows) or over a
// kernel (remote.fetch(request) resolves to one page of rows, in blocks).
function table3Explorer(root, data, remote) {
  var cols = data.columns, ncol = cols.length;
  var ROW = 22, BUFFER = 10, CUT = 40;
  var GREY = "rgba(127,127,127,.45)";
  var SOLID = "background-color:var(--vscode-editor-background,var(--jp-layout-color0,Canvas));" +
    "background-image:linear-gradient(hsl(var(--card)),hsl(var(--card)))";
  var NUMERIC = { number: 1, date: 1 };

  function textsOf(row, shownCols, r) {
    var t = [];
    for (var c = 0; c < ncol; c++) {
      var shown = shownCols[c] && shownCols[c][r];
      var v = row[c];
      t.push(shown != null ? shown : v === null ? "null" : String(v));
    }
    return t;
  }

  // A snapshot's display text, and its lowercase for search, once per cell.
  var rows = remote ? [] : data.rows;
  var text = [], lower = [];
  rows.forEach(function (row, r) {
    var t = textsOf(row, data.shown, r);
    text.push(t); lower.push(t.map(function (s) { return s.toLowerCase(); }));
  });

  // A live explorer holds the blocks of rows it has fetched for the current
  // search, filters and sort; each change starts a new version, and an answer
  // for an older one is dropped.
  var BLOCK = remote ? remote.block : 0, cache = {}, asked = {}, version = 0;
  var refreshing = false, waiting = 0, failed = "";
  function block(page) {
    return page.rows.map(function (row, i) {
      return { num: page.index[i], text: textsOf(row, page.shown, i) };
    });
  }
  if (remote) cache[0] = block(data.first);
  var sample = remote ? cache[0].map(function (r) { return r.text; }) : text;

  function esc(s) {
    return s.replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  // Column widths in characters, from the widest text up to the cut.
  var widths = cols.map(function (col, c) {
    // Numbers and dates need room for their filter's from and to boxes.
    // A profiled column needs room for "128 distinct" and "5 missing".
    var w = Math.max(col.name.length + 2, col.type.length,
      NUMERIC[col.kind] ? 12 : data.layouts && data.layouts.length ? 10 : 6);
    for (var r = 0; r < sample.length && w < CUT; r++) w = Math.max(w, sample[r][c].length);
    return Math.min(w, CUT);
  });
  var numWidth = String(remote ? data.total : rows.length).length;

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
  var profileBtn = document.createElement("button");
  profileBtn.type = "button"; profileBtn.textContent = "Profile";
  profileBtn.dataset.profileToggle = "";
  profileBtn.setAttribute("aria-pressed", "true");
  profileBtn.title = "Show or hide each column's profile";
  profileBtn.style.cssText = INPUT + ";cursor:pointer";
  var basis = document.createElement("span");
  basis.dataset.profileBasis = "";
  basis.style.cssText = "opacity:.5";
  var colsBtn = document.createElement("button");
  colsBtn.type = "button"; colsBtn.textContent = "Columns";
  colsBtn.dataset.columnsMenu = "";
  colsBtn.title = "Choose the columns to show and export";
  colsBtn.style.cssText = INPUT + ";cursor:pointer";
  var exportBtn = document.createElement("button");
  exportBtn.type = "button"; exportBtn.textContent = "Export";
  exportBtn.dataset.exportMenu = "";
  exportBtn.title = "Export the rows the search and filters keep";
  exportBtn.style.cssText = INPUT + ";cursor:pointer";
  bar.style.position = "relative";
  bar.appendChild(search); bar.appendChild(filterBtn); bar.appendChild(profileBtn);
  bar.appendChild(colsBtn); bar.appendChild(exportBtn);
  bar.appendChild(status); bar.appendChild(basis);
  root.appendChild(bar);

  // Menus under the Columns and Export buttons; Escape or a click elsewhere closes them.
  var menus = [];
  function menu(btn, fill) {
    var pop = document.createElement("div");
    pop.style.cssText = "display:none;position:absolute;z-index:6;top:100%;margin-top:2px;" +
      "padding:6px 8px;border:1px solid " + GREY + ";border-radius:4px;max-height:260px;" +
      "overflow:auto;min-width:14em;" + SOLID;
    bar.appendChild(pop);
    btn.onclick = function () {
      var open = pop.style.display === "none";
      closeMenus();
      if (!open) return;
      pop.style.left = btn.offsetLeft + "px";
      fill(pop);
      pop.style.display = "block";
    };
    menus.push(pop);
    return pop;
  }
  function closeMenus() { menus.forEach(function (m) { m.style.display = "none"; }); }
  root.addEventListener("keydown", function (e) { if (e.key === "Escape") closeMenus(); });
  document.addEventListener("mousedown", function (e) { if (!bar.contains(e.target)) closeMenus(); });

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
  var order = [], count = 0, query = "";

  // Header: names with sort arrows, types, and, under the Filter button, a
  // filter per column.
  var nameRow = document.createElement("tr"), typeRow = document.createElement("tr"),
    filterRow = document.createElement("tr");
  var RULE = "1px solid " + GREY, typeCells = [], profileCells = [];
  var profileRow = document.createElement("tr");
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
  profileCells.push(corner(profileRow, ""));
  corner(filterRow, "").style.borderBottom = RULE;
  var arrows = [], controls = [], colCells = [], hidden = cols.map(function () { return false; });
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

    var ptd = document.createElement("td");
    ptd.style.cssText = cellStyle(c) + ";height:auto;padding:2px 10px 4px 10px;" +
      "vertical-align:top;white-space:normal;line-height:12px;font-size:10px";
    ptd.dataset.profile = col.name;
    profileRow.appendChild(ptd);
    profileCells.push(ptd);

    var ftd = document.createElement("td");
    ftd.style.cssText = cellStyle(c) + ";height:auto;padding:2px 4px 4px 4px;" +
      "overflow:visible;border-bottom:" + RULE;
    var control = filterControl(col, c);
    ftd.appendChild(control.el);
    controls.push(control);
    filterRow.appendChild(ftd);
    colCells.push([td, ttd, ptd, ftd]);
  });
  thead.appendChild(nameRow); thead.appendChild(typeRow); thead.appendChild(profileRow);
  thead.appendChild(filterRow);

  function showFilters(on) {
    filterBtn.setAttribute("aria-pressed", String(on));
    filterBtn.style.borderColor = on ? "currentColor" : GREY;
    filterRow.style.display = on ? "" : "none";
    rules();
  }
  // The rule goes under the header's last row showing: types, profiles or filters.
  function rules() {
    var filtersOn = filterBtn.getAttribute("aria-pressed") === "true";
    var profilesOn = profileBtn.getAttribute("aria-pressed") === "true";
    typeCells.forEach(function (td) { td.style.borderBottom = filtersOn || profilesOn ? "0" : RULE; });
    profileCells.forEach(function (td) { td.style.borderBottom = profilesOn && !filtersOn ? RULE : "0"; });
  }
  profileBtn.onclick = function () {
    var on = profileBtn.getAttribute("aria-pressed") !== "true";
    profileBtn.setAttribute("aria-pressed", String(on));
    profileBtn.style.borderColor = on ? "currentColor" : GREY;
    profileRow.style.display = on ? "" : "none";
    basis.style.display = on ? "" : "none";
    rules();
  };
  profileBtn.style.borderColor = "currentColor";

  // -- columns: which to show, and so which an export writes ------------------
  function visibleNames() {
    return cols.filter(function (col, c) { return !hidden[c]; }).map(function (col) { return col.name; });
  }
  function showColumns() {
    var off = 0;
    cols.forEach(function (col, c) {
      if (hidden[c]) off++;
      colCells[c].forEach(function (td) { td.style.display = hidden[c] ? "none" : ""; });
    });
    colsBtn.textContent = off ? "Columns " + (ncol - off) + "/" + ncol : "Columns";
    colsBtn.style.borderColor = off ? "currentColor" : GREY;
    render(true);
  }
  menu(colsBtn, function (pop) {
    pop.innerHTML = "";
    cols.forEach(function (col, c) {
      var label = document.createElement("label");
      label.style.cssText = "display:flex;gap:6px;align-items:center;white-space:nowrap;cursor:pointer";
      var box = document.createElement("input");
      box.type = "checkbox"; box.checked = !hidden[c]; box.dataset.columnToggle = col.name;
      box.onchange = function () {
        // One column always shows.
        if (!box.checked && visibleNames().length === 1) { box.checked = true; return; }
        hidden[c] = !box.checked;
        showColumns();
      };
      label.appendChild(box);
      label.appendChild(document.createTextNode(col.name));
      pop.appendChild(label);
    });
  });

  // -- export: every kept row, in the grid's order, the shown columns ---------
  var MAX_FLOAT = 1.7976931348623157e308;
  function csvField(s) {
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  // A snapshot value as polars' CSV writes it: every stored digit, empty for null.
  function csvValue(r, c) {
    var v = rows[r][c], shown = data.shown[c] && data.shown[c][r], col = cols[c];
    var isFloat = /^f(16|32|64)$/.test(col.type);
    if (v === null) return isFloat && shown === "NaN" ? "NaN" : "";
    if (isFloat) {
      if (Math.abs(v) === MAX_FLOAT) return v > 0 ? "inf" : "-inf";
      return Number.isInteger(v) && Math.abs(v) < 1e16 ? v.toFixed(1) : String(v);
    }
    if (shown != null) return shown;  // big integers and decimals, exact
    return String(v);
  }
  function snapshotCsv() {
    var keep = [];
    cols.forEach(function (col, c) { if (!hidden[c]) keep.push(c); });
    var lines = [keep.map(function (c) { return csvField(cols[c].name); }).join(",")];
    order.forEach(function (r) {
      lines.push(keep.map(function (c) { return csvField(csvValue(r, c)); }).join(","));
    });
    return lines.join("\n") + "\n";
  }
  function download(blob, name) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name;
    a.style.display = "none";
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  var exportNote;
  function note(s) { if (exportNote) exportNote.textContent = s; }
  function exportLive(kind, save) {
    var req = request();
    req.columns = visibleNames(); req["export"] = kind;
    if (save) req.save = true;
    note((save ? "Saving " : "Exporting ") + fmt(count) + " rows…");
    remote.fetch(req).then(function (msg) {
      if (msg.error) { note("Error: " + msg.error); return; }
      if (msg.saved) { note("Saved " + msg.saved); return; }
      var type = kind === "csv" ? "text/csv" : "application/vnd.apache.parquet";
      download(new Blob(msg.buffers || [], { type: type }), msg.download.name);
      note("Downloaded " + msg.download.name);
    });
  }
  menu(exportBtn, function (pop) {
    pop.innerHTML = "";
    var cut = !remote && (data.total === null || data.total > rows.length);
    var scope = document.createElement("div");
    scope.dataset.exportScope = "";
    scope.style.cssText = "opacity:.65;margin:0 0 4px 0;white-space:nowrap";
    scope.textContent = fmt(count) + (cut ? " snapshot" : "") + " rows × " +
      visibleNames().length + " columns, as sorted";
    pop.appendChild(scope);
    function item(label, act, attr) {
      var b = document.createElement("button");
      b.type = "button"; b.textContent = label; b.dataset.export = attr;
      b.style.cssText = "display:block;width:100%;text-align:left;font:inherit;color:inherit;" +
        "background:transparent;border:0;padding:2px 0;cursor:pointer";
      b.onclick = act;
      pop.appendChild(b);
    }
    if (remote) {
      item("Download CSV", function () { exportLive("csv", false); }, "csv");
      item("Download Parquet", function () { exportLive("parquet", false); }, "parquet");
      item("Save CSV in the kernel's folder", function () { exportLive("csv", true); }, "save-csv");
      item("Save Parquet in the kernel's folder", function () { exportLive("parquet", true); }, "save-parquet");
    } else {
      item("Download CSV", function () {
        download(new Blob([snapshotCsv()], { type: "text/csv" }), "table3-export.csv");
        note("Downloaded table3-export.csv");
      }, "csv");
    }
    exportNote = document.createElement("div");
    exportNote.dataset.exportNote = "";
    exportNote.style.cssText = "opacity:.65;margin:4px 0 0 0;max-width:24em;overflow-wrap:anywhere";
    if (cut) exportNote.textContent = "The snapshot holds the first " + fmt(rows.length) +
      " rows; run the cell to export every row.";
    pop.appendChild(exportNote);
  });
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

  // -- profiles ---------------------------------------------------------------
  // Each column's bars over all rows (faint), and over the rows kept (solid, blue);
  // the layouts (bins, top values) come from Python, once.
  var layouts = data.layouts || [], base = null, BAR = "rgb(59,130,246)";
  function fmt(n) { return n.toLocaleString("en-US"); }

  // A snapshot recounts its rows as its filters change; a live explorer
  // gets each profile from the kernel with the first block of rows.
  function recount() {
    var columns = layouts.map(function (lay, c) {
      var missing = 0, seen = new Set(), k = lay.bins, bins = [], top = [], other = 0, at = {};
      if (lay.type === "hist") for (var i = 0; i < k; i++) bins.push(0);
      else lay.values.forEach(function (v, i) { at[v] = i; top.push(0); });
      for (var j = 0; j < order.length; j++) {
        var r = order[j], v = rows[r][c];
        if (v === null) { missing++; continue; }
        seen.add(v);
        if (lay.type === "hist") {
          if (!k) continue;
          var b = cols[c].kind === "date" ? data.date_bins[c][r]
            : Math.min(k - 1, Math.max(0, Math.floor((v - lay.lo) / lay.width)));
          bins[b]++;
        } else if (text[r][c] in at) top[at[text[r][c]]]++;
        else other++;
      }
      var out = { missing: missing, distinct: seen.size, approx: false };
      if (lay.type === "hist") out.bins = bins; else { out.top = top; out.other = other; }
      return out;
    });
    return { basis: "full", rows: order.length, of: order.length, columns: columns };
  }

  function drawProfiles(p) {
    if (!p || !layouts.length) return;
    if (!base) base = p;
    var cut = !remote && (data.total === null || data.total > rows.length);
    basis.textContent = p.basis === "sampled"
      ? "Profiles: a sample of " + fmt(p.rows) + " of " + fmt(p.of) + " rows"
      : "Profiles: " + (cut ? "these " : "all ") + fmt(p.rows) + (cut ? " snapshot" : "") + " rows";
    basis.title = p.basis === "sampled"
      ? "Bars from a random sample; missing values counted over every row, distinct values estimated (≈)"
      : cut ? "The snapshot holds the first " + fmt(rows.length) + " rows; run the cell to profile every row"
      : "Counted over every row the search and filters keep";
    layouts.forEach(function (lay, c) {
      var td = profileCells[c + 1], now = p.columns[c], all = base.columns[c], html = "", tip = [];
      if (lay.type === "hist") {
        var k = lay.bins, most = Math.max.apply(null, [1].concat(all.bins));
        if (k) {
          html += "<svg viewBox='0 0 " + k + " 1' preserveAspectRatio='none' style='display:block;width:100%;height:24px'>";
          for (var i = 0; i < k; i++) {
            var hb = all.bins[i] / most, hn = now.bins[i] / most;
            html += "<rect x='" + (i + .08) + "' width='.84' y='" + (1 - hb) + "' height='" + hb +
              "' fill='currentColor' fill-opacity='.16'></rect>";
            if (hn > 0) html += "<rect data-bin='" + i + "' x='" + (i + .08) + "' width='.84' y='" +
              (1 - hn) + "' height='" + hn + "' fill='" + BAR + "'></rect>";
          }
          html += "</svg><div style='display:flex;justify-content:space-between;gap:4px;opacity:.6;" +
            "white-space:nowrap;overflow:hidden'><span>" + esc(lay.from) + "</span><span>" +
            esc(lay.to) + "</span></div>";
          tip.push(lay.from + " to " + lay.to + ", " + k + " bins");
        }
      } else {
        var total = now.other, segs = "";
        now.top.forEach(function (n) { total += n; });
        var shade = [1, .7, .45];
        now.top.forEach(function (n, i) {
          if (n) segs += "<span title='" + esc(lay.values[i]) + "' style='display:block;height:100%;width:" +
            (100 * n / Math.max(total, 1)) + "%;background:" + BAR + ";opacity:" + shade[i] + "'></span>";
          tip.push(lay.values[i] + ": " + fmt(n) + " (" + Math.round(100 * n / Math.max(total, 1)) + "%)");
        });
        if (now.other) {
          segs += "<span style='display:block;height:100%;flex:1;background:currentColor;opacity:.18'></span>";
          tip.push("other: " + fmt(now.other));
        }
        html += "<div style='display:flex;height:8px;margin:8px 0 4px 0;border-radius:2px;overflow:hidden'>" +
          segs + "</div><div style='opacity:.6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>" +
          esc(lay.values.slice(0, 2).join(", ")) + "</div>";
      }
      // Distinct and missing on lines of their own, so narrow columns keep
      // both; the missing line stays, blank, so every profile is one height.
      var LINE = "opacity:.6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis";
      var stats = (now.approx ? "≈" : "") + fmt(now.distinct) + " distinct";
      var missing = now.missing ? fmt(now.missing) + " missing" : "";
      html += "<div data-stats style='" + LINE + "'>" + stats + "</div>" +
        "<div data-missing style='" + LINE + "'>" + (missing || "&nbsp;") + "</div>";
      tip.push(stats + (missing ? " · " + missing : ""));
      td.innerHTML = html;
      td.title = tip.join("\n");
    });
  }

  function updateStatus() {
    var all = remote ? data.total : rows.length;
    var label = count.toLocaleString("en-US") + " of " + all.toLocaleString("en-US") +
      " rows | " + ncol + " columns";
    var cut = !remote && (data.total === null || data.total > rows.length);
    if (cut && data.live)
      label += " (a snapshot of the first " + rows.length.toLocaleString("en-US") + " of " +
        (data.total === null ? "more" : data.total.toLocaleString("en-US")) +
        ": search and filters cover these rows; run the cell to explore every row)";
    else if (cut)
      label += " (first " + rows.length.toLocaleString("en-US") + " of " +
        (data.total === null ? "more" : data.total.toLocaleString("en-US")) + ")";
    if (waiting) label += " …";
    status.textContent = failed || label;
    status.dataset.loading = waiting ? "1" : "";
  }

  // The state a live explorer sends: what apply() reads in a snapshot.
  function request() {
    var f = {};
    filters.forEach(function (x, c) { if (x) f[cols[c].name] = x; });
    return {
      search: query, filters: f,
      sort: sortCol >= 0 ? { column: cols[sortCol].name, desc: sortDir < 0 } : null
    };
  }

  function want(b) {
    if (asked[b]) return;
    asked[b] = true;
    var v = version, req = request();
    req.offset = b * BLOCK; req.limit = BLOCK;
    if (b === 0) req.profile = true;
    waiting++; updateStatus();
    remote.fetch(req).then(function (page) {
      if (v !== version) return;  // the search, a filter or the sort changed since
      waiting--;
      if (page.error) { failed = "Error: " + page.error; updateStatus(); return; }
      failed = "";
      if (refreshing) { cache = {}; refreshing = false; }
      cache[b] = block(page); count = page.filtered;
      if (page.profile) drawProfiles(page.profile);
      updateStatus(); render(true);
    });
  }

  function rowAt(i) {
    if (!remote) { var r = order[i]; return { num: r + 1, text: text[r] }; }
    if (refreshing) return null;
    var b = Math.floor(i / BLOCK), got = cache[b];
    if (!got) { want(b); return null; }
    return got[i - b * BLOCK] || null;
  }

  function drawArrows() {
    arrows.forEach(function (a, c) {
      // Every header shows it sorts: a faint ↕, and ▲ or ▼ on the sorted one.
      var on = c === sortCol;
      a.textContent = !on ? " ↕ " : sortDir > 0 ? " ▲ " : " ▼ ";
      a.style.opacity = on ? ".9" : ".5";
    });
  }

  function apply() {
    query = search.value.trim().toLowerCase();
    drawArrows();
    box.scrollTop = 0;
    if (remote) {
      // Keep the old rows, dimmed, until the first block of the new ones comes.
      version++; asked = {}; waiting = 0; refreshing = true;
      want(0);
      tbody.style.opacity = ".5";
      return;
    }
    order = [];
    for (var r = 0; r < rows.length; r++) if (passes(r)) order.push(r);
    if (sortCol >= 0) order.sort(compare);
    count = order.length;
    if (layouts.length) {
      var p = recount();
      if (!base) base = p;
      drawProfiles(p);
    }
    updateStatus();
    render(true);
  }

  var drawn = "";
  function render(force) {
    if (remote && refreshing) return;
    tbody.style.opacity = "";
    var first = Math.max(0, Math.floor(box.scrollTop / ROW) - BUFFER);
    var many = Math.ceil((box.clientHeight || +root.dataset.height) / ROW) + 2 * BUFFER;
    var last = Math.min(count, first + many);
    var key = first + ":" + last;
    if (key === drawn && !force) return;
    drawn = key;
    var html = "<tr style='height:" + first * ROW + "px'></tr>";
    for (var i = first; i < last; i++) {
      var row = rowAt(i), stripe = (i % 2) ? "background:rgba(127,127,127,.08)" : "";
      if (!row) {  // a block still on its way
        html += "<tr data-pending style='" + stripe + "'><td style='" + NUM_STYLE + "'></td>";
        for (var p = 0; p < ncol; p++) if (!hidden[p]) html += "<td style='" + cellStyle(p) + "'></td>";
        html += "</tr>";
        continue;
      }
      var t = row.text;
      html += "<tr data-row='" + row.num + "' style='" + stripe + "'>";
      html += "<td style='" + NUM_STYLE + "'>" + row.num + "</td>";
      for (var c = 0; c < ncol; c++) {
        if (hidden[c]) continue;
        var s = t[c], cut = s.length > CUT;
        html += "<td style='" + cellStyle(c) + "'" + (cut ? " title='" + esc(s) + "'" : "") + ">" +
          esc(cut ? s.slice(0, CUT - 1) + "…" : s) + "</td>";
      }
      html += "</tr>";
    }
    html += "<tr style='height:" + (count - last) * ROW + "px'></tr>";
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
  if (remote) {
    count = data.first.filtered;
    drawArrows();
    drawProfiles(data.first.profile);
    updateStatus();
    render(true);
  } else apply();
}
"""

EXPLORER_JS = r"""
(function () {
  var root = document.getElementById("__ID__");
  if (!root || root.dataset.explorer) return;
  root.dataset.explorer = "1";
""" + EXPLORER_CORE + r"""
  // A live explorer of the same data, drawn by its widget, stands in for this snapshot.
  if (document.querySelector("[data-table3-live-for='__ID__']")) {
    root.style.display = "none";
    return;
  }
  var data = JSON.parse(root.querySelector("script[type='application/json']").textContent);
  var fallback = root.querySelector("[data-fallback]");
  if (fallback) fallback.style.display = "none";
  table3Explorer(root, data, null);
  // Reopened without a kernel, JupyterLab writes "model not found" where the
  // live explorer was: this snapshot is the explorer now, so hide that line.
  function hideDeadWidget() {
    var area = root.closest(".jp-OutputArea");
    if (!area) return;
    area.querySelectorAll(".jupyter-widgets").forEach(function (w) {
      if (/model not found/.test(w.textContent))
        (w.closest(".jp-OutputArea-child") || w).style.display = "none";
    });
  }
  if (data.live) [300, 1500, 5000].forEach(function (ms) { setTimeout(hideDeadWidget, ms); });
})();
"""

# The live explorer's widget (anywidget): the same grid, its rows fetched from
# the kernel. It hides its snapshot, the output displayed just before it.
WIDGET_ESM = EXPLORER_CORE + r"""
export default {
  render({ model, el }) {
    var meta = model.get("meta");
    var root = document.createElement("div");
    root.setAttribute("data-table3-live-for", meta.snapshot || "");
    root.dataset.height = meta.height;
    // VS Code draws widgets on a white area in grey text, whatever its theme:
    // the explorer paints the editor's own colours, as its outputs have.
    root.style.cssText = "font:" + meta.font +
      ";color:var(--vscode-editor-foreground,var(--jp-content-font-color1,inherit))" +
      ";background:var(--vscode-editor-background,var(--jp-layout-color0,transparent))";
    if (meta.caption) {
      var cap = document.createElement("div");
      cap.style.cssText = "opacity:.85;margin:0 0 4px 0";
      cap.textContent = meta.caption;
      root.appendChild(cap);
    }
    el.appendChild(root);
    // VS Code also sets the widget's containers on white, with padding round
    // them (.cell-output-ipywidget-background, !important): clear them, so the
    // output sits on the editor's background as other outputs do. ipywidgets
    // renders a view before attaching it, so wait until it is on the page.
    var tries = 0;
    (function clearFrame() {
      for (var up = el.parentElement; up; up = up.parentElement)
        if (/ipywidget-background/.test(typeof up.className === "string" ? up.className : ""))
          up.style.setProperty("background", "transparent", "important");
      if (!el.isConnected && ++tries < 100) setTimeout(clearFrame, 50);
    })();
    var snap = meta.snapshot && document.getElementById(meta.snapshot);
    if (snap) snap.style.display = "none";
    // Each view numbers its own requests; a model can be shown in two places.
    var view = Math.random().toString(36).slice(2), seq = 0, waiting = {};
    function answer(msg, buffers) {
      var done = msg && waiting[msg.id];
      if (done) { delete waiting[msg.id]; msg.buffers = buffers; done(msg); }
    }
    model.on("msg:custom", answer);
    table3Explorer(root, meta, {
      block: meta.block,
      fetch: function (req) {
        return new Promise(function (resolve) {
          req.id = view + ":" + (++seq);
          waiting[req.id] = resolve;
          model.send(req);
        });
      }
    });
    return function () { model.off("msg:custom", answer); };
  }
};
"""

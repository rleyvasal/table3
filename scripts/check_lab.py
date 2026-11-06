"""table3.view() in JupyterLab: live, reloaded with its kernel, reopened without it.

    pip install -e ".[dev,browser,live]" jupyterlab
    python scripts/check_lab.py /tmp/table3-lab

Starts JupyterLab on port 8898 in the given folder, runs a notebook ending
in view() over 50,000 rows, and checks in headless Chromium that the live
grid draws and searches every row, exports the kept rows (downloaded and
saved in the kernel's folder), comes back on reload, and that, reopened
after its kernel is shut down, the snapshot shows with its note and
JupyterLab's "model not found" line is hidden.
"""
import json, subprocess, sys, time, pathlib, urllib.request
from playwright.sync_api import sync_playwright

work = pathlib.Path(sys.argv[1]); work.mkdir(exist_ok=True)
cell = '''
import polars as pl, table3
df = pl.DataFrame({"x": list(range(50_000)), "s": [f"item {i}" for i in range(50_000)]})
table3.view(df, n=1000)
'''
nb = {"cells": [{"cell_type": "code", "metadata": {}, "source": cell, "outputs": [], "execution_count": None}],
      "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}},
      "nbformat": 4, "nbformat_minor": 5}
(work / "e2e.ipynb").write_text(json.dumps(nb))
port = 8898
srv = subprocess.Popen([sys.executable, "-m", "jupyter", "lab", "--no-browser", f"--port={port}",
    "--IdentityProvider.token=e2e", "--LabApp.expose_app_in_browser=True",
    f"--ServerApp.root_dir={work}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
STATE = """() => [...document.querySelectorAll('.jp-OutputArea-child')].map(c => ({
  visible: c.offsetParent !== null && getComputedStyle(c).display !== 'none',
  live: !!c.querySelector('[data-table3-live-for]'),
  snapshot: !!c.querySelector('[id^=table3-explore]'),
  snapshotShown: !!c.querySelector('[id^=table3-explore]') && c.querySelector('[id^=table3-explore]').style.display !== 'none',
  status: (c.querySelector('[data-status]') || {}).textContent || null,
  text: c.innerText.slice(0, 60)}))"""
ok = True
def check(label, cond, got):
    global ok
    ok &= bool(cond); print(("PASS " if cond else "FAIL ") + label, "" if cond else json.dumps(got, indent=1))
try:
    for _ in range(60):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api?token=e2e"); break
        except Exception: time.sleep(1)
    with sync_playwright() as pw:
        b = pw.chromium.launch(); page = b.new_page()
        def openit():
            page.goto(f"http://127.0.0.1:{port}/lab/tree/e2e.ipynb?token=e2e")
            page.wait_for_function("window.jupyterapp && document.querySelector('.jp-Notebook')", timeout=60000)
            time.sleep(4)
        openit()
        page.evaluate("jupyterapp.commands.execute('notebook:run-all-cells')")
        page.wait_for_selector("[data-table3-live-for]", timeout=60000); time.sleep(1)
        s = page.evaluate(STATE)
        live = [o for o in s if o["live"]]
        check("live grid drawn, over every row", live and live[0]["status"] == "50,000 of 50,000 rows | 2 columns", s)
        check("snapshot hidden while live", not any(o["snapshotShown"] for o in s), s)
        page.fill("[data-table3-live-for] input[type=search]", "item 4999")
        page.wait_for_function("() => document.querySelector('[data-table3-live-for] [data-status]').textContent.startsWith('11 of')", timeout=20000)
        check("search runs in the kernel over all 50,000 rows", True, None)
        live_root = "[data-table3-live-for]"
        page.click(f"{live_root} [data-export-menu]")
        with page.expect_download() as info:
            page.click(f"{live_root} [data-export='csv']")
        lines = open(info.value.path()).read().splitlines()
        check("export downloads every kept row through the kernel",
              lines[0] == "x,s" and len(lines) == 12 and lines[1] == "4999,item 4999", lines[:3])
        page.click(f"{live_root} [data-export='save-parquet']")
        page.wait_for_function(f"() => document.querySelector('{live_root} [data-export-note]').textContent.startsWith('Saved')", timeout=20000)
        saved = page.eval_on_selector(f"{live_root} [data-export-note]", "n => n.textContent")[6:]
        import polars as pl
        check("export saves a Parquet file in the kernel's folder",
              pl.read_parquet(saved).height == 11 and str(work) in saved, saved)
        page.keyboard.press("Escape")
        page.fill(f"{live_root} input[type=search]", "")
        page.wait_for_function("() => document.querySelector('[data-table3-live-for] [data-status]').textContent.startsWith('50,000 of')", timeout=20000)
        page.click(f"{live_root} [data-export-menu]")
        with page.expect_download() as info:
            page.click(f"{live_root} [data-export='parquet']")
        check("export of all 50,000 rows, whatever the page", pl.read_parquet(info.value.path()).height == 50_000, None)
        page.keyboard.press("Escape")
        page.evaluate("jupyterapp.commands.execute('docmanager:save')"); time.sleep(2)
        openit(); page.reload(); page.wait_for_selector(".jp-Notebook"); time.sleep(6)
        s = page.evaluate(STATE)
        check("reloaded with its kernel: live again, snapshot hidden",
              any(o["live"] and o["status"] for o in s) and not any(o["snapshotShown"] for o in s), s)
        page.evaluate("jupyterapp.commands.execute('kernelmenu:shutdown')"); time.sleep(3)
        page.evaluate("jupyterapp.commands.execute('docmanager:save')"); time.sleep(2)
        page.reload(); page.wait_for_selector(".jp-Notebook"); time.sleep(8)
        s = page.evaluate(STATE)
        snap = [o for o in s if o["snapshot"]]
        check("without a kernel: the snapshot shows and says so",
              snap and snap[0]["snapshotShown"] and "a snapshot of the first 1,000 of 50,000" in (snap[0]["status"] or ""), s)
        check("without a kernel: no 'model not found' line",
              not any(o["visible"] and "model not found" in o["text"] for o in s), s)
        size = len((work / "e2e.ipynb").read_text())
        print(f"saved notebook: {size/1024:.0f} KB")
        b.close()
finally:
    srv.terminate()
sys.exit(0 if ok else 1)

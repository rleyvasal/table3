#!/usr/bin/env bash
# Run what CI runs (.github/workflows/tests.yml), locally, before pushing.
#
# Each job gets a fresh environment with only table3's declared dependencies,
# so nothing installed on this machine can hide a failure that CI would see.
#
#   scripts/check.sh          all jobs, one after another
#   scripts/check.sh 3.12     one Python version only, then the browser and
#                             distribution jobs
#
# The browser job installs Playwright's Chromium. On Linux it needs the
# libraries Chromium links to (playwright install --with-deps, with sudo);
# without sudo, unpack the missing ones and list their folder in
# LD_LIBRARY_PATH, which this script passes on.
#
# Needs uv (https://docs.astral.sh/uv/); it downloads missing Pythons.
set -euo pipefail

cd "$(dirname "$0")/.."
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

versions=("${@:-3.10 3.11 3.12 3.13 3.14}")
versions=(${versions[@]})
failed=()

run() {
  local name="$1"; shift
  printf '\n── %s ──\n' "$name"
  if "$@"; then
    printf '   ok: %s\n' "$name"
  else
    printf '   FAILED: %s\n' "$name"
    failed+=("$name")
  fi
}

pytest_job() {
  local env="$work/py$1"
  uv venv -q --python "$1+gil" "$env" &&
    uv pip install -q --python "$env/bin/python" -e ".[dev,live]" &&
    "$env/bin/python" -m pytest -q -p no:cacheprovider
}

browser_job() {
  local env="$work/browser"
  uv venv -q --python 3.12 "$env" &&
    uv pip install -q --python "$env/bin/python" -e ".[dev,browser,live]" &&
    "$env/bin/python" -m playwright install chromium > /dev/null &&
    "$env/bin/python" -m pytest -q -p no:cacheprovider tests/test_explorer_browser.py tests/test_pager_browser.py tests/test_live_browser.py
}

distributions_job() {
  local env="$work/build" clean="$work/clean"
  rm -rf build dist src/*.egg-info
  uv venv -q --python 3.12 "$env" &&
    uv pip install -q --python "$env/bin/python" build twine &&
    "$env/bin/python" -m build -q --outdir "$work/dist" &&
    "$env/bin/python" -m twine check --strict "$work"/dist/* &&
    uv venv -q --python 3.12 "$clean" &&
    uv pip install -q --python "$clean/bin/python" "$work"/dist/*.whl &&
    (cd "$work" && "$clean/bin/python" -c "import polars as pl, table3; h = table3.html(pl.DataFrame({'x': [1.5, None]})); assert '>1.5<' in h and '>null<' in h; print(table3.__version__)")
}

for v in "${versions[@]}"; do
  run "pytest (Python $v)" pytest_job "$v"
done
run "explorer and pages in headless Chromium" browser_job
run "distributions" distributions_job

if (( ${#failed[@]} )); then
  printf '\nFailed: %s\n' "${failed[*]}"
  exit 1
fi
printf '\nAll jobs passed.\n'

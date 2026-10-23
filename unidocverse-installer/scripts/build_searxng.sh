#!/bin/bash
# Builds searxng-portable/: a relocatable Python (python-build-standalone via uv) with SearxNG
# installed, plus its settings. The desktop app starts it on 127.0.0.1:8888 for web search.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HERE/searxng-portable"
SEARX_REF="${SEARX_REF:-master}"
rm -rf "$OUT"; mkdir -p "$OUT"
uv python install 3.12 --install-dir "$OUT/.uv" >/dev/null
PYDIR="$(find "$OUT/.uv" -maxdepth 1 -type d -name "cpython-3.12.*-macos-aarch64-none" | head -1)"
mv "$PYDIR" "$OUT/python"; rm -rf "$OUT/.uv"
PY="$OUT/python/bin/python3"
TMP="$(mktemp -d)"
curl -sL "https://github.com/searxng/searxng/archive/refs/heads/${SEARX_REF}.tar.gz" | tar -xz -C "$TMP"
SRC="$(ls -d "$TMP"/searxng-*)"
uv pip install --python "$PY" --break-system-packages -r "$SRC/requirements.txt" setuptools wheel
uv pip install --python "$PY" --break-system-packages --no-build-isolation "$SRC"
rm -rf "$TMP"
cp "$HERE/scripts/searxng-settings.yml" "$OUT/settings.yml"
# Trim: tests, caches and parts SearxNG never uses
L="$OUT/python/lib/python3.12"
rm -rf "$L"/site-packages/pip* "$L"/ensurepip "$L"/idlelib "$L"/tkinter "$L"/turtledemo "$L"/lib2to3 \
       "$L"/lib-dynload/_tkinter* "$OUT/python/lib"/libtcl* "$OUT/python/lib"/libtk* "$OUT/python/lib"/tcl* "$OUT/python/lib"/tk* \
       "$OUT/python/include" "$OUT/python/share" "$L"/config-3.12-darwin
find "$OUT/python" -name "*.a" -delete
find "$OUT/python" -type d \( -name "__pycache__" -o -name "test" -o -name "tests" \) -prune -exec rm -rf {} + 2>/dev/null || true
SEARXNG_SETTINGS_PATH="$OUT/settings.yml" SEARXNG_SECRET=buildcheck "$PY" -c "import searx.webapp" && echo "SearxNG portable ready: $(du -sh "$OUT" | cut -f1)"

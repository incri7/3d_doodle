#!/usr/bin/env bash
# Install headless Blender (the bpy module) into .venv. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"
if [ -x .venv/bin/python ] && .venv/bin/python -c "import bpy" 2>/dev/null; then
  exit 0
fi
if command -v uv >/dev/null; then
  uv venv .venv --python 3.13 -q
  uv pip install --python .venv/bin/python -q -r requirements.txt
else
  python3.13 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
.venv/bin/python -c "import bpy; print('Blender', bpy.app.version_string)"

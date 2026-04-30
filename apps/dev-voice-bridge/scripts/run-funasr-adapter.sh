#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PREFERRED_PYTHON="$ROOT_DIR/.venv-funasr/bin/python"

if [[ -x "$PREFERRED_PYTHON" ]]; then
  PYTHON_BIN="$PREFERRED_PYTHON"
else
  PYTHON_BIN="${FUNASR_PYTHON_BIN:-python3}"
fi

exec "$PYTHON_BIN" "$ROOT_DIR/funasr_adapter/server.py"


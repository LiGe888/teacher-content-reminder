#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv-funasr"

python3 -m venv "$VENV_DIR"
export PATH="$VENV_DIR/bin:$PATH"
"$VENV_DIR/bin/pip" install -U pip setuptools wheel
"$VENV_DIR/bin/pip" install cmake

CMAKE_BIN_DIR="$("$VENV_DIR/bin/python" -c 'import pathlib, cmake; print(pathlib.Path(cmake.__file__).resolve().parent / "data" / "bin")')"
export PATH="$CMAKE_BIN_DIR:$VENV_DIR/bin:$PATH"

"$VENV_DIR/bin/pip" install -r "$ROOT_DIR/funasr_adapter/requirements.txt"

cat <<'EOF'

FunASR adapter dependencies installed.

Next:
1. export VOICE_CODER_TRANSCRIBE_PROVIDER=funasr
2. export VOICE_CODER_FUNASR_URL=http://127.0.0.1:7861/transcribe
3. ./scripts/run-funasr-adapter.sh

EOF

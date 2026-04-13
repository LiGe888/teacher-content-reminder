#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "错误: 未找到虚拟环境 Python: $PYTHON_BIN" >&2
  echo "请先在项目根目录创建并安装 .venv 依赖。" >&2
  exit 1
fi

DEFAULT_ARGS=(
  --source nasa_news
  --audience senior
  --provider router
  --limit 1
  --output-dir .exports
  --formats markdown,html,json,pdf
)

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
用法:
  ./export-pdf.sh [额外参数...]

默认会执行:
  teacher_content_reminder export-preview \
    --source nasa_news \
    --audience senior \
    --provider router \
    --limit 1 \
    --output-dir .exports \
    --formats markdown,html,json,pdf

示例:
  ./export-pdf.sh
  ./export-pdf.sh --source science_news --limit 2
  ./export-pdf.sh --formats html,pdf
EOF
  exit 0
fi

cd "$ROOT_DIR"
PYTHONPATH=src "$PYTHON_BIN" -m teacher_content_reminder export-preview "${DEFAULT_ARGS[@]}" "$@"

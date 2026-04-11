#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/teacher-content-reminder}"

cd "${APP_DIR}"

export PYTHONPATH=src

.venv/bin/python -m unittest discover -s tests
.venv/bin/teacher-content-reminder doctor
.venv/bin/teacher-content-reminder beta-check --live
.venv/bin/teacher-content-reminder alert-smoke-test --title "Teacher Content Reminder deploy smoke test" --message "Server-side smoke test completed."

python3 - <<'PY'
from urllib.request import urlopen
for path in ("/healthz", "/review", "/alerts", "/api/dashboard-summary"):
    with urlopen(f"http://127.0.0.1:8000{path}") as resp:
        print(path, resp.status, resp.headers.get_content_type())
PY

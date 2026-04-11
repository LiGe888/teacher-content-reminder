#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/teacher-content-reminder}"
APP_USER="${APP_USER:-teacherreminder}"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

install_packages_apt() {
  sudo apt update
  sudo apt install -y git "${PYTHON_BIN}" python3.11-venv python3-pip build-essential nginx
}

install_packages_dnf() {
  sudo dnf install -y git "${PYTHON_BIN}" python3.11-pip gcc gcc-c++ make nginx
}

ensure_packages() {
  if command -v apt >/dev/null 2>&1; then
    install_packages_apt
  elif command -v dnf >/dev/null 2>&1; then
    install_packages_dnf
  else
    echo "Unsupported package manager. Install git, ${PYTHON_BIN}, pip, and nginx manually." >&2
    exit 1
  fi
}

ensure_user() {
  if ! id "${APP_USER}" >/dev/null 2>&1; then
    sudo useradd --system --create-home --shell /bin/bash "${APP_USER}"
  fi
}

prepare_directories() {
  sudo mkdir -p "${APP_DIR}"
  sudo chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
  sudo timedatectl set-timezone Asia/Shanghai
}

print_next_steps() {
  cat <<EOF
Bootstrap complete.

Next steps:
1. Put your repository in ${APP_DIR}
2. Create the virtualenv and install dependencies:
   sudo -u ${APP_USER} bash -lc 'cd ${APP_DIR} && ${PYTHON_BIN} -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -e ".[api]"'
3. Copy deploy/env/production.env.example to ${APP_DIR}/.env and fill in the secrets
4. Copy the systemd files from deploy/systemd/ to /etc/systemd/system/
5. Copy deploy/nginx/teacher-content-reminder.conf to /etc/nginx/conf.d/ and adjust server_name
EOF
}

ensure_packages
ensure_user
prepare_directories
print_next_steps

#!/usr/bin/env bash
set -euo pipefail

SERVER_IP="${SERVER_IP:-47.98.198.2}"
SERVER_USER="${SERVER_USER:-root}"
SERVER_PORT="${SERVER_PORT:-22}"
APP_USER="${APP_USER:-teacherreminder}"
REMOTE_DIR="${REMOTE_DIR:-/opt/teacher-content-reminder}"
DOMAIN="${DOMAIN:-_}"
SYNC_ENV="${SYNC_ENV:-1}"
RUN_POST_CHECK="${RUN_POST_CHECK:-1}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-mirrors.aliyun.com}"

SSH_TARGET="${SERVER_USER}@${SERVER_IP}"
SSH_OPTS=(-p "${SERVER_PORT}")
RSYNC_SSH="ssh -p ${SERVER_PORT}"

LOCAL_ENV_FILE=".env"
REMOTE_ENV_FILE="${REMOTE_DIR}/.env"

echo "=========================================================="
echo "Teacher Content Reminder 阿里云一键部署"
echo "SERVER_IP=${SERVER_IP}"
echo "SERVER_USER=${SERVER_USER}"
echo "REMOTE_DIR=${REMOTE_DIR}"
echo "APP_USER=${APP_USER}"
echo "DOMAIN=${DOMAIN}"
echo "SYNC_ENV=${SYNC_ENV}"
echo "PIP_INDEX_URL=${PIP_INDEX_URL}"
echo "=========================================================="

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync 未安装，请先在本机安装 rsync。" >&2
  exit 1
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "ssh 未安装，请先在本机安装 openssh-client。" >&2
  exit 1
fi

echo
echo "1. 远端准备系统用户和目录..."
ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" "mkdir -p '${REMOTE_DIR}' && id '${APP_USER}' >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash '${APP_USER}'"

echo
echo "2. 同步代码到远端..."
rsync -avz --delete --progress -e "${RSYNC_SSH}" \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.data/' \
  --exclude '.exports/' \
  --exclude '.DS_Store' \
  "${PWD}/" "${SSH_TARGET}:${REMOTE_DIR}/"

if [[ "${SYNC_ENV}" == "1" && -f "${LOCAL_ENV_FILE}" ]]; then
  echo
  echo "3. 同步本地 .env 到远端..."
  rsync -avz -e "${RSYNC_SSH}" "${LOCAL_ENV_FILE}" "${SSH_TARGET}:${REMOTE_ENV_FILE}"
else
  echo
  echo "3. 跳过 .env 同步。"
fi

echo
echo "4. 远端安装依赖、配置服务、执行检查..."
ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" \
  "REMOTE_DIR='${REMOTE_DIR}' APP_USER='${APP_USER}' DOMAIN='${DOMAIN}' SERVER_IP='${SERVER_IP}' REMOTE_ENV_FILE='${REMOTE_ENV_FILE}' RUN_POST_CHECK='${RUN_POST_CHECK}' PIP_INDEX_URL='${PIP_INDEX_URL}' PIP_TRUSTED_HOST='${PIP_TRUSTED_HOST}' bash -s" <<'EOF'
set -euo pipefail

install_packages_apt() {
  apt update
  apt install -y git python3.11 python3.11-venv python3-pip build-essential nginx
}

install_packages_dnf() {
  dnf install -y git python3.11 python3.11-pip gcc gcc-c++ make nginx
}

ensure_packages() {
  if command -v apt >/dev/null 2>&1; then
    install_packages_apt
  elif command -v dnf >/dev/null 2>&1; then
    install_packages_dnf
  else
    echo "Unsupported package manager. Please install git, python3.11, pip, and nginx manually." >&2
    exit 1
  fi
}

ensure_python_venv() {
  if ! command -v python3.11 >/dev/null 2>&1; then
    echo "python3.11 不存在，无法继续。" >&2
    exit 1
  fi
}

run_as_app_user() {
  local command="$1"
  if command -v sudo >/dev/null 2>&1; then
    sudo -u "${APP_USER}" bash -lc "${command}"
  else
    su -s /bin/bash - "${APP_USER}" -c "${command}"
  fi
}

render_systemd_unit() {
  local source_file="$1"
  local target_file="$2"
  sed \
    -e "s#/opt/teacher-content-reminder#${REMOTE_DIR}#g" \
    -e "s#teacherreminder#${APP_USER}#g" \
    "${source_file}" > "${target_file}"
}

render_nginx_conf() {
  local source_file="$1"
  local target_file="$2"
  local server_name="${DOMAIN}"
  if [[ -z "${server_name}" || "${server_name}" == "_" ]]; then
    server_name="${SERVER_IP}"
  fi
  sed -e "s#your-domain.example.com#${server_name}#g" "${source_file}" > "${target_file}"
}

ensure_packages
ensure_python_venv
timedatectl set-timezone Asia/Shanghai || true

mkdir -p "${REMOTE_DIR}"
chown -R "${APP_USER}:${APP_USER}" "${REMOTE_DIR}"

if [[ -f "${REMOTE_ENV_FILE}" ]]; then
  chmod 600 "${REMOTE_ENV_FILE}"
  chown "${APP_USER}:${APP_USER}" "${REMOTE_ENV_FILE}"
  if ! grep -q '^ALERT_VIEW_HOST=' "${REMOTE_ENV_FILE}"; then
    echo "ALERT_VIEW_HOST=http://${SERVER_IP}" >> "${REMOTE_ENV_FILE}"
  fi
fi

run_as_app_user "
  cd '${REMOTE_DIR}' && \
  python3.11 -m venv .venv && \
  .venv/bin/pip install --upgrade pip setuptools wheel --index-url '${PIP_INDEX_URL}' --trusted-host '${PIP_TRUSTED_HOST}' && \
  .venv/bin/pip install -e '.[api]' --no-build-isolation --index-url '${PIP_INDEX_URL}' --trusted-host '${PIP_TRUSTED_HOST}' && \
  mkdir -p .data .exports && \
  PYTHONPATH=src .venv/bin/python -m teacher_content_reminder init-db
"

render_systemd_unit "${REMOTE_DIR}/deploy/systemd/teacher-content-api.service" "/etc/systemd/system/teacher-content-api.service"
render_systemd_unit "${REMOTE_DIR}/deploy/systemd/teacher-content-scheduler.service" "/etc/systemd/system/teacher-content-scheduler.service"
cp "${REMOTE_DIR}/deploy/systemd/teacher-content-scheduler.timer" "/etc/systemd/system/teacher-content-scheduler.timer"

mkdir -p /etc/nginx/conf.d
render_nginx_conf "${REMOTE_DIR}/deploy/nginx/teacher-content-reminder.conf" "/etc/nginx/conf.d/teacher-content-reminder.conf"

systemctl daemon-reload
systemctl enable --now teacher-content-api
systemctl enable --now teacher-content-scheduler.timer
nginx -t
systemctl enable --now nginx
systemctl reload nginx

if [[ "${RUN_POST_CHECK}" == "1" ]]; then
  run_as_app_user "cd '${REMOTE_DIR}' && APP_DIR='${REMOTE_DIR}' ./deploy/scripts/post_deploy_check.sh"
fi

echo "----------------------------------------------------------"
echo "部署完成"
echo "Review UI:  http://${SERVER_IP}/review"
echo "Alerts UI:  http://${SERVER_IP}/alerts"
echo "----------------------------------------------------------"
EOF

echo
echo "=========================================================="
echo "部署闭环已执行完成"
echo "Review UI: http://${SERVER_IP}/review"
echo "Alerts UI: http://${SERVER_IP}/alerts"
echo "=========================================================="

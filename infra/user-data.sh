#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

APP_USER="openmic"
APP_GROUP="openmic"
APP_DIR="/opt/openmicodyssey"
APP_REPO="https://github.com/zwitschi/openmicodyssey-website.git"
APP_BRANCH="main"
PYTHON_BIN="/usr/bin/python3"
VENV_DIR="${APP_DIR}/.venv"

log() {
  echo "[user-data] $1"
}

log "Updating apt cache and installing base packages"
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  nginx \
  python3 \
  python3-venv \
  python3-pip

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  log "Creating application user"
  useradd --system --create-home --shell /bin/bash "${APP_USER}"
fi

log "Preparing application directory"
mkdir -p "${APP_DIR}"
chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"

if [ ! -d "${APP_DIR}/.git" ]; then
  log "Cloning application repository"
  sudo -u "${APP_USER}" git clone --branch "${APP_BRANCH}" --depth 1 "${APP_REPO}" "${APP_DIR}"
else
  log "Updating existing repository checkout"
  sudo -u "${APP_USER}" git -C "${APP_DIR}" fetch --all --prune
  sudo -u "${APP_USER}" git -C "${APP_DIR}" checkout "${APP_BRANCH}"
  sudo -u "${APP_USER}" git -C "${APP_DIR}" reset --hard "origin/${APP_BRANCH}"
fi

log "Setting up Python virtual environment"
if [ ! -d "${VENV_DIR}" ]; then
  sudo -u "${APP_USER}" "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip wheel
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"

log "Writing systemd unit for Gunicorn (entrypoint: app:app)"
cat >/etc/systemd/system/openmicodyssey.service <<'UNIT'
[Unit]
Description=Open Mic Odyssey Gunicorn Service
After=network.target

[Service]
Type=simple
User=openmic
Group=openmic
WorkingDirectory=/opt/openmicodyssey
Environment=PYTHONUNBUFFERED=1
Environment=FLASK_ENV=production
ExecStart=/opt/openmicodyssey/.venv/bin/gunicorn app:app --bind 127.0.0.1:8000 --workers 3
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

log "Configuring Nginx reverse proxy"
cat >/etc/nginx/sites-available/openmicodyssey <<'NGINX'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_buffering off;
    }
}
NGINX

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/openmicodyssey /etc/nginx/sites-enabled/openmicodyssey

log "Enabling and starting services"
systemctl daemon-reload
systemctl enable --now openmicodyssey.service
nginx -t
systemctl enable --now nginx

log "Bootstrap complete"

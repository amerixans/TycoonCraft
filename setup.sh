#!/usr/bin/env bash
# TycoonCraft one-shot deployment with interactive secrets
# - Prompts for OPENAI_API_KEY, DB password, and Django superuser password
# - Stores secrets in /etc/tycooncraft/env (root:www-data 640)
set -euo pipefail

########################
# Basic config
########################
DOMAIN="tycooncraft.com"
WWW_DOMAIN="www.tycooncraft.com"
PUBLIC_IP="159.65.255.82"
REPO_URL="https://github.com/amerixans/tycooncraft.git"
REPO_BRANCH="feature/big-refactor"

APP_ROOT="/var/www/tycooncraft"
BACKEND_DIR="${APP_ROOT}/backend"
FRONTEND_DIR="${APP_ROOT}/frontend"
VENV_DIR="${BACKEND_DIR}/.venv"

DB_NAME="tycooncraft"
DB_USER="tycooncraft"
SYSTEMD_UNIT="/etc/systemd/system/tycooncraft.service"
NGINX_SITE="/etc/nginx/sites-available/tycooncraft"
NGINX_LINK="/etc/nginx/sites-enabled/tycooncraft"
LOG_DIR="/var/log/tycooncraft"
SECRETS_DIR="/etc/tycooncraft"
SECRETS_FILE="${SECRETS_DIR}/env"

# Prompt helper (hidden input)
prompt_secret () {
  local var="$1" prompt="$2" allow_empty="${3:-no}"
  if [[ -n "${!var-}" ]]; then return 0; fi
  local val=""
  while :; do
    read -r -s -p "${prompt}: " val; echo
    if [[ -z "$val" && "$allow_empty" != "yes" ]]; then
      echo "Value cannot be empty."
    else
      break
    fi
  done
  export "$var=$val"
}

# Random generator (fallbacks)
rand_password () {
  python3 - <<'PY' || head -c 32 /dev/urandom | base64 | tr -d '\n'
import secrets,string
alphabet=string.ascii_letters+string.digits+'!@#%^*-_=+'
print(''.join(secrets.choice(alphabet) for _ in range(24)))
PY
}

########################
# Interactive secrets
########################
echo "==> Gathering secrets (input is hidden; press Enter to accept defaults where shown)."

# 1) OpenAI key (optional; can leave blank and set later)
prompt_secret OPENAI_API_KEY "Enter OPENAI_API_KEY (or leave blank to skip)" "yes"

# 2) DB password (required; default generate if blank)
read -r -s -p "Enter PostgreSQL DB password for user '${DB_USER}' (leave blank to auto-generate): " DB_PASSWORD || true
echo
if [[ -z "${DB_PASSWORD:-}" ]]; then
  DB_PASSWORD="$(rand_password)"
  echo "Generated DB password."
fi
export DB_PASSWORD

# 3) Django superuser creds (password can be generated)
read -r -p "Django superuser username [admin]: " DJANGO_SUPERUSER || true
DJANGO_SUPERUSER="${DJANGO_SUPERUSER:-admin}"
read -r -p "Django superuser email [admin@${DOMAIN}]: " DJANGO_SUPEREMAIL || true
DJANGO_SUPEREMAIL="${DJANGO_SUPEREMAIL:-admin@${DOMAIN}}"
read -r -s -p "Django superuser password (leave blank to auto-generate): " DJANGO_SUPERPASS || true
echo
if [[ -z "${DJANGO_SUPERPASS:-}" ]]; then
  DJANGO_SUPERPASS="$(rand_password)"
  echo "Generated Django superuser password."
fi
export DJANGO_SUPERUSER DJANGO_SUPEREMAIL DJANGO_SUPERPASS

########################
# System packages
########################
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export NEEDRESTART_S=1

apt-get update -y
apt-get upgrade -y -o Dpkg::Options::="--force-confnew"
apt-get dist-upgrade -y -o Dpkg::Options::="--force-confnew"

apt-get install -y -o Dpkg::Options::="--force-confnew" \
  python3 python3-pip python3-venv \
  postgresql postgresql-contrib \
  nginx git curl ca-certificates \
  build-essential libpq-dev

########################
# Node 18 (clean install)
########################
dpkg --configure -a || true
apt-get purge -y npm nodejs nodejs-doc libnode-dev libnode72 node-gyp || true
apt-get autoremove -y
apt-get clean
rm -rf /usr/include/node /usr/lib/node_modules /usr/local/bin/node /usr/local/bin/npm /usr/bin/node /usr/bin/npm || true
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs
node -v && npm -v

########################
# Fetch app
########################
mkdir -p /var/www
rm -rf "${APP_ROOT}" || true
git clone -b "${REPO_BRANCH}" --single-branch --depth 1 "${REPO_URL}" "${APP_ROOT}"

########################
# Backend venv & deps
########################
cd "${BACKEND_DIR}"
python3 -m venv "${VENV_DIR}"
chmod 755 "${VENV_DIR}/bin/"* || true
. "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install --upgrade --no-cache-dir gunicorn

########################
# Secrets file (/etc/tycooncraft/env)
########################
mkdir -p "${SECRETS_DIR}"
umask 027
cat > "${SECRETS_FILE}" <<EOF
# Loaded by systemd and our manage.py steps
OPENAI_API_KEY=${OPENAI_API_KEY:-}
DB_PASSWORD=${DB_PASSWORD}
DJANGO_SUPERUSER_PASSWORD=${DJANGO_SUPERPASS}
EOF
chown root:www-data "${SECRETS_FILE}"
chmod 640 "${SECRETS_FILE}"

########################
# Backend .env (non-secret + generated DJANGO_SECRET_KEY)
########################
DJANGO_SECRET_KEY="$(python3 - <<'PY'
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
PY
)"
cat > "${BACKEND_DIR}/.env" <<EOF
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DEBUG=False
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_HOST=localhost
DB_PORT=5432
ALLOWED_HOSTS=${DOMAIN},${WWW_DOMAIN},127.0.0.1,localhost,${PUBLIC_IP}
EOF

########################
# Postgres: role & DB
########################
systemctl enable --now postgresql
sudo -u postgres psql <<SQL
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
      CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
   END IF;
END
\$\$;
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}') THEN
      CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
   END IF;
END
\$\$;
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

########################
# Django: migrate & collectstatic
########################
# Export both env files for manage.py
set -a
source "${SECRETS_FILE}"
source "${BACKEND_DIR}/.env"
set +a

mkdir -p game/migrations && touch game/migrations/__init__.py || true
python manage.py makemigrations --noinput || true
python manage.py migrate --noinput
python manage.py initialize_starter_objects || true
python - <<PY
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','tycooncraft.settings')
from django.contrib.auth import get_user_model
User=get_user_model()
u=User.objects.filter(username='${DJANGO_SUPERUSER}').first()
if not u:
    from django.core.management import call_command
    call_command('createsuperuser', interactive=False,
                 username='${DJANGO_SUPERUSER}',
                 email='${DJANGO_SUPEREMAIL}',
                 verbosity=0)
    u=User.objects.get(username='${DJANGO_SUPERUSER}')
    u.set_password('${DJANGO_SUPERPASS}')
    u.save()
PY
python manage.py collectstatic --noinput

########################
# Frontend build
########################
cd "${FRONTEND_DIR}"
rm -rf node_modules package-lock.json
npm install
REACT_APP_API_URL="http://${DOMAIN}/api" npm run build

########################
# Nginx
########################
cat > "${NGINX_SITE}" <<'EOF'
server {
    listen 80;
    server_name tycooncraft.com www.tycooncraft.com;

    client_max_body_size 100M;

    location /static/admin/       { alias /var/www/tycooncraft/backend/staticfiles/admin/; }
    location /static/rest_framework/ { alias /var/www/tycooncraft/backend/staticfiles/rest_framework/; }
    location /media/              { alias /var/www/tycooncraft/backend/media/; }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /var/www/tycooncraft/backend/staticfiles/;
    }

    location / {
        root /var/www/tycooncraft/frontend/build;
        try_files $uri $uri/ /index.html;
    }
}
EOF
ln -sf "${NGINX_SITE}" "${NGINX_LINK}"
rm -f /etc/nginx/sites-enabled/default

chown -R www-data:www-data "${APP_ROOT}"
find "${APP_ROOT}" -type d -exec chmod 755 {} \;
find "${APP_ROOT}" -type f -exec chmod 644 {} \;

nginx -t
systemctl reload nginx

########################
# Gunicorn (systemd)
########################
mkdir -p "${LOG_DIR}"
chown -R www-data:www-data "${LOG_DIR}"

cat > "${SYSTEMD_UNIT}" <<EOF
[Unit]
Description=TycoonCraft Django (gunicorn)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${BACKEND_DIR}
EnvironmentFile=${SECRETS_FILE}
EnvironmentFile=${BACKEND_DIR}/.env
ExecStart=${VENV_DIR}/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 --timeout 120 \\
  --access-logfile ${LOG_DIR}/access.log --error-logfile ${LOG_DIR}/error.log \\
  tycooncraft.wsgi:application
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "${SYSTEMD_UNIT}"
systemctl daemon-reload
systemctl enable --now tycooncraft

########################
# Smoke checks
########################
curl -sSf -I http://127.0.0.1:8000/ >/dev/null || true
curl -sSf -I http://127.0.0.1:8000/api/game-state/ >/dev/null || true
curl -sSf -I -H "Host: ${DOMAIN}" http://127.0.0.1/ >/dev/null

echo "✅ Done. Secrets stored at ${SECRETS_FILE} (root:www-data 640)."
echo "   Superuser: ${DJANGO_SUPERUSER} / ${DJANGO_SUPERPASS}"
echo "   If you pasted a real OpenAI key earlier, rotate it now."

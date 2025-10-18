# TycoonCraft Deployment Guide

TycoonCraft ships with a Django API, React frontend, Gunicorn, and Nginx. This document explains how to deploy the production stack onto an Ubuntu 22.04 droplet, starting with the automated script path and then detailing the manual process.

> All commands assume you are running as `root` (or prefix them with `sudo`).

## Prerequisites

- Ubuntu 22.04 LTS droplet with at least 2 vCPUs, 2 GB RAM, and SSH access
- Domain pointed at the droplet IP (for example `tycooncraft.com`)
- OpenAI API key with access to `gpt-5-mini` and `gpt-image-1-mini`
- Strong passwords for the PostgreSQL role and Django admin account
- Outbound HTTPS access (git clone, package downloads, OpenAI)

## Recommended Path: `deploy.sh`

The repository includes `deploy.sh`, a non-interactive deployment script that provisions the full stack. Run it on a fresh droplet or when rebuilding from scratch.

### 1. Fetch the deployment scripts

```bash
ssh root@your_droplet_ip
apt update && apt install -y git
git clone https://github.com/amerixans/tycooncraft.git /opt/tycooncraft-deployer
cd /opt/tycooncraft-deployer
chmod +x deploy.sh update.sh
```

> Replace the repository URL with your fork if you maintain a custom branch.

### 2. Export required environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DB_PASSWORD` | ✅ | Password for the PostgreSQL role `tycooncraft` |
| `OPENAI_API_KEY` | ✅ | Production OpenAI key used for crafting and image generation |
| `DJANGO_ADMIN_PASSWORD` | ⭕ | Overrides the default admin password (falls back to `DB_PASSWORD`) |
| `DOMAIN` | ⭕ | Public domain used for ALLOWED_HOSTS/CORS (defaults to `tycooncraft.com`) |
| `SERVER_IP` | ⭕ | Public IP for fallback CORS/CSRF entries |
| `ADMIN_EMAIL` | ⭕ | Email for Let's Encrypt registration |
| `SLACK_WEBHOOK_URL` | ⭕ | Slack webhook for deployment notifications |

```bash
export DB_PASSWORD="change-me"
export OPENAI_API_KEY="sk-..."
export DOMAIN="tycooncraft.com"
export SERVER_IP="203.0.113.10"
# export DJANGO_ADMIN_PASSWORD="..."
# export ADMIN_EMAIL="ops@tycooncraft.com"
# export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

### 3. Run the deployment

```bash
./deploy.sh production          # choose the branch name you want to deploy
```

Pass `no-ssl` (or `skip-ssl`) as a second argument to skip Let's Encrypt certificate provisioning.

### 4. What the script configures

- Updates Ubuntu packages and installs Python 3, PostgreSQL, Nginx, Node.js 18, fail2ban, and logrotate
- Creates `/var/backups/tycooncraft`, snapshots any existing deployment, and clones the repo to `/var/www/tycooncraft`
- Provisions PostgreSQL (`tycooncraft` database/user) and runs Django migrations, seeding starter data and upgrade keys
- Creates a Pro-enabled admin account, collects static files, and builds the React frontend
- Writes `/etc/systemd/system/tycooncraft.service` for Gunicorn, with log rotation and health checks
- Configures Nginx with security headers, gzip, API proxying, and React static hosting
- Optionally runs Certbot for HTTPS, enables fail2ban rules, and verifies all services are healthy
- Posts Slack notifications when `SLACK_WEBHOOK_URL` is provided

### 5. Immediate follow-up tasks

```bash
systemctl status tycooncraft
journalctl -u tycooncraft -n 50
tail -n 100 /var/log/nginx/error.log
curl -I https://tycooncraft.com     # replace with your domain
```

Rotate the admin password right away:

```bash
cd /var/www/tycooncraft/backend
source .venv/bin/activate
python manage.py changepassword admin
```

For future releases, reuse the same checkout and run the update script:

```bash
cd /opt/tycooncraft-deployer
./update.sh production
```

---

## Manual Deployment Reference

If you need a highly customized install, implement the steps below. They mirror what `deploy.sh` performs.

### 1. System preparation

```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv postgresql nginx git curl fail2ban logrotate
mkdir -p /var/backups/tycooncraft
```

Optional hardening:

```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### 2. Clone the application

```bash
cd /var/www
git clone https://github.com/amerixans/tycooncraft.git
cd tycooncraft
```

Confirm you are on the intended branch (`git checkout production`, etc.).

### 3. Configure PostgreSQL

```bash
sudo -u postgres psql -c "CREATE DATABASE tycooncraft;"
sudo -u postgres psql -c "CREATE USER tycooncraft WITH PASSWORD 'strong_password_here';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE tycooncraft TO tycooncraft;"
```

### 4. Backend setup

```bash
cd /var/www/tycooncraft/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

Generate a Django secret key:

```bash
SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
```

Create `backend/.env` (adjust values for your environment):

```bash
cat > /var/www/tycooncraft/backend/.env <<EOF
DJANGO_SECRET_KEY=$SECRET_KEY
DEBUG=False
DB_NAME=tycooncraft
DB_USER=tycooncraft
DB_PASSWORD=strong_password_here
DB_HOST=localhost
DB_PORT=5432
CONN_MAX_AGE=600
OPENAI_API_KEY=sk-...
DOMAIN=tycooncraft.com
SERVER_IP=203.0.113.10
CORS_ALLOWED_ORIGINS=http://tycooncraft.com,https://tycooncraft.com,http://www.tycooncraft.com,https://www.tycooncraft.com
CSRF_TRUSTED_ORIGINS=http://tycooncraft.com,https://tycooncraft.com,http://www.tycooncraft.com,https://www.tycooncraft.com
EOF
unset SECRET_KEY
```

Run migrations and seed content:

```bash
python manage.py makemigrations game
python manage.py migrate
python manage.py initialize_starter_objects
python manage.py generate_upgrade_keys
DJANGO_SUPERUSER_PASSWORD="change-me" python manage.py create_admin_account
python manage.py collectstatic --noinput
```

Optional: run tests (`python manage.py test --no-input`).

### 5. Frontend build

```bash
cd /var/www/tycooncraft/frontend
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs
rm -rf node_modules package-lock.json
npm install
REACT_APP_API_URL=https://tycooncraft.com/api npm run build    # update with your domain/API host
```

### 6. File ownership

```bash
chown -R www-data:www-data /var/www/tycooncraft
```

Ensure the Gunicorn binary is executable (normally already true):

```bash
chmod +x /var/www/tycooncraft/backend/.venv/bin/gunicorn
```

### 7. Gunicorn systemd service

Create `/etc/systemd/system/tycooncraft.service`:

```
[Unit]
Description=TycoonCraft Django (gunicorn)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/tycooncraft/backend
EnvironmentFile=/var/www/tycooncraft/backend/.env
ExecStart=/var/www/tycooncraft/backend/.venv/bin/gunicorn \
  --workers 5 \
  --bind 127.0.0.1:8000 \
  --timeout 120 \
  --access-logfile /var/log/tycooncraft-access.log \
  --error-logfile /var/log/tycooncraft-error.log \
  tycooncraft.wsgi:application
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

- Adjust `--workers` to `(2 × CPU cores) + 1`, capped at 9.
- Logs live in `/var/log/tycooncraft-access.log` and `/var/log/tycooncraft-error.log`.

```bash
touch /var/log/tycooncraft-access.log /var/log/tycooncraft-error.log
chown www-data:www-data /var/log/tycooncraft-*.log
systemctl daemon-reload
systemctl enable --now tycooncraft
```

### 8. Nginx configuration

Create `/etc/nginx/sites-available/tycooncraft`:

```
server {
    listen 80;
    server_name tycooncraft.com www.tycooncraft.com;

    client_max_body_size 100M;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json image/svg+xml;

    location /static/admin/ {
        alias /var/www/tycooncraft/backend/staticfiles/admin/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /static/rest_framework/ {
        alias /var/www/tycooncraft/backend/staticfiles/rest_framework/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/tycooncraft/backend/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/tycooncraft/frontend/build/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        root /var/www/tycooncraft/frontend/build;
        try_files $uri $uri/ /index.html;
        expires -1;
        add_header Cache-Control "no-cache, must-revalidate";
    }
}
```

Enable the site:

```bash
ln -sf /etc/nginx/sites-available/tycooncraft /etc/nginx/sites-enabled/tycooncraft
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
```

### 9. HTTPS (recommended)

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d tycooncraft.com -d www.tycooncraft.com --non-interactive --agree-tos --email admin@tycooncraft.com --redirect
certbot renew --dry-run
```

### 10. Log rotation and fail2ban (optional hardening)

`/etc/logrotate.d/tycooncraft`:

```
/var/log/tycooncraft-*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload tycooncraft >/dev/null 2>&1 || true
    endscript
}
```

`/etc/fail2ban/jail.d/nginx-tycooncraft.conf`:

```
[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-noscript]
enabled = true
port = http,https
logpath = /var/log/nginx/access.log

[nginx-badbots]
enabled = true
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 2

[nginx-noproxy]
enabled = true
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 2
```

Enable and restart:

```bash
systemctl enable --now fail2ban
```

---

## Validation Checklist

- `curl -sSf http://127.0.0.1/api/` returns JSON from the Django API
- `https://tycooncraft.com` (or your domain) loads the React build without mixed-content warnings
- Django admin is reachable at `/admin/` and uses the hardened password
- Uploaded/generated media appears under `/var/www/tycooncraft/backend/media/objects`
- Logs reach `/var/log/tycooncraft-access.log` and `/var/log/tycooncraft-error.log`

## Routine Maintenance

- `./update.sh production` – pulls latest code, rebuilds, and restarts (backs up first)
- `journalctl -u tycooncraft -f` – follow Gunicorn logs
- `tail -f /var/log/nginx/error.log` – monitor Nginx errors
- `sudo -u postgres pg_dump tycooncraft > /var/backups/tycooncraft/db_$(date +%Y%m%d).sql` – manual DB backup
- `du -sh /var/www/tycooncraft/backend/media/objects` – watch image storage growth
- `apt update && apt upgrade` – keep the OS patched

## Troubleshooting

- Service down: `systemctl status tycooncraft` then `journalctl -u tycooncraft -n 100`
- HTTP 502/504: inspect `/var/log/nginx/error.log` and confirm Gunicorn is running
- Database login failures: `sudo -u postgres psql -c "\du"` and `\l` to verify roles/databases
- OpenAI errors: make sure `OPENAI_API_KEY` is present in `/var/www/tycooncraft/backend/.env` and not rate-limited
- Out-of-memory: add swap (`fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`) or upgrade the droplet

With these steps complete, TycoonCraft runs at your configured domain behind Nginx and Gunicorn. Use the deployment scripts for future releases and keep credentials stored securely.

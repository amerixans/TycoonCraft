#!/bin/bash
set -euo pipefail

# TycoonCraft Deployment Script

# Prevent interactive prompts
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export NEEDRESTART_SUSPEND=1

# Configure needrestart to not prompt
mkdir -p /etc/needrestart
cat > /etc/needrestart/needrestart.conf << 'EOF'
$nrconf{restart} = 'a';
$nrconf{kernelhints} = 0;
EOF

# Check for required environment variables
if [ -z "${DB_PASSWORD:-}" ]; then
    echo "ERROR: DB_PASSWORD environment variable is required"
    exit 1
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "ERROR: OPENAI_API_KEY environment variable is required"
    exit 1
fi

# Optional: Set default values for other variables
SERVER_IP="${SERVER_IP:-159.65.255.82}"
DOMAIN="${DOMAIN:-tycooncraft.com}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@tycooncraft.com}"

echo "Starting TycoonCraft deployment..."

# Configure apt for non-interactive use
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export NEEDRESTART_S=1

# System updates
echo "Updating system packages..."
apt-get update -y
apt-get upgrade -y -o Dpkg::Options::="--force-confnew"
apt-get dist-upgrade -y -o Dpkg::Options::="--force-confnew"

# Install base dependencies
echo "Installing dependencies..."
apt-get install -y -o Dpkg::Options::="--force-confnew" \
  python3 python3-pip python3-venv postgresql nginx git curl

# Clone repository
echo "Cloning repository..."
cd /var/www
if [ -d "tycooncraft" ]; then
    echo "Directory exists, removing..."
    rm -rf tycooncraft
fi
git clone -b production --single-branch --depth 1 https://github.com/amerixans/tycooncraft.git
cd tycooncraft

# Setup PostgreSQL
echo "Setting up PostgreSQL..."
sudo -u postgres psql -c "CREATE DATABASE tycooncraft;" || true
sudo -u postgres psql -c "CREATE USER tycooncraft WITH PASSWORD '${DB_PASSWORD}';" || true
sudo -u postgres psql -c "ALTER ROLE tycooncraft SET client_encoding TO 'utf8';" || true
sudo -u postgres psql -c "ALTER ROLE tycooncraft SET default_transaction_isolation TO 'read committed';" || true
sudo -u postgres psql -c "ALTER ROLE tycooncraft SET timezone TO 'UTC';" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE tycooncraft TO tycooncraft;" || true

# Setup Python backend
echo "Setting up Python backend..."
cd /var/www/tycooncraft/backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

# Create .env file
echo "Creating environment configuration..."
cat > .env << EOF
DJANGO_SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
DEBUG=False
DB_NAME=tycooncraft
DB_USER=tycooncraft
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=localhost
DB_PORT=5432
OPENAI_API_KEY=${OPENAI_API_KEY}
ALLOWED_HOSTS=${DOMAIN},127.0.0.1,localhost,${SERVER_IP}
EOF

# Run Django migrations
echo "Running Django migrations..."
mkdir -p game/migrations
touch game/migrations/__init__.py
python manage.py makemigrations game
python manage.py migrate

# Initialize data
echo "Initializing starter objects..."
python manage.py initialize_starter_objects

# Create superuser
echo "Creating superuser..."
export DJANGO_SUPERUSER_PASSWORD="${DB_PASSWORD}"
python manage.py createsuperuser --noinput --username admin --email "${ADMIN_EMAIL}" || true

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Clean up old Node installation
echo "Cleaning up old Node.js installation..."
sudo dpkg --configure -a || true
sudo apt-get purge -y npm nodejs nodejs-doc libnode-dev libnode72 node-gyp 2>/dev/null || true
sudo apt-get autoremove -y
sudo apt-get clean
sudo rm -rf /usr/include/node /usr/lib/node_modules \
            /usr/local/bin/node /usr/local/bin/npm \
            /usr/bin/node /usr/bin/npm

# Install Node 18
echo "Installing Node.js 18..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify Node installation
echo "Node version: $(node -v)"
echo "NPM version: $(npm -v)"

# Build React frontend
echo "Building React frontend..."
cd /var/www/tycooncraft/frontend
rm -rf node_modules package-lock.json
npm install
REACT_APP_API_URL=https://${DOMAIN}/api npm run build

# Configure Nginx
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/tycooncraft << 'NGINXEOF'
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER www.DOMAIN_PLACEHOLDER;

    client_max_body_size 100M;

    # Django admin static files
    location /static/admin/ {
        alias /var/www/tycooncraft/backend/staticfiles/admin/;
    }

    # Django REST framework static files
    location /static/rest_framework/ {
        alias /var/www/tycooncraft/backend/staticfiles/rest_framework/;
    }

    location /media/ {
        alias /var/www/tycooncraft/backend/media/;
    }

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

    # React app static files
    location /static/ {
        alias /var/www/tycooncraft/frontend/build/static/;
    }

    # React app root
    location / {
        root /var/www/tycooncraft/frontend/build;
        try_files $uri $uri/ /index.html;
    }
}
NGINXEOF

# Replace domain placeholder
sed -i "s/DOMAIN_PLACEHOLDER/${DOMAIN}/g" /etc/nginx/sites-available/tycooncraft

# Enable site
ln -sf /etc/nginx/sites-available/tycooncraft /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Set permissions
echo "Setting permissions..."
sudo chown -R www-data:www-data /var/www/tycooncraft
find /var/www/tycooncraft -type d -exec chmod 755 {} \;
find /var/www/tycooncraft -type f -exec chmod 644 {} \;

# Make venv executables runnable
chmod 755 /var/www/tycooncraft/backend/.venv/bin/* 2>/dev/null || true

# Test and reload Nginx
echo "Testing Nginx configuration..."
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

echo "=========================================="
echo "Setting up SSL/HTTPS..."
echo "=========================================="


# Install certbot
apt-get install -y certbot python3-certbot-nginx

# Get SSL certificate (requires domain pointing to this server)
certbot --nginx \
  -d ${DOMAIN} \
  -d www.${DOMAIN} \
  --non-interactive \
  --agree-tos \
  --email ${ADMIN_EMAIL} \
  --redirect

# Test renewal
certbot renew --dry-run

echo "SSL setup complete! Site is now HTTPS"


# Create systemd service for Gunicorn
echo "Creating systemd service..."
cat > /etc/systemd/system/tycooncraft.service << 'SERVICEEOF'
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
  --workers 3 \
  --bind 127.0.0.1:8000 \
  --timeout 120 \
  --access-logfile /var/log/tycooncraft-access.log \
  --error-logfile /var/log/tycooncraft-error.log \
  tycooncraft.wsgi:application
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Fix permissions for www-data to execute venv
echo "Fixing venv permissions..."
chown -R www-data:www-data /var/www/tycooncraft/backend/.venv
chmod +x /var/www/tycooncraft/backend/.venv/bin/gunicorn

# Test gunicorn manually first
echo "Testing gunicorn..."
cd /var/www/tycooncraft/backend
sudo -u www-data bash -c "source .venv/bin/activate && gunicorn --bind 127.0.0.1:8001 --timeout 30 --check-config tycooncraft.wsgi:application"

# Create log files with proper permissions
touch /var/log/tycooncraft-access.log /var/log/tycooncraft-error.log
chown www-data:www-data /var/log/tycooncraft-*.log

# Start the service
echo "Starting TycoonCraft service..."
systemctl daemon-reload
systemctl enable tycooncraft
systemctl start tycooncraft

# Wait for service to initialize
sleep 5

# Check status and show errors if failed
if ! systemctl is-active --quiet tycooncraft; then
    echo "ERROR: Service failed to start. Checking logs..."
    journalctl -u tycooncraft -n 50 --no-pager
    exit 1
fi

systemctl status tycooncraft --no-pager

# Verify deployment
echo "Verifying deployment..."
ls -lah /var/www/tycooncraft/frontend/build/index.html
curl -I -H "Host: ${DOMAIN}" http://127.0.0.1/ || true



echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo "Site: http://${DOMAIN}"
echo "Admin: http://${DOMAIN}/admin"
echo "API: http://${DOMAIN}/api"
echo ""
echo "Admin credentials:"
echo "  Username: admin"
echo "  Password: [same as DB_PASSWORD]"
echo ""
echo "To check logs:"
echo "  sudo journalctl -u tycooncraft -f"
echo "  sudo tail -f /var/log/tycooncraft-*.log"
echo "=========================================="

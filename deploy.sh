#!/bin/bash
set -euo pipefail

# TycoonCraft Deployment Script - Enhanced Version
# Usage: ./deploy.sh [branch] [ssl_option]
# Examples: 
#   ./deploy.sh production          # Deploy production with SSL
#   ./deploy.sh dev no-ssl          # Deploy dev without SSL
#   ./deploy.sh staging skip-ssl    # Deploy staging without SSL

# ============================================================================
# DEPLOYMENT LOCK - Prevent concurrent deployments
# ============================================================================
exec 200>/tmp/tycooncraft_deploy.lock
if ! flock -n 200; then
    echo "ERROR: Another deployment is already in progress"
    echo "If you're sure no deployment is running, remove: /tmp/tycooncraft_deploy.lock"
    exit 1
fi

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

# ============================================================================
# CONFIGURATION
# ============================================================================

# Get branch from argument or default to 'dev'
BRANCH="${1:-dev}"

# Get SSL option from second argument (default is to enable SSL)
SSL_OPTION="${2:-ssl}"
ENABLE_SSL=true
if [[ "$SSL_OPTION" == "no-ssl" ]] || [[ "$SSL_OPTION" == "skip-ssl" ]]; then
    ENABLE_SSL=false
fi

if [ "$ENABLE_SSL" = true ]; then
    DJANGO_DEBUG_VALUE="False"
    API_PROTOCOL="https"
    SESSION_COOKIE_SECURE_VALUE="True"
    CSRF_COOKIE_SECURE_VALUE="True"
    SECURE_SSL_REDIRECT_VALUE="True"
else
    DJANGO_DEBUG_VALUE="False"
    API_PROTOCOL="http"
    SESSION_COOKIE_SECURE_VALUE="False"
    CSRF_COOKIE_SECURE_VALUE="False"
    SECURE_SSL_REDIRECT_VALUE="False"
fi

# Version pinning for better reproducibility
NODE_VERSION="18"  # Major version - allows minor updates
BACKUP_RETENTION_DAYS=7

# ============================================================================
# ENVIRONMENT VALIDATION
# ============================================================================

echo "Validating environment..."

# Required environment variables
required_vars=("DB_PASSWORD" "OPENAI_API_KEY" "DJANGO_ADMIN_PASSWORD")
for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var environment variable is required"
        echo ""
        echo "Required variables:"
        echo "  - DB_PASSWORD: Database password"
        echo "  - OPENAI_API_KEY: OpenAI API key"
        echo "  - DJANGO_ADMIN_PASSWORD: Password assigned to the admin account"
        echo ""
        echo "Optional variables:"
        echo "  - DJANGO_SUPERUSER_USERNAME: Admin username (defaults to 'admin')"
        echo "  - SERVER_IP: Server IP address"
        echo "  - DOMAIN: Domain name"
        echo "  - ADMIN_EMAIL: Admin email"
        echo "  - SLACK_WEBHOOK_URL: For deployment notifications"
        exit 1
    fi
done

# Optional: Set default values for other variables
SERVER_IP="${SERVER_IP:-159.65.255.82}"
DOMAIN="${DOMAIN:-tycooncraft.com}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@tycooncraft.com}"
DJANGO_ADMIN_PASSWORD="${DJANGO_ADMIN_PASSWORD}"
DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"

# Validate domain format
if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$ ]]; then
    echo "WARNING: DOMAIN '$DOMAIN' may not be a valid domain name"
fi

echo "=========================================="
echo "TycoonCraft Deployment"
echo "=========================================="
echo "Target branch: $BRANCH"
echo "Domain: $DOMAIN"
echo "Server IP: $SERVER_IP"
if [ "$ENABLE_SSL" = true ]; then
    echo "SSL/HTTPS: Enabled"
else
    echo "SSL/HTTPS: Disabled (HTTP only)"
fi
echo "=========================================="
echo ""

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

send_notification() {
    local message="$1"
    local status="${2:-info}"
    
    echo "$message"
    
    # Send to Slack if webhook is configured
    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        local color="good"
        if [ "$status" = "error" ]; then
            color="danger"
        elif [ "$status" = "warning" ]; then
            color="warning"
        fi
        
        curl -X POST "$SLACK_WEBHOOK_URL" \
            -H 'Content-Type: application/json' \
            -d "{\"text\":\"$message\",\"color\":\"$color\"}" \
            --silent --fail || true
    fi
}

cleanup_old_backups() {
    echo "Cleaning up old backups (older than $BACKUP_RETENTION_DAYS days)..."
    find /var/backups/tycooncraft -name "*.sql" -mtime +$BACKUP_RETENTION_DAYS -delete 2>/dev/null || true
    find /var/backups/tycooncraft -type d -name "tycooncraft.backup.*" -mtime +$BACKUP_RETENTION_DAYS -exec rm -rf {} + 2>/dev/null || true
}

# ============================================================================
# SYSTEM PREPARATION
# ============================================================================

send_notification "🚀 Starting deployment of branch: $BRANCH"

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
  python3 python3-pip python3-venv postgresql nginx git curl \
  fail2ban logrotate

# ============================================================================
# BACKUP EXISTING DEPLOYMENT
# ============================================================================

echo "Creating backup directory..."
mkdir -p /var/backups/tycooncraft

# Backup existing application if it exists
if [ -d "/var/www/tycooncraft" ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_DIR="/var/backups/tycooncraft/tycooncraft.backup.$TIMESTAMP"
    
    echo "Backing up existing deployment to: $BACKUP_DIR"
    cp -a /var/www/tycooncraft "$BACKUP_DIR"
    
    # Backup database
    if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw tycooncraft; then
        echo "Backing up database..."
        sudo -u postgres pg_dump tycooncraft > "/var/backups/tycooncraft/db_backup_$TIMESTAMP.sql"
        echo "Database backup saved to: /var/backups/tycooncraft/db_backup_$TIMESTAMP.sql"
    fi
fi

# Clean up old backups
cleanup_old_backups

# ============================================================================
# CLONE REPOSITORY
# ============================================================================

echo "Cloning repository from branch: $BRANCH..."
cd /var/www
if [ -d "tycooncraft" ]; then
    echo "Removing old deployment..."
    rm -rf tycooncraft
fi
git clone -b $BRANCH --single-branch --depth 1 https://github.com/amerixans/tycooncraft.git
cd tycooncraft

# Store git commit hash for tracking
GIT_COMMIT=$(git rev-parse HEAD)
echo "Deployed commit: $GIT_COMMIT"
echo "$GIT_COMMIT" > /var/www/tycooncraft/.deployed_commit

# ============================================================================
# POSTGRESQL SETUP
# ============================================================================

echo "Setting up PostgreSQL..."
sudo -u postgres psql -c "CREATE DATABASE tycooncraft;" || true
sudo -u postgres psql -c "CREATE USER tycooncraft WITH PASSWORD '${DB_PASSWORD}';" || true
sudo -u postgres psql -c "ALTER ROLE tycooncraft SET client_encoding TO 'utf8';" || true
sudo -u postgres psql -c "ALTER ROLE tycooncraft SET default_transaction_isolation TO 'read committed';" || true
sudo -u postgres psql -c "ALTER ROLE tycooncraft SET timezone TO 'UTC';" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE tycooncraft TO tycooncraft;" || true

# ============================================================================
# PYTHON BACKEND SETUP
# ============================================================================

echo "Setting up Python backend..."
cd /var/www/tycooncraft/backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

# Install gunicorn if not in requirements
pip install gunicorn

# Create .env file
echo "Creating environment configuration..."
cat > .env << EOF
DJANGO_SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
DEBUG=${DJANGO_DEBUG_VALUE}
DB_NAME=tycooncraft
DB_USER=tycooncraft
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=localhost
DB_PORT=5432
CONN_MAX_AGE=600
OPENAI_API_KEY=${OPENAI_API_KEY}
ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN},127.0.0.1,localhost,${SERVER_IP}
DOMAIN=${DOMAIN}
SERVER_IP=${SERVER_IP}
CORS_ALLOWED_ORIGINS=http://${DOMAIN},https://${DOMAIN},http://www.${DOMAIN},https://www.${DOMAIN},http://${SERVER_IP},https://${SERVER_IP}
CSRF_TRUSTED_ORIGINS=http://${DOMAIN},https://${DOMAIN},http://www.${DOMAIN},https://www.${DOMAIN},http://${SERVER_IP},https://${SERVER_IP}
SESSION_COOKIE_SECURE=${SESSION_COOKIE_SECURE_VALUE}
CSRF_COOKIE_SECURE=${CSRF_COOKIE_SECURE_VALUE}
SECURE_SSL_REDIRECT=${SECURE_SSL_REDIRECT_VALUE}
DJANGO_ADMIN_PASSWORD=${DJANGO_ADMIN_PASSWORD}
DJANGO_SUPERUSER_USERNAME=${DJANGO_SUPERUSER_USERNAME}
DJANGO_SUPERUSER_PASSWORD=${DJANGO_ADMIN_PASSWORD}
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

# Generate upgrade keys
echo "Generating upgrade keys..."
python manage.py generate_upgrade_keys

# Create admin account with pro status
echo "Creating admin account with pro status..."
export DJANGO_SUPERUSER_PASSWORD="${DJANGO_ADMIN_PASSWORD}"
export DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME}"
python manage.py create_admin_account

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run tests if test suite exists (optional)
if [ -d "game/tests" ] || grep -q "TestCase" game/*.py 2>/dev/null; then
    echo "Running tests..."
    if python manage.py test --no-input; then
        echo "✓ Tests passed"
    else
        echo "WARNING: Tests failed - continuing anyway"
        send_notification "⚠️ Deployment tests failed for $BRANCH" "warning"
    fi
fi

# ============================================================================
# NODE.JS SETUP
# ============================================================================

# Clean up old Node installation
echo "Cleaning up old Node.js installation..."
sudo dpkg --configure -a || true
sudo apt-get purge -y npm nodejs nodejs-doc libnode-dev libnode72 node-gyp 2>/dev/null || true
sudo apt-get autoremove -y
sudo apt-get clean
sudo rm -rf /usr/include/node /usr/lib/node_modules \
            /usr/local/bin/node /usr/local/bin/npm \
            /usr/bin/node /usr/bin/npm

# Install Node (version pinned)
echo "Installing Node.js ${NODE_VERSION}..."
curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify Node installation
NODE_INSTALLED_VERSION=$(node -v)
NPM_INSTALLED_VERSION=$(npm -v)
echo "Node version: $NODE_INSTALLED_VERSION"
echo "NPM version: $NPM_INSTALLED_VERSION"

# ============================================================================
# REACT FRONTEND BUILD
# ============================================================================

echo "Building React frontend..."
cd /var/www/tycooncraft/frontend

# Check if we can skip the build (optimization)
SHOULD_BUILD=true
FRONTEND_HASH=$(git log -1 --format=%H -- .)
PACKAGE_JSON_HASH=$(md5sum package.json 2>/dev/null | cut -d' ' -f1 || echo "none")

if [ -f .last_build_info ]; then
    source .last_build_info
    if [ "$LAST_FRONTEND_HASH" = "$FRONTEND_HASH" ] && \
       [ "$LAST_PACKAGE_JSON_HASH" = "$PACKAGE_JSON_HASH" ] && \
       [ -d "build" ] && [ -f "build/index.html" ]; then
        echo "Frontend unchanged since last build, checking if build exists..."
        SHOULD_BUILD=false
        echo "✓ Skipping frontend build (no changes detected)"
    fi
fi

if [ "$SHOULD_BUILD" = true ]; then
    echo "Building frontend (changes detected or first build)..."
    rm -rf node_modules package-lock.json
    npm install
    
    # Ensure node_modules binaries are executable
    chmod +x node_modules/.bin/* 2>/dev/null || true
    
    REACT_APP_API_URL=${API_PROTOCOL}://${DOMAIN}/api npm run build
    
    # Store build info for next deployment
    cat > .last_build_info << EOF
LAST_FRONTEND_HASH="$FRONTEND_HASH"
LAST_PACKAGE_JSON_HASH="$PACKAGE_JSON_HASH"
EOF
fi

# Verify build succeeded
if [ ! -f "build/index.html" ]; then
    echo "ERROR: Frontend build failed - build/index.html not found"
    send_notification "❌ Frontend build failed for $BRANCH" "error"
    exit 1
fi

# ============================================================================
# NGINX CONFIGURATION
# ============================================================================

echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/tycooncraft << 'NGINXEOF'
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER www.DOMAIN_PLACEHOLDER;

    client_max_body_size 100M;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript 
               application/x-javascript application/xml+rss 
               application/json application/javascript 
               application/xml image/svg+xml;
    gzip_disable "msie6";

    # Django admin static files
    location /static/admin/ {
        alias /var/www/tycooncraft/backend/staticfiles/admin/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Django REST framework static files
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

    # API endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # Django admin
    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # React app static files with caching
    location /static/ {
        alias /var/www/tycooncraft/frontend/build/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # React app root
    location / {
        root /var/www/tycooncraft/frontend/build;
        try_files $uri $uri/ /index.html;
        expires -1;
        add_header Cache-Control "no-cache, must-revalidate";
    }
}
NGINXEOF

# Replace domain placeholder
sed -i "s/DOMAIN_PLACEHOLDER/${DOMAIN}/g" /etc/nginx/sites-available/tycooncraft

# Enable site
ln -sf /etc/nginx/sites-available/tycooncraft /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# ============================================================================
# PERMISSIONS
# ============================================================================

echo "Setting permissions..."
sudo chown -R www-data:www-data /var/www/tycooncraft
find /var/www/tycooncraft -type d -exec chmod 755 {} \;
find /var/www/tycooncraft -type f -exec chmod 644 {} \;

# Make venv executables runnable
chmod 755 /var/www/tycooncraft/backend/.venv/bin/* 2>/dev/null || true

# ============================================================================
# NGINX RELOAD
# ============================================================================

# Test and reload Nginx
echo "Testing Nginx configuration..."
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

# ============================================================================
# SSL/HTTPS SETUP
# ============================================================================

if [ "$ENABLE_SSL" = true ]; then
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
else
    echo "=========================================="
    echo "Skipping SSL/HTTPS setup"
    echo "=========================================="
    echo "Site will be available via HTTP only"
fi

# ============================================================================
# SYSTEMD SERVICE
# ============================================================================

# Calculate optimal number of workers (cap at 9)
CPU_CORES=$(nproc)
GUNICORN_WORKERS=$((CPU_CORES * 2 + 1))
if [ $GUNICORN_WORKERS -gt 9 ]; then
    GUNICORN_WORKERS=9
fi
echo "Configuring Gunicorn with $GUNICORN_WORKERS workers (CPUs: $CPU_CORES)"

# Create systemd service for Gunicorn
echo "Creating systemd service..."
cat > /etc/systemd/system/tycooncraft.service << SERVICEEOF
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
ExecStart=/var/www/tycooncraft/backend/.venv/bin/gunicorn \\
  --workers $GUNICORN_WORKERS \\
  --bind 127.0.0.1:8000 \\
  --timeout 120 \\
  --access-logfile /var/log/tycooncraft-access.log \\
  --error-logfile /var/log/tycooncraft-error.log \\
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
echo "Testing gunicorn configuration..."
cd /var/www/tycooncraft/backend
sudo -u www-data bash -c "source .venv/bin/activate && gunicorn --bind 127.0.0.1:8001 --timeout 30 --check-config tycooncraft.wsgi:application"

# Create log files with proper permissions
touch /var/log/tycooncraft-access.log /var/log/tycooncraft-error.log
chown www-data:www-data /var/log/tycooncraft-*.log

# ============================================================================
# LOG ROTATION
# ============================================================================

echo "Configuring log rotation..."
cat > /etc/logrotate.d/tycooncraft << 'LOGROTATE_EOF'
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
LOGROTATE_EOF

# ============================================================================
# FAIL2BAN CONFIGURATION
# ============================================================================

echo "Configuring fail2ban..."

# Configure fail2ban for nginx
cat > /etc/fail2ban/jail.d/nginx-tycooncraft.conf << 'FAIL2BAN_EOF'
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
FAIL2BAN_EOF

systemctl enable fail2ban
systemctl restart fail2ban

# ============================================================================
# START SERVICE
# ============================================================================

# Start the service
echo "Starting TycoonCraft service..."
systemctl daemon-reload
systemctl enable tycooncraft
systemctl restart tycooncraft

# Wait for service to initialize
echo "Waiting for service to start..."
sleep 5

# Check status and show errors if failed
if ! systemctl is-active --quiet tycooncraft; then
    echo "ERROR: Service failed to start. Checking logs..."
    journalctl -u tycooncraft -n 50 --no-pager
    send_notification "❌ Deployment failed: Service won't start on $BRANCH" "error"
    exit 1
fi

echo "✓ Service started successfully"
systemctl status tycooncraft --no-pager

# ============================================================================
# HEALTH CHECK
# ============================================================================

echo "Running health checks..."

# Verify frontend build
if [ ! -f /var/www/tycooncraft/frontend/build/index.html ]; then
    echo "ERROR: Frontend build missing!"
    send_notification "❌ Health check failed: Frontend missing on $BRANCH" "error"
    exit 1
fi
echo "✓ Frontend build exists"

# Check if nginx is serving content
NGINX_CHECK=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ${DOMAIN}" http://127.0.0.1/ || echo "000")
if [ "$NGINX_CHECK" = "200" ]; then
    echo "✓ Nginx responding (HTTP $NGINX_CHECK)"
else
    echo "WARNING: Nginx returned HTTP $NGINX_CHECK"
fi

# Check Django backend health
echo "Checking Django backend..."
BACKEND_HEALTHY=false
for i in {1..30}; do
    if curl -f -s http://127.0.0.1:8000/api/ &>/dev/null; then
        echo "✓ Backend API responding"
        BACKEND_HEALTHY=true
        break
    fi
    sleep 2
done

if [ "$BACKEND_HEALTHY" = false ]; then
    echo "WARNING: Backend health check timeout - API may not be responding"
    echo "Check logs: journalctl -u tycooncraft -f"
fi

# ============================================================================
# DEPLOYMENT SUMMARY
# ============================================================================

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo "Branch deployed: $BRANCH"
echo "Commit: $GIT_COMMIT"
echo "Timestamp: $(date)"
echo ""
if [ "$ENABLE_SSL" = true ]; then
    echo "🌐 Site: https://${DOMAIN}"
    echo "🔧 Admin: https://${DOMAIN}/admin"
    echo "📡 API: https://${DOMAIN}/api"
else
    echo "🌐 Site: http://${DOMAIN}"
    echo "🔧 Admin: http://${DOMAIN}/admin"
    echo "📡 API: http://${DOMAIN}/api"
fi
echo ""
echo "👤 Admin credentials:"
echo "  Username: ${DJANGO_SUPERUSER_USERNAME}"
echo "  Password: (value from DJANGO_ADMIN_PASSWORD environment variable)"
echo ""
echo "📊 Monitoring:"
echo "  sudo journalctl -u tycooncraft -f"
echo "  sudo tail -f /var/log/tycooncraft-*.log"
echo "  sudo fail2ban-client status"
echo ""
echo "💾 Backups located in: /var/backups/tycooncraft"
echo "   (Retention: $BACKUP_RETENTION_DAYS days)"
echo ""
echo "🔄 Workers: $GUNICORN_WORKERS"
echo "🖥️  Node: $NODE_INSTALLED_VERSION"
echo "=========================================="

# Send success notification
send_notification "✅ Deployment successful: $BRANCH ($GIT_COMMIT)" "success"

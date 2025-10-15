#!/bin/bash
set -euo pipefail

# TycoonCraft Update Script - Fixed Backend Issues
# Updates the application with latest changes from git
# Usage: ./update.sh [branch]
# Example: ./update.sh production

# ============================================================================
# UPDATE LOCK - Prevent concurrent updates
# ============================================================================
exec 200>/tmp/tycooncraft_update.lock
if ! flock -n 200; then
    echo "ERROR: Another update is already in progress"
    echo "If you're sure no update is running, remove: /tmp/tycooncraft_update.lock"
    exit 1
fi

echo "=========================================="
echo "TycoonCraft Update Script"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run as root (use sudo)"
    exit 1
fi

# ============================================================================
# CONFIGURATION
# ============================================================================

# Get branch from argument or default to 'dev'
BRANCH="${1:-dev}"
echo "Target branch: $BRANCH"

# Get domain from environment or use default
DOMAIN="${DOMAIN:-tycooncraft.com}"
BACKUP_RETENTION_DAYS=7
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"

# Detect if SSL is enabled
SSL_ENABLED=false
if [ -f /etc/letsencrypt/live/${DOMAIN}/fullchain.pem ]; then
    SSL_ENABLED=true
fi

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

send_notification() {
    local message="$1"
    local status="${2:-info}"
    
    echo "$message"
    
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
    find /var/backups/tycooncraft -type d -name "update_backup.*" -mtime +$BACKUP_RETENTION_DAYS -exec rm -rf {} + 2>/dev/null || true
}

# ============================================================================
# PRE-UPDATE VALIDATION
# ============================================================================

# Verify we're in the right directory
if [ ! -d "/var/www/tycooncraft" ]; then
    echo "ERROR: /var/www/tycooncraft directory not found"
    echo "Have you run the initial deployment script?"
    exit 1
fi

if [ ! -f "/var/www/tycooncraft/backend/.env" ]; then
    echo "ERROR: Backend .env file not found"
    echo "Have you run the initial deployment script?"
    exit 1
fi

# Check if service exists (check both systemctl and file system)
if ! systemctl list-unit-files tycooncraft.service &>/dev/null && ! [ -f /etc/systemd/system/tycooncraft.service ]; then
    echo "ERROR: tycooncraft.service not found"
    echo "Have you run the initial deployment script?"
    exit 1
fi

# ============================================================================
# BACKUP BEFORE UPDATE
# ============================================================================

send_notification "📄 Starting update of branch: $BRANCH"

echo "Creating backup directory..."
mkdir -p /var/backups/tycooncraft

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/tycooncraft/update_backup.$TIMESTAMP"

echo "Backing up current deployment..."
cp -a /var/www/tycooncraft "$BACKUP_DIR"

# Backup database
echo "Backing up database..."
if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw tycooncraft; then
    sudo -u postgres pg_dump tycooncraft > "/var/backups/tycooncraft/db_backup_$TIMESTAMP.sql"
    echo "✓ Database backup saved"
else
    echo "WARNING: Database 'tycooncraft' not found - skipping database backup"
fi

# Clean up old backups
cleanup_old_backups

echo "✓ Backup complete: $BACKUP_DIR"

# ============================================================================
# GET CURRENT STATE
# ============================================================================

cd /var/www/tycooncraft

# Store current commit for comparison
CURRENT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
echo "Current commit: $CURRENT_COMMIT"

# ============================================================================
# STOP SERVICE
# ============================================================================

echo "Stopping TycoonCraft service..."
systemctl stop tycooncraft
echo "✓ Service stopped"

# Wait to ensure full shutdown
sleep 2

# ============================================================================
# UPDATE CODE
# ============================================================================

echo "Pulling latest changes from git ($BRANCH branch)..."

# Stash any local changes first (shouldn't be any, but just in case)
git stash save "Auto-stash before update $(date)" 2>/dev/null || true

git fetch origin $BRANCH
git reset --hard origin/$BRANCH

NEW_COMMIT=$(git rev-parse HEAD)
echo "New commit: $NEW_COMMIT"

# Check if anything actually changed
if [ "$CURRENT_COMMIT" = "$NEW_COMMIT" ]; then
    echo "⚠️  No changes detected - code is already up to date"
    CHANGES_DETECTED=false
else
    echo "✓ Code updated"
    CHANGES_DETECTED=true
    
    # Show what changed
    echo ""
    echo "Changes since last update:"
    git log --oneline --no-decorate $CURRENT_COMMIT..$NEW_COMMIT | head -10
    echo ""
fi

# ============================================================================
# UPDATE BACKEND
# ============================================================================

echo "Updating backend..."
cd /var/www/tycooncraft/backend

# Check if requirements.txt changed
REQUIREMENTS_CHANGED=false
if [ "$CHANGES_DETECTED" = true ]; then
    if git diff --name-only $CURRENT_COMMIT $NEW_COMMIT | grep -q "backend/requirements.txt"; then
        REQUIREMENTS_CHANGED=true
        echo "📦 Requirements.txt changed - updating dependencies..."
    fi
fi

# CRITICAL FIX: Ensure virtual environment exists and is functional
if [ ! -d ".venv" ]; then
    echo "⚠️  Virtual environment missing - creating new one..."
    python3 -m venv .venv
    REQUIREMENTS_CHANGED=true
fi

# CRITICAL FIX: Ensure venv binaries are executable after git reset
echo "Fixing virtual environment permissions..."
chmod +x .venv/bin/* 2>/dev/null || true

# Activate virtual environment
source .venv/bin/activate

# Verify activation worked
if [ -z "$VIRTUAL_ENV" ]; then
    echo "ERROR: Failed to activate virtual environment"
    exit 1
fi

echo "✓ Virtual environment activated: $VIRTUAL_ENV"

# CRITICAL FIX: Always verify/reinstall core dependencies
echo "Verifying core dependencies..."
pip install --upgrade pip setuptools wheel --quiet

# Update dependencies only if requirements changed or if it's a forced update
if [ "$REQUIREMENTS_CHANGED" = true ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt --quiet
    echo "✓ Dependencies updated"
else
    echo "✓ Dependencies unchanged (skipping pip install)"
fi

# CRITICAL FIX: Verify gunicorn is installed
if ! command -v gunicorn &> /dev/null; then
    echo "⚠️  Gunicorn not found - installing..."
    pip install gunicorn --quiet
fi

# Run migrations (always run to be safe)
echo "Running database migrations..."
python manage.py migrate
echo "✓ Migrations complete"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput
echo "✓ Static files collected"

# CRITICAL FIX: Test Django configuration
echo "Testing Django configuration..."
if ! python manage.py check --deploy 2>&1 | tee /tmp/django_check.log; then
    echo "⚠️  Django check found issues (see above)"
    echo "Continuing anyway, but check logs if backend fails..."
else
    echo "✓ Django configuration valid"
fi

# Deactivate venv (systemd will use it directly)
deactivate

# ============================================================================
# UPDATE FRONTEND
# ============================================================================

echo "Updating frontend..."
cd /var/www/tycooncraft/frontend

# Check if frontend actually changed
FRONTEND_CHANGED=false
PACKAGE_JSON_CHANGED=false

if [ "$CHANGES_DETECTED" = true ]; then
    if git diff --name-only $CURRENT_COMMIT $NEW_COMMIT | grep -q "frontend/"; then
        FRONTEND_CHANGED=true
        echo "🎨 Frontend files changed"
    fi
    
    if git diff --name-only $CURRENT_COMMIT $NEW_COMMIT | grep -q "frontend/package.json"; then
        PACKAGE_JSON_CHANGED=true
        echo "📦 package.json changed"
    fi
fi

# Determine if we need to rebuild
SHOULD_REBUILD=false

if [ "$FRONTEND_CHANGED" = true ] || [ "$PACKAGE_JSON_CHANGED" = true ]; then
    SHOULD_REBUILD=true
elif [ ! -f "build/index.html" ]; then
    echo "⚠️  Build directory missing - forcing rebuild"
    SHOULD_REBUILD=true
fi

if [ "$SHOULD_REBUILD" = true ]; then
    echo "Building frontend..."
    
    # Only npm install if package.json changed
    if [ "$PACKAGE_JSON_CHANGED" = true ]; then
        echo "Installing npm dependencies..."
        npm install --quiet
    fi
    
    # Ensure node_modules binaries are executable (git reset may strip permissions)
    chmod +x node_modules/.bin/* 2>/dev/null || true
    
    # Build with correct API URL
    if [ "$SSL_ENABLED" = true ]; then
        REACT_APP_API_URL=https://${DOMAIN}/api npm run build
    else
        REACT_APP_API_URL=http://${DOMAIN}/api npm run build
    fi
    echo "✓ Frontend built"
else
    echo "✓ Frontend unchanged (skipping build - saves 2-5 minutes)"
fi

# Verify build exists
if [ ! -f "build/index.html" ]; then
    echo "ERROR: Frontend build failed - build/index.html not found"
    send_notification "❌ Update failed: Frontend build missing for $BRANCH" "error"
    
    echo ""
    echo "=========================================="
    echo "ROLLBACK INSTRUCTIONS"
    echo "=========================================="
    echo "1. Restore from backup:"
    echo "   rm -rf /var/www/tycooncraft"
    echo "   cp -a $BACKUP_DIR /var/www/tycooncraft"
    echo ""
    echo "2. Restore database:"
    echo "   sudo -u postgres psql tycooncraft < /var/backups/tycooncraft/db_backup_$TIMESTAMP.sql"
    echo ""
    echo "3. Restart service:"
    echo "   systemctl start tycooncraft"
    echo "=========================================="
    exit 1
fi

# ============================================================================
# FIX PERMISSIONS
# ============================================================================

echo "Setting permissions..."
cd /var/www/tycooncraft

# CRITICAL FIX: Set proper ownership
chown -R www-data:www-data /var/www/tycooncraft

# Set directory permissions
find /var/www/tycooncraft -type d -exec chmod 755 {} \;

# Set file permissions
find /var/www/tycooncraft -type f -exec chmod 644 {} \;

# CRITICAL FIX: Ensure backend executables are executable
chmod +x /var/www/tycooncraft/backend/.venv/bin/* 2>/dev/null || true
chmod +x /var/www/tycooncraft/backend/manage.py 2>/dev/null || true

# CRITICAL FIX: Ensure .env is readable by www-data
chmod 640 /var/www/tycooncraft/backend/.env

echo "✓ Permissions set"

# ============================================================================
# VERIFY SYSTEMD SERVICE CONFIGURATION
# ============================================================================

echo "Verifying systemd service configuration..."

# Check if service file uses the correct Python interpreter
SERVICE_FILE="/etc/systemd/system/tycooncraft.service"
if [ -f "$SERVICE_FILE" ]; then
    if grep -q "/var/www/tycooncraft/backend/.venv/bin/python" "$SERVICE_FILE" || \
       grep -q "/var/www/tycooncraft/backend/.venv/bin/gunicorn" "$SERVICE_FILE"; then
        echo "✓ Service file correctly references virtual environment"
    else
        echo "⚠️  WARNING: Service file may not reference virtual environment correctly"
        echo "   Service file: $SERVICE_FILE"
        echo "   Check ExecStart line uses: /var/www/tycooncraft/backend/.venv/bin/gunicorn"
    fi
else
    echo "⚠️  WARNING: Service file not found at $SERVICE_FILE"
fi

# Reload systemd in case service file was modified
systemctl daemon-reload

# ============================================================================
# RESTART SERVICES
# ============================================================================

echo "Starting TycoonCraft service..."
systemctl start tycooncraft

echo "Reloading Nginx..."
systemctl reload nginx

# Wait for service to initialize
echo "Waiting for service to start..."
sleep 5

# ============================================================================
# COMPREHENSIVE HEALTH CHECKS
# ============================================================================

echo "Running comprehensive health checks..."

# Check if service is active
if ! systemctl is-active --quiet tycooncraft; then
    echo "❌ ERROR: Service failed to start"
    echo ""
    echo "Service status:"
    systemctl status tycooncraft --no-pager -l
    echo ""
    echo "Recent logs:"
    journalctl -u tycooncraft -n 100 --no-pager
    echo ""
    send_notification "❌ Update failed: Service won't start on $BRANCH" "error"
    
    echo "=========================================="
    echo "ROLLBACK INSTRUCTIONS"
    echo "=========================================="
    echo "1. Stop failed service:"
    echo "   systemctl stop tycooncraft"
    echo ""
    echo "2. Restore from backup:"
    echo "   rm -rf /var/www/tycooncraft"
    echo "   cp -a $BACKUP_DIR /var/www/tycooncraft"
    echo ""
    echo "3. Restore database:"
    echo "   sudo -u postgres psql tycooncraft < /var/backups/tycooncraft/db_backup_$TIMESTAMP.sql"
    echo ""
    echo "4. Restart service:"
    echo "   systemctl start tycooncraft"
    echo "=========================================="
    exit 1
fi
echo "✓ Service is running"

# CRITICAL FIX: Verify gunicorn process is actually running
echo "Checking for gunicorn processes..."
if pgrep -f "gunicorn.*tycooncraft" > /dev/null; then
    GUNICORN_COUNT=$(pgrep -f "gunicorn.*tycooncraft" | wc -l)
    echo "✓ Gunicorn processes running: $GUNICORN_COUNT"
else
    echo "❌ ERROR: No gunicorn processes found!"
    echo "Service may be started but gunicorn is not running"
    echo ""
    echo "Checking logs for errors..."
    journalctl -u tycooncraft -n 50 --no-pager
    exit 1
fi

# Check if nginx is serving content
NGINX_CHECK=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ${DOMAIN}" http://127.0.0.1/ || echo "000")
if [ "$NGINX_CHECK" = "200" ]; then
    echo "✓ Nginx responding (HTTP $NGINX_CHECK)"
else
    echo "⚠️  WARNING: Nginx returned HTTP $NGINX_CHECK"
fi

# CRITICAL FIX: More robust backend health check
echo "Checking Django backend (30 second timeout)..."
BACKEND_HEALTHY=false
for i in {1..15}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/ || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✓ Backend API responding (HTTP $HTTP_CODE)"
        BACKEND_HEALTHY=true
        break
    elif [ "$HTTP_CODE" != "000" ]; then
        echo "Attempt $i: Backend returned HTTP $HTTP_CODE (waiting...)"
    else
        echo "Attempt $i: Backend not responding yet (waiting...)"
    fi
    sleep 2
done

if [ "$BACKEND_HEALTHY" = false ]; then
    echo "❌ ERROR: Backend health check failed - API not responding after 30 seconds"
    echo ""
    echo "Checking backend logs..."
    journalctl -u tycooncraft -n 100 --no-pager
    echo ""
    echo "Checking error logs..."
    if [ -f /var/log/tycooncraft-error.log ]; then
        tail -50 /var/log/tycooncraft-error.log
    fi
    send_notification "❌ Update failed: Backend not responding on $BRANCH" "error"
    exit 1
fi

# Store deployed commit
echo "$NEW_COMMIT" > /var/www/tycooncraft/.deployed_commit

# ============================================================================
# SUCCESS SUMMARY
# ============================================================================

echo ""
echo "=========================================="
echo "✅ Update Successful!"
echo "=========================================="
echo "Branch: $BRANCH"
echo "Previous commit: $CURRENT_COMMIT"
echo "New commit: $NEW_COMMIT"
echo "Timestamp: $(date)"
echo ""

if [ "$SSL_ENABLED" = true ]; then
    echo "🌐 Site: https://${DOMAIN}"
    echo "🔧 Admin: https://${DOMAIN}/admin"
    echo "📡 API: https://${DOMAIN}/api"
else
    echo "🌐 Site: http://${DOMAIN}"
    echo "🔧 Admin: http://${DOMAIN}/admin"
    echo "📡 API: http://${DOMAIN}/api"
fi

echo ""
echo "📊 Service status:"
systemctl status tycooncraft --no-pager -l | head -15
echo ""
echo "📋 Monitoring:"
echo "  Live logs: sudo journalctl -u tycooncraft -f"
echo "  Error logs: sudo tail -f /var/log/tycooncraft-error.log"
echo ""
echo "💾 Backup saved to: $BACKUP_DIR"
echo "   (Retention: $BACKUP_RETENTION_DAYS days)"
echo ""

# Show summary of what was updated
echo "📝 Changes applied:"
if [ "$CHANGES_DETECTED" = false ]; then
    echo "  - No code changes (already up to date)"
else
    if [ "$REQUIREMENTS_CHANGED" = true ]; then
        echo "  - ✓ Python dependencies updated"
    else
        echo "  - ○ Python dependencies unchanged"
    fi
    
    echo "  - ✓ Database migrations applied"
    
    if [ "$SHOULD_REBUILD" = true ]; then
        echo "  - ✓ Frontend rebuilt"
    else
        echo "  - ○ Frontend unchanged (skipped build)"
    fi
fi

echo "=========================================="

send_notification "✅ Update successful: $BRANCH ($NEW_COMMIT)" "success"

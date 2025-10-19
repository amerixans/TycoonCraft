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

# Load environment variables (including admin credentials)
set -a
source /var/www/tycooncraft/backend/.env
set +a

if [ -z "${DJANGO_SUPERUSER_PASSWORD:-}" ] && [ -z "${DJANGO_ADMIN_PASSWORD:-}" ]; then
    echo "ERROR: Admin password not found in backend/.env (DJANGO_SUPERUSER_PASSWORD or DJANGO_ADMIN_PASSWORD)"
    exit 1
fi

DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}"
DJANGO_SUPERUSER_PASSWORD="${DJANGO_SUPERUSER_PASSWORD:-${DJANGO_ADMIN_PASSWORD}}"

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
# Run as www-data to avoid git ownership issues
CURRENT_COMMIT=$(sudo -u www-data git rev-parse HEAD 2>/dev/null || echo "unknown")
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

# CRITICAL FIX: Run git commands as www-data to avoid ownership issues
# Git has security protections against running in directories owned by other users
# Since /var/www/tycooncraft is owned by www-data, we should run git as www-data

# Stash any local changes first (shouldn't be any, but just in case)
sudo -u www-data git stash save "Auto-stash before update $(date)" 2>/dev/null || true

sudo -u www-data git fetch origin $BRANCH
sudo -u www-data git reset --hard origin/$BRANCH

NEW_COMMIT=$(sudo -u www-data git rev-parse HEAD)
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
    sudo -u www-data git log --oneline --no-decorate $CURRENT_COMMIT..$NEW_COMMIT | head -10
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
    if sudo -u www-data git diff --name-only $CURRENT_COMMIT $NEW_COMMIT | grep -q "backend/requirements.txt"; then
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

# Create admin account (idempotent - safe to run multiple times)
echo "Setting up admin testing account..."
export DJANGO_SUPERUSER_USERNAME
export DJANGO_SUPERUSER_PASSWORD
python manage.py create_admin_account
echo "✓ Admin account configured"

# Initialize starter objects (idempotent - safe to run multiple times)
echo "Initializing starter objects..."
python manage.py initialize_starter_objects
echo "✓ Starter objects initialized"

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

# NEW: Verify URL configuration exists
echo "Verifying Django URL patterns..."
if python manage.py show_urls 2>/dev/null | head -20; then
    echo "✓ URL patterns detected"
elif python -c "
import sys
sys.path.insert(0, '/var/www/tycooncraft/backend')
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tycooncraft.settings')
import django
django.setup()
from django.urls import get_resolver
resolver = get_resolver()
patterns = [str(p.pattern) for p in resolver.url_patterns[:10]]
print('Configured URL patterns:', patterns)
" 2>/dev/null; then
    echo "✓ URL configuration found"
else
    echo "⚠️  Warning: Could not verify URL patterns (this is OK if custom configuration)"
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
    if sudo -u www-data git diff --name-only $CURRENT_COMMIT $NEW_COMMIT | grep -q "frontend/"; then
        FRONTEND_CHANGED=true
        echo "🎨 Frontend files changed"
    fi
    
    if sudo -u www-data git diff --name-only $CURRENT_COMMIT $NEW_COMMIT | grep -q "frontend/package.json"; then
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

# CRITICAL FIX: Comprehensive backend health check with actual API endpoints
echo "Checking Django backend (30 second timeout)..."
BACKEND_HEALTHY=false
TESTED_ENDPOINT=""

# Test actual API endpoints that should exist based on your game/urls.py
# Also test admin which we know works from diagnostics
ENDPOINTS_TO_TEST=(
    "/admin/"              # Should redirect (301/302) - proves Django is working
    "/api/game-state/"     # Actual API endpoint from your game/urls.py
    "/api/register/"       # Actual API endpoint
    "/api/login/"          # Actual API endpoint
)

# Function to check if response code indicates health
is_healthy_response() {
    local code="$1"
    # Accept: 200 OK, 301/302 redirect, 401 unauthorized (means endpoint exists but needs auth),
    # 403 forbidden (means endpoint exists), 405 method not allowed (means endpoint exists)
    if [ "$code" = "200" ] || [ "$code" = "301" ] || [ "$code" = "302" ] || \
       [ "$code" = "401" ] || [ "$code" = "403" ] || [ "$code" = "405" ]; then
        return 0
    fi
    return 1
}

# First pass: Quick test of all endpoints
echo "Testing Django endpoints..."
for endpoint in "${ENDPOINTS_TO_TEST[@]}"; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000${endpoint} 2>/dev/null || echo "000")
    
    if is_healthy_response "$HTTP_CODE"; then
        BACKEND_HEALTHY=true
        TESTED_ENDPOINT="$endpoint"
        echo "✓ Backend responding on ${endpoint} (HTTP $HTTP_CODE)"
        break
    else
        echo "  ${endpoint}: HTTP ${HTTP_CODE}"
    fi
done

# If no endpoint worked immediately, retry with delays
if [ "$BACKEND_HEALTHY" = false ]; then
    echo "No endpoints responded immediately, retrying with delays..."
    for i in {1..15}; do
        # Test admin first (most likely to work), then actual API endpoints
        for endpoint in "/admin/" "/api/game-state/" "/api/register/"; do
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000${endpoint} 2>/dev/null || echo "000")
            
            if is_healthy_response "$HTTP_CODE"; then
                echo "✓ Backend responding on ${endpoint} (HTTP $HTTP_CODE)"
                BACKEND_HEALTHY=true
                TESTED_ENDPOINT="$endpoint"
                break 2
            fi
        done
        echo "Attempt $i/15: Waiting for backend to respond..."
        sleep 2
    done
fi

if [ "$BACKEND_HEALTHY" = false ]; then
    echo "❌ ERROR: Backend health check failed - No endpoints responding after 30 seconds"
    echo ""
    echo "Comprehensive Django Diagnostics:"
    echo "======================================"
    echo "Testing all known endpoints:"
    echo ""
    
    # Test all possible endpoints with detailed output
    ALL_ENDPOINTS=(
        "/"
        "/admin/"
        "/api/"
        "/api/register/"
        "/api/login/"
        "/api/game-state/"
        "/api/craft/"
        "/api/place/"
    )
    
    for endpoint in "${ALL_ENDPOINTS[@]}"; do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000${endpoint} 2>/dev/null || echo "000")
        RESPONSE=$(curl -s http://127.0.0.1:8000${endpoint} 2>/dev/null | head -c 200)
        
        printf "%-20s: HTTP %-3s" "$endpoint" "$HTTP_CODE"
        
        if is_healthy_response "$HTTP_CODE"; then
            echo " ✓ (Healthy response)"
        elif [ "$HTTP_CODE" = "404" ]; then
            echo " ✗ (Not Found)"
        elif [ "$HTTP_CODE" = "500" ]; then
            echo " ✗ (Server Error)"
        elif [ "$HTTP_CODE" = "000" ]; then
            echo " ✗ (No Response)"
        else
            echo " ? (Unexpected: $HTTP_CODE)"
        fi
        
        if [ -n "$RESPONSE" ] && [ "$HTTP_CODE" != "000" ]; then
            echo "     Response preview: ${RESPONSE:0:100}"
        fi
    done
    
    echo ""
    echo "======================================"
    echo "Service Logs (last 50 lines):"
    echo "======================================"
    journalctl -u tycooncraft -n 50 --no-pager
    echo ""
    echo "======================================"
    echo "Error Logs:"
    echo "======================================"
    if [ -f /var/log/tycooncraft-error.log ]; then
        tail -30 /var/log/tycooncraft-error.log
    else
        echo "No error log found at /var/log/tycooncraft-error.log"
    fi
    echo ""
    echo "======================================"
    echo "❌ DIAGNOSIS:"
    echo "   - Gunicorn is running (verified earlier)"
    echo "   - But Django is not responding to any endpoints"
    echo "   - Check for Django errors in logs above"
    echo "   - Possible issues: ALLOWED_HOSTS, database connection, imports"
    echo "======================================"
    echo ""
    send_notification "❌ Update failed: Backend not responding on $BRANCH" "error"
    exit 1
else
    echo ""
    echo "✓ Backend health check passed using endpoint: ${TESTED_ENDPOINT}"
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

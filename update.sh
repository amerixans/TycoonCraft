#!/bin/bash
set -euo pipefail

# TycoonCraft Update Script
# Updates the application with latest changes from git
# Usage: ./update_tycooncraft.sh [branch]
# Example: ./update_tycooncraft.sh production

echo "=========================================="
echo "TycoonCraft Update Script"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run as root (use sudo)"
    exit 1
fi

# Get branch from argument or default to 'dev'
BRANCH="${1:-dev}"
echo "Target branch: $BRANCH"

# Get domain from environment or use default
DOMAIN="${DOMAIN:-tycooncraft.com}"

# Stop the application
echo "Stopping TycoonCraft service..."
systemctl stop tycooncraft

# Change ownership to root for update operations
echo "Adjusting permissions for updates..."
chown -R root:root /var/www/tycooncraft

# Navigate to repo
cd /var/www/tycooncraft

# Pull latest changes
echo "Pulling latest changes from git ($BRANCH branch)..."
git fetch origin $BRANCH
git reset --hard origin/$BRANCH

# Update Backend
echo "Updating backend..."
cd /var/www/tycooncraft/backend

# Activate virtual environment and update dependencies
source .venv/bin/activate
pip install -r requirements.txt --quiet

# Run migrations
echo "Running database migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Update Frontend
echo "Updating frontend..."
cd /var/www/tycooncraft/frontend

# Install dependencies and rebuild
npm install --quiet

# Ensure node_modules binaries are executable
chmod +x node_modules/.bin/* 2>/dev/null || true

REACT_APP_API_URL=https://${DOMAIN}/api npm run build

# Fix permissions
echo "Setting permissions..."
chown -R www-data:www-data /var/www/tycooncraft
find /var/www/tycooncraft -type d -exec chmod 755 {} \;
find /var/www/tycooncraft -type f -exec chmod 644 {} \;
chmod 755 /var/www/tycooncraft/backend/.venv/bin/* 2>/dev/null || true

# Restart services
echo "Restarting services..."
systemctl start tycooncraft
systemctl reload nginx

# Wait for service to initialize
sleep 3

# Check if service is running
if systemctl is-active --quiet tycooncraft; then
    echo "=========================================="
    echo "✓ Update successful!"
    echo "=========================================="
    echo "Branch deployed: $BRANCH"
    echo "Service status:"
    systemctl status tycooncraft --no-pager -l
    echo ""
    echo "Site: https://${DOMAIN}"
    echo "To monitor logs: sudo journalctl -u tycooncraft -f"
else
    echo "=========================================="
    echo "✗ ERROR: Service failed to start"
    echo "=========================================="
    echo "Recent logs:"
    journalctl -u tycooncraft -n 50 --no-pager
    exit 1
fi

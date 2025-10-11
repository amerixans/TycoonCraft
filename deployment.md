# TycoonCraft Deployment Guide

This guide will help you deploy TycoonCraft to a Digital Ocean droplet in under 10 minutes.

## Prerequisites

- Digital Ocean account with a $12/month droplet (2GB RAM, Ubuntu 22.04)
- Domain name (TycoonCraft.com) pointed to droplet IP
- OpenAI API key

## Quick Deployment (< 10 minutes)

### 1. Initial Server Setup (2 minutes)

SSH into your droplet:
```bash
ssh root@your_droplet_ip
```

Update system and install dependencies:
```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv postgresql nginx git nodejs npm
```

### 2. Setup PostgreSQL (1 minute)

```bash
sudo -u postgres psql -c "CREATE DATABASE tycooncraft;"
sudo -u postgres psql -c "CREATE USER tycooncraft WITH PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE tycooncraft TO tycooncraft;"
```

### 3. Clone and Setup Application (3 minutes)

```bash
cd /var/www
git clone https://github.com/yourusername/tycooncraft.git
cd tycooncraft

# Setup backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create environment file
cat > .env << EOF
DJANGO_SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
DEBUG=False
DB_NAME=tycooncraft
DB_USER=tycooncraft
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432
OPENAI_API_KEY=your_openai_api_key_here
EOF

# Run migrations
python manage.py makemigrations
python manage.py migrate
python manage.py initialize_starter_objects
python manage.py createsuperuser --noinput --username admin --email admin@tycooncraft.com || true
python manage.py collectstatic --noinput

# Setup frontend
cd ../frontend
npm install
REACT_APP_API_URL=https://tycooncraft.com/api npm run build
```

### 4. Configure Nginx (2 minutes)

```bash
cat > /etc/nginx/sites-available/tycooncraft << 'EOF'
server {
    listen 80;
    server_name tycooncraft.com www.tycooncraft.com;

    client_max_body_size 100M;

    location /static/ {
        alias /var/www/tycooncraft/backend/staticfiles/;
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

    location / {
        root /var/www/tycooncraft/frontend/build;
        try_files $uri $uri/ /index.html;
    }
}
EOF

ln -sf /etc/nginx/sites-available/tycooncraft /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
```

### 5. Setup Systemd Service (1 minute)

```bash
cat > /etc/systemd/system/tycooncraft.service << 'EOF'
[Unit]
Description=TycoonCraft Django Application
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/tycooncraft/backend
Environment="PATH=/var/www/tycooncraft/backend/venv/bin"
EnvironmentFile=/var/www/tycooncraft/backend/.env
ExecStart=/var/www/tycooncraft/backend/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /var/log/tycooncraft/access.log \
    --error-logfile /var/log/tycooncraft/error.log \
    tycooncraft.wsgi:application

[Install]
WantedBy=multi-user.target
EOF

mkdir -p /var/log/tycooncraft
chown -R www-data:www-data /var/www/tycooncraft
chown -R www-data:www-data /var/log/tycooncraft

systemctl daemon-reload
systemctl enable tycooncraft
systemctl start tycooncraft
```

### 6. Setup SSL (Optional, 1 minute)

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d tycooncraft.com -d www.tycooncraft.com --non-interactive --agree-tos -m admin@tycooncraft.com
```

## Verification

Check services are running:
```bash
systemctl status tycooncraft
systemctl status nginx
systemctl status postgresql
```

View logs:
```bash
tail -f /var/log/tycooncraft/error.log
```

## Deployment Complete!

Your TycoonCraft instance should now be live at https://tycooncraft.com

## Post-Deployment

### Set Admin Password
```bash
cd /var/www/tycooncraft/backend
source venv/bin/activate
python manage.py changepassword admin
```

### Monitor Resources
```bash
htop  # Monitor CPU/Memory
du -sh /var/www/tycooncraft/backend/media/  # Check storage
```

### Update Application
```bash
cd /var/www/tycooncraft
git pull
cd backend
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
cd ../frontend
npm install
REACT_APP_API_URL=https://tycooncraft.com/api npm run build
systemctl restart tycooncraft
```

## Troubleshooting

### Application won't start
```bash
journalctl -u tycooncraft -n 50
```

### Database connection issues
```bash
sudo -u postgres psql -c "\l"  # List databases
```

### Nginx issues
```bash
nginx -t  # Test configuration
tail -f /var/log/nginx/error.log
```

### Out of memory
```bash
free -h  # Check memory
# Consider adding swap space or upgrading droplet
```

## Maintenance

### Backup Database
```bash
sudo -u postgres pg_dump tycooncraft > backup_$(date +%Y%m%d).sql
```

### Restore Database
```bash
sudo -u postgres psql tycooncraft < backup_20241010.sql
```

### Clear old images (if storage fills up)
```bash
# Be careful - this removes all generated images!
rm -rf /var/www/tycooncraft/backend/media/objects/*
```

## Security Notes

- Change all default passwords
- Keep your OPENAI_API_KEY secure
- Regularly update system packages: `apt update && apt upgrade`
- Monitor API usage to avoid unexpected costs
- Set up firewall: `ufw allow 22,80,443/tcp && ufw enable`

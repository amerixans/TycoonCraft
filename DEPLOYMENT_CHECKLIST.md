# TycoonCraft Deployment Checklist

Use this checklist to ensure a smooth deployment.

## Pre-Deployment

### Requirements
- [ ] Digital Ocean account created
- [ ] 2GB droplet created (Ubuntu 22.04)
- [ ] Domain name (TycoonCraft.com) purchased
- [ ] Domain DNS pointed to droplet IP
- [ ] OpenAI API key obtained
- [ ] SSH access to droplet configured

### Local Testing
- [ ] Backend runs without errors
- [ ] Frontend runs without errors
- [ ] Can register new user
- [ ] Can craft objects
- [ ] Can place objects
- [ ] Can unlock eras
- [ ] Export/import works
- [ ] No console errors

## Deployment Steps

### 1. Server Setup
- [ ] SSH into droplet
- [ ] System updated (`apt update && apt upgrade`)
- [ ] Python 3 installed
- [ ] Node.js installed
- [ ] PostgreSQL installed
- [ ] Nginx installed
- [ ] Git installed

### 2. Database Setup
- [ ] PostgreSQL service running
- [ ] Database 'tycooncraft' created
- [ ] User 'tycooncraft' created
- [ ] Permissions granted
- [ ] Connection tested

### 3. Application Setup
- [ ] Repository cloned to /var/www
- [ ] Virtual environment created
- [ ] Python requirements installed
- [ ] .env file created with production values
- [ ] Migrations run successfully
- [ ] Starter objects initialized
- [ ] Superuser created
- [ ] Static files collected
- [ ] Frontend dependencies installed
- [ ] Frontend built with production API URL

### 4. Web Server Setup
- [ ] Nginx configuration created
- [ ] Configuration linked to sites-enabled
- [ ] Default site disabled
- [ ] Configuration tested (`nginx -t`)
- [ ] Nginx restarted

### 5. Application Service
- [ ] Systemd service file created
- [ ] Log directory created (/var/log/tycooncraft)
- [ ] Permissions set correctly (www-data)
- [ ] Service enabled
- [ ] Service started
- [ ] Service status checked (should be active)

### 6. SSL (Optional but Recommended)
- [ ] Certbot installed
- [ ] SSL certificate obtained
- [ ] Auto-renewal configured
- [ ] HTTPS tested

## Post-Deployment Testing

### Functionality Tests
- [ ] Site loads at domain
- [ ] Can register new account
- [ ] Can login
- [ ] Can craft objects
- [ ] Images generate and display
- [ ] Can place objects on canvas
- [ ] Coins accumulate over time
- [ ] Can remove objects
- [ ] Can export game state
- [ ] Can import game state
- [ ] Admin panel accessible

### Performance Tests
- [ ] Page load time < 3 seconds
- [ ] API response time < 500ms
- [ ] Images load properly
- [ ] No console errors
- [ ] No memory leaks (check with htop)

### Security Checks
- [ ] HTTPS enabled (if SSL configured)
- [ ] Admin password changed from default
- [ ] Database password is secure
- [ ] DJANGO_SECRET_KEY is random
- [ ] DEBUG=False in production
- [ ] Firewall configured (ports 22, 80, 443)
- [ ] OpenAI API key is secret

## Monitoring Setup

### Logging
- [ ] Django logs writing to file
- [ ] Nginx logs accessible
- [ ] Log rotation configured

### Backups
- [ ] Database backup script created
- [ ] Backup cron job scheduled
- [ ] Backup restoration tested

### Alerts
- [ ] Disk space monitoring
- [ ] Service health checks
- [ ] API rate limit monitoring

## Final Verification

### Production Checklist
- [ ] All environment variables set correctly
- [ ] SECRET_KEY is secure and unique
- [ ] DEBUG is False
- [ ] ALLOWED_HOSTS configured
- [ ] Database credentials are secure
- [ ] Static files serving correctly
- [ ] Media files serving correctly
- [ ] CORS configured properly
- [ ] Rate limits set appropriately

### Documentation
- [ ] README.md reviewed
- [ ] QUICKSTART.md reviewed
- [ ] deployment.md followed
- [ ] Admin credentials documented securely

### Access & Credentials
- [ ] SSH keys backed up
- [ ] Database credentials saved securely
- [ ] OpenAI API key saved securely
- [ ] Admin password saved securely
- [ ] Domain registrar login saved

## Maintenance Schedule

### Daily
- [ ] Check service status
- [ ] Monitor disk space
- [ ] Review error logs

### Weekly
- [ ] Database backup
- [ ] Review API usage
- [ ] Check for updates

### Monthly
- [ ] Security patches
- [ ] Performance review
- [ ] Cost analysis

## Troubleshooting

If something goes wrong:

1. **Service won't start**
   ```bash
   journalctl -u tycooncraft -n 50
   ```

2. **Nginx errors**
   ```bash
   nginx -t
   tail -f /var/log/nginx/error.log
   ```

3. **Database issues**
   ```bash
   sudo -u postgres psql -c "\l"
   ```

4. **Application errors**
   ```bash
   tail -f /var/log/tycooncraft/error.log
   ```

## Emergency Contacts

- Digital Ocean Support: support.digitalocean.com
- OpenAI Support: help.openai.com
- Domain Registrar: [Your registrar support]

## Notes

Date Deployed: ________________

Deployed By: ________________

Droplet IP: ________________

Domain: TycoonCraft.com

Version: 1.0.0

Special Configurations: ________________

Issues Encountered: ________________

________________

________________

________________

# 🚀 LexAI Practice Partner - Production Deployment Guide

This guide covers database setup, migrations, and production deployment for the LexAI Practice Partner platform.

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL (for production) or SQLite (for development)
- Redis (optional, for caching and rate limiting)
- Email server (for password resets)

## 🔧 Environment Setup

### 1. Clone and Setup Virtual Environment

```bash
git clone <repository-url>
cd lexai-app
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your specific values
nano .env
```

**Required Environment Variables:**

```bash
# Security
SECRET_KEY=your-secure-secret-key
XAI_API_KEY=your-xai-api-key

# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Email (optional)
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

## 🗄️ Database Management

### Development Database Setup

```bash
# Initialize migrations
python manage.py init-db

# Check current status
python manage.py status

# Create initial migration
python manage.py create-migration -m "Initial schema"

# Apply migrations
python manage.py upgrade-db

# Seed with sample data
python manage.py seed-db
```

### Production Database Setup

```bash
# Complete production setup (recommended)
python manage.py setup-production

# Or step by step:
python manage.py init-db
python manage.py upgrade-db
python manage.py seed-db
python manage.py backup-db
```

### Migration Commands

```bash
# Create new migration
python manage.py create-migration -m "Add new feature"

# Apply all pending migrations
python manage.py upgrade-db

# Rollback to previous migration
python manage.py downgrade-db -r head~1

# Show migration history
python manage.py migration-history

# Validate database schema
python manage.py validate-db

# Create backup
python manage.py backup-db --path backup.sql

# Reset database (DANGER)
python manage.py reset-db
```

## 🔐 Security Configuration

### Production Security Settings

In your `.env` file:

```bash
FLASK_ENV=production
DEBUG=false
SESSION_COOKIE_SECURE=true
WTF_CSRF_ENABLED=true
```

### SSL/TLS Configuration

For production, ensure:
- SSL certificate is properly configured
- All traffic redirected to HTTPS
- Secure headers are enabled

## 🚀 Production Deployment

### Option 1: Using Gunicorn (Recommended)

```bash
# Install production dependencies
pip install gunicorn

# Start production server
gunicorn --bind 0.0.0.0:8000 --workers 4 app:app

# Or use the provided script
./start_production.sh
```

### Option 2: Using Docker

```dockerfile
# Dockerfile example
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app:app"]
```

### Option 3: Platform Deployment

#### Heroku
```bash
# Create Procfile
echo "web: gunicorn app:app" > Procfile

# Deploy
git add .
git commit -m "Production deployment"
git push heroku main

# Run migrations
heroku run python manage.py setup-production
```

#### Railway/Render
- Connect GitHub repository
- Set environment variables in dashboard
- Use build command: `pip install -r requirements.txt`
- Use start command: `gunicorn app:app`

## 📊 Database Migration Strategies

### Development to Production

1. **Generate migrations locally:**
   ```bash
   python manage.py create-migration -m "Feature description"
   ```

2. **Test migrations:**
   ```bash
   python manage.py upgrade-db
   python manage.py validate-db
   ```

3. **Deploy to production:**
   ```bash
   # On production server
   python manage.py backup-db
   python manage.py upgrade-db
   ```

### Zero-Downtime Deployments

1. **Backward-compatible migrations**
2. **Use migration hooks for data transformations**
3. **Test rollback procedures**
4. **Monitor application health during deployment**

## 🔄 Backup and Recovery

### Automated Backups

```bash
# Create backup script
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
python manage.py backup-db --path "backups/backup_$TIMESTAMP.sql"

# Add to crontab for daily backups
0 2 * * * /path/to/backup_script.sh
```

### Recovery Process

```bash
# Restore from backup (PostgreSQL)
psql -h hostname -U username -d database < backup.sql

# Restore from backup (SQLite)
cp backup.db production.db
```

## 📈 Monitoring and Health Checks

### Health Check Endpoint

```bash
# Check application health
curl http://your-domain.com/health

# Expected response:
{
  "status": "healthy",
  "database": "connected",
  "api_configured": true,
  "config_valid": true
}
```

### Database Health

```bash
# Check database status
python manage.py status

# Validate schema
python manage.py validate-db
```

## 🔧 Troubleshooting

### Common Issues

1. **Migration conflicts:**
   ```bash
   python manage.py migration-history
   python manage.py downgrade-db -r <revision>
   python manage.py upgrade-db
   ```

2. **Database connection issues:**
   - Check DATABASE_URL format
   - Verify database server is running
   - Test connection with psql/sqlite3

3. **Permission errors:**
   - Check file permissions
   - Verify database user permissions
   - Ensure upload directories are writable

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python app.py
```

## 📋 Production Checklist

- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] SSL certificate installed
- [ ] Backup system configured
- [ ] Health checks working
- [ ] Error monitoring setup (Sentry)
- [ ] Rate limiting configured
- [ ] Security headers enabled
- [ ] Admin user created
- [ ] Sample data seeded (if needed)

## 🆘 Emergency Procedures

### Rollback Deployment

```bash
# Rollback database
python manage.py backup-db --path emergency_backup.sql
python manage.py downgrade-db -r <previous-revision>

# Restart application
sudo systemctl restart lexai-app
```

### Database Recovery

```bash
# Stop application
sudo systemctl stop lexai-app

# Restore from backup
python manage.py reset-db  # DANGER: Only if necessary
# Or restore from backup file

# Restart application
sudo systemctl start lexai-app
```

## 📞 Support

For deployment issues:
1. Check logs: `tail -f logs/lexai.log`
2. Verify configuration: `python manage.py status`
3. Test health endpoint: `/health`
4. Review this deployment guide

---

**Remember:** Always test deployments in a staging environment first!
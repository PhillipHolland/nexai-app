# LexAI Production Deployment Guide

## 🚀 Production Readiness Checklist

### ✅ Completed Components

- [x] **Comprehensive Testing Framework**
  - Unit tests, integration tests, security tests
  - Performance and load testing
  - API endpoint testing
  - Automated test runner with reporting

- [x] **Security Hardening**
  - Rate limiting and DDoS protection
  - Input sanitization and validation
  - CSRF protection and secure headers
  - File upload security
  - SQL injection and XSS prevention
  - Session security and IP validation

- [x] **Performance Optimization**
  - Real-time performance monitoring
  - Caching system with TTL
  - Resource usage tracking
  - Response time optimization
  - Memory leak detection

- [x] **Monitoring & Analytics**
  - Health check endpoints
  - Performance metrics collection
  - Security event logging
  - System resource monitoring
  - Alert system for critical issues

## 🏗️ Deployment Architecture

### Production Environment

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │  Application    │    │    Database     │
│   (Nginx/CF)    │────│   Servers       │────│   (PostgreSQL)  │
│                 │    │   (Flask)       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CDN/Static    │    │   File Storage  │    │   Redis Cache   │
│   Assets        │    │   (S3/GCS)      │    │   (Optional)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Required Environment Variables

```bash
# Core Application
SECRET_KEY=your-super-secret-key-here
FLASK_ENV=production
DATABASE_URL=postgresql://user:pass@host:port/dbname

# AI Services
BAGEL_RL_API_KEY=your-bagel-rl-api-key
OPENAI_API_KEY=your-openai-api-key (fallback)

# Security
RATE_LIMIT_STORAGE_URL=redis://localhost:6379/0
SECURITY_SALT=your-security-salt

# External Services
STRIPE_SECRET_KEY=sk_live_your-stripe-key
STRIPE_PUBLISHABLE_KEY=pk_live_your-stripe-key

# Monitoring
SENTRY_DSN=https://your-sentry-dsn
LOG_LEVEL=INFO

# File Storage
UPLOAD_FOLDER=/secure/uploads
MAX_CONTENT_LENGTH=10485760  # 10MB
```

## 🔒 Security Configuration

### SSL/TLS Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name lexai.example.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Firewall Configuration

```bash
# UFW firewall rules
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 📊 Monitoring Setup

### Health Check Endpoints

- `GET /api/health` - Application health status
- `GET /api/metrics` - Performance metrics
- `GET /api/performance` - Real-time performance data
- `GET /api/security/status` - Security status

### Monitoring Integration

```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
  
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=secure_password
```

## 🚀 Deployment Process

### 1. Pre-deployment Testing

```bash
# Run comprehensive test suite
python run_tests.py all

# Security audit
bandit -r api/ -f json -o reports/security_report.json
safety check --json --output reports/vulnerability_report.json

# Performance baseline
python run_tests.py performance
```

### 2. Database Migration

```bash
# Backup current database
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migrations
python -c "from api.database_models import db; db.create_all()"
```

### 3. Application Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Install production dependencies
pip install -r tests/test_requirements.txt

# Set environment variables
export FLASK_ENV=production
export SECRET_KEY="your-production-secret"

# Start application with gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 api.index:app
```

### 4. Post-deployment Verification

```bash
# Health check
curl -f https://your-domain.com/api/health

# Security check
curl -I https://your-domain.com/ | grep -i security

# Performance check
curl -w "@curl-format.txt" -s -o /dev/null https://your-domain.com/api/status
```

## 🔧 Performance Optimization

### Application Server Configuration

```python
# gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 120
keepalive = 5
preload_app = True
```

### Database Optimization

```sql
-- PostgreSQL performance settings
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
SELECT pg_reload_conf();

-- Indexes for common queries
CREATE INDEX idx_clients_email ON clients(email);
CREATE INDEX idx_cases_status ON cases(status);
CREATE INDEX idx_documents_type ON documents(document_type);
```

### Redis Cache Configuration

```redis
# redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
tcp-keepalive 300
timeout 0
```

## 📈 Scaling Considerations

### Horizontal Scaling

```yaml
# kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lexai-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: lexai
  template:
    metadata:
      labels:
        app: lexai
    spec:
      containers:
      - name: lexai
        image: lexai:latest
        ports:
        - containerPort: 5000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: lexai-secrets
              key: database-url
```

### Load Balancing

```nginx
upstream lexai_backend {
    least_conn;
    server 127.0.0.1:5000 weight=1 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:5001 weight=1 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:5002 weight=1 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name lexai.example.com;
    
    location / {
        proxy_pass http://lexai_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow

```yaml
name: LexAI Production Deployment

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r tests/test_requirements.txt
    
    - name: Run tests
      run: python run_tests.py all
    
    - name: Security scan
      run: |
        bandit -r api/ -f json -o reports/security.json
        safety check --json --output reports/vulnerabilities.json
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
    - name: Deploy to production
      run: |
        # Your deployment script here
        echo "Deploying to production..."
```

## 🚨 Incident Response

### Monitoring Alerts

```python
# alerts.py
ALERT_THRESHOLDS = {
    'response_time': 5.0,      # 5 seconds
    'error_rate': 5.0,         # 5%
    'memory_usage': 85.0,      # 85%
    'cpu_usage': 90.0,         # 90%
    'disk_usage': 95.0         # 95%
}

def send_alert(alert_type, message, severity='warning'):
    # Send to Slack, email, or monitoring service
    pass
```

### Emergency Procedures

1. **High Error Rate**
   - Check application logs: `/logs/lexai.log`
   - Verify database connectivity
   - Check external service status

2. **Performance Issues**
   - Monitor `/api/performance` endpoint
   - Check system resources
   - Review slow query logs

3. **Security Incidents**
   - Check security logs: `/logs/security_audit.log`
   - Review rate limiting logs
   - Monitor failed authentication attempts

## 📋 Maintenance Checklist

### Daily
- [ ] Check application health status
- [ ] Review error logs
- [ ] Monitor performance metrics
- [ ] Verify backup completion

### Weekly
- [ ] Run security scans
- [ ] Review system resource usage
- [ ] Check SSL certificate expiry
- [ ] Update dependencies (security patches)

### Monthly
- [ ] Performance testing
- [ ] Security audit
- [ ] Database maintenance
- [ ] Disaster recovery testing

## 🆘 Troubleshooting

### Common Issues

**Application Won't Start**
```bash
# Check logs
tail -f logs/lexai.log

# Verify environment variables
python -c "import os; print(os.environ.get('DATABASE_URL'))"

# Test database connection
python -c "from api.database_models import db; print(db.engine.execute('SELECT 1').scalar())"
```

**High Memory Usage**
```bash
# Monitor memory usage
python -c "from api.production_monitoring import performance_monitor; print(performance_monitor.get_dashboard_data())"

# Check for memory leaks
python -m memory_profiler api/index.py
```

**Database Connection Issues**
```bash
# Test direct connection
psql $DATABASE_URL -c "SELECT version();"

# Check connection pool
python -c "from api.database_models import db; print(db.engine.pool.status())"
```

## 📞 Support Contacts

- **Development Team**: dev@lexai.com
- **Infrastructure**: ops@lexai.com
- **Security**: security@lexai.com
- **Emergency**: +1-555-LEXAI-911

---

This deployment guide ensures a secure, scalable, and maintainable production environment for LexAI.
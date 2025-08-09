# Tapsi Food Map Dashboard - Deployment Guide

This guide provides step-by-step instructions for deploying the optimized Tapsi Food Map Dashboard in various environments.

## 🎯 Deployment Scenarios

1. **Local Development** - For testing and development
2. **Single Server Production** - Direct deployment on a Linux/Windows server
3. **Docker Deployment** - Containerized deployment
4. **Cloud Deployment** - AWS/GCP/Azure deployment
5. **Load Balanced Setup** - High-availability deployment

---

## 🔧 Prerequisites

### System Requirements

**Minimum Requirements:**
- **CPU**: 2 cores, 2.0 GHz
- **RAM**: 4GB
- **Storage**: 10GB free space
- **OS**: Linux (Ubuntu 20.04+), Windows 10+, macOS 10.15+

**Recommended for Production:**
- **CPU**: 4+ cores, 2.5+ GHz
- **RAM**: 8GB+
- **Storage**: 50GB+ SSD
- **OS**: Ubuntu 20.04+ or CentOS 8+

### Software Dependencies

```bash
# Python 3.9+
python3 --version

# Git (for deployment)
git --version

# SQLite3 (usually pre-installed)
sqlite3 --version
```

---

## 📦 Scenario 1: Local Development

Perfect for testing the application before production deployment.

### Step 1: Environment Setup

```bash
# Create project directory
mkdir tapsi-food-dashboard
cd tapsi-food-dashboard

# Copy your project files here
# (Use the files from the artifacts above)

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

### Step 2: Install Dependencies

```bash
# Install requirements
pip install -r requirements.txt

# Install development dependencies (optional)
pip install pytest black flake8 ipython
```

### Step 3: Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env  # or use your preferred editor
```

**Required configuration for development:**
```bash
METABASE_URL=https://metabase.ofood.cloud
METABASE_USERNAME=your.email@company.com
METABASE_PASSWORD=your_password
ORDER_DATA_QUESTION_ID=5822
VENDOR_DATA_QUESTION_ID=5045

# Development settings
FLASK_ENV=development
FLASK_DEBUG=true
PRELOAD_COVERAGE_GRIDS=false
WORKER_COUNT=4
```

### Step 4: Initialize and Run

```bash
# Run migration if upgrading
python migrate_to_optimized.py

# Start development server
python app_optimized.py

# Or use production runner
python run_production_optimized.py
```

### Step 5: Verify Installation

```bash
# Check application
curl http://localhost:5001/api/initial-data

# Check admin endpoints
curl http://localhost:5001/api/admin/scheduler-status
```

---

## 🚀 Scenario 2: Single Server Production

Deploy directly on a Linux server for production use.

### Step 1: Server Preparation

```bash
# Update system (Ubuntu/Debian)
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3 python3-pip python3-venv git \
                    sqlite3 curl wget nginx supervisor \
                    gdal-bin libgdal-dev libspatialindex-dev \
                    proj-bin libproj-dev libgeos-dev

# For CentOS/RHEL
sudo yum update -y
sudo yum install -y python3 python3-pip git sqlite \
                    curl wget nginx supervisor \
                    gdal gdal-devel spatialindex-devel \
                    proj proj-devel geos geos-devel
```

### Step 2: Application Deployment

```bash
# Create application user
sudo useradd -m -s /bin/bash tapsi
sudo usermod -aG sudo tapsi

# Switch to application user
sudo su - tapsi

# Create application directory
mkdir -p /opt/tapsi-dashboard
cd /opt/tapsi-dashboard

# Deploy application files
# (Copy your files here or use git clone if available)

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Production Configuration

```bash
# Create production environment file
cp .env.example .env.production

# Edit production configuration
nano .env.production
```

**Production configuration:**
```bash
# Metabase (production values)
METABASE_URL=https://metabase.ofood.cloud
METABASE_USERNAME=prod.user@company.com
METABASE_PASSWORD=secure_production_password

# Database
DATABASE_PATH=/opt/tapsi-dashboard/data/tapsi_food_data.db

# Production settings
FLASK_ENV=production
FLASK_DEBUG=false
FLASK_HOST=0.0.0.0
FLASK_PORT=5001

# Performance optimization
WORKER_COUNT=10
PAGE_SIZE=150000
ENABLE_QUERY_OPTIMIZATION=true
PRELOAD_COVERAGE_GRIDS=true
ENABLE_COMPRESSION=true

# Scheduler settings
VENDORS_UPDATE_INTERVAL_MINUTES=10
ORDERS_UPDATE_TIME=09:00
CACHE_CLEANUP_TIME=02:00
```

### Step 4: System Service Setup

Create systemd service file:

```bash
sudo nano /etc/systemd/system/tapsi-dashboard.service
```

```ini
[Unit]
Description=Tapsi Food Map Dashboard
After=network.target

[Service]
Type=simple
User=tapsi
Group=tapsi
WorkingDirectory=/opt/tapsi-dashboard
Environment=PATH=/opt/tapsi-dashboard/venv/bin
EnvironmentFile=/opt/tapsi-dashboard/.env.production
ExecStart=/opt/tapsi-dashboard/venv/bin/python run_production_optimized.py
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/tapsi-dashboard/data /opt/tapsi-dashboard/logs

[Install]
WantedBy=multi-user.target
```

### Step 5: Nginx Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/tapsi-dashboard
```

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files (if served separately)
    location /static/ {
        alias /opt/tapsi-dashboard/public/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:5001/api/admin/scheduler-status;
    }
}
```

### Step 6: SSL Configuration (Recommended)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Step 7: Start Services

```bash
# Enable nginx site
sudo ln -s /etc/nginx/sites-available/tapsi-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Start application service
sudo systemctl daemon-reload
sudo systemctl enable tapsi-dashboard
sudo systemctl start tapsi-dashboard

# Check status
sudo systemctl status tapsi-dashboard
```

### Step 8: Monitoring Setup

```bash
# Create log rotation
sudo nano /etc/logrotate.d/tapsi-dashboard
```

```
/opt/tapsi-dashboard/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 tapsi tapsi
    postrotate
        systemctl reload tapsi-dashboard
    endscript
}
```

---

## 🐳 Scenario 3: Docker Deployment

Containerized deployment for easy scaling and management.

### Step 1: Docker Setup

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in to apply changes
```

### Step 2: Project Setup

```bash
# Create project directory
mkdir tapsi-dashboard-docker
cd tapsi-dashboard-docker

# Create directory structure
mkdir -p data logs src public

# Copy application files
# (Copy all the files from the artifacts)
```

### Step 3: Environment Configuration

```bash
# Create production environment file
cp .env.example .env

# Edit configuration
nano .env
```

### Step 4: Docker Compose Deployment

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

### Step 5: Production Docker Compose

For production, create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  tapsi-dashboard:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: tapsi-food-dashboard
    restart: unless-stopped
    ports:
      - "5001:5001"
    environment:
      - METABASE_URL=${METABASE_URL}
      - METABASE_USERNAME=${METABASE_USERNAME}
      - METABASE_PASSWORD=${METABASE_PASSWORD}
      - DATABASE_PATH=/app/data/tapsi_food_data.db
      - FLASK_ENV=production
      - WORKER_COUNT=12
      - PRELOAD_COVERAGE_GRIDS=true
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./src:/app/src:ro
      - ./public:/app/public:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/api/initial-data"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'

  nginx:
    image: nginx:alpine
    container_name: tapsi-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - tapsi-dashboard
```

Run with:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## ☁️ Scenario 4: Cloud Deployment (AWS Example)

Deploy on AWS EC2 with auto-scaling capabilities.

### Step 1: EC2 Instance Setup

```bash
# Launch EC2 instance (Ubuntu 20.04, t3.medium or larger)
# Configure security groups: HTTP (80), HTTPS (443), SSH (22)

# Connect to instance
ssh -i your-key.pem ubuntu@your-instance-ip

# Update system
sudo apt update && sudo apt upgrade -y
```

### Step 2: AWS-Specific Configuration

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure CloudWatch agent (optional)
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb
```

### Step 3: Application Deployment

Follow the same steps as "Single Server Production" but with AWS-specific modifications:

```bash
# Use RDS for database (optional)
DATABASE_PATH=postgresql://user:pass@rds-endpoint:5432/tapsi_db

# Use S3 for backups (optional)
aws s3 sync /opt/tapsi-dashboard/data/ s3://your-backup-bucket/data/

# Use CloudWatch for monitoring
# Configure cloudwatch-agent with custom metrics
```

### Step 4: Auto Scaling Setup

Create Launch Template:
```json
{
  "LaunchTemplateName": "tapsi-dashboard-template",
  "LaunchTemplateData": {
    "ImageId": "ami-0abcdef1234567890",
    "InstanceType": "t3.medium",
    "SecurityGroupIds": ["sg-0123456789abcdef0"],
    "UserData": "base64-encoded-startup-script"
  }
}
```

Create Auto Scaling Group with appropriate policies.

---

## ⚖️ Scenario 5: Load Balanced Setup

High-availability deployment with multiple servers.

### Step 1: Load Balancer Configuration

Using Nginx as load balancer:

```nginx
upstream tapsi_backend {
    least_conn;
    server 10.0.1.10:5001 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:5001 max_fails=3 fail_timeout=30s;
    server 10.0.1.12:5001 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://tapsi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Health check
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://tapsi_backend/api/admin/scheduler-status;
    }
}
```

### Step 2: Shared Database

Configure shared database (PostgreSQL recommended):

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb tapsi_dashboard
sudo -u postgres createuser tapsi_user

# Update application configuration
DATABASE_PATH=postgresql://tapsi_user:password@db-server:5432/tapsi_dashboard
```

### Step 3: Session Management

Configure shared cache (Redis):

```bash
# Install Redis
sudo apt install redis-server

# Configure application to use Redis for caching
REDIS_URL=redis://cache-server:6379/0
```

---

## 🔍 Post-Deployment Verification

### Health Checks

```bash
# Application health
curl -f http://your-domain.com/api/initial-data

# Scheduler status
curl http://your-domain.com/api/admin/scheduler-status

# Database connectivity
curl http://your-domain.com/api/admin/cache-stats
```

### Performance Testing

```bash
# Load testing with Apache Bench
ab -n 1000 -c 10 http://your-domain.com/

# Monitor resource usage
htop
iotop
```

### Monitoring Setup

```bash
# Set up log monitoring
tail -f /opt/tapsi-dashboard/logs/dashboard.log

# Set up metrics collection
# Configure Prometheus/Grafana for detailed monitoring
```

---

## 🚨 Troubleshooting

### Common Deployment Issues

**Port conflicts:**
```bash
# Check port usage
sudo netstat -tlnp | grep :5001

# Change port in configuration
FLASK_PORT=5002
```

**Permission issues:**
```bash
# Fix file permissions
sudo chown -R tapsi:tapsi /opt/tapsi-dashboard
sudo chmod -R 755 /opt/tapsi-dashboard
```

**Database lock issues:**
```bash
# Check for zombie processes
ps aux | grep python | grep tapsi

# Restart service
sudo systemctl restart tapsi-dashboard
```

### Log Analysis

```bash
# Application logs
sudo journalctl -u tapsi-dashboard -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# System logs
sudo tail -f /var/log/syslog
```

---

## 📋 Maintenance Procedures

### Daily Tasks
- Check application logs
- Monitor resource usage
- Verify data updates

### Weekly Tasks
- Review performance metrics
- Clean up old logs
- Check database integrity

### Monthly Tasks
- Update dependencies
- Backup database
- Review security settings

### Backup Strategy

```bash
#!/bin/bash
# backup.sh - Database backup script

BACKUP_DIR="/backup/tapsi-dashboard"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
cp /opt/tapsi-dashboard/data/tapsi_food_data.db "$BACKUP_DIR/db_backup_$DATE.db"

# Backup configuration
tar -czf "$BACKUP_DIR/config_backup_$DATE.tar.gz" -C /opt/tapsi-dashboard .env src/

# Clean old backups (keep 30 days)
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

Add to crontab:
```bash
# Daily backup at 2 AM
0 2 * * * /opt/tapsi-dashboard/backup.sh >> /var/log/tapsi-backup.log 2>&1
```

---

This deployment guide covers all major scenarios for deploying the Tapsi Food Map Dashboard. Choose the scenario that best fits your infrastructure and requirements.

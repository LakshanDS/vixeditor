# VixEditor CI/CD Deployment Guide

Complete setup guide for automated deployments using GitHub/GitLab webhooks.

## 📋 Overview

This deployment system provides:

- **Automated deployments** via webhook triggers
- **One-click deployment** from GitHub/GitLab
- **Service management** with systemd
- **Deployment logging** for audit trail
- **Security** via webhook secret validation

---

## ⚠️ IMPORTANT: Source Files Setup

The `source/` folder contains large media files and is **NOT included in the git repository**. You must manually create and populate this folder on your deployment server.

### Required Source Directories

```bash
mkdir -p source/videos/styles
mkdir -p source/audio
mkdir -p source/fonts
mkdir -p source/logo
```

### Upload Your Media Files

- **Video Styles**: Copy your video template files to `source/videos/styles/`
- **Audio Files**: Copy background music files to `source/audio/`
- **Fonts**: Copy custom font files (.ttf, .otf) to `source/fonts/`
- **Logo**: Copy logo images to `source/logo/`

**Without these files, the application will not function properly!**

---

## 🚀 Quick Setup

### 1. Configure Webhook Secret

Edit `.env.deploy` and set a strong secret:

```bash
# Generate a random secret
openssl rand -hex 32

# Add to .env.deploy
WEBHOOK_SECRET=your-generated-secret-here
WEBHOOK_PORT=4001
SERVICE_NAME=vixeditor
```

### 2. Install Dependencies

```bash
cd /path/to/CatVideo
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set Up Systemd Services

#### A. Install VixEditor API Service

```bash
# Edit service file with correct paths
sudo nano vixeditor.service

# Update these lines:
# WorkingDirectory=/path/to/CatVideo
# Environment="PATH=/path/to/CatVideo/venv/bin"
# ExecStart=/path/to/CatVideo/venv/bin/python main.py
# StandardOutput=append:/path/to/CatVideo/logs/vixeditor.log
# StandardError=append:/path/to/CatVideo/logs/vixeditor-error.log

# Copy to systemd
sudo cp vixeditor.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable vixeditor
sudo systemctl start vixeditor
sudo systemctl status vixeditor
```

#### B. Install Webhook Service

```bash
# Edit webhook service file
sudo nano vixeditor-webhook.service

# Update paths (same as above)

# Copy to systemd
sudo cp vixeditor-webhook.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable vixeditor-webhook
sudo systemctl start vixeditor-webhook
sudo systemctl status vixeditor-webhook
```

### 4. Configure Firewall

```bash
# Allow webhook port (4001)
sudo ufw allow 4001/tcp

# Allow API port (8000)
sudo ufw allow 8000/tcp

# Check status
sudo ufw status
```

---

## 🔗 GitHub Webhook Setup

### 1. Go to Repository Settings

Navigate to: `https://github.com/LakshanDS/Vix-Video-Editor/settings/hooks`

### 2. Add Webhook

- **Payload URL**: `http://your-server-ip:4001/deploy`
- **Content type**: `application/json`
- **Secret**: `your-webhook-secret-from-.env.deploy`
- **Events**: Select "Just the push event"
- **Active**: ✓ Checked

### 3. Test Webhook

Click "Test" in GitHub or push a commit to trigger deployment.

---

## 🔗 GitLab Webhook Setup

### 1. Go to Repository Settings

Navigate to: `https://gitlab.com/LakshanDS/Vix-Video-Editor/-/settings/hooks`

### 2. Add Webhook

- **URL**: `http://your-server-ip:4001/deploy`
- **Secret Token**: `your-webhook-secret-from-.env.deploy`
- **Trigger**: Select "Push events"
- **Enable SSL verification**: ✓ (if using HTTPS)

### 3. Test Webhook

Click "Test" in GitLab or push a commit.

---

## 🧪 Testing

### Test Deployment Script Manually

```bash
cd /path/to/Vix-Video-Editor
./deploy.sh
```

Expected output:

```
[2025-11-24 22:40:00] ℹ ========================================
[2025-11-24 22:40:00] ℹ Starting deployment for vixeditor
[2025-11-24 22:40:00] ℹ Pulling latest code from git...
[2025-11-24 22:40:01] ✓ Code pulled successfully
[2025-11-24 22:40:01] ✓ Dependencies updated successfully
[2025-11-24 22:40:02] ✓ Service restarted via systemd
[2025-11-24 22:40:04] ✓ Service is running
[2025-11-24 22:40:04] ✓ Deployment completed successfully!
```

### Test Webhook Endpoint

```bash
# Test with curl
curl -X POST http://localhost:4001/deploy \
  -H "X-Webhook-Secret: your-secret-here" \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

Expected response:

```json
{
  "status": "success",
  "message": "Deployment completed successfully",
  "timestamp": "2025-11-24T22:40:05.123456"
}
```

### Check Webhook Service Health

```bash
curl http://localhost:4001/health
```

### View Deployment Logs

```bash
# Webhook logs
tail -f logs/webhook.log

# Deployment logs
tail -f logs/deploy.log

# Service logs
sudo journalctl -u vixeditor -f
sudo journalctl -u vixeditor-webhook -f
```

---

## 📊 Monitoring

### Service Status

```bash
# Check if services are running
sudo systemctl status vixeditor
sudo systemctl status vixeditor-webhook

# View recent logs
sudo journalctl -u vixeditor --since "1 hour ago"
sudo journalctl -u vixeditor-webhook --since "1 hour ago"
```

### Webhook Logs Endpoint

View recent webhook logs via HTTP:

```bash
curl http://localhost:4001/logs
```

---

## 🔒 Security Best Practices

1. **Use Strong Webhook Secret**: Generate with `openssl rand -hex 32`
2. **Firewall Configuration**: Only allow necessary ports
3. **HTTPS**: Use nginx reverse proxy with SSL for production
4. **User Permissions**: Run services as dedicated user (not root)
5. **Log Rotation**: Configure logrotate for log files

### Nginx Reverse Proxy (Optional)

```nginx
# /etc/nginx/sites-available/vixeditor-webhook
server {
    listen 443 ssl;
    server_name webhook.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /deploy {
        proxy_pass http://localhost:4001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 🛠️ Troubleshooting

### Deployment Fails

**Check logs:**

```bash
tail -50 logs/deploy.log
```

**Common issues:**

- Git authentication: Set up SSH keys or use deploy tokens
- Permission errors: Ensure deploy script is executable (`chmod +x deploy.sh`)
- Service restart fails: Check systemd service configuration
- **Missing source files**: Verify `source/` directories exist with media files

### Webhook Not Triggering

**Check webhook service:**

```bash
sudo systemctl status vixeditor-webhook
curl http://localhost:4001/health
```

**Check firewall:**

```bash
sudo ufw status
telnet your-server-ip 4001
```

**Verify webhook secret:**

- Check `.env.deploy` matches GitHub/GitLab webhook secret
- Check webhook service logs: `tail -f logs/webhook.log`

### Service Won't Start

**Check service file paths:**

```bash
sudo systemctl status vixeditor
sudo journalctl -u vixeditor -n 50
```

**Common issues:**

- Incorrect paths in service file
- Virtual environment not activated
- Port already in use
- Missing dependencies
- **Missing source files**: Check `source/` directories

---

## 📁 File Structure

```
Vix-Video-Editor/
├── deploy.sh                    # Deployment script
├── deploy_webhook.py            # Webhook service
├── .env.deploy                  # Deployment config
├── vixeditor.service           # API systemd service
├── vixeditor-webhook.service   # Webhook systemd service
├── source/                      # Source assets (NOT in git!)
│   ├── videos/styles/          # Video templates
│   ├── audio/                  # Background audio
│   ├── fonts/                  # Custom fonts
│   └── logo/                   # Logo images
├── logs/
│   ├── deploy.log              # Deployment history
│   ├── webhook.log             # Webhook activity
│   ├── vixeditor.log          # API logs
│   └── webhook-service.log    # Webhook service logs
└── main.py                     # API application
```

---

## 🔄 Deployment Flow

```
GitHub/GitLab Push
       ↓
   Webhook Trigger
       ↓
Webhook Service (Port 4001)
       ↓
 Verify Signature
       ↓
Execute deploy.sh
       ↓
  1. Git pull
  2. Update dependencies
  3. Restart service
       ↓
  Deployment Complete
       ↓
   Send Response
```

---

## ⚡ Quick Commands

```bash
# Restart API
sudo systemctl restart vixeditor

# Restart webhook
sudo systemctl restart vixeditor-webhook

# View API logs
sudo journalctl -u vixeditor -f

# View webhook logs
sudo journalctl -u vixeditor-webhook -f

# Manual deployment
./deploy.sh

# Check service status
sudo systemctl status vixeditor vixeditor-webhook
```

---

## 📞 Support

For issues or questions:

1. Check logs in `logs/` directory
2. Review systemd service status
3. Verify webhook secret configuration
4. **Ensure source files are uploaded**
5. Test manual deployment with `./deploy.sh`

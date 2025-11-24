# Quick Installation Guide

## One-Command Installation

For a fresh Ubuntu server, you can install Vix-Video-Editor with a single command:

```bash
wget https://raw.githubusercontent.com/LakshanDS/Vix-Video-Editor/main/install.sh
chmod +x install.sh
sudo ./install.sh
```

Or one-liner:

```bash
curl -sSL https://raw.githubusercontent.com/LakshanDS/Vix-Video-Editor/main/install.sh | sudo bash
```

## What the Installer Does

The interactive installer will:

1. **Repository Setup**

   - Asks for git repository URL
   - Asks for installation directory
   - Clones the repository

2. **SSL Configuration (Optional)**

   - Asks if you want SSL/HTTPS
   - If yes:
     - Installs Nginx
     - Asks for domain name
     - Asks for email for Let's Encrypt
     - Sets up SSL certificates
     - Configures reverse proxy for ports 80/443
   - If no:
     - Asks for custom ports to use

3. **Firewall Setup**

   - Opens necessary ports automatically
   - Configures UFW firewall

4. **Environment Configuration**

   - Asks for MASTER_KEY (required)
   - Asks for Google Fonts API key (optional)
   - Asks for IP restrictions (optional)
   - Auto-generates webhook secret

5. **Application Setup**

   - Creates virtual environment
   - Installs all Python dependencies
   - Creates source directories
   - Configures systemd services

6. **Service Deployment**
   - Sets up API service
   - Sets up webhook service
   - Starts all services automatically

## Installation Prompts

You'll be asked for:

- **Repository URL**: Default is `https://github.com/LakshanDS/Vix-Video-Editor.git`
- **Installation Directory**: Default is `/opt/vixeditor`
- **SSL Setup**: Yes/No
  - If yes: Domain, email for SSL
  - If no: Custom ports
- **MASTER_KEY**: (Required) Your admin API key
- **Google Fonts API Key**: (Optional) For Google Fonts integration
- **IP Restriction**: (Optional) Restrict admin endpoints to specific IP

## After Installation

Once installed, you'll need to:

1. **Upload Media Files**

   ```bash
   cd /opt/vixeditor
   # Upload to:
   # - source/videos/styles/
   # - source/audio/
   # - source/fonts/
   # - source/logo/
   ```

2. **Configure Webhook** (GitHub/GitLab)

   - Use the URL provided at end of installation
   - Secret is in `.env.deploy`

3. **Test the API**

   ```bash
   # With SSL:
   curl https://your-domain.com/v1/admin/keys -H "X-Master-Key: your-key"

   # Without SSL:
   curl http://your-ip:8000/v1/admin/keys -H "X-Master-Key: your-key"
   ```

## Manual Installation

For manual installation, see [DEPLOYMENT.md](DEPLOYMENT.md)

## Troubleshooting

If installation fails:

1. Check the logs:

   ```bash
   sudo journalctl -u vixeditor -n 50
   sudo journalctl -u vixeditor-webhook -n 50
   ```

2. Verify services:

   ```bash
   sudo systemctl status vixeditor
   sudo systemctl status vixeditor-webhook
   ```

3. Check firewall:
   ```bash
   sudo ufw status
   ```

## System Requirements

- Ubuntu 20.04 or newer
- Sudo privileges
- 2GB RAM minimum
- 10GB disk space
- Domain name (for SSL setup)

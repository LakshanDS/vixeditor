#!/bin/bash

###############################################################################
# Vix-Video-Editor Automated Installation Script
# One-command setup for complete deployment
###############################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║         Vix-Video-Editor Installation Script             ║"
echo "║              Automated Setup Wizard                      ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please do not run as root. Run as regular user with sudo privileges.${NC}"
   exit 1
fi

# Check Ubuntu version
if [ ! -f /etc/os-release ]; then
    echo -e "${RED}Cannot detect OS. This script is designed for Ubuntu 20.04+${NC}"
    exit 1
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Step 1: Repository Configuration${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# Get repository URL
read -p "Enter the Git repository URL (default: https://github.com/LakshanDS/Vix-Video-Editor.git): " REPO_URL
REPO_URL=${REPO_URL:-https://github.com/LakshanDS/Vix-Video-Editor.git}

# Get installation directory
read -p "Enter installation directory (default: /opt/vixeditor): " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-/opt/vixeditor}

echo -e "${GREEN}✓ Repository: $REPO_URL${NC}"
echo -e "${GREEN}✓ Installation directory: $INSTALL_DIR${NC}"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Step 2: SSL Configuration${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

read -p "Do you want to setup SSL/HTTPS with Nginx reverse proxy? (y/n): " SETUP_SSL
SETUP_SSL=${SETUP_SSL:-n}

if [[ $SETUP_SSL =~ ^[Yy]$ ]]; then
    read -p "Enter your domain name (e.g., vixeditor.example.com): " DOMAIN
    read -p "Enter API subdomain (e.g., api.example.com) or press Enter to use main domain: " API_DOMAIN
    API_DOMAIN=${API_DOMAIN:-$DOMAIN}
    
    read -p "Enter webhook subdomain (e.g., webhook.example.com) or press Enter to skip: " WEBHOOK_DOMAIN
    
    read -p "Enter email for Let's Encrypt SSL certificate: " SSL_EMAIL
    
    USE_HTTPS=true
    API_PORT=443
    WEBHOOK_PORT=443
    echo -e "${GREEN}✓ SSL will be configured for: $API_DOMAIN${NC}"
    if [ -n "$WEBHOOK_DOMAIN" ]; then
        echo -e "${GREEN}✓ Webhook SSL: $WEBHOOK_DOMAIN${NC}"
    fi
else
    USE_HTTPS=false
    read -p "Enter API port (default: 8000): " API_PORT
    API_PORT=${API_PORT:-8000}
    
    read -p "Enter webhook port (default: 4001): " WEBHOOK_PORT
    WEBHOOK_PORT=${WEBHOOK_PORT:-4001}
    
    echo -e "${GREEN}✓ No SSL. Using ports: API=$API_PORT, Webhook=$WEBHOOK_PORT${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Step 3: Firewall Configuration${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

if [ "$USE_HTTPS" = true ]; then
    PORTS_TO_OPEN="80 443 22"
else
    read -p "Enter additional ports to open (space-separated, e.g., 8000 4001): " CUSTOM_PORTS
    PORTS_TO_OPEN="22 $CUSTOM_PORTS"
fi

echo -e "${GREEN}✓ Ports to open: $PORTS_TO_OPEN${NC}"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Step 4: Application Configuration${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# Master Key (required)
while true; do
    read -sp "Enter MASTER_KEY (required, will be hidden): " MASTER_KEY
    echo ""
    if [ -n "$MASTER_KEY" ]; then
        break
    else
        echo -e "${RED}Master key is required!${NC}"
    fi
done

# Google Fonts API Key (optional)
read -p "Enter Google Fonts API Key (optional, press Enter to skip): " GOOGLE_FONTS_KEY

# IP Block (optional)
read -p "Enter IP restriction for admin endpoints (optional, press Enter for none): " MASTER_IP

# Webhook Secret
read -sp "Enter webhook secret (or press Enter to auto-generate): " WEBHOOK_SECRET
echo ""
if [ -z "$WEBHOOK_SECRET" ]; then
    WEBHOOK_SECRET=$(openssl rand -hex 32)
    echo -e "${GREEN}✓ Auto-generated webhook secret${NC}"
fi

echo -e "${GREEN}✓ Configuration collected${NC}"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Installation Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "Repository: ${CYAN}$REPO_URL${NC}"
echo -e "Install Directory: ${CYAN}$INSTALL_DIR${NC}"
echo -e "SSL/HTTPS: ${CYAN}$([ "$USE_HTTPS" = true ] && echo 'Yes' || echo 'No')${NC}"
if [ "$USE_HTTPS" = true ]; then
    echo -e "Domain: ${CYAN}$API_DOMAIN${NC}"
fi
echo -e "Ports: ${CYAN}$PORTS_TO_OPEN${NC}"
echo ""
read -p "Proceed with installation? (y/n): " CONFIRM
if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
    echo -e "${RED}Installation cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Starting Installation...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# Update system
echo -e "${YELLOW}[1/10] Updating system packages...${NC}"
sudo apt-get update -qq

# Install dependencies
echo -e "${YELLOW}[2/10] Installing dependencies...${NC}"
sudo apt-get install -y -qq python3 python3-pip python3-venv git curl wget ffmpeg

if [ "$USE_HTTPS" = true ]; then
    sudo apt-get install -y -qq nginx certbot python3-certbot-nginx
fi

# Setup firewall
echo -e "${YELLOW}[3/10] Configuring firewall...${NC}"
sudo ufw --force enable
for port in $PORTS_TO_OPEN; do
    sudo ufw allow $port/tcp >/dev/null 2>&1
    echo -e "${GREEN}  ✓ Opened port $port${NC}"
done

# Clone repository
echo -e "${YELLOW}[4/10] Cloning repository...${NC}"
sudo mkdir -p $INSTALL_DIR
sudo chown $USER:$USER $INSTALL_DIR
git clone $REPO_URL $INSTALL_DIR
cd $INSTALL_DIR

# Create virtual environment
echo -e "${YELLOW}[5/10] Setting up Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Install Python requirements
echo -e "${YELLOW}[6/10] Installing Python packages...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Create source directories
echo -e "${YELLOW}[7/10] Creating source directories...${NC}"
mkdir -p source/videos/styles source/audio source/fonts source/logo
mkdir -p logs outputs cache
echo -e "${GREEN}  ✓ Source directories created${NC}"
echo -e "${YELLOW}  ⚠  Remember to upload your media files to source/ directories!${NC}"

# Configure environment
echo -e "${YELLOW}[8/10] Configuring environment...${NC}"

cat > .env << EOF
# Admin
MASTER_KEY=$MASTER_KEY
$([ -n "$MASTER_IP" ] && echo "MASTER_IP=$MASTER_IP" || echo "# MASTER_IP=")

# Google Fonts
$([ -n "$GOOGLE_FONTS_KEY" ] && echo "GOOGLE_FONTS_API_KEY=$GOOGLE_FONTS_KEY" || echo "# GOOGLE_FONTS_API_KEY=")

# Database
DATABASE_URL=sqlite:///./catvideo.db

# Cleanup Settings
OUTPUT_RETENTION_HOURS=24
CLEANUP_INTERVAL_MINUTES=60

# Directory Paths
STYLES_DIR=source/videos/styles
AUDIO_DIR=source/audio
FONTS_DIR=source/fonts
LOGO_DIR=source/logo
OUTPUTS_DIR=outputs
EOF

cat > .env.deploy << EOF
# Webhook Configuration
WEBHOOK_SECRET=$WEBHOOK_SECRET
WEBHOOK_PORT=$([ "$USE_HTTPS" = true ] && echo "4001" || echo "$WEBHOOK_PORT")
SERVICE_NAME=vixeditor
EOF

echo -e "${GREEN}  ✓ Environment configured${NC}"

# Setup systemd services
echo -e "${YELLOW}[9/10] Setting up systemd services...${NC}"

# API Service
sudo tee /etc/systemd/system/vixeditor.service > /dev/null << EOF
[Unit]
Description=VixEditor API Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python main.py
Restart=always
RestartSec=10

StandardOutput=append:$INSTALL_DIR/logs/vixeditor.log
StandardError=append:$INSTALL_DIR/logs/vixeditor-error.log

[Install]
WantedBy=multi-user.target
EOF

# Webhook Service
sudo tee /etc/systemd/system/vixeditor-webhook.service > /dev/null << EOF
[Unit]
Description=VixEditor Webhook Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python deploy_webhook.py
Restart=always
RestartSec=10

StandardOutput=append:$INSTALL_DIR/logs/webhook-service.log
StandardError=append:$INSTALL_DIR/logs/webhook-service-error.log

[Install]
WantedBy=multi-user.target
EOF

# Make deploy script executable
chmod +x deploy.sh

echo -e "${GREEN}  ✓ Systemd services created${NC}"

# Setup Nginx with SSL if requested
if [ "$USE_HTTPS" = true ]; then
    echo -e "${YELLOW}[10/10] Setting up Nginx with SSL...${NC}"
    
    # API Nginx config
    sudo tee /etc/nginx/sites-available/vixeditor-api > /dev/null << EOF
server {
    listen 80;
    server_name $API_DOMAIN;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    
    sudo ln -sf /etc/nginx/sites-available/vixeditor-api /etc/nginx/sites-enabled/
    
    # Webhook Nginx config (if domain provided)
    if [ -n "$WEBHOOK_DOMAIN" ]; then
        sudo tee /etc/nginx/sites-available/vixeditor-webhook > /dev/null << EOF
server {
    listen 80;
    server_name $WEBHOOK_DOMAIN;
    
    location / {
        proxy_pass http://127.0.0.1:4001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF
        sudo ln -sf /etc/nginx/sites-available/vixeditor-webhook /etc/nginx/sites-enabled/
    fi
    
    # Test nginx config
    sudo nginx -t
    sudo systemctl restart nginx
    
    # Setup SSL with certbot
    echo -e "${YELLOW}  Setting up SSL certificates...${NC}"
    sudo certbot --nginx -d $API_DOMAIN --non-interactive --agree-tos -m $SSL_EMAIL --redirect
    
    if [ -n "$WEBHOOK_DOMAIN" ]; then
        sudo certbot --nginx -d $WEBHOOK_DOMAIN --non-interactive --agree-tos -m $SSL_EMAIL --redirect
    fi
    
    echo -e "${GREEN}  ✓ Nginx and SSL configured${NC}"
else
    echo -e "${YELLOW}[10/10] Skipping SSL setup...${NC}"
fi

# Enable and start services
echo -e "${YELLOW}Starting services...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable vixeditor vixeditor-webhook
sudo systemctl start vixeditor vixeditor-webhook

# Wait a moment for services to start
sleep 3

# Check service status
if sudo systemctl is-active --quiet vixeditor; then
    echo -e "${GREEN}  ✓ VixEditor API service is running${NC}"
else
    echo -e "${RED}  ✗ VixEditor API service failed to start${NC}"
    sudo journalctl -u vixeditor -n 20 --no-pager
fi

if sudo systemctl is-active --quiet vixeditor-webhook; then
    echo -e "${GREEN}  ✓ Webhook service is running${NC}"
else
    echo -e "${RED}  ✗ Webhook service failed to start${NC}"
    sudo journalctl -u vixeditor-webhook -n 20 --no-pager
fi

# Final summary
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║          Installation Complete! 🎉                       ║${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Installation Details:${NC}"
echo -e "  Install Directory: ${YELLOW}$INSTALL_DIR${NC}"

if [ "$USE_HTTPS" = true ]; then
    echo -e "  API URL: ${YELLOW}https://$API_DOMAIN${NC}"
    [ -n "$WEBHOOK_DOMAIN" ] && echo -e "  Webhook URL: ${YELLOW}https://$WEBHOOK_DOMAIN/deploy${NC}"
else
    SERVER_IP=$(hostname -I | awk '{print $1}')
    echo -e "  API URL: ${YELLOW}http://$SERVER_IP:$API_PORT${NC}"
    echo -e "  Webhook URL: ${YELLOW}http://$SERVER_IP:$WEBHOOK_PORT/deploy${NC}"
fi

echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo -e "  1. ${YELLOW}Upload media files to:${NC}"
echo -e "     - $INSTALL_DIR/source/videos/styles/ (video templates)"
echo -e "     - $INSTALL_DIR/source/audio/ (background music)"
echo -e "     - $INSTALL_DIR/source/fonts/ (custom fonts)"
echo -e "     - $INSTALL_DIR/source/logo/ (logo images)"
echo ""
echo -e "  2. ${YELLOW}Configure GitHub/GitLab webhook:${NC}"
if [ "$USE_HTTPS" = true ] && [ -n "$WEBHOOK_DOMAIN" ]; then
    echo -e "     URL: https://$WEBHOOK_DOMAIN/deploy"
else
    echo -e "     URL: http://$SERVER_IP:$WEBHOOK_PORT/deploy"
fi
echo -e "     Secret: (saved in .env.deploy)"
echo ""
echo -e "  3. ${YELLOW}Test the API:${NC}"
if [ "$USE_HTTPS" = true ]; then
    echo -e "     curl https://$API_DOMAIN/v1/admin/keys -H \"X-Master-Key: your-key\""
else
    echo -e "     curl http://$SERVER_IP:$API_PORT/v1/admin/keys -H \"X-Master-Key: your-key\""
fi
echo ""
echo -e "${CYAN}Useful Commands:${NC}"
echo -e "  View API logs: ${YELLOW}sudo journalctl -u vixeditor -f${NC}"
echo -e "  View webhook logs: ${YELLOW}sudo journalctl -u vixeditor-webhook -f${NC}"
echo -e "  Restart services: ${YELLOW}sudo systemctl restart vixeditor vixeditor-webhook${NC}"
echo -e "  Check status: ${YELLOW}sudo systemctl status vixeditor vixeditor-webhook${NC}"
echo ""
echo -e "${GREEN}Documentation: $INSTALL_DIR/README.md${NC}"
echo -e "${GREEN}For support: https://github.com/LakshanDS/Vix-Video-Editor${NC}"
echo ""

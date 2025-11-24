# Vix-Video-Editor

<div align="center">

![Vix-Video-Editor](https://img.shields.io/badge/Vix-Video%20Editor-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9+-green?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal?style=for-the-badge&logo=fastapi)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**A powerful video generation API with automated text overlays, audio integration, and style customization**

[Features](#-features) • [Quick Start](#-quick-start) • [API Documentation](#-api-documentation) • [Deployment](#-deployment)

</div>

---

## 📋 Overview

**Vix-Video-Editor** (VixEditor) is a high-performance FastAPI-based video generation service that creates custom videos with:

- Dynamic text overlays with customizable fonts and positioning
- Audio track integration
- Multiple video style templates
- Queue-based rendering system
- Automated file cleanup
- Webhook-based CI/CD deployment

Perfect for automated video content creation, marketing materials, social media content, and more.

---

## ✨ Features

### Core Capabilities

- 🎥 **Automated Video Generation** - Queue-based rendering system
- 🎨 **Style Templates** - Pre-configured video styles or custom backgrounds
- 📝 **Dynamic Text Overlays** - Customizable fonts, colors, positioning
- 🎵 **Audio Integration** - Background music from library or custom uploads
- 📊 **Progress Tracking** - Real-time job status and queue position
- 🔄 **Auto Cleanup** - Configurable file retention (default: 24 hours)

### API Features

- 🔐 **API Key Management** - Rate-limited access control
- 📈 **Queue Management** - Efficient job processing
- 💾 **Asset Library** - Browse available styles, audio, and fonts
- 🌐 **Google Fonts Support** - Access to 1000+ web fonts
- 📥 **Direct Download** - Generated video retrieval

### DevOps

- 🚀 **Webhook Deployment** - GitHub/GitLab integration
- 🔧 **Systemd Services** - Production-ready service management
- 📝 **Comprehensive Logging** - Deployment and runtime logs
- 🛡️ **Security** - Webhook secret validation

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- FFmpeg installed
- Ubuntu 20.04+ (for production deployment)
- Git

### Local Development Setup

```bash
# Clone repository
git clone https://github.com/LakshanDS/vixeditor.git
cd vixeditor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create required directories
mkdir -p source/videos/styles source/audio source/fonts source/logo outputs logs cache

# ⚠️ IMPORTANT: Add your source files
# Copy your video styles to: source/videos/styles/
# Copy your audio files to: source/audio/
# Copy your fonts to: source/fonts/
# Copy your logo to: source/logo/

# Configure environment
cp env.example .env
nano .env  # Update MASTER_KEY and other settings

# Run the application
python main.py
```

The API will be available at `http://localhost:8000`

---

## 📁 Project Structure

```
vixeditor/
├── api/                    # API routes and models
│   ├── routers.py         # FastAPI endpoints
│   ├── models.py          # Pydantic models
│   └── security.py        # Authentication
├── core/                   # Core functionality
│   ├── config.py          # Configuration settings
│   ├── renderer.py        # Video rendering engine
│   ├── utils.py           # Utility functions
│   ├── cleanup.py         # File cleanup system
│   └── logging.py         # Logging configuration
├── database/               # Database models
│   └── models.py          # SQLAlchemy models
├── source/                 # Source assets (NOT in git)
│   ├── videos/styles/     # Video style templates
│   ├── audio/             # Background audio files
│   ├── fonts/             # Custom font files
│   └── logo/              # Logo images
├── outputs/                # Generated videos (auto-cleanup)
├── logs/                   # Application logs
├── cache/                  # Font and video cache
├── main.py                # Application entry point
├── deploy.sh              # Deployment script
├── deploy_webhook.py      # Webhook service
└── README.md              # This file
```

> **⚠️ Note**: The `source/` folder contains large media files and is excluded from git. You must manually create and populate this folder on each deployment server.

---

## 📚 API Documentation

### Authentication

All API endpoints (except status checks) require authentication via API key.

**Admin Endpoints** require the `MASTER_KEY` header:

```bash
curl -H "X-Master-Key: your-master-key" http://localhost:8000/v1/admin/keys
```

**Client Endpoints** require an API key header:

```bash
curl -H "X-Api-Key: catv_xxxxx" http://localhost:8000/v1/generate
```

### Core Endpoints

#### 1. Create API Key (Admin)

```http
POST /v1/admin/keys/create
X-Master-Key: your-master-key

{
  "daily_limit": 100,
  "minute_limit": 10
}
```

#### 2. Generate Video

```http
POST /v1/generate
X-Api-Key: catv_xxxxx
Content-Type: application/json

{
  "style": "random",
  "text_lines": [
    {"text": "Hello World", "font": "Arial", "color": "#FFFFFF"}
  ],
  "duration": 10,
  "audio_file": "background-music.mp3"
}
```

**Response:**

```json
{
  "job_id": "job_abc123",
  "status": "in_queue"
}
```

#### 3. Check Status

```http
GET /v1/status/{job_id}
```

**Response:**

```json
{
  "job_id": "job_abc123",
  "status": "complete",
  "progress": 100,
  "filename": "job_abc123.mp4"
}
```

#### 4. Download Video

```http
GET /v1/download/{filename}
```

#### 5. List Available Assets

```http
GET /v1/assets/styles    # List video styles
GET /v1/assets/audios    # List audio files
GET /v1/assets/fonts     # List fonts (local + Google Fonts)
```

For complete API documentation, see [API.md](API.md)

---

## 🔧 Configuration

### Environment Variables (`.env`)

```env
# Admin
MASTER_KEY=your-secure-master-key
MASTER_IP=127.0.0.1  # Optional IP restriction

# Google Fonts API
GOOGLE_FONTS_API_KEY=your-google-api-key

# Database
DATABASE_URL=sqlite:///./catvideo.db

# Cleanup Settings
OUTPUT_RETENTION_HOURS=24
CLEANUP_INTERVAL_MINUTES=60

# Directory Paths (relative to project root)
STYLES_DIR=source/videos/styles
AUDIO_DIR=source/audio
FONTS_DIR=source/fonts
LOGO_DIR=source/logo
OUTPUTS_DIR=outputs
```

### Deployment Configuration (`.env.deploy`)

```env
# Webhook Configuration
WEBHOOK_SECRET=your-webhook-secret
WEBHOOK_PORT=4001
SERVICE_NAME=vixeditor
```

---

## 🚀 Deployment

### Production Deployment on Ubuntu

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete deployment instructions.

**Quick deployment steps:**

```bash
# 1. Setup server and clone repository
git clone https://github.com/yourusername/vixeditor.git
cd vixeditor

# 2. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. ⚠️ CRITICAL: Create source directories and add media files
mkdir -p source/videos/styles source/audio source/fonts source/logo
# Copy your video styles, audio, fonts, and logo files here

# 4. Configure environment
cp env.example .env
nano .env  # Update settings

# 5. Setup systemd services
sudo cp vixeditor.service /etc/systemd/system/
sudo cp vixeditor-webhook.service /etc/systemd/system/
# Edit service files with correct paths first!

sudo systemctl daemon-reload
sudo systemctl enable vixeditor vixeditor-webhook
sudo systemctl start vixeditor vixeditor-webhook

# 6. Configure webhook in GitHub/GitLab
# URL: http://your-server:4001/deploy
# Secret: [your webhook secret from .env.deploy]
```

### Source Files Setup

The `source/` folder is **NOT** included in the repository due to large file sizes. On each deployment server:

1. **Create source directories:**

   ```bash
   mkdir -p source/videos/styles source/audio source/fonts source/logo
   ```

2. **Upload your media files:**

   - Video styles → `source/videos/styles/`
   - Audio files → `source/audio/`
   - Fonts → `source/fonts/`
   - Logo → `source/logo/`

3. **Verify files:**
   ```bash
   ls -lh source/videos/styles/
   ls -lh source/audio/
   ```

---

## 🛠️ Development

### Running Tests

```bash
# Test cleanup system
python test_cleanup.py

# Manual deployment test
./deploy.sh
```

### Adding New Features

1. Create feature branch
2. Implement changes
3. Test locally
4. Push to GitHub
5. Webhook triggers automatic deployment

### Monitoring

```bash
# View application logs
tail -f logs/catvideo.log

# View deployment logs
tail -f logs/deploy.log

# View webhook logs
tail -f logs/webhook.log

# Check service status
sudo systemctl status vixeditor
```

---

## 📊 System Requirements

### Development

- Python 3.9+
- 2GB RAM minimum
- 1GB disk space

### Production

- Ubuntu 20.04+ recommended
- 4GB RAM recommended
- 10GB+ disk space (depending on source files)
- FFmpeg installed
- systemd for service management

---

## 🔒 Security

- **API Key Authentication** - All endpoints protected
- **Rate Limiting** - Per-key daily and minute limits
- **Webhook Signatures** - GitHub/GitLab signature validation
- **IP Restrictions** - Optional MASTER_IP configuration
- **Secrets Management** - Environment variable configuration

---

## 🐛 Troubleshooting

### Common Issues

**Issue**: Video generation fails

- Check FFmpeg is installed: `ffmpeg -version`
- Verify source files exist in `source/` directories
- Check logs: `tail -f logs/catvideo.log`

**Issue**: Webhook not triggering

- Verify webhook secret matches `.env.deploy`
- Check firewall allows port 4001
- View webhook logs: `tail -f logs/webhook.log`

**Issue**: Service won't start

- Check systemd status: `sudo systemctl status vixeditor`
- Verify paths in service files are correct
- Check permissions on project directory

---

## 📝 License

This project is licensed under the MIT License.

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## 📧 Support

For issues and questions:

- Open an issue on GitHub
- Check logs in `logs/` directory
- Review [DEPLOYMENT.md](DEPLOYMENT.md)

---

<div align="center">

**Made with ❤️ by Lakshan De Silva**

⭐ Star us on GitHub if you find this project useful!

</div>

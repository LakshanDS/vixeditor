# Vix-Video-Editor API Documentation

Complete API reference for the VixEditor video generation service.

---

## 🔐 Authentication

VixEditor uses two levels of authentication:

### 1. Master Key (Admin Endpoints)

Used for administrative operations like API key management.

**Header:**

```
X-Master-Key: your-master-key-here
```

**Example:**

```bash
curl -H "X-Master-Key: your-master-key" \
  http://localhost:8000/v1/admin/keys
```

### 2. API Key (Client Endpoints)

Used for video generation and asset retrieval.

**Header:**

```
X-Api-Key: catv_xxxxxxxxxxxxx
```

**Example:**

```bash
curl -H "X-Api-Key: catv_abc123xyz" \
  http://localhost:8000/v1/generate
```

---

## 📡 Base URL

**Development:**

```
http://localhost:8000
```

**Production:**

```
http://your-server-ip:8000
```

---

## 🔑 Admin Endpoints

### Create API Key

Create a new API key with rate limits.

**Endpoint:** `POST /v1/admin/keys/create`

**Authentication:** Master Key required

**Request Body:**

```json
{
  "daily_limit": 100,
  "minute_limit": 10
}
```

**Response:**

```json
{
  "key": "catv_abc123xyz456",
  "daily_limit": 100,
  "minute_limit": 10,
  "created_at": "2025-11-24T22:47:00",
  "usage_count": 0
}
```

**Example:**

```bash
curl -X POST http://localhost:8000/v1/admin/keys/create \
  -H "X-Master-Key: your-master-key" \
  -H "Content-Type: application/json" \
  -d '{
    "daily_limit": 100,
    "minute_limit": 10
  }'
```

---

### List All API Keys

Retrieve all created API keys.

**Endpoint:** `GET /v1/admin/keys`

**Authentication:** Master Key required

**Response:**

```json
{
  "api_keys": [
    {
      "key": "catv_abc123",
      "daily_limit": 100,
      "minute_limit": 10,
      "created_at": "2025-11-24T22:47:00",
      "usage_count": 45
    }
  ]
}
```

**Example:**

```bash
curl http://localhost:8000/v1/admin/keys \
  -H "X-Master-Key: your-master-key"
```

---

### Update API Key

Update rate limits for an existing API key.

**Endpoint:** `PUT /v1/admin/keys/update/{key}`

**Authentication:** Master Key required

**Request Body:**

```json
{
  "daily_limit": 200,
  "minute_limit": 20
}
```

**Response:**

```json
{
  "key": "catv_abc123",
  "daily_limit": 200,
  "minute_limit": 20,
  "created_at": "2025-11-24T22:47:00",
  "usage_count": 45
}
```

**Example:**

```bash
curl -X PUT http://localhost:8000/v1/admin/keys/update/catv_abc123 \
  -H "X-Master-Key: your-master-key" \
  -H "Content-Type: application/json" \
  -d '{
    "daily_limit": 200,
    "minute_limit": 20
  }'
```

---

## 🎥 Video Generation Endpoints

### Generate Video

Submit a video generation job to the queue.

**Endpoint:** `POST /v1/generate`

**Authentication:** API Key required

**Request Body:**

```json
{
  "style": "random",
  "text_lines": [
    {
      "text": "Hello World",
      "font": "Arial",
      "font_size": 60,
      "color": "#FFFFFF",
      "x": 100,
      "y": 200,
      "duration_start": 0,
      "duration_end": 5
    },
    {
      "text": "Welcome to VixEditor",
      "font": "Google:Roboto",
      "font_size": 40,
      "color": "#FFD700",
      "x": 150,
      "y": 300,
      "duration_start": 2,
      "duration_end": 8
    }
  ],
  "duration": 10,
  "audio_file": "background-music.mp3"
}
```

**Field Descriptions:**

| Field        | Type    | Required | Description                            |
| ------------ | ------- | -------- | -------------------------------------- |
| `style`      | string  | Yes      | Video style name or "random"           |
| `text_lines` | array   | Yes      | Array of text overlay configurations   |
| `duration`   | integer | Yes      | Total video duration in seconds        |
| `audio_file` | string  | No       | Background audio filename from library |

**Text Line Fields:**

| Field            | Type    | Required | Default   | Description                            |
| ---------------- | ------- | -------- | --------- | -------------------------------------- |
| `text`           | string  | Yes      | -         | Text content to display                |
| `font`           | string  | No       | "Arial"   | Font name (local or "Google:FontName") |
| `font_size`      | integer | No       | 50        | Font size in pixels                    |
| `color`          | string  | No       | "#FFFFFF" | Hex color code                         |
| `x`              | integer | No       | 100       | X position (pixels from left)          |
| `y`              | integer | No       | 100       | Y position (pixels from top)           |
| `duration_start` | float   | No       | 0         | When text appears (seconds)            |
| `duration_end`   | float   | No       | duration  | When text disappears (seconds)         |

**Response:**

```json
{
  "job_id": "job_abc123def",
  "status": "in_queue"
}
```

**Status Values:**

- `in_queue` - Waiting to be processed
- `rendering` - Currently being rendered
- `complete` - Video ready for download
- `failed` - Rendering failed

**Example:**

```bash
curl -X POST http://localhost:8000/v1/generate \
  -H "X-Api-Key: catv_abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "style": "random",
    "text_lines": [
      {
        "text": "Hello World",
        "font": "Arial",
        "color": "#FFFFFF"
      }
    ],
    "duration": 10,
    "audio_file": "background-music.mp3"
  }'
```

---

### Check Job Status

Get the current status and progress of a video generation job.

**Endpoint:** `GET /v1/status/{job_id}`

**Authentication:** None required

**Path Parameters:**

- `job_id` - Job ID returned from /v1/generate

**Response (In Queue):**

```json
{
  "job_id": "job_abc123",
  "status": "in_queue",
  "progress": 0,
  "queue_position": 3,
  "estimated_time_remaining_s": null
}
```

**Response (Rendering):**

```json
{
  "job_id": "job_abc123",
  "status": "rendering",
  "progress": 45,
  "queue_position": null,
  "estimated_time_remaining_s": 12
}
```

**Response (Complete):**

```json
{
  "job_id": "job_abc123",
  "status": "complete",
  "progress": 100,
  "queue_position": null,
  "estimated_time_remaining_s": 0,
  "filename": "job_abc123.mp4"
}
```

**Example:**

```bash
curl http://localhost:8000/v1/status/job_abc123
```

---

### Download Video

Download a completed video.

**Endpoint:** `GET /v1/download/{filename}`

**Authentication:** None required

**Path Parameters:**

- `filename` - Filename returned from status endpoint

**Response:** Video file (video/mp4)

**Example:**

```bash
curl http://localhost:8000/v1/download/job_abc123.mp4 \
  --output my-video.mp4
```

Or open in browser:

```
http://localhost:8000/v1/download/job_abc123.mp4
```

---

## 📦 Asset Endpoints

### List Video Styles

Get available video style templates.

**Endpoint:** `GET /v1/assets/styles`

**Authentication:** API Key required

**Response:**

```json
{
  "styles": ["random", "style1", "style2", "modern-dark", "gradient-blue"]
}
```

**Example:**

```bash
curl http://localhost:8000/v1/assets/styles \
  -H "X-Api-Key: catv_abc123"
```

---

### List Audio Files

Get available background audio files.

**Endpoint:** `GET /v1/assets/audios`

**Authentication:** API Key required

**Response:**

```json
{
  "audios": ["background-music.mp3", "upbeat-track.mp3", "calm-ambient.mp3"]
}
```

**Example:**

```bash
curl http://localhost:8000/v1/assets/audios \
  -H "X-Api-Key: catv_abc123"
```

---

### List Fonts

Get available fonts (local + Google Fonts).

**Endpoint:** `GET /v1/assets/fonts`

**Authentication:** API Key required

**Response:**

```json
{
  "local_fonts": [
    "Arial",
    "CustomFont",
    "MyFont"
  ],
  "google_fonts": [
    "Roboto",
    "Open Sans",
    "Lato",
    "Montserrat",
    ...
  ]
}
```

**Using Google Fonts:**

Use the prefix `Google:` before the font name:

```json
{
  "text": "Hello",
  "font": "Google:Roboto"
}
```

**Example:**

```bash
curl http://localhost:8000/v1/assets/fonts \
  -H "X-Api-Key: catv_abc123"
```

---

## 📋 Complete Workflow Example

### 1. Create API Key (Admin)

```bash
API_KEY=$(curl -X POST http://localhost:8000/v1/admin/keys/create \
  -H "X-Master-Key: your-master-key" \
  -H "Content-Type: application/json" \
  -d '{"daily_limit": 100, "minute_limit": 10}' \
  | jq -r '.key')

echo "API Key: $API_KEY"
```

### 2. List Available Assets

```bash
# Get styles
curl http://localhost:8000/v1/assets/styles \
  -H "X-Api-Key: $API_KEY"

# Get audio files
curl http://localhost:8000/v1/assets/audios \
  -H "X-Api-Key: $API_KEY"

# Get fonts
curl http://localhost:8000/v1/assets/fonts \
  -H "X-Api-Key: $API_KEY"
```

### 3. Generate Video

```bash
JOB_ID=$(curl -X POST http://localhost:8000/v1/generate \
  -H "X-Api-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "style": "random",
    "text_lines": [
      {
        "text": "Amazing Video",
        "font": "Google:Roboto",
        "font_size": 60,
        "color": "#FFFFFF",
        "x": 100,
        "y": 200
      }
    ],
    "duration": 10,
    "audio_file": "background-music.mp3"
  }' | jq -r '.job_id')

echo "Job ID: $JOB_ID"
```

### 4. Monitor Progress

```bash
# Check status
curl http://localhost:8000/v1/status/$JOB_ID

# Loop until complete
while true; do
  STATUS=$(curl -s http://localhost:8000/v1/status/$JOB_ID | jq -r '.status')
  PROGRESS=$(curl -s http://localhost:8000/v1/status/$JOB_ID | jq -r '.progress')
  echo "Status: $STATUS - Progress: $PROGRESS%"

  if [ "$STATUS" = "complete" ]; then
    break
  fi

  sleep 2
done
```

### 5. Download Video

```bash
FILENAME=$(curl -s http://localhost:8000/v1/status/$JOB_ID | jq -r '.filename')
curl http://localhost:8000/v1/download/$FILENAME --output my-video.mp4

echo "Video downloaded: my-video.mp4"
```

---

## ⚠️ Error Responses

### 401 Unauthorized

```json
{
  "detail": "Invalid or missing API key"
}
```

**Cause:** Missing or invalid X-Api-Key header

---

### 404 Not Found

```json
{
  "detail": "Job not found"
}
```

**Cause:** Invalid job_id or filename

---

### 429 Too Many Requests

```json
{
  "detail": "Rate limit exceeded"
}
```

**Cause:** Exceeded daily or minute rate limits

---

### 500 Internal Server Error

```json
{
  "detail": "Video rendering failed"
}
```

**Cause:** Error during video generation (check logs)

---

## 🔧 Rate Limiting

Rate limits are enforced per API key:

- **Daily Limit**: Maximum requests per 24 hours
- **Minute Limit**: Maximum requests per minute

**Headers in Response:**

```
X-RateLimit-Daily-Limit: 100
X-RateLimit-Daily-Remaining: 85
X-RateLimit-Minute-Limit: 10
X-RateLimit-Minute-Remaining: 8
```

---

## 💡 Best Practices

1. **Poll Wisely**: Check job status every 2-5 seconds, not faster
2. **Handle Failures**: Implement retry logic for failed jobs
3. **Validate Assets**: Use asset endpoints to validate style/audio/font names
4. **Cache Responses**: Cache asset lists to reduce API calls
5. **Use Webhooks**: For production, implement a webhook callback instead of polling

---

## 📚 Additional Resources

- [README.md](README.md) - Project overview and setup
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [GitHub Repository](https://github.com/yourusername/vixeditor)

---

<div align="center">

**VixEditor API Documentation**

Version 1.0.0

</div>

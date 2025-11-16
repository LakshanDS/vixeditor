
CATVIDEO/
├── api/
│   ├── __init__.py
│   ├── models.py         # Pydantic models for request/response validation
│   ├── routers.py        # API endpoint definitions
│   └── security.py       # API key and master key handling
├── core/
│   ├── __init__.py
|   ├── config.py         # Application configuration
│   ├── renderer.py       # The main video processing logic
│   └── utils.py          # Helper functions (e.g., getting video duration)
├── database/
│   ├── __init__.py
│   ├── database.py       # Database connection and session management
│   └── models.py         # Job and API key table models
├── jobs/                 # A placeholder for job-related temporary files
├── logs/                 # For application logs
├── outputs/              # Where final videos will be stored
├── source/               # Your existing source assets (videos, audio, etc.)
│   ├── audio/
│   ├── fonts/
│   ├── logo/
│   └── videos/
│       └── styles/
│           ├── California.mp4
│           └── style_skips.json
├── .env                  # Environment variables (API keys, secrets)
├── main.py               # Main FastAPI application entry point
└── requirements.txt      # Python dependencies


### **1. Proposed Architecture & Technology Stack**

Given your requirements, here's a recommended stack that builds on your existing structure:

*   **API Framework:** **FastAPI**. It's a modern, high-performance Python framework perfect for this task. It handles asynchronous requests (like your `/generate` endpoint) gracefully, automatically generates interactive documentation, and uses Pydantic for data validation, which maps perfectly to your JSON request body.
*   **Video Processing:** **OpenCV (`cv2`)** as you requested, for frame-by-frame manipulation. We'll also use **Pillow (`PIL`)** for advanced text rendering and **NumPy** for efficient frame data handling.
*   **Audio Processing:** **pydub** or **moviepy** are excellent libraries for handling audio fades, volume adjustments, and slicing.
*   **Database:** **SQLite** as requested, using Python's built-in `sqlite3` module or an ORM like **SQLAlchemy** for easier management.
*   **Background Jobs:** A separate process for video rendering is crucial so the API doesn't hang. We can start with Python's built-in **`multiprocessing`** module to spawn a new process for each job. For a more robust solution later, you could integrate a task queue like **Celery**.
*   **In-Memory Job Tracking:** A simple Python dictionary can act as our "short-term memory" to track job statuses before they are finalized in the database.

---

### **2. Database Schema (SQLite)**

We'll need two main tables to start.

**`jobs` Table:** To track each video generation request.
```sql
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    progress INTEGER DEFAULT 0,
    queue_position INTEGER DEFAULT 0,
    request_data TEXT NOT NULL,
    output_filename TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**`api_keys` Table:** For managing access and rate limiting.
```sql
CREATE TABLE IF NOT EXISTS api_keys (
    key TEXT PRIMARY KEY,
    daily_limit INTEGER NOT NULL,
    minute_limit INTEGER NOT NULL,
    daily_usage INTEGER DEFAULT 0,
    last_request_timestamp TIMESTAMP
);
```

---

### **3. Detailed Endpoint Design**

Here is a breakdown of the API endpoints based on your plan.

#### **Endpoint 1 & 2: Video Generation and Status**

These two work together. The generation endpoint creates the job, and the status endpoint checks its progress.

**A) `POST /v1/generate`** (The "reserve" endpoint)

*   **Purpose:** Accepts the video creation JSON, validates it, creates a unique `job_id`, and places the job in a queue.
*   **Authentication:** Requires a valid API key in the header. Performs rate-limiting checks against the `api_keys` table.
*   **Process:**
    1.  Generate a unique `job_id` (e.g., using `uuid.uuid4()`).
    2.  Store the full JSON request and initial status (`in_queue`) in the `jobs` table.
    3.  Add the `job_id` to a background processing queue.
    4.  Immediately return a `202 Accepted` response.
*   **Success Response (202 Accepted):**
    ```json
    {
      "job_id": "a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8",
      "status": "in_queue",
      "queue_position": 5 // e.g., 5th item in the queue
    }
    ```

**B) `GET /v1/status/{job_id}`**

*   **Purpose:** Provides the real-time status of a video rendering job.
*   **Process:**
    1.  Query the `jobs` table using the `job_id`.
    2.  Return the current status and progress.
*   **Responses:**
    *   **If Queued:**
        ```json
        {
          "status": "in_queue",
          "queue_position": 1
        }
        ```
    *   **If Rendering:**
        ```json
        {
          "status": "rendering",
          "progress": "44%"
        }
        ```
    *   **If Complete:**
        ```json
        {
          "status": "complete",
          "download_url": "/v1/download/a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8.mp4"
        }
        ```
    *   **If Failed:**
        ```json
        {
          "status": "failed",
          "error_message": "Could not find a source video with sufficient duration."
        }
        ```

**C) `GET /v1/download/{filename}`**

*   **Purpose:** Serves the final rendered video file. FastAPI has a `FileResponse` object perfect for this.

---

### **4. Supporting Endpoints (Data Retrieval)**

**A) `GET /v1/assets/styles`**

*   **Purpose:** Lists all available video styles.
*   **Process:** Scans the `source/videos/styles/` directory and returns the names of the video files (e.g., "California.mp4", "driving.mp4").
*   **Response:**
    ```json
    {
      "styles": ["California", "driving", "raining"]
    }
    ```

**B) `GET /v1/assets/audios`**

*   **Purpose:** Lists all available audio tracks.
*   **Process:** Scans the `source/audio/` directory.
*   **Response:**
    ```json
    {
      "audios": ["upbeat-track.mp3", "cinematic-strings.wav", "lofi-beat.mp3"]
    }
    ```

**C) `GET /v1/assets/fonts`**

*   **Purpose:** Lists all available local and Google Fonts.
*   **Process:**
    1.  Scan `source/fonts/` for local `.ttf` and `.otf` files.
    2.  Use your Google Fonts API key to fetch a list of available font families.
    3.  Combine the lists. When a Google Font is used in a render, the API will download it and cache it in the `source/fonts/google/` directory.
*   **Response:**
    ```json
    {
      "local_fonts": ["AlanSans-Medium", "BebasNeue-Regular", "Oswald-Regular"],
      "google_fonts": ["Roboto", "Lato", "Montserrat", "Poppins", "...etc"]
    }
    ```

---

### **5. Admin Endpoint**

**`POST /v1/admin/create-key`**

*   **Purpose:** Generates a new API key.
*   **Authentication:** This endpoint must be protected. The simplest way is to require a `MASTER_KEY` and `MASTER_IP` (as you suggested) stored in your `.env` file. The request must include this master key in a header.
*   **Request Body:**
    ```json
    {
      "daily_limit": 1000,
      "minute_limit": 10
    }
    ```
*   **Process:**
    1.  Generate a new secure key.
    2.  Store it in the `api_keys` table with the specified limits.
*   **Success Response:**
    ```json
    {
      "message": "API key created successfully",
      "api_key": "newly-generated-secure-api-key"
    }
    ```

---

### **6. Core Logic for the Video Renderer**

This is the heart of the application, which will run in a background process.

1.  **Asset Selection & Validation:**
    *   If `style` is "random", pick a random video from the `source/videos/styles/` directory. Otherwise, use the specified style.
    *   **Crucial Duration Check:** Calculate the required source video duration: `required_length = final_duration / speed`.
    *   Use a tool like `ffprobe` (via a subprocess) or OpenCV's `get(cv2.CAP_PROP_FRAME_COUNT)` and `get(cv2.CAP_PROP_FPS)` to get the duration of candidate videos.
    *   Filter out any videos that are shorter than `required_length`. If no video is long enough, the job fails.
    *   **Skip Zones:** If a style is chosen (e.g., "California"), parse `style_skips.json`. Find all valid time ranges in the source video that can provide a continuous clip of `required_length`. Pick a random starting point from one of these valid ranges.

2.  **Frame Processing with Parallelism:**
    *   The main rendering process will spawn a pool of worker processes using `multiprocessing.Pool`, with the number of workers ideally matching the number of CPU cores.
    *   The main process reads frames one by one from the source video clip.
    *   Each frame (as a NumPy array) is sent to a worker process in the pool.
    *   **The worker function applies all effects to a single frame:**
        *   **Adjustments:** Brightness, contrast, and saturation can be applied using OpenCV's `cv2.add`, `cv2.multiply`, and color space conversions (e.g., to HSV).
        *   **Blur:** Apply `cv2.GaussianBlur`.
        *   **Text/Signature/Logo:** Use Pillow to draw text and logos onto a transparent overlay image, then blend this overlay with the frame using OpenCV. This gives you more control over fonts and anti-aliasing.
        *   **Fades:** For fade-in/out, calculate an opacity multiplier based on the frame number and blend the frame with a black frame.
    *   The main process collects the processed frames in order from the workers.

3.  **Final Compilation:**
    *   The sequence of processed frames is written to a temporary output video file using `cv2.VideoWriter`.
    *   The selected audio track is processed (fades, volume) using `pydub` and combined with the output video using **FFmpeg** (this is one area where a direct FFmpeg command is often simplest and most reliable).
    *   The final video is moved to a public-facing download directory, and the job status is updated to "complete" in the database.

---
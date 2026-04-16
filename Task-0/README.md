# Genderize Classify API

A REST API built with **FastAPI** that wraps the [Genderize.io](https://genderize.io) service to classify names by gender with confidence scoring.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Deployment](#deployment)

---

## Overview

This API accepts a name as a query parameter, calls the Genderize.io API, processes the response, and returns structured data including a confidence flag based on probability and sample size thresholds.

---

## Tech Stack

- **Python 3.12**
- **FastAPI** — web framework
- **Uvicorn** — ASGI server
- **HTTPX** — async HTTP client

---

## Project Structure

```
.
├── main.py            # Application entry point
├── requirements.txt   # Python dependencies
├── Procfile           # Process file for Railway/Heroku deployment
├── nixpacks.toml      # Build config for Railway
├── runtime.txt        # Python version declaration
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip

### Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --port 3000
```

The server will be running at `http://localhost:3000`

---

## API Reference

### Classify Name

```
GET /api/classify?name={name}
```

Classifies a name by gender using the Genderize.io API.

#### Query Parameters

| Parameter | Type   | Required | Description          |
|-----------|--------|----------|----------------------|
| `name`    | string | Yes      | The name to classify |

#### Success Response `200 OK`

```json
{
  "status": "success",
  "data": {
    "name": "john",
    "gender": "male",
    "probability": 0.99,
    "sample_size": 1234,
    "is_confident": true,
    "processed_at": "2026-04-15T10:00:00Z"
  }
}
```

#### Response Fields

| Field | Description |
|-------|-------------|
| `name` | The name that was classified |
| `gender` | `male` or `female` |
| `probability` | Probability score from Genderize.io (0 to 1) |
| `sample_size` | Number of samples used for prediction (renamed from `count`) |
| `is_confident` | `true` only when `probability >= 0.7` AND `sample_size >= 100` |
| `processed_at` | UTC timestamp in ISO 8601 format, generated fresh on every request |

#### Error Responses

| Status | Condition | Message |
|--------|-----------|---------|
| `400` | Missing or empty `name` parameter | `"Missing or empty name parameter"` |
| `422` | `name` is not a valid string | `"name must be a string"` |
| `200` | Name has no gender data on Genderize.io | `"No prediction available for the provided name"` |
| `502` | Genderize.io is unreachable or timed out | Upstream error message |

All errors follow this structure:

```json
{
  "status": "error",
  "message": "<error message>"
}
```

#### Example Requests

```bash
# Valid name
curl "http://localhost:3000/api/classify?name=john"

# Missing name → 400
curl "http://localhost:3000/api/classify"

# Empty name → 400
curl "http://localhost:3000/api/classify?name="

# Unknown name → no prediction
curl "http://localhost:3000/api/classify?name=xyzabc999"
```

---

## Deployment

### Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New** → **Web Service**
3. Connect your GitHub repo
4. Set the following:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Click **Deploy**

### Railway

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Select your repo — Railway will use the `Procfile` and `nixpacks.toml` automatically
4. Click **Generate Domain** under Settings to get your public URL

### Heroku

```bash
heroku create your-app-name
git push heroku main
```
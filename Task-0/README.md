# Genderize Classify API (Python)

A FastAPI service that wraps [Genderize.io](https://genderize.io) and returns structured gender classification data.

---

## Endpoint

### `GET /api/classify?name={name}`

#### Success Response — `200 OK`

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

#### Error Responses

| Status | Condition | Message |
|--------|-----------|---------|
| 400 | Missing or empty `name` | `"Missing or empty name parameter"` |
| 422 | `name` is not a string | `"name must be a string"` |
| 200 | Name has no gender data | `"No prediction available for the provided name"` |
| 502 | Genderize unreachable | Upstream error message |

---

## Running Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 3000
```

Test:
```bash
curl "http://localhost:3000/api/classify?name=john"
```

---

## Deployment

### Railway (recommended)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Railway uses the `Procfile` automatically — add a `PORT` env var if needed (Railway injects it)
4. Click **Generate Domain**

### Heroku

```bash
heroku create your-app-name
git push heroku main
```

### Render

```
Start command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## Tech Stack

- **FastAPI** — web framework
- **uvicorn** — ASGI server
- **httpx** — async HTTP client for Genderize calls
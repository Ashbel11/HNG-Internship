# Profile Intelligence Service

A REST API that accepts a name, enriches it using three external APIs, persists the result in SQLite, and exposes full CRUD and filtering endpoints.

---

## Tech Stack

| Component    | Choice                                           |
|--------------|--------------------------------------------------|
| Language     | Python 3.12+                                     |
| Framework    | FastAPI + Uvicorn                                |
| Database     | SQLite (Python stdlib — no setup needed)         |
| HTTP client  | httpx with asyncio.gather (parallel API calls)   |
| IDs          | UUID v7 (time-ordered, implemented from scratch) |

---

## Quick Start

### 1. Install dependencies
```bash
cd profile-service-py
pip install -r requirements.txt
```

### 2. Run the server
```bash
python main.py
```

You should see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:3000
```

Leave the terminal open — closing it stops the server.

### 3. Verify it's working

Open a new terminal and run:
```bash
curl http://localhost:3000/api/profiles
```

Expected response:
```json
{"status": "success", "count": 0, "data": []}
```

---

## Environment Variables

| Variable  | Default       | Description                      |
|-----------|---------------|----------------------------------|
| `PORT`    | `3000`        | HTTP port the server listens on  |
| `DB_PATH` | `profiles.db` | Path to the SQLite database file |

Override at startup:
```bash
PORT=8080 python main.py
```

---

## Docker

```bash
# Build
docker build -t profile-service .

# Run (database persisted in a named volume)
docker run -p 3000:3000 -v profile-data:/app/data profile-service
```

---

## API Reference

### `POST /api/profiles`

Creates a new profile by calling Genderize, Agify, and Nationalize in parallel.
Submitting the same name again is **idempotent** — the existing record is returned, no duplicate is created.

**Request**
```json
{ "name": "ella" }
```

**Response `201`** — new profile created
```json
{
  "status": "success",
  "data": {
    "id":                  "019508a2-3c1e-7000-9a0b-1f2e3d4c5b6a",
    "name":                "ella",
    "gender":              "female",
    "gender_probability":  0.98,
    "sample_size":         85042,
    "age":                 35,
    "age_group":           "adult",
    "country_id":          "GB",
    "country_probability": 0.12,
    "created_at":          "2026-04-17T10:00:00Z"
  }
}
```

**Response `200`** — profile already exists
```json
{
  "status":  "success",
  "message": "Profile already exists",
  "data":    { "...existing profile..." }
}
```

---

### `GET /api/profiles`

Returns all profiles. Supports optional, case-insensitive query filters.

| Parameter    | Example            |
|--------------|--------------------|
| `gender`     | `?gender=female`   |
| `country_id` | `?country_id=NG`   |
| `age_group`  | `?age_group=adult` |

Filters can be combined:
```
GET /api/profiles?gender=male&country_id=NG&age_group=adult
```

**Response `200`**
```json
{
  "status": "success",
  "count":  2,
  "data": [
    { "id": "...", "name": "ella",     "gender": "female", "age": 35, "age_group": "adult", "country_id": "GB" },
    { "id": "...", "name": "emmanuel", "gender": "male",   "age": 25, "age_group": "adult", "country_id": "NG" }
  ]
}
```

---

### `GET /api/profiles/{id}`

Returns a single full profile by UUID.

**Response `200`**
```json
{
  "status": "success",
  "data": {
    "id":                  "019508a2-3c1e-7000-9a0b-1f2e3d4c5b6a",
    "name":                "ella",
    "gender":              "female",
    "gender_probability":  0.98,
    "sample_size":         85042,
    "age":                 35,
    "age_group":           "adult",
    "country_id":          "GB",
    "country_probability": 0.12,
    "created_at":          "2026-04-17T10:00:00Z"
  }
}
```

**Response `404`**
```json
{ "status": "error", "message": "Profile not found" }
```

---

### `DELETE /api/profiles/{id}`

Deletes a profile. Returns `204 No Content` on success, `404` if the ID does not exist.

---

## Business Rules

### Age Group Classification

| Age Range | Group      |
|-----------|------------|
| 0 – 12    | `child`    |
| 13 – 19   | `teenager` |
| 20 – 59   | `adult`    |
| 60+       | `senior`   |

### Country Selection

Nationalize may return multiple countries. The one with the **highest probability** is stored as `country_id` and `country_probability`.

### 502 Trigger Conditions

If any external API returns unusable data, the request fails with `502` and **nothing is stored**.

| API         | Condition that triggers 502           |
|-------------|---------------------------------------|
| Genderize   | `gender` is `null` OR `count` is `0`  |
| Agify       | `age` is `null`                       |
| Nationalize | `country` array is empty or missing   |

---

## Error Reference

| Status Code | Triggered When                                          |
|-------------|---------------------------------------------------------|
| `400`       | `name` is missing, null, empty, or whitespace-only      |
| `422`       | `name` is the wrong type (integer, list, boolean, etc.) |
| `404`       | Profile ID does not exist                               |
| `502`       | An external API returned invalid data                   |
| `500`       | Unexpected internal server error                        |

All error responses:
```json
{ "status": "error", "message": "<description>" }
```

502 errors use a slightly different envelope:
```json
{ "status": "502", "message": "Genderize returned an invalid response" }
```

---

## CORS

Every response includes `Access-Control-Allow-Origin: *` via an HTTP middleware, ensuring the header is always present regardless of whether the client sends an `Origin` header.

---

## Project Files

| File               | Purpose                                               |
|--------------------|-------------------------------------------------------|
| `main.py`          | Complete application — all routes, DB, validation     |
| `requirements.txt` | pip dependencies (FastAPI, uvicorn, httpx)            |
| `Dockerfile`       | Container build with persistent volume for the DB     |
| `.env.example`     | Documents `PORT` and `DB_PATH` environment variables  |
| `.gitignore`       | Excludes `venv/`, `.env`, `*.db` from version control |
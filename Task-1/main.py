"""
Profile Intelligence Service
FastAPI + SQLite (stdlib) + httpx (async)
"""

import asyncio
import os
import sqlite3
import struct
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, field_validator



def uuid7() -> str:
    """
    Generate a UUID version 7 (time-ordered).
    48-bit unix_ts_ms | 4-bit ver(0111) | 12-bit rand_a | 2-bit var(10) | 62-bit rand_b
    """
    ts_ms  = int(time.time() * 1000)
    rand_a = random.getrandbits(12)
    rand_b = random.getrandbits(62)
    high   = (ts_ms << 16) | (0x7 << 12) | rand_a
    low    = (0b10 << 62) | rand_b
    raw    = struct.pack(">QQ", high, low)
    h      = raw.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"



DB_PATH = os.environ.get("DB_PATH", "profiles.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id                  TEXT PRIMARY KEY,
                name                TEXT NOT NULL UNIQUE,
                gender              TEXT,
                gender_probability  REAL,
                sample_size         INTEGER,
                age                 INTEGER,
                age_group           TEXT,
                country_id          TEXT,
                country_probability REAL,
                created_at          TEXT NOT NULL
            )
        """)
        conn.commit()



@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Profile Intelligence Service", lifespan=lifespan)


# ─── CORS — force header on EVERY response (not just origin-bearing requests) ─

@app.middleware("http")
async def add_cors_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.options("/{rest:path}")
async def preflight(_: Request):
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )



def classify_age(age: int) -> str:
    if age <= 12:  return "child"
    if age <= 19:  return "teenager"
    if age <= 59:  return "adult"
    return "senior"


def row_to_full(row: sqlite3.Row) -> dict:
    return {
        "id":                  row["id"],
        "name":                row["name"],
        "gender":              row["gender"],
        "gender_probability":  row["gender_probability"],
        "sample_size":         row["sample_size"],
        "age":                 row["age"],
        "age_group":           row["age_group"],
        "country_id":          row["country_id"],
        "country_probability": row["country_probability"],
        "created_at":          row["created_at"],
    }


def row_to_summary(row: sqlite3.Row) -> dict:
    return {
        "id":         row["id"],
        "name":       row["name"],
        "gender":     row["gender"],
        "age":        row["age"],
        "age_group":  row["age_group"],
        "country_id": row["country_id"],
    }


def err(status: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"status": "error", "message": message},
        headers={"Access-Control-Allow-Origin": "*"},
    )



class ProfileRequest(BaseModel):
    name: object  # accept anything; validate manually for precise error codes

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v):
        # null / missing → 400
        if v is None:
            raise ValueError("__missing__")
        # wrong type → 422
        if not isinstance(v, str):
            raise TypeError("__type__")
        # empty / whitespace → 400
        if not v.strip():
            raise ValueError("__missing__")
        return v.strip()



async def fetch_all(name: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        responses = await asyncio.gather(
            client.get("https://api.genderize.io",   params={"name": name}),
            client.get("https://api.agify.io",       params={"name": name}),
            client.get("https://api.nationalize.io", params={"name": name}),
            return_exceptions=True,
        )

    names = ["Genderize", "Agify", "Nationalize"]
    result = []
    for i, resp in enumerate(responses):
        if isinstance(resp, Exception) or resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail={"status": "502", "message": f"{names[i]} returned an invalid response"},
            )
        result.append(resp.json())
    return result[0], result[1], result[2]


def validate_apis(g, a, n):
    if not g.get("gender") or not g.get("count"):
        raise HTTPException(502, detail={"status": "502", "message": "Genderize returned an invalid response"})
    if a.get("age") is None:
        raise HTTPException(502, detail={"status": "502", "message": "Agify returned an invalid response"})
    if not n.get("country"):
        raise HTTPException(502, detail={"status": "502", "message": "Nationalize returned an invalid response"})



@app.post("/api/profiles", status_code=201)
async def create_profile(request: Request):
    # Parse body manually so we can return precise error codes
    try:
        body = await request.json()
    except Exception:
        return err(400, "Missing or empty name")

    if not isinstance(body, dict) or "name" not in body:
        return err(400, "Missing or empty name")

    raw_name = body["name"]

    # null → 400
    if raw_name is None:
        return err(400, "Missing or empty name")

    # wrong type → 422
    if not isinstance(raw_name, str):
        return err(422, "Invalid type: name must be a string")

    name = raw_name.strip()
    if not name:
        return err(400, "Missing or empty name")

    # Idempotency check
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM profiles WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()

    if existing:
        return JSONResponse(
            status_code=200,
            content={
                "status":  "success",
                "message": "Profile already exists",
                "data":    row_to_full(existing),
            },
        )

    # Parallel external API calls
    gender_data, age_data, nation_data = await fetch_all(name)
    validate_apis(gender_data, age_data, nation_data)

    # Extract & process
    gender             = gender_data["gender"]
    gender_probability = gender_data["probability"]
    sample_size        = gender_data["count"]

    age       = age_data["age"]
    age_group = classify_age(age)

    top_country         = max(nation_data["country"], key=lambda c: c["probability"])
    country_id          = top_country["country_id"]
    country_probability = top_country["probability"]

    profile_id = uuid7()
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO profiles
               (id, name, gender, gender_probability, sample_size,
                age, age_group, country_id, country_probability, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (profile_id, name, gender, gender_probability, sample_size,
             age, age_group, country_id, country_probability, created_at),
        )
        conn.commit()

    return JSONResponse(
        status_code=201,
        content={
            "status": "success",
            "data": {
                "id":                  profile_id,
                "name":                name,
                "gender":              gender,
                "gender_probability":  gender_probability,
                "sample_size":         sample_size,
                "age":                 age,
                "age_group":           age_group,
                "country_id":          country_id,
                "country_probability": country_probability,
                "created_at":          created_at,
            },
        },
    )


@app.get("/api/profiles")
def list_profiles(
    gender:     Optional[str] = Query(default=None),
    country_id: Optional[str] = Query(default=None),
    age_group:  Optional[str] = Query(default=None),
):
    sql    = "SELECT * FROM profiles WHERE 1=1"
    params = []

    if gender:
        sql += " AND LOWER(gender) = LOWER(?)"; params.append(gender)
    if country_id:
        sql += " AND LOWER(country_id) = LOWER(?)"; params.append(country_id)
    if age_group:
        sql += " AND LOWER(age_group) = LOWER(?)"; params.append(age_group)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    return {"status": "success", "count": len(rows), "data": [row_to_summary(r) for r in rows]}


@app.get("/api/profiles/{profile_id}")
def get_profile(profile_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    if not row:
        return err(404, "Profile not found")
    return {"status": "success", "data": row_to_full(row)}


@app.delete("/api/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            return err(404, "Profile not found")
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        conn.commit()
    return Response(status_code=204)



@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    for e in exc.errors():
        if e["type"] in ("string_type", "model_attributes_type", "missing"):
            return JSONResponse(422, {"status": "error", "message": "Invalid type: name must be a string"})
    return JSONResponse(400, {"status": "error", "message": "Missing or empty name"})


@app.exception_handler(HTTPException)
async def http_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail,
                            headers={"Access-Control-Allow-Origin": "*"})
    return JSONResponse(exc.status_code, {"status": "error", "message": exc.detail},
                        headers={"Access-Control-Allow-Origin": "*"})


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    return JSONResponse(500, {"status": "error", "message": "Internal server error"})



if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 3000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
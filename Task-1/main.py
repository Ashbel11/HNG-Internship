import asyncio, httpx, os, sqlite3, time, uuid
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Any

app = FastAPI()

# ── CORS — raw middleware so header is ALWAYS present regardless of Origin ─────
@app.middleware("http")
async def cors(request: Request, call_next):
    if request.method == "OPTIONS":
        return Response(status_code=204, headers={
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        })
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# ── Database ──────────────────────────────────────────────────────────────────
con = sqlite3.connect("/tmp/profiles.db", check_same_thread=False)
con.row_factory = sqlite3.Row
con.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id TEXT PRIMARY KEY, name TEXT UNIQUE, gender TEXT,
        gender_probability REAL, sample_size INTEGER, age INTEGER,
        age_group TEXT, country_id TEXT, country_probability REAL, created_at TEXT
    )
""")
con.commit()

# ── Helpers ───────────────────────────────────────────────────────────────────
def uuidv7() -> str:
    ts_ms = int(time.time() * 1000)
    rand  = int.from_bytes(os.urandom(10), "big")
    hi    = (ts_ms << 16) | 0x7000 | ((rand >> 64) & 0x0FFF)
    lo    = 0x8000000000000000 | (rand & 0x3FFFFFFFFFFFFFFF)
    return str(uuid.UUID(int=(hi << 64) | lo))

def classify(a: int) -> str:
    return "child" if a <= 12 else "teenager" if a <= 19 else "adult" if a <= 59 else "senior"

def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def err(code: int, msg: str):
    return JSONResponse(status_code=code, content={"status": "error", "message": msg})

def err502(api: str):
    return JSONResponse(status_code=502, content={"status": "502", "message": f"{api} returned an invalid response"})

class NameBody(BaseModel):
    name: Any = None

# ── POST /api/profiles ────────────────────────────────────────────────────────
@app.post("/api/profiles")
async def create_profile(body: NameBody):
    name = body.name
    if name is None:              return err(400, "Missing or empty name")
    if not isinstance(name, str): return err(422, "Invalid type")
    if not name.strip():          return err(400, "Missing or empty name")

    row = con.execute("SELECT * FROM profiles WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if row:
        return JSONResponse(status_code=200, content={
            "status": "success", "message": "Profile already exists", "data": dict(row)
        })

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            g_res, a_res, n_res = await asyncio.gather(
                client.get(f"https://api.genderize.io?name={name}"),
                client.get(f"https://api.agify.io?name={name}"),
                client.get(f"https://api.nationalize.io?name={name}"),
            )
        g, a, n = g_res.json(), a_res.json(), n_res.json()
    except Exception as e:
        return err(500, f"External API unreachable: {str(e)}")

    if not g.get("gender") or not g.get("count"):  return err502("Genderize")
    if a.get("age") is None:                        return err502("Agify")
    if not n.get("country"):                        return err502("Nationalize")

    top = max(n["country"], key=lambda c: c["probability"])
    profile = {
        "id":                  uuidv7(),
        "name":                name,
        "gender":              g["gender"],
        "gender_probability":  g["probability"],
        "sample_size":         g["count"],
        "age":                 a["age"],
        "age_group":           classify(a["age"]),
        "country_id":          top["country_id"],
        "country_probability": top["probability"],
        "created_at":          stamp(),
    }
    con.execute("INSERT INTO profiles VALUES (?,?,?,?,?,?,?,?,?,?)", list(profile.values()))
    con.commit()
    return JSONResponse(status_code=201, content={"status": "success", "data": profile})

# ── GET /api/profiles ─────────────────────────────────────────────────────────
@app.get("/api/profiles")
def list_profiles(gender: str = None, country_id: str = None, age_group: str = None):
    q, params = "SELECT id,name,gender,age,age_group,country_id FROM profiles WHERE 1=1", []
    if gender:     q += " AND gender = ? COLLATE NOCASE";     params.append(gender)
    if country_id: q += " AND country_id = ? COLLATE NOCASE"; params.append(country_id)
    if age_group:  q += " AND age_group = ? COLLATE NOCASE";  params.append(age_group)
    rows = [dict(r) for r in con.execute(q, params).fetchall()]
    return {"status": "success", "count": len(rows), "data": rows}

# ── GET /api/profiles/{id} ────────────────────────────────────────────────────
@app.get("/api/profiles/{profile_id}")
def get_profile(profile_id: str):
    row = con.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    if not row: return err(404, "Profile not found")
    return {"status": "success", "data": dict(row)}

# ── DELETE /api/profiles/{id} ─────────────────────────────────────────────────
@app.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: str):
    cur = con.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
    con.commit()
    if cur.rowcount == 0: return err(404, "Profile not found")
    return Response(status_code=204)

# ── Debug — see raw external API responses ────────────────────────────────────
@app.get("/api/debug/{name}")
async def debug(name: str):
    async with httpx.AsyncClient(timeout=20) as client:
        g, a, n = await asyncio.gather(
            client.get(f"https://api.genderize.io?name={name}"),
            client.get(f"https://api.agify.io?name={name}"),
            client.get(f"https://api.nationalize.io?name={name}"),
        )
    return {"genderize": g.json(), "agify": a.json(), "nationalize": n.json()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
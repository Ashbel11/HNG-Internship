from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import os

from database import engine, Base
from routers.profiles import router as profiles_router

# Create all tables on startup
Base.metadata.create_all(bind=engine)

if os.path.exists("profiles_seed.json"):  
    from seed import seed                  
    seed("profiles_seed.json") 

app = FastAPI(
    title="Insighta Labs Intelligence Query Engine",
    version="2.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Custom exception handlers ─────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Override FastAPI's default 422 to match required error format."""
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": "Invalid parameter type"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(profiles_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}

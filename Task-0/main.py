from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import httpx
from datetime import datetime, timezone
from typing import Union

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": "name must be a string"},
    )

GENDERIZE_URL = "https://api.genderize.io/"


def error(message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "message": message},
    )


@app.get("/api/classify")
async def classify(name: Union[str, None] = Query(default=None)):
    
    if name is None or name.strip() == "":
        return error("Missing or empty name parameter", 400)

    
    if not isinstance(name, str):
        return error("name must be a string", 422)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(GENDERIZE_URL, params={"name": name.strip()})

        if response.status_code != 200:
            return error(f"Upstream API returned status {response.status_code}", 502)

        data = response.json()

    except httpx.TimeoutException:
        return error("Upstream API timed out", 502)
    except Exception:
        return error("Failed to reach upstream API", 502)

    if not data.get("gender") or data.get("count", 0) == 0:
        return JSONResponse(
            status_code=200,
            content={
                "status": "error",
                "message": "No prediction available for the provided name",
            },
        )

    probability = data["probability"]
    sample_size = data["count"]
    is_confident = probability >= 0.7 and sample_size >= 100

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "data": {
                "name": data["name"],
                "gender": data["gender"],
                "probability": probability,
                "sample_size": sample_size,
                "is_confident": is_confident,
                "processed_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            },
        },
    )
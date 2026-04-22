from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc
from typing import Optional

from database import get_db
from models import Profile
from schemas import ProfileListResponse
from services.nlp_parser import parse_nlp_query

router = APIRouter()

# ── Constants ─────────────────────────────────────────────────────────────────
VALID_SORT_FIELDS = {"age", "created_at", "gender_probability"}
VALID_ORDERS = {"asc", "desc"}
VALID_GENDERS = {"male", "female"}
VALID_AGE_GROUPS = {"child", "teenager", "adult", "senior"}


# ── Helpers ───────────────────────────────────────────────────────────────────
def error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "message": message},
    )


def apply_filters(query, filters: dict):
    """Apply filter dict to a SQLAlchemy query and return the modified query."""
    if filters.get("gender"):
        query = query.filter(Profile.gender == filters["gender"])
    if filters.get("age_group"):
        query = query.filter(Profile.age_group == filters["age_group"])
    if filters.get("country_id"):
        query = query.filter(Profile.country_id == filters["country_id"].upper())
    if filters.get("min_age") is not None:
        query = query.filter(Profile.age >= filters["min_age"])
    if filters.get("max_age") is not None:
        query = query.filter(Profile.age <= filters["max_age"])
    if filters.get("min_gender_probability") is not None:
        query = query.filter(Profile.gender_probability >= filters["min_gender_probability"])
    if filters.get("min_country_probability") is not None:
        query = query.filter(Profile.country_probability >= filters["min_country_probability"])
    return query


def paginate_and_sort(query, sort_by: str, order: str, page: int, limit: int):
    """Apply sorting and pagination to a query. Returns (items, total)."""
    total = query.count()

    sort_column = getattr(Profile, sort_by)
    query = query.order_by(desc(sort_column) if order == "desc" else asc(sort_column))

    items = query.offset((page - 1) * limit).limit(limit).all()
    return items, total


def build_list_response(items, total: int, page: int, limit: int) -> dict:
    from schemas import ProfileOut
    return {
        "status": "success",
        "page": page,
        "limit": limit,
        "total": total,
        "data": [ProfileOut.model_validate(p).model_dump() for p in items],
    }


# ── GET /api/profiles ─────────────────────────────────────────────────────────
@router.get("/profiles")
def get_profiles(
    gender: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    country_id: Optional[str] = Query(None),
    min_age: Optional[int] = Query(None, ge=0),
    max_age: Optional[int] = Query(None, ge=0),
    min_gender_probability: Optional[float] = Query(None, ge=0.0, le=1.0),
    min_country_probability: Optional[float] = Query(None, ge=0.0, le=1.0),
    sort_by: str = Query("created_at"),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    # ── Validate enum-like parameters ─────────────────────────────────────────
    if sort_by not in VALID_SORT_FIELDS:
        return error_response(400, "Invalid query parameters")
    if order not in VALID_ORDERS:
        return error_response(400, "Invalid query parameters")
    if gender and gender.lower() not in VALID_GENDERS:
        return error_response(400, "Invalid query parameters")
    if age_group and age_group.lower() not in VALID_AGE_GROUPS:
        return error_response(400, "Invalid query parameters")

    filters = {
        "gender": gender.lower() if gender else None,
        "age_group": age_group.lower() if age_group else None,
        "country_id": country_id,
        "min_age": min_age,
        "max_age": max_age,
        "min_gender_probability": min_gender_probability,
        "min_country_probability": min_country_probability,
    }

    query = db.query(Profile)
    query = apply_filters(query, filters)
    items, total = paginate_and_sort(query, sort_by, order, page, limit)

    return JSONResponse(
        status_code=200,
        content=build_list_response(items, total, page, limit),
    )


# ── GET /api/profiles/search ──────────────────────────────────────────────────
@router.get("/profiles/search")
def search_profiles(
    q: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    sort_by: str = Query("created_at"),
    order: str = Query("asc"),
    db: Session = Depends(get_db),
):
    if not q or not q.strip():
        return error_response(400, "Missing or empty query parameter")

    if sort_by not in VALID_SORT_FIELDS:
        return error_response(400, "Invalid query parameters")
    if order not in VALID_ORDERS:
        return error_response(400, "Invalid query parameters")

    filters = parse_nlp_query(q)
    if filters is None:
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": "Unable to interpret query"},
        )

    query = db.query(Profile)
    query = apply_filters(query, filters)
    items, total = paginate_and_sort(query, sort_by, order, page, limit)

    return JSONResponse(
        status_code=200,
        content=build_list_response(items, total, page, limit),
    )

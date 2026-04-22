from sqlalchemy import Column, String, Float, Integer, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from database import Base
from utils import generate_uuid7
from datetime import datetime, timezone


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    name = Column(String, unique=True, nullable=False, index=True)
    gender = Column(String, nullable=False)
    gender_probability = Column(Float, nullable=False)
    age = Column(Integer, nullable=False)
    age_group = Column(String, nullable=False)
    country_id = Column(String(2), nullable=False)
    country_name = Column(String, nullable=False)
    country_probability = Column(Float, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_profiles_gender", "gender"),
        Index("ix_profiles_age_group", "age_group"),
        Index("ix_profiles_country_id", "country_id"),
        Index("ix_profiles_age", "age"),
        Index("ix_profiles_created_at", "created_at"),
        Index("ix_profiles_gender_probability", "gender_probability"),
        Index("ix_profiles_country_probability", "country_probability"),
    )

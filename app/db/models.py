from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship

from datetime import datetime, timezone
from uuid import uuid4

from .session import Base

class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sha256 = Column(String(64), unique=True, index=True)
    path = Column(String)
    filename = Column(String, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    jobs = relationship("ScanJob", back_populates="file")


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"))
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=True)
    status = Column(String, default="pending...")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True)) 

    file = relationship("File", back_populates="jobs")
    results = relationship("EngineResult", back_populates="job")
    api_key = relationship("APIKey", back_populates="jobs")


class EngineResult(Base):
    __tablename__ = "engine_results"
    __table_args__ = (
        UniqueConstraint("job_id", "engine", name="uq_engine_results_job_engine"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("scan_jobs.id"))

    engine = Column(String)
    status = Column(String)
    result = Column(MutableDict.as_mutable(JSON))
    scanned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    job = relationship("ScanJob", back_populates="results")


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    key_hash = Column(String(64), unique=True, index=True, nullable=False)  # sha256 hash of the raw key
    name = Column(String, nullable=False)  # e.g: frontend-service
    rate_limit_per_day = Column(
        "rate_limit_per_day",
        Integer,
        nullable=False,
        default=60,
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True, nullable=False)

    jobs = relationship("ScanJob", back_populates="api_key")

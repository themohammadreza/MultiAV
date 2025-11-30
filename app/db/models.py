from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from datetime import datetime
from uuid import uuid4

from .session import Base

class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sha256 = Column(String(64), unique=True, index=True)
    path = Column(String)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("ScanJob", back_populates="file")


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"))
    status = Column(String, default="pending...")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    file = relationship("File", back_populates="jobs")
    results = relationship("EngineResult", back_populates="job")


class EngineResult(Base):
    __tablename__ = "engine_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("scan_jobs.id"))

    engine = Column(String)
    status = Column(String)
    result = Column(JSON)

    scanned_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("ScanJob", back_populates="results")

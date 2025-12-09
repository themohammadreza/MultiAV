import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.models import EngineResult, File, ScanJob
from app.db.session import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.unit
def test_file_sha256_unique_constraint(db_session):
    file1 = File(sha256="abc123", path="/tmp/file1")
    db_session.add(file1)
    db_session.commit()

    file2 = File(sha256="abc123", path="/tmp/file2")
    db_session.add(file2)

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.unit
def test_engine_result_unique_per_job_and_engine(db_session):
    file = File(sha256="test", path="/tmp/test")
    db_session.add(file)
    db_session.flush()

    job = ScanJob(file_id=file.id)
    db_session.add(job)
    db_session.flush()

    result1 = EngineResult(job_id=job.id, engine="clamav", status="success", result={})
    db_session.add(result1)
    db_session.commit()

    result2 = EngineResult(job_id=job.id, engine="clamav", status="error", result={})
    db_session.add(result2)

    with pytest.raises(IntegrityError):  # Violates unique constraint
        db_session.commit()

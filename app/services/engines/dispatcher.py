from . import clamav, yara
from app.db.session import SessionLocal
from app.db.models import EngineResult, ScanJob
from datetime import datetime


def run_all_engines(job_id: str, file_path: str):

    engines = {
        "clamav": clamav.run,
        "yara": yara.run,
    }

    db = SessionLocal()

    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    job.status = "running..."
    db.commit()

    for name, fn in engines.items():
        try:
            result = fn(file_path)
            entry = EngineResult(
                job_id=job_id,
                engine=name,
                status="success",
                result=result,
            )
        except Exception as e:
            entry = EngineResult(
                job_id=job_id,
                engine=name,
                status="error",
                result={"error": str(e)},
            )

        db.add(entry)
        db.commit()

    job.status = "done"
    job.completed_at = datetime.utcnow()
    db.commit()
    db.close()


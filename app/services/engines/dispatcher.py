from app.services.engines.clamav.engine import run as clamav_run
from app.services.engines.yara.yara import run as yara_run
from app.services.engines.windows_defender.engine import run as windows_defender_run
from app.db.session import SessionLocal
from app.db.models import EngineResult, ScanJob
from datetime import datetime


def run_all_engines(job_id: str, file_path: str):

    engines = {
        "clamav": clamav_run,
        "yara": yara_run,
        "windows-defender": windows_defender_run,
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

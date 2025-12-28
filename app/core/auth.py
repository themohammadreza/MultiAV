from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.db.models import APIKey as APIKeyModel
from app.db.session import get_db

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

API_KEY_TTL_DAYS = int(os.getenv("API_KEY_TTL_DAYS", "30"))


def get_current_api_key(
    api_key: Optional[str] = Security(api_key_header),
    db: Session = Depends(get_db),
) -> Optional[APIKeyModel]:
    bypass = os.getenv("BYPASS_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}
    if bypass:
        return None

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing api_key")

    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    db_key = (
        db.query(APIKeyModel)
        .filter(
            APIKeyModel.key_hash == key_hash,
        )
        .first()
    )

    if not db_key:
        raise HTTPException(status_code=401, detail="Invalid api_key")

    if db_key.revoked_at is not None or getattr(db_key, "is_active", True) is False:
        raise HTTPException(status_code=401, detail="Invalid api_key")

    created_at = db_key.created_at
    if created_at is None:
        raise HTTPException(status_code=401, detail="Invalid api_key")

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    expires_at = created_at + timedelta(days=API_KEY_TTL_DAYS)
    now = datetime.now(timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=401, detail="API key expired")

    db_key.last_used_at = now
    db.add(db_key)
    db.commit()

    return db_key

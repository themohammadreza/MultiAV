from __future__ import annotations

import hashlib
import os
from typing import Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.db.models import APIKey as APIKeyModel
from app.db.session import get_db

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


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
            APIKeyModel.is_active.is_(True),
        )
        .first()
    )

    if not db_key:
        raise HTTPException(status_code=401, detail="Invalid api_key")

    return db_key


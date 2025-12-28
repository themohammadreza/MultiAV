from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import AdminUser


DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_DEFAULT_USERNAME", "superadmin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "mohammad")


def ensure_default_admin(db: Session) -> AdminUser | None:
    """Ensure a default superadmin exists when no admins are present."""
    existing = db.query(AdminUser).first()
    if existing:
        return None

    now = datetime.now(timezone.utc)
    admin = AdminUser(
        username=DEFAULT_ADMIN_USERNAME,
        password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
        is_superadmin=True,
        created_at=now,
        updated_at=now,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin

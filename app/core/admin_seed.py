from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import AdminUser

logger = logging.getLogger(__name__)


def ensure_default_admin(db: Session) -> AdminUser | None:
    """Ensure a default superadmin exists when no admins are present."""
    existing = db.query(AdminUser).first()
    if existing:
        logger.warning(
            "Default admin seed skipped because an admin user already exists.",
        )
        return None

    username = os.getenv("ADMIN_DEFAULT_USERNAME")
    password = os.getenv("ADMIN_DEFAULT_PASSWORD")
    if not username or not password:
        logger.warning(
            "Default admin seed failed because ADMIN_DEFAULT_USERNAME or "
            "ADMIN_DEFAULT_PASSWORD is not set.",
        )
        raise RuntimeError(
            "ADMIN_DEFAULT_USERNAME and ADMIN_DEFAULT_PASSWORD must be set "
            "to seed the initial admin user."
        )

    now = datetime.now(timezone.utc)
    admin = AdminUser(
        username=username,
        password_hash=hash_password(password),
        is_superadmin=True,
        created_at=now,
        updated_at=now,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    logger.warning(
        "Default admin user created with username '%s'. Rotate credentials after login.",
        username,
    )
    return admin

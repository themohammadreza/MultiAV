import hashlib
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.db.models import APIKey  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


API_KEY_TTL_DAYS = 30


def create_key(name: str, rate_limit: int = 60) -> str:
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    with SessionLocal() as session:
        session.add(
            APIKey(
                key_hash=key_hash,
                name=name,
                rate_limit_per_day=rate_limit,
            )
        )
        session.commit()

    print(f"API Key: {raw_key}")
    print(f"Name: {name}")
    print(f"Rate Limit: {rate_limit}/day")
    print(f"Expires: {(datetime.now(timezone.utc) + timedelta(days=API_KEY_TTL_DAYS)).date().isoformat()} (UTC)")
    print("Save this key - it won't be shown again")
    return raw_key


def list_keys() -> None:
    with SessionLocal() as session:
        keys = session.query(APIKey).order_by(APIKey.created_at.desc()).all()

    if not keys:
        print("No API keys found.")
        return

    rows = []
    for key in keys:
        active = "✓" if key.is_active else "✗"
        created = key.created_at.isoformat() if key.created_at else ""
        rate = str(key.rate_limit_per_day)
        rows.append((key.name, active, rate, created))

    headers = ("Name", "Active", "Rate Limit", "Created")
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    fmt = "  ".join("{:<" + str(width) + "}" for width in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * width for width in widths)))
    for row in rows:
        print(fmt.format(*row))


def _query_keys(session, identifier: str) -> list[APIKey]:
    identifier = identifier.strip()
    try:
        parsed_uuid = UUID(identifier)
    except ValueError:
        parsed_uuid = None

    if parsed_uuid is not None:
        return session.query(APIKey).filter(APIKey.id == parsed_uuid).all()
    return session.query(APIKey).filter(APIKey.name == identifier).all()


def revoke_key(identifier: str) -> int:
    with SessionLocal() as session:
        keys = _query_keys(session, identifier)
        if not keys:
            print("No matching API keys found.")
            return 0

        revoked = 0
        for key in keys:
            if key.is_active:
                key.is_active = False
                revoked += 1
        session.commit()

    print(f"Revoked {revoked} key(s).")
    return revoked


def delete_key(identifier: str) -> int:
    with SessionLocal() as session:
        keys = _query_keys(session, identifier)
        if not keys:
            print("No matching API keys found.")
            return 0
        deleted = len(keys)
        for key in keys:
            session.delete(key)
        session.commit()

    print(f"Deleted {deleted} key(s).")
    return deleted


def set_rate_limit(identifier: str, rate_limit: int) -> int:
    if rate_limit < 0:
        print("rate_limit_per_day must be >= 0 (0 disables limiting)")
        return 0

    with SessionLocal() as session:
        keys = _query_keys(session, identifier)
        if not keys:
            print("No matching API keys found.")
            return 0

        updated = 0
        for key in keys:
            if key.rate_limit_per_day != rate_limit:
                key.rate_limit_per_day = rate_limit
                updated += 1
        session.commit()

    print(f"Updated rate limit for {updated} key(s).")
    return updated


def renew_key(identifier: str) -> int:
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        keys = _query_keys(session, identifier)
        if not keys:
            print("No matching API keys found.")
            return 0

        renewed = 0
        for key in keys:
            key.created_at = now
            key.is_active = True
            renewed += 1
        session.commit()

    print(f"Renewed {renewed} key(s) for {API_KEY_TTL_DAYS} more days (UTC).")
    return renewed


def _usage() -> None:
    print("Usage:")
    print("  python scripts/manage_keys.py create <name> [rate_limit_per_day]")
    print("  python scripts/manage_keys.py list")
    print("  python scripts/manage_keys.py revoke <name|uuid>")
    print("  python scripts/manage_keys.py delete <name|uuid>")
    print("  python scripts/manage_keys.py set-limit <name|uuid> <rate_limit_per_day>")
    print("  python scripts/manage_keys.py renew <name|uuid>")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        _usage()
        return 2

    command = argv[1].strip().lower()

    if command == "create":
        if len(argv) < 3:
            _usage()
            return 2
        name = argv[2]
        rate_limit = 60
        if len(argv) >= 4:
            try:
                rate_limit = int(argv[3])
            except ValueError:
                print("rate_limit_per_day must be an integer")
                return 2
        create_key(name, rate_limit=rate_limit)
        return 0

    if command == "list":
        list_keys()
        return 0

    if command == "revoke":
        if len(argv) < 3:
            _usage()
            return 2
        revoke_key(argv[2])
        return 0

    if command == "delete":
        if len(argv) < 3:
            _usage()
            return 2
        delete_key(argv[2])
        return 0

    if command in {"set-limit", "set_limit"}:
        if len(argv) < 4:
            _usage()
            return 2
        try:
            rate_limit = int(argv[3])
        except ValueError:
            print("rate_limit_per_day must be an integer")
            return 2
        set_rate_limit(argv[2], rate_limit)
        return 0

    if command == "renew":
        if len(argv) < 3:
            _usage()
            return 2
        renew_key(argv[2])
        return 0

    _usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

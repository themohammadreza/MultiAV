import hashlib
import secrets
import sys
from pathlib import Path
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.db.models import APIKey  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def create_key(name: str, rate_limit: int = 60) -> str:
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    with SessionLocal() as session:
        session.add(
            APIKey(
                key_hash=key_hash,
                name=name,
                rate_limit_per_minute=rate_limit,
            )
        )
        session.commit()

    print(f"API Key: {raw_key}")
    print(f"Name: {name}")
    print(f"Rate Limit: {rate_limit}/min")
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
        rows.append((key.name, active, str(key.rate_limit_per_minute), created))

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


def revoke_key(identifier: str) -> int:
    identifier = identifier.strip()
    try:
        parsed_uuid = UUID(identifier)
    except ValueError:
        parsed_uuid = None

    with SessionLocal() as session:
        if parsed_uuid is not None:
            keys = session.query(APIKey).filter(APIKey.id == parsed_uuid).all()
        else:
            keys = session.query(APIKey).filter(APIKey.name == identifier).all()

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


def _usage() -> None:
    print("Usage:")
    print("  python scripts/manage_keys.py create <name> [rate_limit_per_minute]")
    print("  python scripts/manage_keys.py list")
    print("  python scripts/manage_keys.py revoke <name|uuid>")


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
                print("rate_limit_per_minute must be an integer")
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

    _usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

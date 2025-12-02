#!/bin/bash
set -euo pipefail

echo "[ClamAV Engine] Preparing directories..."
chown -R clamav:clamav /var/run/clamav /var/lib/clamav /var/log/clamav || true

echo "[ClamAV Engine] Updating virus definitions (best effort)..."
su -s /bin/bash -c "freshclam" clamav || true

echo "[ClamAV Engine] Starting freshclam in the background for continuous updates..."
su -s /bin/bash -c "freshclam -d" clamav || true

if [ "$#" -eq 0 ]; then
    set -- clamd -F
fi

echo "[ClamAV Engine] Starting clamd service..."
if [ "$1" = "clamd" ]; then
    shift
    exec su -s /bin/bash -c "clamd $* -c /etc/clamav/clamd.conf" clamav
fi

exec "$@"

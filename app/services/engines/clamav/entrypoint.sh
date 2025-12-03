#!/bin/bash
set -euo pipefail

DB_DIR=/var/lib/clamav
RUN_DIR=/var/run/clamav
LOG_DIR=/var/log/clamav

db_present() {
    ls "$DB_DIR"/*.c[lv]d >/dev/null 2>&1
}

fetch_via_curl() {
    echo "[ClamAV Engine] freshclam failed; trying direct HTTP download as fallback..."
    local ua="ClamAV/1.0"
    local base_url="http://database.clamav.net"
    for file in main.cvd daily.cvd bytecode.cvd; do
        echo "[ClamAV Engine] Downloading ${file}..."
        if curl -fL --retry 3 --retry-delay 5 --connect-timeout 10 --max-time 300 \
            -H "User-Agent: ${ua}" \
            -o "${DB_DIR}/${file}" \
            "${base_url}/${file}"; then
            chown clamav:clamav "${DB_DIR}/${file}" || true
        else
            echo "[ClamAV Engine] Failed to download ${file} via HTTP fallback." >&2
        fi
    done
}

echo "[ClamAV Engine] Preparing directories..."
mkdir -p "$RUN_DIR" "$DB_DIR" "$LOG_DIR"
chown -R clamav:clamav "$RUN_DIR" "$DB_DIR" "$LOG_DIR" || true

if db_present; then
    echo "[ClamAV Engine] Existing database found, skipping blocking download."
else
    echo "[ClamAV Engine] Updating virus definitions (timed, best effort)..."
    for attempt in 1 2 3; do
        if timeout 120s su -s /bin/bash -c "freshclam --foreground --stdout" clamav; then
            break
        fi

        echo "[ClamAV Engine] freshclam attempt ${attempt} failed, retrying shortly..." >&2
        sleep 10
    done

    if ! db_present; then
        fetch_via_curl
    fi

    if ! db_present; then
        echo "[ClamAV Engine] No ClamAV databases available after fallback; cannot start clamd." >&2
        exit 1
    fi
fi

echo "[ClamAV Engine] Starting freshclam in the background for continuous updates..."
su -s /bin/bash -c "freshclam -d" clamav >/var/log/clamav/freshclam.log 2>&1 & disown

if [ "$#" -eq 0 ]; then
    set -- clamd --foreground --config-file=/etc/clamav/clamd.conf
fi

echo "[ClamAV Engine] Starting clamd service..."
if [ "$1" = "clamd" ]; then
    shift
    exec su -s /bin/bash -c "exec clamd --config-file=/etc/clamav/clamd.conf $*" clamav
fi

exec "$@"

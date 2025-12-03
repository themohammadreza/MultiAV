FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install ClamAV daemon + tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    clamav \
    clamav-daemon \
    clamav-freshclam \
    ca-certificates \
    netcat-openbsd \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Configure clamd for TCP (no host socket) + logs in foreground
RUN set -eux; \
    sed -i 's/^Example/#Example/' /etc/clamav/clamd.conf; \
    sed -i '/^LocalSocket /d' /etc/clamav/clamd.conf; \
    sed -i '/^TCPSocket /d' /etc/clamav/clamd.conf; \
    sed -i '/^TCPAddr /d' /etc/clamav/clamd.conf; \
    sed -i '/^Foreground /d' /etc/clamav/clamd.conf; \
    sed -i '/^LogFile /d' /etc/clamav/clamd.conf; \
    sed -i '/^LogTime /d' /etc/clamav/clamd.conf; \
    cat >> /etc/clamav/clamd.conf <<'EOF'
TCPSocket 3310
TCPAddr 0.0.0.0
#LocalSocket disabled
Foreground yes
LogFile /var/log/clamav/clamd.log
LogTime yes
EOF
RUN sed -i 's/^Example/#Example/' /etc/clamav/freshclam.conf \
    && sed -i 's/^#Checks .*/Checks 12/' /etc/clamav/freshclam.conf

# Runtime folders + permissions
RUN mkdir -p /var/run/clamav /var/lib/clamav /var/log/clamav /app \
    && chown -R clamav:clamav /var/run/clamav /var/lib/clamav /var/log/clamav /app

# Python deps + helper client
WORKDIR /app
COPY app/services/engines/clamav/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app/services/engines/clamav/engine.py engine.py
COPY app/services/engines/schema.py schema.py

# Entrypoint
COPY app/services/engines/clamav/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3310

HEALTHCHECK --interval=30s --timeout=10s --start-period=5m --retries=5 \
    CMD clamdscan --ping --config-file=/etc/clamav/clamd.conf || exit 1

ENTRYPOINT ["tini", "--", "/entrypoint.sh"]
CMD ["clamd"]

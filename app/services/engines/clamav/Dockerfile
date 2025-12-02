FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install ClamAV daemon + tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    clamav \
    clamav-daemon \
    clamav-freshclam \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Configure clamd for both TCP (default) and local socket
RUN sed -i 's/^Example/#Example/' /etc/clamav/clamd.conf \
    && sed -i 's/^#TCPSocket .*/TCPSocket 3310/' /etc/clamav/clamd.conf \
    && sed -i 's/^#TCPAddr .*/TCPAddr 0.0.0.0/' /etc/clamav/clamd.conf \
    && sed -i 's~^#LocalSocket .*~LocalSocket /var/run/clamav/clamd.ctl~' /etc/clamav/clamd.conf \
    && sed -i 's~^#Foreground .*~Foreground yes~' /etc/clamav/clamd.conf \
    && sed -i 's~^#LogFile /var/log/clamav/clamd.log~LogFile /var/log/clamav/clamd.log~' /etc/clamav/clamd.conf \
    && sed -i 's/^#LogTime/LogTime yes/' /etc/clamav/clamd.conf \
    && sed -i 's/^Example/#Example/' /etc/clamav/freshclam.conf \
    && sed -i 's/^#DatabaseMirror .*/DatabaseMirror database.clamav.net/' /etc/clamav/freshclam.conf \
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

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD clamdscan --ping || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["clamd", "-F"]

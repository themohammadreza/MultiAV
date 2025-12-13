FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

# Base build tools and certs (needed for some wheels / SSL) with a retry to handle transient mirror issues
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        libssl-dev \
        libffi-dev \
        libmagic1 \
    || { \
        apt-get clean; \
        rm -rf /var/lib/apt/lists/*; \
        apt-get update; \
        apt-get install -y --no-install-recommends \
            build-essential \
            ca-certificates \
            libssl-dev \
            libffi-dev \
            libmagic1; \
    }; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt

# Copy configuration so defaults work even without a bind mount
COPY config ./config

# Copy application code (including YARA rules)
COPY app ./app
COPY ui ./ui

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

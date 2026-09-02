# ============================================================
#  PATAGONIA — PRODUCTION DOCKERFILE (MULTI-STAGE)
# ============================================================

# --- Build Stage ---
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    libpq-dev \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# --- Final Stage ---
FROM python:3.11-slim AS final

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_APP=wsgi:app
ENV FLASK_ENV=production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    libpq5 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY backend/ ./backend/
COPY core/ ./core/
COPY templates/ ./templates/
COPY static/ ./static/
COPY wsgi.py .
COPY app.py .
COPY config.py .
COPY gunicorn.conf.py .

RUN groupadd -g 1001 patagonia_user \
 && useradd --system --uid 1001 --gid 1001 --create-home --shell /usr/sbin/nologin patagonia_user
# Do not create local uploads directory in production images (storage is GCS-only).
USER patagonia_user

EXPOSE 8080

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]

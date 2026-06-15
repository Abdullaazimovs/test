# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

# - PYTHONUNBUFFERED: stream logs immediately (so dev verification codes show up)
# - PYTHONDONTWRITEBYTECODE: keep the image clean of .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user (least privilege).
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["bash", "/app/docker-entrypoint.sh"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

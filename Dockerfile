# Single stage: every dependency ships a manylinux wheel (pydantic-core is the
# only compiled one), so there is no toolchain to keep out of the runtime
# image. Idles around 90 MB resident, well inside the ~200 MB budget on a
# 961 MB box shared with every other app.
FROM python:3.12-slim

# busybox only for its wget: the healthcheck runs every 30 s, and spawning a
# Python interpreter for it can time out on the memory-starved droplet.
RUN apt-get update \
 && apt-get install -y --no-install-recommends busybox \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py gunicorn_config.py ./
COPY game ./game
COPY content ./content
COPY public ./public

# DATA_DIR is a mounted volume in production. Create it anyway so a bare
# `docker run` with no volume still boots -- that is exactly what the CI
# smoke test does.
RUN mkdir -p /app/data \
 && useradd --create-home --uid 10001 tycoon \
 && chown -R tycoon:tycoon /app/data
USER tycoon

ENV PORT=8080 \
    BASE_PATH="" \
    DATA_DIR=/app/data \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# Bare /health: the app strips BASE_PATH when present and answers either way.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ["busybox", "wget", "-qO-", "http://127.0.0.1:8080/health"]

CMD ["gunicorn", "-c", "gunicorn_config.py", "app:app"]

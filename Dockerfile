# Single stage: every dependency ships a manylinux wheel (pydantic-core is the
# only compiled one), so there is no toolchain to keep out of the runtime
# image. Idles around 90 MB resident, well inside the ~200 MB budget on a
# 961 MB box shared with every other app.
FROM python:3.12-slim

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

# BASE_PATH-aware: the healthcheck runs inside the container, where the app
# answers on the prefix it was configured with.
HEALTHCHECK --interval=30s --timeout=4s --start-period=5s --retries=3 \
  CMD python -c "import os,urllib.request,sys; \
b=os.environ.get('BASE_PATH',''); \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080'+b+'/health',timeout=3).status==200 else 1)" \
  || exit 1

CMD ["gunicorn", "-c", "gunicorn_config.py", "app:app"]

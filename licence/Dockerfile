# License Pulse – production image (standard library only, no pip install).
FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LICENCE_ENV=production \
    LICENCE_HOST=0.0.0.0 \
    LICENCE_PORT=8000 \
    LICENCE_DB=/data/licence.db \
    LICENCE_BACKUP_DIR=/data/backups

# Unprivileged user; /data is the only writable path (mount a volume there).
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
 && mkdir -p /data && chown app:app /data

WORKDIR /app
COPY --chown=root:root licence_app ./licence_app
COPY --chown=root:root web ./web

USER app
VOLUME ["/data"]
EXPOSE 8000
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python3", "-c", "import os,sys,urllib.request; p=os.environ.get('LICENCE_PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/api/health', timeout=2).status == 200 else 1)"]

CMD ["python3", "-m", "licence_app", "serve"]

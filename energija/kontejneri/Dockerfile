# Lagana slika lokalne jezgre (~60 MB): Python + jedna ovisnost, bez kompajlera u konačnoj slici.
FROM python:3.13-slim AS jezgra
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ENERGIJA_PODACI=/podaci
RUN pip install --no-cache-dir "cryptography>=42" && useradd -r -u 10001 energija \
    && mkdir /podaci && chown energija /podaci
WORKDIR /app
COPY jezgra ./jezgra
COPY sucelje ./sucelje
USER energija
VOLUME ["/podaci"]
EXPOSE 8443 1883
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
  CMD python -c "import ssl,urllib.request as u;u.urlopen('https://127.0.0.1:8443/api/zdravlje',context=ssl._create_unverified_context(),timeout=4)"
ENTRYPOINT ["python", "-m", "jezgra"]

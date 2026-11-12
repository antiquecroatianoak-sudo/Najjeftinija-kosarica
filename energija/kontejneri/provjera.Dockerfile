# Slika za simulatore (pymodbus, MQTT senzori, lažni Open-Meteo) i za provjeru sustava.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt requirements-provjera.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-provjera.txt && useradd -r -u 10001 energija
WORKDIR /app
COPY jezgra ./jezgra
COPY simulator ./simulator
COPY provjera ./provjera
USER 10001

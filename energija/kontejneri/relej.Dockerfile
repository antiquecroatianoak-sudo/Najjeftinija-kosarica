# Relej za tunel (na VPS-u ili u oblaku): spaja jezgru i klijenta, ne vidi sadržaj (E2E šifra).
FROM python:3.13-slim
RUN pip install --no-cache-dir "cryptography>=42" && useradd -r -u 10002 relej
WORKDIR /app
COPY jezgra ./jezgra
USER relej
EXPOSE 7443
ENTRYPOINT ["python", "-c", "from jezgra.tunel import Relej; import threading; Relej('0.0.0.0', 7443).pokreni(); threading.Event().wait()"]

FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY scripts scripts
COPY server/server.py server/page.py server/abonnement.py server/
COPY server/static server/static
COPY docs/apercu-social.png server/og.png
COPY docker/entrypoint.sh entrypoint.sh
ENV DROIT_DATA=/data HOST=0.0.0.0 PORT=8000 PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -fs http://localhost:8000/ping || exit 1
CMD ["./entrypoint.sh"]

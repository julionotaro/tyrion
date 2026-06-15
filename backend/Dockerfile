FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema mínimas (psycopg2 binario no las necesita)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# El código se monta como volumen en dev (hot-reload).
# En producción COPY . . aquí.
COPY . .

# Script de arranque: aplica migraciones y luego lanza la app
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["api"]

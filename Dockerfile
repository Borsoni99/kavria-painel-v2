# Imagem única do painel: compila o frontend (React) e roda o backend (FastAPI) servindo tudo.

# --- 1) Frontend -------------------------------------------------------------
FROM node:20.18-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2) Backend --------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=America/Sao_Paulo
WORKDIR /app/backend

# Versões exatas testadas (constraints.txt) para o servidor rodar igual ao ambiente de testes
COPY backend/requirements.txt backend/constraints.txt ./
RUN pip install -r requirements.txt -c constraints.txt

COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# Usuário sem privilégios; o banco, os logs e os backups ficam no volume data/
RUN useradd --system --uid 1000 --create-home kavria \
    && mkdir -p /app/backend/data && chown -R kavria /app/backend/data
USER kavria

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"

# O Caddy (outro container) faz o HTTPS e repassa para cá; só ele alcança esta porta.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

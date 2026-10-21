# ==============================================================================
# Multi-stage Dockerfile para Proyecto OCR (FastAPI + Next.js)
# Permite construir tanto Backend como Frontend desde la raíz del proyecto
# ==============================================================================

# ------------------------------------------------------------------------------
# STAGE 1: Backend (FastAPI + Python 3.12 + OpenCV + PaddleOCR + Tesseract)
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias del sistema para OpenCV, PyMuPDF, PaddleOCR y Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    libglib2.0-dev \
    poppler-utils \
    wget \
    curl \
    tesseract-ocr \
    tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY backend/ .

RUN mkdir -p /app/uploads /app/exports /app/logs /app/credentials

# Usuario sin privilegios para la aplicación (docker-entrypoint.sh le pasa las carpetas de datos)
RUN groupadd --system --gid 10001 kondid \
    && useradd --system --uid 10001 --gid kondid --home-dir /home/kondid --create-home --shell /usr/sbin/nologin kondid

# Arranca como root un instante para ajustar permisos de los volúmenes y luego corre como kondid
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh && chmod 755 /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ------------------------------------------------------------------------------
# STAGE 2: Frontend (Next.js 16 - Node 24 LTS)
# ------------------------------------------------------------------------------
FROM node:24-alpine AS frontend-base

FROM frontend-base AS frontend-deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

FROM frontend-base AS frontend-builder
WORKDIR /app
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY --from=frontend-deps /app/node_modules ./node_modules
COPY frontend/ .
RUN mkdir -p public
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM frontend-base AS frontend
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=frontend-builder /app/public ./public
COPY --from=frontend-builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=frontend-builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]

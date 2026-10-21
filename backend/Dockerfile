# ──────────────────────────────────────────
# Backend Dockerfile - Python 3.12
# v2: agrega Tesseract + directorio credentials (Google DocAI)
# ──────────────────────────────────────────
FROM python:3.12-slim

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias del sistema para OpenCV, PaddleOCR y Tesseract (fallback)
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
    # Tesseract OCR (fallback cuando Google Document AI no está disponible)
    tesseract-ocr \
    tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar código fuente
COPY . .

# Crear directorios necesarios
# /app/credentials se monta como volumen read-only desde docker-compose.yml
# El JSON de Google Cloud NUNCA se copia dentro de la imagen
RUN mkdir -p /app/uploads /app/exports /app/logs /app/credentials

# Usuario sin privilegios para la aplicación (docker-entrypoint.sh le pasa las carpetas de datos)
RUN groupadd --system --gid 10001 kondid \
    && useradd --system --uid 10001 --gid kondid --home-dir /home/kondid --create-home --shell /usr/sbin/nologin kondid

# Arranca como root un instante para ajustar permisos de los volúmenes y luego corre como kondid
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh && chmod 755 /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

# Puerto de exposición
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

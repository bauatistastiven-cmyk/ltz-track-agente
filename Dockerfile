FROM python:3.11-slim

# Metadatos
LABEL maintainer="AgentKit"
LABEL description="WhatsApp AI Agent — Built with AgentKit"

# Variables de entorno base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY agent/ ./agent/
COPY config/ ./config/
COPY knowledge/ ./knowledge/

# Crear directorio para la base de datos
RUN mkdir -p /data
ENV DB_PATH=/data/agentkit.db

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Exponer puerto
EXPOSE ${PORT}

# Comando de inicio
CMD uvicorn agent.main:app --host 0.0.0.0 --port ${PORT}

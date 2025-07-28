# Usar imagen base de Python con uv
FROM ghcr.io/astral-sh/uv:python3.12-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias para IMAP/SSL
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Copiar archivos de configuración del proyecto
COPY pyproject.toml .
COPY .python-version .

# Instalar dependencias de Python con uv
RUN uv sync --frozen

# Copiar el código fuente
COPY . .

# Hacer ejecutable el script de entrada
RUN chmod +x /app/docker-entrypoint.sh

# Script de entrada que inicia Ollama y luego el asistente
CMD ["/app/docker-entrypoint.sh"]

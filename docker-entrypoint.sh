#!/bin/bash
set -e

echo "🚀 Iniciando Secretaria en contenedor Docker..."

# Iniciar Ollama en segundo plano
echo "📦 Iniciando Ollama..."
ollama serve &
OLLAMA_PID=$!

# Esperar a que Ollama esté listo
echo "⏳ Esperando a que Ollama esté listo..."
sleep 10

# Verificar si el modelo está disponible, si no, descargarlo
echo "🤖 Verificando modelo $OLLAMA_MODEL..."
if ! ollama list | grep -q "${OLLAMA_MODEL%:*}"; then
    echo "📥 Descargando modelo $OLLAMA_MODEL..."
    ollama pull "$OLLAMA_MODEL"
else
    echo "✅ Modelo $OLLAMA_MODEL ya disponible"
fi

# Verificar credenciales requeridas
if [ -z "$IMAP_USER" ] || [ -z "$IMAP_PASSWORD" ] || [ -z "$IMAP_SERVER" ]; then
    echo "❌ Error: Variables de entorno IMAP requeridas no configuradas"
    echo "   Configura: IMAP_SERVER, IMAP_USER, IMAP_PASSWORD"
    exit 1
fi

# Verificar credenciales de Google Calendar
if [ ! -f "/app/credentials/credentials.json" ]; then
    echo "❌ Error: credentials.json no encontrado en /app/credentials/"
    echo "   Monta el archivo como volumen: -v /ruta/credentials.json:/app/credentials/credentials.json"
    exit 1
fi

echo "✅ Configuración completada. Iniciando servicio..."

# Función para manejar señales de terminación
cleanup() {
    echo "🛑 Deteniendo servicios..."
    kill $OLLAMA_PID 2>/dev/null || true
    exit 0
}

# Capturar señales de terminación
trap cleanup SIGTERM SIGINT

# Ejecutar el asistente con uv
cd /app
exec uv run python secretaria_service.py

#!/bin/bash
set -e

echo "🚀 Iniciando Secretaria en contenedor Docker..."

# Verificar credenciales requeridas
if [ -z "$IMAP_USER" ] || [ -z "$IMAP_PASSWORD" ] || [ -z "$IMAP_SERVER" ]; then
    echo "❌ Error: Variables de entorno IMAP requeridas no configuradas"
    echo "   Configura: IMAP_SERVER, IMAP_USER, IMAP_PASSWORD"
    exit 1
fi

echo "✅ Configuración completada. Iniciando servicio..."

# Capturar señales de terminación
trap cleanup SIGTERM SIGINT

# Ejecutar el asistente con uv
cd /app
exec uv run python secretaria_service.py

# Secretaria - Asistente de Correo y Calendar

Asistente inteligente que se ejecuta continuamente como servicio Docker:
1. 📧 Se conecta a **cualquier servidor de correo** vía IMAP (Gmail, Outlook, Yahoo, etc.)
2. 🤖 Analiza correos con un modelo LLM local (Ollama) para detectar información de reuniones
3. 📅 Crea automáticamente eventos en **Google Calendar**
4. 🔄 **Funciona como servicio continuo** verificando correos periódicamente

## 🚀 Características

- ✅ **IMAP Universal**: Compatible con cualquier proveedor de correo
- ✅ **Integración Google Calendar**: API oficial con OAuth2
- ✅ **IA Local**: Usa Ollama para análisis privado de correos
- ✅ **Servicio Continuo**: Ejecuta en bucle verificando correos automáticamente
- ✅ **Containerizado**: Desplegable fácilmente con Docker
- ✅ **Configuración Flexible**: Todo configurable vía variables de entorno
- ✅ **Logging**: Logs estructurados para monitoreo

## 📋 Requisitos

### Para Docker (Recomendado)
- Docker y Docker Compose
- **Google Calendar API**: `credentials.json` desde [Google Cloud Console](https://console.cloud.google.com/)
- **Servidor IMAP**: Credenciales de tu proveedor de correo

### Para desarrollo local
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) para gestión de dependencias
- [Ollama](https://ollama.ai/) instalado con un modelo (ej: `llama3`)

## 🐳 Despliegue con Docker (Recomendado)

### 1. Configuración inicial
```bash
# Clonar el repositorio
git clone <tu-repo-url>
cd secretaria

# Copiar configuración de ejemplo
cp .env.example .env

# Editar variables de entorno
nano .env
```

### 2. Configurar credenciales IMAP
Edita el archivo `.env` con tus datos:
```bash
IMAP_SERVER=imap.gmail.com          # Tu servidor IMAP
IMAP_USER=tu.email@gmail.com        # Tu email
IMAP_PASSWORD=tu_app_password       # App password (recomendado)
CHECK_INTERVAL=300                  # Verificar cada 5 minutos
```

### 3. Configurar Google Calendar API
1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un proyecto o selecciona uno existente
3. Habilita la Google Calendar API
4. Crea credenciales OAuth2 para aplicación de escritorio
5. Descarga el archivo como `credentials.json` en el directorio del proyecto

### 4. Ejecutar con Docker Compose
```bash
# Construir y ejecutar
docker-compose up -d

# Ver logs
docker-compose logs -f secretaria

# Detener
docker-compose down
```

## ⚙️ Configuración Avanzada

### Variables de entorno disponibles
```bash
# IMAP (REQUERIDO)
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
IMAP_USER=tu.email@gmail.com
IMAP_PASSWORD=tu_contraseña

# Servicio
CHECK_INTERVAL=300              # Segundos entre verificaciones
TIMEZONE=Europe/Madrid          # Zona horaria
OLLAMA_MODEL=llama3:8b-instruct-q4_K_M  # Modelo LLM
```

### Estructura de directorios para Docker
```
secretaria/
├── credentials.json       # Credenciales Google Calendar
├── .env                  # Variables de entorno
├── data/                 # Tokens persistentes (auto-creado)
└── logs/                 # Logs del servicio (opcional)
```

## 🛠️ Desarrollo Local

### 1. Instalar dependencias
```bash
uv sync
```

### 2. Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### 3. Ejecutar
```bash
# Ejecución única
uv run python hello.py

# Servicio continuo
uv run python secretaria_service.py
```

## � Monitoreo y Logs

### Ver logs del contenedor
```bash
# Logs en tiempo real
docker-compose logs -f secretaria

# Últimas 100 líneas
docker-compose logs --tail=100 secretaria

# Logs con timestamps
docker-compose logs -t secretaria
```

### Healthcheck
El contenedor incluye un healthcheck que verifica si el servicio está ejecutándose correctamente.

```bash
# Verificar estado
docker-compose ps
```

## 📧 Proveedores IMAP Comunes

| Proveedor | Servidor IMAP | Puerto |
|-----------|---------------|--------|
| Gmail | `imap.gmail.com` | 993 |
| Outlook/Hotmail | `imap-mail.outlook.com` | 993 |
| Yahoo | `imap.mail.yahoo.com` | 993 |
| Apple iCloud | `imap.mail.me.com` | 993 |

## 🔒 Seguridad

- **App Passwords**: Usa contraseñas de aplicación en lugar de tu contraseña principal
- **OAuth2**: Autenticación segura con Google
- **LLM Local**: El análisis se hace localmente, no se envían datos a terceros

## 📄 Licencia

GPL v3 - Ve el archivo `LICENSE` para más detalles.

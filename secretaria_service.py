"""secretaria_service.py
Servicio continuo del asistente de correo y calendario.
Ejecuta en bucle para verificar nuevos correos periódicamente.
"""

import time
import signal
import sys
import logging
from main import main as process_latest_email

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Variables globales para control del servicio
running = True

def signal_handler(signum, frame):
    """Maneja señales de terminación del sistema."""
    global running
    logger.info(f"Señal {signum} recibida. Deteniendo servicio...")
    running = False

def main():
    """Bucle principal del servicio."""
    global running
    
    # Configurar manejadores de señales
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Obtener intervalo de verificación (en segundos)
    import os
    check_interval = int(os.getenv("CHECK_INTERVAL", "300"))  # 5 minutos por defecto
    
    logger.info("🤖 Secretaria iniciada como servicio")
    logger.info(f"⏰ Verificando correos cada {check_interval} segundos")
    
    last_check_time = 0
    
    while running:
        try:
            current_time = time.time()
            
            # Verificar si es tiempo de procesar correos
            if current_time - last_check_time >= check_interval:
                logger.info("📧 Verificando nuevos correos...")
                
                try:
                    process_latest_email()
                    logger.info("✅ Verificación completada")
                except Exception as e:
                    logger.error(f"❌ Error procesando correos: {e}")
                
                last_check_time = current_time
            
            # Dormir brevemente para no consumir CPU innecesariamente
            time.sleep(10)
            
        except KeyboardInterrupt:
            logger.info("🛑 Interrupción manual recibida")
            break
        except Exception as e:
            logger.error(f"❌ Error inesperado en el servicio: {e}")
            time.sleep(30)  # Esperar antes de reintentar
    
    logger.info("👋 Servicio Secretaria detenido")

if __name__ == "__main__":
    main()

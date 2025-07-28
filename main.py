"""assistant_email_calendar.py
Pequeño asistente que:
  1. Conecta a cualquier servidor de correo vía IMAP y extrae el último correo recibido.
  2. Pasa el asunto + cuerpo por un modelo LLM ejecutado localmente con Ollama
     para determinar si hay información de reunión.
  3. Si hay reunión, crea un evento en Google Calendar con la API.

Requisitos:
  uv sync  # instalar dependencias con uv
  Instalar Ollama y tener un modelo descargado (por ejemplo llama3).

Variables de entorno necesarias:
  IMAP_SERVER   → host del servidor IMAP (p. ej. "imap.mail.eu")
  IMAP_PORT     → puerto (993 SSL por defecto)
  IMAP_USER     → usuario (email)
  IMAP_PASSWORD → contraseña o app‑password

Coloca `credentials.json` (Calendar API) descargado de Google Cloud Console
y ejecuta el script. La primera vez se abrirá un navegador para autorización
y creará `token.json`.
"""

from __future__ import print_function
import email
import imaplib
import json
import os
from datetime import datetime, timedelta

import requests
from dateutil import parser as dateparser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ---------------- Configuración -----------------------
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b-instruct-q4_K_M")  # ajusta al que tengas
TIMEZONE = "Europe/Madrid"

# Configuración del calendario
CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")  # ID del calendario específico
MAX_EMAILS_TO_CHECK = int(os.getenv("MAX_EMAILS_TO_CHECK", "10"))  # Número de correos a revisar

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.example.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")
# ------------------------------------------------------

SYSTEM_PROMPT = (
    "Eres un asistente que detecta si un correo electrónico incluye detalles de una reunión.\n"
    "IMPORTANTE: Estamos en el año 2025. Si el correo no especifica año, usa 2025.\n"
    "Si el correo menciona fechas pasadas o futuras, interprétalas correctamente según el contexto.\n"
    "Devuelve SIEMPRE un JSON con la siguiente estructura:\n"
    "{\n  \"has_meeting\": bool,\n  \"title\": str,\n  \"start\": str(ISO 8601 con zona horaria),\n  \"end\": str(ISO 8601 con zona horaria),\n  \"location\": str,\n  \"description\": str\n}\n"
    "Si no hay reunión, has_meeting debe ser false y los demás campos pueden ser cadenas vacías.\n"
    "Si hay reunión, rellena todos los campos con información actual (año 2025).\n"
    "Extrae toda la información relevante del correo y establece un título descriptivo. Intenta incorporar detalles en el titulo que se encuentran en el cuerpo del correo.\n"
    "Las fechas deben estar en formato ISO 8601 con zona horaria, por ejemplo: '2025-07-28T14:00:00+02:00'\n"
    "Si falta hora de fin, pon una hora después de inicio.\n"
    "Si la fecha es relativa (ej: 'mañana', 'próximo lunes'), calcula la fecha correcta basándote en la fecha actual proporcionada."
)

# ------------ Google Calendar helpers ----------------

def list_calendars(cal_service):
    """Lista todos los calendarios disponibles para ayudar a encontrar el ID correcto."""
    try:
        calendars_result = cal_service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])
        
        print("\n📅 Calendarios disponibles:")
        for calendar in calendars:
            cal_id = calendar['id']
            summary = calendar.get('summary', 'Sin nombre')
            primary = " (PRINCIPAL)" if calendar.get('primary', False) else ""
            print(f"  ID: {cal_id}")
            print(f"  Nombre: {summary}{primary}")
            print("  ---")
        return calendars
    except Exception as e:
        print(f"Error listando calendarios: {e}")
        return []

def get_google_service(api_name: str, version: str):
    creds = None
    token_path = "credentials/token.json" if os.path.exists("credentials") else "token.json"
    credentials_path = "credentials/credentials.json" if os.path.exists("credentials") else "credentials.json"
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return build(api_name, version, credentials=creds)

# ---------------- IMAP helpers -----------------------

def get_latest_emails_imap(max_emails=10):
    """Devuelve una lista de (subject, body, email_id) de los últimos N correos en INBOX."""
    if not all([IMAP_USER, IMAP_PASSWORD]):
        raise RuntimeError("IMAP_USER y/o IMAP_PASSWORD no definidos en el entorno")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(IMAP_USER, IMAP_PASSWORD)
    mail.select("INBOX")
    typ, data = mail.search(None, "ALL")
    ids = data[0].split()
    if not ids:
        mail.logout()
        return []
    
    # Obtener los últimos max_emails correos
    latest_ids = ids[-max_emails:]
    emails = []
    
    for email_id in latest_ids:
        try:
            email_id_str = email_id.decode()
            typ, msg_data = mail.fetch(email_id, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email, policy=email.policy.default)
            
            # ---- Subject ----
            subject = str(email.header.make_header(email.header.decode_header(msg.get("Subject", "(sin asunto)"))))
            
            # ---- Body (texto plano) ----
            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disp = str(part.get("Content-Disposition"))
                    if ctype == "text/plain" and "attachment" not in disp:
                        body_text = part.get_content()
                        break
            else:
                body_text = msg.get_content()
            
            emails.append((subject, body_text, email_id_str))
        except Exception as e:
            print(f"Error procesando correo {email_id}: {e}")
            continue
    
    mail.logout()
    return emails

def get_latest_email_imap():
    """Devuelve (subject, body, email_id) del email más reciente en INBOX."""
    emails = get_latest_emails_imap(1)
    if emails:
        return emails[0]
    return None, None, None

# ------------- LLM analysis --------------------------

def analyze_email_with_llm(subject: str, body: str):
    # Obtener fecha actual para contexto
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M")
    current_date_spanish = datetime.now().strftime("%d de %B de %Y")
    
    prompt = f"Fecha actual: {current_date} {current_time} ({current_date_spanish})\nAsunto: {subject}\nCuerpo:\n{body}"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "format": "json",
        "stream": False,
    }
    resp = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    try:
        meeting_info = json.loads(data["response"])
    except (KeyError, json.JSONDecodeError):
        meeting_info = {"has_meeting": False}
    return meeting_info

# ------------- Calendar event ------------------------

def create_calendar_event(cal_service, meeting_info):
    start_iso = meeting_info["start"]
    end_iso = meeting_info["end"]
    
    # Validar que las fechas sean razonables (año 2024 o posterior)
    try:
        start_dt = dateparser.parse(start_iso)
        if start_dt and start_dt.year < 2024:
            print(f"⚠️ Fecha sospechosa detectada: {start_iso}. Ajustando al año actual...")
            start_dt = start_dt.replace(year=datetime.now().year)
            start_iso = start_dt.isoformat()
            
        if not end_iso:
            end_dt = start_dt + timedelta(hours=1)
            end_iso = end_dt.isoformat()
        else:
            end_dt = dateparser.parse(end_iso)
            if end_dt and end_dt.year < 2024:
                end_dt = end_dt.replace(year=datetime.now().year)
                end_iso = end_dt.isoformat()
                
    except Exception as e:
        print(f"❌ Error parseando fechas: {e}")
        return None
        
    event = {
        "summary": meeting_info["title"],
        "location": meeting_info.get("location", ""),
        "description": meeting_info.get("description", ""),
        "start": {"dateTime": start_iso, "timeZone": TIMEZONE},
        "end": {"dateTime": end_iso, "timeZone": TIMEZONE},
    }
    print(f"Creando evento: {event['summary']} ({start_iso} - {end_iso}) en el calendario {CALENDAR_ID}")
    if not CALENDAR_ID:
        raise ValueError("CALENDAR_ID no definido. Asegúrate de configurarlo en el entorno.")
    if not cal_service:
        cal_service = get_google_service("calendar", "v3")
    # Crear el evento en el calendario
    created = cal_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    print(f"Evento creado: {created.get('htmlLink')}")
    return created

# ------------------- main ----------------------------

def load_processed_ids():
    """Carga los IDs de los correos ya procesados."""
    try:
        with open("processed_emails.json", "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_processed_ids(processed_ids):
    """Guarda los IDs de los correos procesados."""
    with open("processed_emails.json", "w") as f:
        json.dump(list(processed_ids), f)

def main():
    cal_service = get_google_service("calendar", "v3")
    
    # Descomentar la siguiente línea para ver todos los calendarios disponibles
    # list_calendars(cal_service)

    # Obtener los últimos correos
    emails = get_latest_emails_imap(MAX_EMAILS_TO_CHECK)
    if not emails:
        print("No hay correos en bandeja de entrada.")
        return

    # Cargar IDs ya procesados
    processed_ids = load_processed_ids()
    new_meetings_found = 0
    
    print(f"📧 Revisando los últimos {len(emails)} correos...")
    
    for i, (subject, body, email_id) in enumerate(emails, 1):
        print(f"\n--- Correo {i}/{len(emails)} (ID: {email_id}) ---")
        print(f"Asunto: {subject[:100]}{'...' if len(subject) > 100 else ''}")
        
        # Verificar si ya se procesó este correo
        if email_id in processed_ids:
            print("✅ Ya procesado anteriormente. Omitiendo...")
            continue

        try:
            meeting_info = analyze_email_with_llm(subject, body)
            if meeting_info.get("has_meeting"):
                create_calendar_event(cal_service, meeting_info)
                print(f"🗓️ Reunión detectada y evento creado para correo {email_id}")
                new_meetings_found += 1
            else:
                print("📝 No contiene información de reunión.")
            
            # Marcar como procesado
            processed_ids.add(email_id)
            
        except Exception as e:
            print(f"❌ Error procesando correo {email_id}: {e}")
            continue
    
    # Guardar IDs procesados
    save_processed_ids(processed_ids)
    
    if new_meetings_found > 0:
        print(f"\n🎉 Se crearon {new_meetings_found} nuevos eventos en el calendario")
    else:
        print(f"\n📋 No se encontraron nuevas reuniones en los últimos {len(emails)} correos")

if __name__ == "__main__":
    main()

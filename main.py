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
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3:8b-instruct-q4_K_M"  # ajusta al que tengas
TIMEZONE = "Europe/Madrid"

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.example.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")
# ------------------------------------------------------

SYSTEM_PROMPT = (
    "Eres un asistente que detecta si un correo electrónico incluye detalles de una reunión.\n"
    "Devuelve SIEMPRE un JSON con la siguiente estructura:\n"
    "{\n  \"has_meeting\": bool,\n  \"title\": str,\n  \"start\": str(ISO 8601),\n  \"end\": str(ISO 8601),\n  \"location\": str,\n  \"description\": str\n}\n"
    "Si no hay reunión, has_meeting debe ser false y los demás campos pueden ser cadenas vacías.\n"
    "Si hay reunión, rellena todos los campos; si falta hora de fin, pon una hora después de inicio."
)

# ------------ Google Calendar helpers ----------------

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

def get_latest_email_imap():
    """Devuelve (subject, body) del email más reciente en INBOX."""
    if not all([IMAP_USER, IMAP_PASSWORD]):
        raise RuntimeError("IMAP_USER y/o IMAP_PASSWORD no definidos en el entorno")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(IMAP_USER, IMAP_PASSWORD)
    mail.select("INBOX")
    typ, data = mail.search(None, "ALL")
    ids = data[0].split()
    if not ids:
        mail.logout()
        return None, None
    latest_id = ids[-1]
    typ, msg_data = mail.fetch(latest_id, "(RFC822)")
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
    mail.logout()
    return subject, body_text

# ------------- LLM analysis --------------------------

def analyze_email_with_llm(subject: str, body: str):
    prompt = f"Asunto: {subject}\nCuerpo:\n{body}"
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
    if not end_iso:
        start_dt = dateparser.parse(start_iso)
        end_dt = start_dt + timedelta(hours=1)
        end_iso = end_dt.isoformat()
    event = {
        "summary": meeting_info["title"],
        "location": meeting_info.get("location", ""),
        "description": meeting_info.get("description", ""),
        "start": {"dateTime": start_iso, "timeZone": TIMEZONE},
        "end": {"dateTime": end_iso, "timeZone": TIMEZONE},
    }
    created = cal_service.events().insert(calendarId="primary", body=event).execute()
    print(f"Evento creado: {created.get('htmlLink')}")
    return created

# ------------------- main ----------------------------

def main():
    cal_service = get_google_service("calendar", "v3")

    subject, body = get_latest_email_imap()
    if not body:
        print("No hay correos en bandeja de entrada.")
        return

    meeting_info = analyze_email_with_llm(subject, body)
    if meeting_info.get("has_meeting"):
        create_calendar_event(cal_service, meeting_info)
    else:
        print("El último correo no contiene información de reunión.")

if __name__ == "__main__":
    main()

import imaplib
import email
from email.header import decode_header
from email.message import EmailMessage
import os
import datetime
import ssl
import re
import time
import socket
import json
from render_email import procesar_correo

# 1. TIMEOUT GLOBAL PARA EVITAR CUELGUES
socket.setdefaulttimeout(15)

# ==========================================
# CONFIGURACIÓN 
# ==========================================
IMAP_SERVER = os.environ.get("XOLOS_IMAP_SERVER", "mail.xolosramirez.com")
IMAP_USER = os.environ.get("XOLOS_IMAP_USER", "fernando@xolosramirez.com")
IMAP_PASS = os.environ.get("XOLOS_IMAP_PASS", "")

DRAFTS_FOLDER = "Drafts"
HISTORY_FILE = "processed_history.json"

# ==========================================
# UTILIDADES DE SOPORTE
# ==========================================
def log(mensaje):
    """Imprime mensajes con timestamp para un cron.log limpio"""
    hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{hora}] {mensaje}")

def cargar_historial():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []

def guardar_historial(historial):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(historial, f)

def guardar_lead_json(nombre, email_cliente, asunto, origen):
    os.makedirs("leads", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    lead_data = {
        "fecha_registro": timestamp,
        "nombre": nombre,
        "email": email_cliente,
        "asunto_original": asunto,
        "origen": origen
    }
    with open(f"leads/lead_{timestamp}.json", 'w', encoding='utf-8') as f:
        json.dump(lead_data, f, ensure_ascii=False, indent=4)

def decodificar_asunto(header_value):
    if not header_value: return "Sin Asunto"
    decoded_bytes, charset = decode_header(header_value)[0]
    if charset:
        return decoded_bytes.decode(charset)
    elif isinstance(decoded_bytes, bytes):
        return decoded_bytes.decode('utf-8', errors='ignore')
    return str(decoded_bytes)

def extraer_cuerpo(msg):
    cuerpo = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                cuerpo = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                break
    else:
        cuerpo = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
    return cuerpo

def extraer_nombre(remitente_raw):
    if remitente_raw and '<' in remitente_raw:
        nombre = remitente_raw.split('<')[0].strip().replace('"', '')
        if nombre: 
            return nombre
    return "Amigo(a)"

def parsear_formspree(cuerpo_crudo):
    nombre_real = "Amigo(a)"
    email_real = ""
    mensaje_real = cuerpo_crudo

    match_nombre = re.search(r'(?im)^(?:nombre|name)\s*:\s*(.+)$', cuerpo_crudo)
    if match_nombre:
        nombre_real = match_nombre.group(1).strip()

    match_email = re.search(r'(?im)^(?:correo|email|e-mail)\s*:\s*(.+)$', cuerpo_crudo)
    if match_email:
        email_real = match_email.group(1).strip()

    match_mensaje = re.search(r'(?is)(?:^|\n)(?:mensaje|message)\s*:\s*(.+)', cuerpo_crudo)
    if match_mensaje:
        mensaje_real = match_mensaje.group(1).strip()

    return nombre_real, email_real, mensaje_real

# ==========================================
# BUCLE PRINCIPAL
# ==========================================
def leer_inbox():
    log(f"Iniciando ciclo. Conectando a {IMAP_SERVER}...")

    if not IMAP_PASS:
        log("ERROR CRÍTICO: La variable de entorno XOLOS_IMAP_PASS no está configurada.")
        return

    historial_procesados = cargar_historial()

    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE  # Ignora self-signed

        mail = imaplib.IMAP4_SSL(IMAP_SERVER, 993, ssl_context=ssl_context)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("INBOX")

        status, data = mail.search(None, "UNSEEN")

        if status != "OK":
            log("Error al buscar correos.")
            mail.logout()
            return

        ids_mensajes = data[0].split()
        if not ids_mensajes:
            log("-> No hay correos nuevos.")
            mail.logout()
            return

        os.makedirs("outputs", exist_ok=True)

        for num_bytes in ids_mensajes:
            num = num_bytes.decode("utf-8")

            status, fetch_data = mail.fetch(num, "(RFC822)")
            for response_part in fetch_data:
                if not isinstance(response_part, tuple):
                    continue

                msg = email.message_from_bytes(response_part[1])

                message_id = msg.get("Message-ID", f"no-id-{num}")
                if message_id in historial_procesados:
                    log(f"[!] MSG {message_id} ya procesado previamente. Saltando...")
                    mail.store(num, "+FLAGS", "\\Seen")
                    continue

                asunto_original = decodificar_asunto(msg.get("Subject"))
                remitente_raw = msg.get("From", "")
                cuerpo_crudo = extraer_cuerpo(msg)
                correo_respuesta = remitente_raw
                origen_lead = "Directo"

                if "formspree" in remitente_raw.lower() or "formspree" in asunto_original.lower():
                    log("[+] Formspree Detectado. Limpiando Lead...")
                    origen_lead = "Formspree"
                    nombre_remitente, email_real, cuerpo_real = parsear_formspree(cuerpo_crudo)
                    if email_real:
                        correo_respuesta = email_real
                else:
                    log("[+] Correo Directo Detectado.")
                    nombre_remitente = extraer_nombre(remitente_raw)
                    cuerpo_real = cuerpo_crudo
                    match_correo = re.search(r"<([^>]+)>", remitente_raw)
                    if match_correo:
                        correo_respuesta = match_correo.group(1)

                log(f"De (Real): {nombre_remitente} | Email: {correo_respuesta}")

                html_respuesta = procesar_correo(asunto_original, cuerpo_real, nombre_remitente)

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", message_id)[:40]
                filename = f"outputs/draft_{timestamp}_{safe_id}.html"

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(html_respuesta)

                borrador = EmailMessage()
                borrador["Subject"] = f"Re: {asunto_original}"
                borrador["From"] = IMAP_USER
                borrador["To"] = correo_respuesta
                borrador.set_content("Por favor visualiza este correo en un cliente que soporte HTML.")
                borrador.add_alternative(html_respuesta, subtype="html")

                status_append, data_append = mail.append(
                    DRAFTS_FOLDER,
                    "\\Draft",
                    imaplib.Time2Internaldate(time.time()),
                    borrador.as_bytes()
                )

                if status_append == "OK":
                    log("[🚀] ¡Borrador inyectado en Mailcow exitosamente!")
                    mail.store(num, "+FLAGS", "\\Seen")
                    log("[✔] Correo original marcado como leído.")

                    guardar_lead_json(nombre_remitente, correo_respuesta, asunto_original, origen_lead)
                    historial_procesados.append(message_id)
                    guardar_historial(historial_procesados)
                else:
                    log(f"[X] Error al inyectar borrador: {status_append} | {data_append}")

        mail.logout()
        log("Ciclo finalizado con éxito.")

    except socket.timeout:
        log("[!] ERROR: Timeout de socket al intentar conectar por IMAP. El servidor no respondió en 15 segundos.")
    except Exception as e:
        log(f"[!] ERROR conectando por IMAP: {type(e).__name__}: {e}")

if __name__ == "__main__":
    leer_inbox()

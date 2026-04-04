import imaplib
import smtplib
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
from render_email import procesar_correo, detectar_intencion, detectar_cachorro, cargar_cachorros

# 1. TIMEOUT GLOBAL Y CONFIGURACION
socket.setdefaulttimeout(15)

IMAP_SERVER = os.environ.get("XOLOS_IMAP_SERVER", "mail.xolosramirez.com")
IMAP_USER = os.environ.get("XOLOS_IMAP_USER", "fernando@xolosramirez.com")
IMAP_PASS = os.environ.get("XOLOS_IMAP_PASS", "")

# MODO_AUTO: "ON" para enviar correos seguros, "OFF" para que todo sea Draft
MODO_AUTO = os.environ.get("XOLOS_MODO_AUTO", "OFF")

DRAFTS_FOLDER = "Drafts"
HISTORY_FILE = "processed_history.json"

# ==========================================
# UTILIDADES DE SOPORTE
# ==========================================
def log(mensaje):
    hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{hora}] {mensaje}")


def cargar_historial():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []


def guardar_historial(historial):
    with open(HISTORY_FILE, "w") as f:
        json.dump(historial, f)


def guardar_lead_json(nombre, email_cliente, asunto, origen, estrategia):
    os.makedirs("leads", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    lead_data = {
        "fecha": timestamp,
        "nombre": nombre,
        "email": email_cliente,
        "asunto": asunto,
        "origen": origen,
        "accion_tomada": estrategia,
    }
    with open(f"leads/lead_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump(lead_data, f, ensure_ascii=False, indent=4)


# ==========================================
# MOTOR DE ENVIO REAL (SMTP)
# ==========================================
def enviar_correo_real(destinatario, asunto, html_cuerpo):
    try:
        msg = EmailMessage()
        msg["Subject"] = asunto
        msg["From"] = f"Xolos Ramirez <{IMAP_USER}>"
        msg["To"] = destinatario
        msg.set_content("Por favor visualiza este correo en un cliente que soporte HTML.")
        msg.add_alternative(html_cuerpo, subtype="html")

        # Usamos el puerto 587 con STARTTLS
        with smtplib.SMTP(IMAP_SERVER, 587, timeout=15) as server:
            server.starttls()
            server.login(IMAP_USER, IMAP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        log(f"    [X] Error critico en envio SMTP: {e}")
        return False


# ==========================================
# CLASIFICADOR DE CONFIANZA
# ==========================================
def decidir_estrategia(intencion, cachorro, nombre_cliente, email_cliente):
    """
    Determina si el lead es seguro para responder automaticamente.
    """
    if MODO_AUTO != "ON":
        return "REVIEW"

    if not email_cliente or "@" not in email_cliente:
        return "REVIEW"

    # 1. Casos de alta confianza (Auto-envio)
    if intencion in ["precio", "llamada"]:
        return "SAFE"

    if cachorro and nombre_cliente != "Amigo(a)":
        return "SAFE"

    # 2. Casos que requieren ojo humano
    return "REVIEW"


# ==========================================
# PARSEO Y EXTRACCION
# ==========================================
def decodificar_asunto(header_value):
    if not header_value:
        return "Sin Asunto"
    decoded_bytes, charset = decode_header(header_value)[0]
    if charset:
        return decoded_bytes.decode(charset)
    return str(decoded_bytes)


def extraer_cuerpo(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode("utf-8", errors="ignore")
    return msg.get_payload(decode=True).decode("utf-8", errors="ignore")


def parsear_formspree(cuerpo_crudo):
    nombre = "Amigo(a)"
    email_dest = ""
    match_nombre = re.search(r"(?im)^(?:nombre|name)\s*:\s*(.+)$", cuerpo_crudo)
    if match_nombre:
        nombre = match_nombre.group(1).strip()
    match_email = re.search(r"(?im)^(?:correo|email|e-mail)\s*:\s*(.+)$", cuerpo_crudo)
    if match_email:
        email_dest = match_email.group(1).strip()
    return nombre, email_dest


# ==========================================
# PROCESO PRINCIPAL
# ==========================================
def leer_inbox():
    log(f"Iniciando ciclo (Modo Auto: {MODO_AUTO}). Conectando...")
    if not IMAP_PASS:
        log("ERROR: Contraseña IMAP no configurada.")
        return

    historial = cargar_historial()
    cachorros_db = cargar_cachorros("cachorros.json")

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        mail = imaplib.IMAP4_SSL(IMAP_SERVER, 993, ssl_context=ctx)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("INBOX")

        status, data = mail.search(None, "UNSEEN")
        ids = data[0].split()
        if not ids:
            log("-> No hay correos nuevos.")
            mail.logout()
            return

        for num_bytes in ids:
            num = num_bytes.decode("utf-8")
            _, fetch_data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(fetch_data[0][1])

            msg_id = msg.get("Message-ID", f"no-id-{num}")
            if msg_id in historial:
                mail.store(num, "+FLAGS", "\\Seen")
                continue

            asunto = decodificar_asunto(msg["Subject"])
            remitente_raw = msg.get("From", "")
            cuerpo = extraer_cuerpo(msg)

            # Detectar origen y limpiar datos
            es_formspree = "formspree" in remitente_raw.lower() or "formspree" in asunto.lower()
            if es_formspree:
                nombre, email_cliente = parsear_formspree(cuerpo)
                origen = "Formspree"
            else:
                nombre = remitente_raw.split("<")[0].strip().replace('"', "") or "Amigo(a)"
                email_cliente = re.search(r"<([^>]+)>", remitente_raw).group(1) if "<" in remitente_raw else remitente_raw
                origen = "Directo"

            # Inteligencia de respuesta
            texto_analisis = f"{asunto} {cuerpo}"
            intencion = detectar_intencion(texto_analisis)
            cachorro = detectar_cachorro(texto_analisis, cachorros_db)
            html_res = procesar_correo(asunto, cuerpo, nombre)

            # Decidir Estrategia
            estrategia = decidir_estrategia(intencion, cachorro, nombre, email_cliente)

            if estrategia == "SAFE":
                log(f"    [AUTO] AUTO-ENVIO a: {email_cliente} (Intencion: {intencion})")
                if enviar_correo_real(email_cliente, f"Re: {asunto}", html_res):
                    mail.store(num, "+FLAGS", "\\Seen")
                    log("        [OK] Enviado exitosamente.")
                else:
                    estrategia = "REVIEW"  # Fallback si falla SMTP

            if estrategia == "REVIEW":
                log(f"    [DRAFT] DRAFT para: {email_cliente} (Revision requerida)")
                borrador = EmailMessage()
                borrador["Subject"] = f"Re: {asunto}"
                borrador["From"] = IMAP_USER
                borrador["To"] = email_cliente
                borrador.add_alternative(html_res, subtype="html")

                mail.append(DRAFTS_FOLDER, "\\Draft", imaplib.Time2Internaldate(time.time()), borrador.as_bytes())
                mail.store(num, "+FLAGS", "\\Seen")
                log("        [OK] Borrador creado.")

            guardar_lead_json(nombre, email_cliente, asunto, origen, estrategia)
            historial.append(msg_id)
            guardar_historial(historial)

        mail.logout()
        log("Ciclo finalizado.")

    except Exception as e:
        log(f"ERROR: {e}")


if __name__ == "__main__":
    leer_inbox()

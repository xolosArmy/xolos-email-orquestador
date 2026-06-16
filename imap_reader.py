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
import errno
from render_email import procesar_correo, detectar_intencion, detectar_cachorro, cargar_cachorros

# 1. TIMEOUT GLOBAL Y CONFIGURACION
SOCKET_TIMEOUT = 15
socket.setdefaulttimeout(SOCKET_TIMEOUT)

DEFAULT_IMAP_SERVER = "mail.xolosramirez.com"
DEFAULT_IMAP_PORT = "993"
DEFAULT_IMAP_USER = "fernando@xolosramirez.com"
DEFAULT_SMTP_PORT = "587"
FALLO_TCP_MENSAJE = (
    "Fallo de conectividad TCP hacia IMAP/SMTP. DNS resuelve, pero el puerto no responde. "
    "Revisar firewall, proveedor o host configurado."
)

IMAP_SERVER = os.environ.get("XOLOS_IMAP_SERVER", DEFAULT_IMAP_SERVER)
IMAP_PORT = int(os.environ.get("XOLOS_IMAP_PORT", DEFAULT_IMAP_PORT))
IMAP_USER = os.environ.get("XOLOS_IMAP_USER", DEFAULT_IMAP_USER)
IMAP_PASS = os.environ.get("XOLOS_IMAP_PASS", "")
SMTP_SERVER = os.environ.get("XOLOS_SMTP_SERVER", IMAP_SERVER)
SMTP_PORT = int(os.environ.get("XOLOS_SMTP_PORT", DEFAULT_SMTP_PORT))

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


def detalle_error(exc):
    return f"{type(exc).__name__}: {exc}"


class FalloConectividadTCP(ConnectionError):
    pass


def es_fallo_tcp(exc):
    codigos_tcp = {
        errno.ECONNREFUSED,
        errno.EHOSTUNREACH,
        errno.ENETUNREACH,
        errno.ETIMEDOUT,
    }
    return isinstance(exc, (socket.timeout, TimeoutError)) or getattr(exc, "errno", None) in codigos_tcp


def log_fallo_tcp(servicio, host, puerto, exc):
    if es_fallo_tcp(exc):
        log(f"{FALLO_TCP_MENSAJE} Servicio={servicio} host={host} puerto={puerto}.")


def log_error_servicio(servicio, etapa, host, puerto, exc):
    log(f"ERROR {servicio} en etapa '{etapa}' ({host}:{puerto}): {detalle_error(exc)}")


def resolver_host(servicio, host, puerto):
    etapa = "resolucion DNS"
    log(f"Resolviendo host {servicio}: {host}:{puerto}...")
    try:
        direcciones = socket.getaddrinfo(host, puerto, type=socket.SOCK_STREAM)
        ips = sorted({item[4][0] for item in direcciones})
        log(f"[OK] DNS {servicio}: {host} -> {', '.join(ips)}")
        return direcciones
    except socket.gaierror as exc:
        log_error_servicio(servicio, etapa, host, puerto, exc)
        raise
    except OSError as exc:
        log_error_servicio(servicio, etapa, host, puerto, exc)
        raise


def log_configuracion():
    imap_server_origen = "env XOLOS_IMAP_SERVER" if "XOLOS_IMAP_SERVER" in os.environ else f"default {DEFAULT_IMAP_SERVER}"
    imap_port_origen = "env XOLOS_IMAP_PORT" if "XOLOS_IMAP_PORT" in os.environ else f"default {DEFAULT_IMAP_PORT}"
    imap_user_origen = "env XOLOS_IMAP_USER" if "XOLOS_IMAP_USER" in os.environ else f"default {DEFAULT_IMAP_USER}"
    smtp_server_origen = "env XOLOS_SMTP_SERVER" if "XOLOS_SMTP_SERVER" in os.environ else "fallback a IMAP_SERVER"
    smtp_port_origen = "env XOLOS_SMTP_PORT" if "XOLOS_SMTP_PORT" in os.environ else f"default {DEFAULT_SMTP_PORT}"
    log(
        "Configuracion: "
        f"timeout_socket={SOCKET_TIMEOUT}s, "
        f"IMAP={IMAP_SERVER}:{IMAP_PORT} SSL, "
        f"SMTP={SMTP_SERVER}:{SMTP_PORT} STARTTLS, "
        f"usuario={'configurado' if IMAP_USER else 'FALTANTE'}, "
        f"password={'configurado' if IMAP_PASS else 'FALTANTE'}"
    )
    log(
        "Origen configuracion: "
        f"XOLOS_IMAP_SERVER={imap_server_origen}, "
        f"XOLOS_IMAP_PORT={imap_port_origen}, "
        f"XOLOS_IMAP_USER={imap_user_origen}, "
        f"XOLOS_SMTP_SERVER={smtp_server_origen}, "
        f"XOLOS_SMTP_PORT={smtp_port_origen}"
    )


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
    servicio = "SMTP"
    try:
        msg = EmailMessage()
        msg["Subject"] = asunto
        msg["From"] = f"Xolos Ramirez <{IMAP_USER}>"
        msg["To"] = destinatario
        msg.set_content("Por favor visualiza este correo en un cliente que soporte HTML.")
        msg.add_alternative(html_cuerpo, subtype="html")

        # Usamos el puerto 587 con STARTTLS
        resolver_host(servicio, SMTP_SERVER, SMTP_PORT)

        etapa = "conexion SMTP"
        try:
            log(f"Conectando a SMTP {SMTP_SERVER}:{SMTP_PORT} (timeout={SOCKET_TIMEOUT}s)...")
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=SOCKET_TIMEOUT)
            log("[OK] Conexion SMTP establecida.")
        except (socket.timeout, TimeoutError, smtplib.SMTPException, OSError) as exc:
            log_error_servicio(servicio, etapa, SMTP_SERVER, SMTP_PORT, exc)
            log_fallo_tcp(servicio, SMTP_SERVER, SMTP_PORT, exc)
            if es_fallo_tcp(exc):
                raise FalloConectividadTCP(FALLO_TCP_MENSAJE) from exc
            raise

        try:
            etapa = "STARTTLS SMTP"
            try:
                log(f"Iniciando STARTTLS SMTP en {SMTP_SERVER}:{SMTP_PORT}...")
                server.starttls()
                log("[OK] STARTTLS SMTP activo.")
            except (smtplib.SMTPException, ssl.SSLError, OSError) as exc:
                log_error_servicio(servicio, etapa, SMTP_SERVER, SMTP_PORT, exc)
                raise

            etapa = "login SMTP"
            try:
                log(f"Autenticando SMTP como {IMAP_USER}...")
                server.login(IMAP_USER, IMAP_PASS)
                log("[OK] Login SMTP exitoso.")
            except smtplib.SMTPAuthenticationError as exc:
                log_error_servicio(servicio, etapa, SMTP_SERVER, SMTP_PORT, exc)
                raise
            except (smtplib.SMTPException, OSError) as exc:
                log_error_servicio(servicio, etapa, SMTP_SERVER, SMTP_PORT, exc)
                raise

            etapa = "envio SMTP"
            try:
                log(f"Enviando SMTP a {destinatario}...")
                server.send_message(msg)
                log("[OK] Mensaje SMTP enviado.")
            except (smtplib.SMTPException, OSError) as exc:
                log_error_servicio(servicio, etapa, SMTP_SERVER, SMTP_PORT, exc)
                raise
        finally:
            try:
                server.quit()
            except (smtplib.SMTPException, OSError):
                pass
        return True
    except Exception as e:
        log(f"    [X] Error critico en envio SMTP: {detalle_error(e)}")
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
    log_configuracion()
    if not IMAP_PASS:
        log("ERROR: Contraseña IMAP no configurada.")
        return

    historial = cargar_historial()
    cachorros_db = cargar_cachorros("cachorros.json")

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        log("Contexto SSL IMAP creado (verificacion de certificado desactivada).")

        resolver_host("IMAP", IMAP_SERVER, IMAP_PORT)

        etapa = "conexion IMAP SSL"
        try:
            log(f"Conectando a IMAP SSL {IMAP_SERVER}:{IMAP_PORT} (timeout={SOCKET_TIMEOUT}s)...")
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, ssl_context=ctx)
            log("[OK] Conexion IMAP SSL establecida.")
        except (socket.timeout, TimeoutError, ssl.SSLError, OSError, imaplib.IMAP4.error) as exc:
            log_error_servicio("IMAP", etapa, IMAP_SERVER, IMAP_PORT, exc)
            log_fallo_tcp("IMAP", IMAP_SERVER, IMAP_PORT, exc)
            if es_fallo_tcp(exc):
                raise FalloConectividadTCP(FALLO_TCP_MENSAJE) from exc
            raise

        etapa = "login IMAP"
        try:
            log(f"Autenticando IMAP como {IMAP_USER}...")
            mail.login(IMAP_USER, IMAP_PASS)
            log("[OK] Login IMAP exitoso.")
        except imaplib.IMAP4.error as exc:
            log_error_servicio("IMAP", etapa, IMAP_SERVER, IMAP_PORT, exc)
            raise
        except OSError as exc:
            log_error_servicio("IMAP", etapa, IMAP_SERVER, IMAP_PORT, exc)
            raise

        etapa = "seleccion INBOX"
        try:
            log("Seleccionando carpeta IMAP INBOX...")
            mail.select("INBOX")
            log("[OK] Carpeta INBOX seleccionada.")
        except (imaplib.IMAP4.error, OSError) as exc:
            log_error_servicio("IMAP", etapa, IMAP_SERVER, IMAP_PORT, exc)
            raise

        etapa = "busqueda IMAP UNSEEN"
        try:
            log("Buscando correos IMAP UNSEEN...")
            status, data = mail.search(None, "UNSEEN")
            log(f"Resultado search UNSEEN: status={status}, data={data}")
        except (imaplib.IMAP4.error, OSError) as exc:
            log_error_servicio("IMAP", etapa, IMAP_SERVER, IMAP_PORT, exc)
            raise
        ids = data[0].split()
        ids_encontrados = [num.decode("utf-8", errors="replace") for num in ids]
        log(f"Mensajes IMAP UNSEEN encontrados: {ids_encontrados}")
        if not ids:
            log("-> No hay correos nuevos.")
            mail.logout()
            return

        for num_bytes in ids:
            num = num_bytes.decode("utf-8")
            etapa = f"fetch IMAP mensaje {num}"
            try:
                log(f"Descargando mensaje IMAP {num}...")
                _, fetch_data = mail.fetch(num, "(RFC822)")
                log(f"[OK] Mensaje IMAP {num} descargado.")
            except (imaplib.IMAP4.error, OSError) as exc:
                log_error_servicio("IMAP", etapa, IMAP_SERVER, IMAP_PORT, exc)
                raise
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

                etapa = f"append IMAP borrador mensaje {num}"
                try:
                    log(f"Guardando borrador IMAP en {DRAFTS_FOLDER}...")
                    status_append, resp_append = mail.append(
                        DRAFTS_FOLDER,
                        "\\Draft",
                        imaplib.Time2Internaldate(time.time()),
                        borrador.as_bytes(),
                    )
                    log(
                        f"Resultado append Drafts: status={status_append}, "
                        f"resp={resp_append}, carpeta={DRAFTS_FOLDER}"
                    )
                except (imaplib.IMAP4.error, OSError) as exc:
                    log_error_servicio("IMAP", etapa, IMAP_SERVER, IMAP_PORT, exc)
                    raise
                if status_append != "OK":
                    log(f"[ERROR] No se pudo guardar borrador para msg_id={msg_id} en carpeta={DRAFTS_FOLDER}")
                    continue
                mail.store(num, "+FLAGS", "\\Seen")
                log(f"[OK] Borrador guardado y mensaje marcado en historial: {msg_id}")

            guardar_lead_json(nombre, email_cliente, asunto, origen, estrategia)
            historial.append(msg_id)
            guardar_historial(historial)

        mail.logout()
        log("Ciclo finalizado.")

    except Exception as e:
        log(f"ERROR ciclo principal: {detalle_error(e)}")


if __name__ == "__main__":
    leer_inbox()

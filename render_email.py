import json
import re


# ==========================================
# 1. CARGAR BASE DE DATOS
# ==========================================
def cargar_cachorros(path_json):
    try:
        with open(path_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("cachorros", [])
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {path_json}")
        return []


# ==========================================
# 2. MOTORES DE DETECCIÓN (IDIOMA, CACHORRO E INTENCIÓN)
# ==========================================
def detectar_idioma(texto):
    """
    Detecta si el correo entrante está en inglés basándose en palabras clave.
    """
    texto_limpio = texto.lower()
    patron_en = r"\b(how|much|price|cost|visit|meet|call|phone|hello|hi|interested|puppy|dog|shipping|available)\b"
    if re.search(patron_en, texto_limpio):
        return "en"
    return "es"


def detectar_cachorro(texto, cachorros):
    texto_limpio = texto.lower()
    for cachorro in cachorros:
        slug = cachorro["slug"].lower()
        nombre_pila = cachorro["nombre"].split()[0].lower()
        if slug in texto_limpio or nombre_pila in texto_limpio:
            return cachorro
    return None


def detectar_intencion(texto):
    """
    Analiza el texto para detectar la intención (Bilingüe).
    """
    texto_limpio = texto.lower()

    patrones = {
        "visita": r"\b(visita|visitar|ir a ver|conocer|ubicación|ubicacion|visit|meet|location|where)\b",
        "llamada": r"\b(llamar|llamada|teléfono|telefono|marcar|hablemos|call|phone|talk|speak)\b",
        "precio": r"\b(precio|costo|cuánto|cuanto|valor|cotización|cotizacion|price|cost|how much|quote)\b",
    }

    for intencion, patron in patrones.items():
        if re.search(patron, texto_limpio):
            return intencion

    return "general"


# ==========================================
# 3. RENDERIZAR TEMPLATES
# ==========================================
def render_template_cachorro(cachorro, nombre_cliente, path_template, idioma="es"):
    try:
        with open(path_template, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        html = "<p>Hola {{nombre_cliente}}, enviando información de {{nombre}}.</p>"

    cachorro_render = cachorro.copy()

    # Inyección dinámica para el programa Teyolías
    if cachorro_render.get("teyolia"):
        if idioma == "en":
            aviso_teyolia = (
                "<br><br><span style='background-color: #d4af37; color: #000; padding: 4px 8px; "
                "font-weight: bold; border-radius: 4px;'>✨ Teyolía Candidate</span><br>"
                "This puppy is part of our special cultural guardianship program. "
                "<a href='https://www.xolosramirez.com/en/teyolias-guardianship.html' style='color:#d4af37;'>"
                "Learn more about the program here</a>."
            )
        else:
            aviso_teyolia = (
                "<br><br><span style='background-color: #d4af37; color: #000; padding: 4px 8px; "
                "font-weight: bold; border-radius: 4px;'>✨ Candidato a Teyolía</span><br>"
                "Este cachorro ha alcanzado la edad ideal y es parte de nuestro programa especial de guardianía. "
                "<a href='https://www.xolosramirez.com/teyolias-guardiania.html' style='color:#d4af37;'>"
                "Conoce más sobre el programa y cómo participar aquí</a>."
            )

        cachorro_render["descripcion_personalidad"] = (
            cachorro_render.get("descripcion_personalidad", "") + aviso_teyolia
        )

    # Manejo de video condicional
    if cachorro_render.get("video_personalidad_url"):
        html = re.sub(
            r"\{\{#if video_personalidad_url\}\}(.*?)\{\{/if\}\}",
            r"\1",
            html,
            flags=re.DOTALL,
        )
    else:
        html = re.sub(
            r"\{\{#if video_personalidad_url\}\}.*?\{\{/if\}\}",
            "",
            html,
            flags=re.DOTALL,
        )

    # Manejo de videollamada condicional (Google Meet)
    if cachorro_render.get("videollamada_url"):
        html = re.sub(
            r"\{\{#if videollamada_url\}\}(.*?)\{\{/if\}\}",
            r"\1",
            html,
            flags=re.DOTALL,
        )
    else:
        html = re.sub(
            r"\{\{#if videollamada_url\}\}.*?\{\{/if\}\}",
            "",
            html,
            flags=re.DOTALL,
        )

    html = html.replace("{{nombre_cliente}}", nombre_cliente)

    for key, value in cachorro_render.items():
        if value is not None:
            html = html.replace(f"{{{{{key}}}}}", str(value))

    return html


def generar_html_fallback(nombre_cliente, intencion, idioma="es"):
    """
    Fallback inteligente adaptado al idioma y a la intención del cliente.
    """
    if idioma == "en":
        mensajes_en = {
            "visita": "To protect the health of our litters, we do not allow visits without a prior reservation. However, we do offer guided video calls.",
            "llamada": "To provide you with the best service, we handle our initial consultations via email or through a scheduled video call.",
            "precio": "The price for our puppies is $42,000 MXN (approx. USD equivalent), with an initial reservation of $15,000 MXN.",
            "general": "",
        }
        mensaje_intencion = mensajes_en.get(intencion, "")

        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <body style="margin: 0; padding: 0; background-color: #f4f4f4; font-family: Arial, sans-serif; color: #333333;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                <tr>
                    <td style="background-color: #2c3e50; padding: 30px; text-align: center;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 24px; letter-spacing: 2px;">XOLOS RAMÍREZ</h1>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 30px 30px 10px 30px;">
                        <p style="font-size: 16px; line-height: 1.6;">Hello <strong>{nombre_cliente}</strong>,</p>
                        <p style="font-size: 16px; line-height: 1.6;">Thank you for your interest in our Xoloitzcuintles.</p>
                        <p style="font-size: 16px; line-height: 1.6;">{mensaje_intencion} To provide you with accurate information and visual material, it would be great to know <strong>which specific puppy caught your attention</strong>.</p>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 25px 30px; background-color: #fdfbf7; text-align: center;">
                        <a href="https://www.xolosramirez.com/en/available-xolos.html" style="background-color: #d35400; color: #ffffff; padding: 14px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">View Available Xolos</a>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    mensajes_es = {
        "visita": "Para proteger la salud de nuestras camadas, no realizamos visitas sin reserva previa. Sin embargo, te ofrecemos una videollamada guiada.",
        "llamada": "Para brindarte la mejor atención, manejamos nuestras consultas iniciales por este medio o a través de una videollamada programada.",
        "precio": "El precio de nuestros cachorros es de $42,000 MXN, con una reserva inicial de $15,000 MXN.",
        "general": "",
    }
    mensaje_intencion = mensajes_es.get(intencion, "")

    try:
        with open("template-general.html", "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("{{nombre_cliente}}", nombre_cliente)
        html = html.replace("{{mensaje_intencion}}", mensaje_intencion)
        return html
    except FileNotFoundError:
        return f"<p>Hola {nombre_cliente}, {mensaje_intencion} Por favor visita la web.</p>"


# ==========================================
# 4. ORQUESTADOR PRINCIPAL
# ==========================================
def procesar_correo(asunto, cuerpo, remitente_nombre):
    print(f"\n--- Procesando correo de: {remitente_nombre} ---")
    texto_completo = f"{asunto} {cuerpo}"

    cachorros_db = cargar_cachorros("cachorros.json")

    idioma = detectar_idioma(texto_completo)
    cachorro_detectado = detectar_cachorro(texto_completo, cachorros_db)
    intencion = detectar_intencion(texto_completo)

    print(f"-> Idioma detectado: {idioma.upper()}")
    print(f"-> Intención detectada: {intencion.upper()}")

    if cachorro_detectado:
        print(f"-> Cachorro detectado: {cachorro_detectado['nombre']}")
        html_final = render_template_cachorro(
            cachorro_detectado, remitente_nombre, "template-maestro.html", idioma
        )
        return html_final

    print("-> AVISO: No se detectó cachorro. Generando Fallback Inteligente.")
    html_final = generar_html_fallback(remitente_nombre, intencion, idioma)
    return html_final


# ==========================================
# 5. BATERÍA DE PRUEBAS
# ==========================================
if __name__ == "__main__":
    pruebas = [
        {
            "remitente": "Carlos",
            "asunto": "Cachorro Tonatiuh",
            "cuerpo": "Hola, ¿sigue disponible Tonatiuh? Me interesa mucho el programa.",
        },
        {
            "remitente": "John Smith",
            "asunto": "Puppy price",
            "cuerpo": "Hello, how much is the shipping to USA?",
        },
        {
            "remitente": "Luis",
            "asunto": "Información",
            "cuerpo": "¿Cuál es el precio de los cachorros?",
        },
    ]

    for i, test in enumerate(pruebas):
        html_out = procesar_correo(test["asunto"], test["cuerpo"], test["remitente"])
        nombre_archivo = f"output_prueba_{i + 1}.html"

        with open(nombre_archivo, "w", encoding="utf-8") as f:
            f.write(html_out)
        print(f"[*] Archivo '{nombre_archivo}' generado.")

import json
import re
import os

# ==========================================
# 1. CARGAR BASE DE DATOS
# ==========================================
def cargar_cachorros(path_json):
    try:
        with open(path_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('cachorros', [])
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {path_json}")
        return []

# ==========================================
# 2. MOTORES DE DETECCIÓN (CACHORRO E INTENCIÓN)
# ==========================================
def detectar_cachorro(texto, cachorros):
    texto_limpio = texto.lower()
    for cachorro in cachorros:
        slug = cachorro['slug'].lower()
        nombre_pila = cachorro['nombre'].split()[0].lower()
        if slug in texto_limpio or nombre_pila in texto_limpio:
            return cachorro
    return None

def detectar_intencion(texto):
    """
    Analiza el texto para detectar la intención principal del lead.
    Retorna: 'visita', 'llamada', 'precio' o 'general'.
    """
    texto_limpio = texto.lower()
    
    # Patrones de intención
    patrones = {
        'visita': r'\b(visita|visitar|ir a ver|conocer en persona|ir al criadero|ubicación|ubicacion)\b',
        'llamada': r'\b(llamar|llamada|teléfono|telefono|marcar|hablemos)\b',
        'precio': r'\b(precio|costo|cuánto cuesta|cuanto cuesta|valor|cotización|cotizacion)\b'
    }
    
    for intencion, patron in patrones.items():
        if re.search(patron, texto_limpio):
            return intencion
            
    return 'general'

# ==========================================
# 3. RENDERIZAR TEMPLATES
# ==========================================
def render_template_cachorro(cachorro, nombre_cliente, path_template):
    with open(path_template, 'r', encoding='utf-8') as f:
        html = f.read()

    if cachorro.get('video_personalidad_url'):
        html = re.sub(r'\{\{#if video_personalidad_url\}\}(.*?)\{\{/if\}\}', r'\1', html, flags=re.DOTALL)
    else:
        html = re.sub(r'\{\{#if video_personalidad_url\}\}.*?\{\{/if\}\}', '', html, flags=re.DOTALL)

    html = html.replace('{{nombre_cliente}}', nombre_cliente)

    for key, value in cachorro.items():
        if value is not None:
            html = html.replace(f'{{{{{key}}}}}', str(value))

    return html

def generar_html_fallback(nombre_cliente, intencion):
    """
    Genera un HTML general cuando no se detecta un cachorro específico,
    adaptando el mensaje según la intención detectada.
    """
    mensaje_intencion = ""
    
    if intencion == 'visita':
        mensaje_intencion = "Para proteger la salud de nuestras camadas, no realizamos visitas sin reserva previa. Sin embargo, te ofrecemos una videollamada guiada."
    elif intencion == 'llamada':
        mensaje_intencion = "Para brindarte la mejor atención, manejamos nuestras consultas iniciales por este medio o a través de una videollamada programada."
    elif intencion == 'precio':
        mensaje_intencion = "El precio de nuestros cachorros es de $42,000 MXN, con una reserva inicial de $15,000 MXN. "
    
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c3e50;">Xolos Ramírez</h2>
        <p>Hola <strong>{nombre_cliente}</strong>,</p>
        <p>Gracias por tu interés en nuestra crianza.</p>
        <p>{mensaje_intencion} Para poder brindarte información detallada y material visual, nos ayudaría mucho saber <strong>qué cachorro en específico ha llamado tu atención</strong>.</p>
        <p>Puedes conocer a los ejemplares disponibles en nuestra web:</p>
        <p><a href="https://www.xolosramirez.com/xolos-disponibles.html" style="background-color: #d35400; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Ver Xolos Disponibles</a></p>
    </body>
    </html>
    """
    return html

# ==========================================
# 4. ORQUESTADOR PRINCIPAL
# ==========================================
def procesar_correo(asunto, cuerpo, remitente_nombre):
    print(f"\n--- Procesando correo de: {remitente_nombre} ---")
    texto_completo = f"{asunto} {cuerpo}"
    
    cachorros_db = cargar_cachorros('cachorros.json')
    
    cachorro_detectado = detectar_cachorro(texto_completo, cachorros_db)
    intencion = detectar_intencion(texto_completo)
    
    print(f"-> Intención detectada: {intencion.upper()}")
    
    if cachorro_detectado:
        print(f"-> Cachorro detectado: {cachorro_detectado['nombre']}")
        html_final = render_template_cachorro(cachorro_detectado, remitente_nombre, 'template-maestro.html')
        return html_final
    else:
        print("-> AVISO: No se detectó cachorro. Generando Fallback Inteligente.")
        html_final = generar_html_fallback(remitente_nombre, intencion)
        return html_final

# ==========================================
# 5. BATERÍA DE PRUEBAS
# ==========================================
if __name__ == "__main__":
    
    pruebas = [
        {"remitente": "Carlos", "asunto": "Cachorro Teyolia", "cuerpo": "Hola, quiero saber si Teyolia sigue disponible."},
        {"remitente": "Ana", "asunto": "Visita al criadero", "cuerpo": "Me gustaría ir a ver a los perritos este fin de semana."},
        {"remitente": "Luis", "asunto": "Información", "cuerpo": "¿Cuál es el precio de los cachorros?"}
    ]
    
    for i, test in enumerate(pruebas):
        html_out = procesar_correo(test['asunto'], test['cuerpo'], test['remitente'])
        nombre_archivo = f'output_prueba_{i+1}.html'
        
        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            f.write(html_out)
        print(f"[*] Archivo '{nombre_archivo}' generado.")

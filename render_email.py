import json
import re

# ==========================================
# 1. CARGAR BASE DE DATOS
# ==========================================
def cargar_cachorros(path_json):
    """Carga el JSON maestro de cachorros."""
    try:
        with open(path_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('cachorros', [])
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {path_json}")
        return []

# ==========================================
# 2. DETECTAR CACHORRO (LÓGICA MVP)
# ==========================================
def detectar_cachorro(texto, cachorros):
    """
    Busca coincidencias simples del nombre o slug del cachorro en el texto.
    Retorna el objeto del cachorro si lo encuentra, o None si no hay coincidencia.
    """
    texto_limpio = texto.lower()

    for cachorro in cachorros:
        slug = cachorro['slug'].lower()
        nombre_pila = cachorro['nombre'].split()[0].lower()

        if slug in texto_limpio or nombre_pila in texto_limpio:
            return cachorro

    return None

# ==========================================
# 3. RENDERIZAR TEMPLATE
# ==========================================
def render_template(cachorro, nombre_cliente, path_template):
    """
    Toma el HTML maestro, evalúa bloques condicionales y reemplaza las variables.
    """
    with open(path_template, 'r', encoding='utf-8') as f:
        html = f.read()

    # 3.1 Evaluar bloque condicional del video
    if cachorro.get('video_personalidad_url'):
        html = re.sub(r'\{\{#if video_personalidad_url\}\}(.*?)\{\{/if\}\}', r'\1', html, flags=re.DOTALL)
    else:
        html = re.sub(r'\{\{#if video_personalidad_url\}\}.*?\{\{/if\}\}', '', html, flags=re.DOTALL)

    # 3.2 Reemplazar variables del cliente
    html = html.replace('{{nombre_cliente}}', nombre_cliente)

    # 3.3 Reemplazar variables del cachorro
    for key, value in cachorro.items():
        if value is not None:
            html = html.replace(f'{{{{{key}}}}}', str(value))

    return html

# ==========================================
# 4. ORQUESTADOR PRINCIPAL
# ==========================================
def generar_respuesta_html(asunto, cuerpo, remitente_nombre):
    """
    Lee correo -> Detecta cachorro -> Renderiza HTML.
    """
    print(f"--- Procesando correo de: {remitente_nombre} ---")

    texto_completo = f"{asunto} {cuerpo}"
    cachorros_db = cargar_cachorros('cachorros.json')
    cachorro_detectado = detectar_cachorro(texto_completo, cachorros_db)

    if cachorro_detectado:
        print(f"[EXITO] Cachorro detectado: {cachorro_detectado['nombre']}")
        html_final = render_template(cachorro_detectado, remitente_nombre, 'template-maestro.html')
        return html_final
    else:
        print("[AVISO] No se detectó un cachorro específico. Entrando a flujo general.")
        return "<p>Hola, gracias por contactar a Xolos Ramírez. Por favor indícanos qué cachorro te interesa.</p>"

# ==========================================
# 5. CASO DE PRUEBA
# ==========================================
if __name__ == "__main__":
    asunto = "Información de cachorro"
    cuerpo = "Hola, me interesa saber más sobre Ozomatli. ¿Sigue disponible?"
    remitente = "Iván"

    html_salida = generar_respuesta_html(asunto, cuerpo, remitente)

    with open('output_ozomatli.html', 'w', encoding='utf-8') as f:
        f.write(html_salida)

    print("-> El archivo 'output_ozomatli.html' se ha generado exitosamente.")

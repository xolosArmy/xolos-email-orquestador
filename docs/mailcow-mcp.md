# Puente MCP para Mailcow

## Alcance de esta fase

El servidor `mailcow_mcp_server.py` publica únicamente cuatro herramientas:

- `listar_no_leidos`: consulta mensajes `UNSEEN` sin cambiar banderas.
- `buscar_correos`: busca por texto, remitente o asunto.
- `obtener_correo`: obtiene un mensaje por UID.
- `guardar_borrador`: agrega un mensaje a `Drafts` con la bandera `\\Draft`.

No existe herramienta MCP para enviar, borrar, mover, archivar o marcar correos como leídos. El SMTP del orquestador original no se expone. Mantener `XOLOS_MODO_AUTO=OFF` en el proceso tradicional.

## Seguridad

1. Las credenciales permanecen únicamente en el host que ejecuta el servidor.
2. La validación TLS está activa por defecto. No usar `XOLOS_IMAP_VERIFY_TLS=false` en producción.
3. Los adjuntos no se descargan ni se devuelven a ChatGPT.
4. El cuerpo se limita a 12,000 caracteres por defecto.
5. Todo correo se etiqueta como contenido no confiable para reducir el riesgo de prompt injection.
6. El endpoint MCP no debe publicarse sin autenticación. Preferir Secure MCP Tunnel. Como alternativa, colocar OAuth 2.1/OIDC y HTTPS delante del endpoint.
7. Crear una contraseña de aplicación o buzón dedicado si Mailcow lo permite; no reutilizar la contraseña administrativa.

## Instalación local

```bash
python3 -m venv .venv-mcp
source .venv-mcp/bin/activate
pip install -r requirements-mcp.txt
cp .env.mcp.example .env.mcp
chmod 600 .env.mcp
```

Editar `.env.mcp` con la contraseña real. No subir ese archivo al repositorio.

```bash
set -a
source .env.mcp
set +a
python mailcow_mcp_server.py
```

El transporte es Streamable HTTP y el endpoint predeterminado del SDK es:

```text
http://127.0.0.1:8000/mcp
```

## Validación antes de conectar ChatGPT

```bash
npx -y @modelcontextprotocol/inspector
```

Conectar el Inspector a `http://127.0.0.1:8000/mcp` y comprobar:

1. `listar_no_leidos` no cambia el estado del mensaje en Mailcow.
2. `obtener_correo` no descarga adjuntos.
3. `guardar_borrador` crea un borrador visible en el webmail.
4. No aparece ninguna herramienta de envío o borrado.
5. La conexión falla de forma cerrada cuando falta `XOLOS_IMAP_PASS`.

## Conexión con ChatGPT

ChatGPT no se conecta directamente a un servidor MCP local. La ruta recomendada es:

```text
ChatGPT Work / app personalizada
            |
            | MCP remoto autenticado
            v
Secure MCP Tunnel u OAuth + HTTPS
            |
            v
mailcow_mcp_server.py
            |
            | IMAPS 993
            v
Mailcow
```

La app personalizada se configura en ChatGPT desde el modo desarrollador, proporcionando el endpoint MCP y el mecanismo de autenticación. La disponibilidad depende del plan: la compatibilidad MCP completa está orientada a Business y Enterprise/Edu; Pro admite conexiones de lectura/obtención en modo desarrollador. Plus no ofrece actualmente la conexión de una app MCP personalizada.

## Siguiente fase autorizable

Después de probar lectura y borradores, se puede añadir OAuth/OIDC o Secure MCP Tunnel y desplegar el servicio. El envío SMTP debe continuar fuera del alcance hasta una autorización humana separada y una revisión de seguridad.

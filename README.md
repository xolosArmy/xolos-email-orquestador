# xolos-email-orquestador

## Nota operativa: diagnostico IMAP/SMTP

El orquestador usa estos defaults si faltan variables de entorno: `XOLOS_IMAP_SERVER=mail.xolosramirez.com`, `XOLOS_IMAP_PORT=993`, `XOLOS_IMAP_USER=fernando@xolosramirez.com`, `XOLOS_SMTP_SERVER` cae al mismo valor de `XOLOS_IMAP_SERVER` y `XOLOS_SMTP_PORT=587`. Al iniciar cada ciclo, el log indica si cada valor vino de entorno o de fallback/default.

Checklist antes de validar credenciales:

- Confirmar `XOLOS_IMAP_SERVER`.
- Confirmar `XOLOS_SMTP_SERVER`.
- Confirmar que los puertos IMAP/SMTP sean los correctos para el proveedor.
- Probar conectividad TCP con `nc -vz host puerto` para IMAP y SMTP.
- Revisar firewall saliente desde el host donde corre el cron.
- Revisar que el proveedor realmente use ese hostname para IMAP/SMTP.

Si DNS resuelve pero `nc -vz` expira, primero corregir firewall, proveedor o hostname. Hasta que TCP conecte, las credenciales no pueden validarse; el siguiente fallo esperado deberia pasar a login/autenticacion o el ciclo deberia continuar correctamente.


import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    ALERT_EMAIL_PRIMARY,
    ALERT_EMAIL_RECOVERY,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SERVER,
    SMTP_USER,
)


def _enviar_smtp(destinatarios: list[str], asunto: str, cuerpo_html: str) -> tuple[bool, str]:
    if not SMTP_USER or not SMTP_PASSWORD:
        return False, "Faltan SMTP_USER o SMTP_PASSWORD en las variables de entorno de Vercel."

    lista_limpia = list(dict.fromkeys([c.strip() for c in destinatarios if c and c.strip()]))
    if not lista_limpia:
        return False, "No hay correos destinatarios válidos."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = f"Vigía Sabana Centro <{SMTP_USER}>"
    msg["To"] = ", ".join(lista_limpia)
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=12) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, lista_limpia, msg.as_string())
        print(f"✅ Correo enviado a: {lista_limpia}")
        return True, "OK"
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error SMTP: {error_msg}")
        return False, error_msg


def despachar_alerta_incidente(datos: dict):
    destinatarios = [ALERT_EMAIL_PRIMARY, ALERT_EMAIL_RECOVERY]
    es_panico = "pánico" in datos.get("modalidad", "").lower() or "panico" in datos.get("modalidad", "").lower()
    asunto = (
        f"🚨 ALERTA DE PÁNICO - Vigía Sabana Centro ({datos.get('categoria', '')})"
        if es_panico
        else f"🛡️ Nuevo Reporte: {datos.get('modalidad', '')} - Vigía Sabana Centro"
    )

    cuerpo_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden;">
        <div style="background-color: {'#dc2626' if es_panico else '#1e3a8a'}; color: white; padding: 16px;">
            <h2 style="margin: 0;">{'🚨 ALERTA DE PÁNICO ACTIVADA' if es_panico else '🛡️ Reporte Georreferenciado PostGIS'}</h2>
        </div>
        <div style="padding: 20px; color: #1e293b;">
            <p><strong>Categoría:</strong> {datos.get('categoria', 'N/A')}</p>
            <p><strong>Modalidad:</strong> {datos.get('modalidad', 'N/A')}</p>
            <p><strong>Fecha y Hora (UTC):</strong> {datos.get('fecha_hora', 'N/A')}</p>
            <p><strong>Coordenadas:</strong> {datos.get('lat')}, {datos.get('lng')}</p>
            <p><strong>Descripción:</strong> {datos.get('descripcion') or 'Sin detalles adicionales'}</p>
            <p style="margin-top: 16px;">
                <a href="https://www.google.com/maps?q={datos.get('lat')},{datos.get('lng')}"
                   style="background-color: #2563eb; color: white; padding: 10px 16px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                   📍 Ver ubicación en Google Maps
                </a>
            </p>
        </div>
    </div>
    """
    return _enviar_smtp(destinatarios, asunto, cuerpo_html)


def enviar_correo_recuperacion(nombre: str, email_usuario: str, enlace: str, token: str) -> tuple[bool, str]:
    destinatarios = [email_usuario, ALERT_EMAIL_RECOVERY]
    asunto = "🔑 Recuperación de Contraseña - Vigía Sabana Centro"

    cuerpo_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden;">
        <div style="background-color: #1e3a8a; color: white; padding: 16px;">
            <h2 style="margin: 0;">🔑 Recuperación de Cuenta</h2>
        </div>
        <div style="padding: 20px; color: #1e293b;">
            <p>Hola <strong>{nombre}</strong>,</p>
            <p>Se solicitó un restablecimiento de contraseña para tu cuenta (<strong>{email_usuario}</strong>) en <strong>Vigía Sabana Centro</strong>.</p>
            <p><strong>Token de seguridad:</strong> <code style="background:#f1f5f9; padding:4px 8px; border-radius:4px;">{token}</code></p>
            <p style="margin-top: 16px;">
                <a href="{enlace}"
                   style="background-color: #1e3a8a; color: white; padding: 10px 16px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                   Restablecer Contraseña
                </a>
            </p>
            <p style="font-size: 12px; color: #64748b; margin-top: 16px;">Este enlace expira en 1 hora. También se envió copia al correo de recuperación institucional.</p>
        </div>
    </div>
    """
    return _enviar_smtp(destinatarios, asunto, cuerpo_html)

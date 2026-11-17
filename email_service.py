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


def despachar_alerta_incidente(datos: dict):
    if not SMTP_USER or not SMTP_PASSWORD:
        print(" SMTP_USER o SMTP_PASSWORD no configurados en Vercel.")
        return False

    destinatarios = [
        correo.strip()
        for correo in [ALERT_EMAIL_PRIMARY, ALERT_EMAIL_RECOVERY]
        if correo and correo.strip()
    ]
    if not destinatarios:
        print("No hay destinatarios configurados (ALERT_EMAIL_PRIMARY / ALERT_EMAIL_RECOVERY).")
        return False

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
                    Ver ubicación en Google Maps
                </a>
            </p>
        </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = f"Vigía Sabana Centro <{SMTP_USER}>"
    msg["To"] = ", ".join(destinatarios)
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, destinatarios, msg.as_string())
        print(f" Correo enviado correctamente a: {destinatarios}")
        return True
    except Exception as e:
        print(f" Error enviando correo SMTP: {e}")
        return False

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import (
    SMTP_SERVER,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    ALERT_EMAIL_PRIMARY,
    ALERT_EMAIL_RECOVERY,
)


def despachar_alerta_incidente(payload: dict) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        print("SMTP no configurado; omitiendo envío de correo.")
        return False

    destinatarios = [
        correo.strip()
        for correo in [ALERT_EMAIL_PRIMARY, ALERT_EMAIL_RECOVERY]
        if correo and correo.strip()
    ]
    if not destinatarios:
        return False

    asunto = f"[ALERTA VIGÍA SABANA] {payload.get('categoria', 'Incidente')} - {payload.get('modalidad', '')}"
    cuerpo = (
        f"Se ha registrado una nueva alerta en Vigía Sabana Centro.\n\n"
        f"Categoría: {payload.get('categoria')}\n"
        f"Modalidad: {payload.get('modalidad')}\n"
        f"Fecha/Hora: {payload.get('fecha_hora')}\n"
        f"Coordenadas: {payload.get('lat')}, {payload.get('lng')}\n"
        f"Descripción: {payload.get('descripcion') or 'Sin descripción adicional'}\n"
        f"Mapa: https://www.google.com/maps?q={payload.get('lat')},{payload.get('lng')}\n"
    )

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, destinatarios, msg.as_string())
        return True
    except Exception as exc:
        print(f"Error enviando alerta SMTP: {exc}")
        return False

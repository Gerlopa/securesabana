import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings
from database import SessionLocal, PersonaDB

def _enviar_smtp(destinatario: str, asunto: str, cuerpo_html: str):
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f" SMTP no configurado. Simulación de envío a {destinatario}: {asunto}")
        return

    server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
    server.starttls()
    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_USER
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo_html, "html"))

    server.sendmail(settings.SMTP_USER, destinatario, msg.as_string())
    server.quit()

def despachar_alerta_incidente(datos: dict):
    """
    1. Envía alerta al correo principal (ALERT_EMAIL_PRIMARY).
    2. Reenvía copia con etiqueta de respaldo al correo de recuperación (ALERT_EMAIL_RECOVERY).
    3. Notifica a los comerciantes registrados en 'personas' con recibe_alertas = True.
    """
    es_panico = datos.get("es_panico", False)
    titulo = "🚨 ALERTA DE PÁNICO COMERCIAL" if es_panico else "📢 NUEVO REPORTE DE INCIDENTE"
    asunto_base = f"{titulo} - {datos['modalidad']} ({datos['categoria']})"

    cuerpo_html = f"""
    <div style="font-family: Arial, sans-serif; border: 2px solid {'#dc2626' if es_panico else '#1e3a8a'}; border-radius: 8px; padding: 18px;">
        <h2 style="color: {'#dc2626' if es_panico else '#1e3a8a'}; margin-top: 0;">{titulo}</h2>
        <p><strong>ID Incidente:</strong> #{datos['id']}</p>
        <p><strong>Modalidad:</strong> {datos['modalidad']}</p>
        <p><strong>Categoría / Comercio:</strong> {datos['categoria']}</p>
        <p><strong>Fecha y Hora:</strong> {datos['fecha_hora']}</p>
        <p><strong>Descripción:</strong> {datos['descripcion']}</p>
        <p><strong>Coordenadas PostGIS (SRID 4326):</strong> {datos['lat']}, {datos['lng']}</p>
        <p><a href="https://www.google.com/maps?q={datos['lat']},{datos['lng']}" style="background:#1e3a8a;color:#fff;padding:8px 14px;text-decoration:none;border-radius:5px;">Ver ubicación exacta en Mapa</a></p>
    </div>
    """

    try:
        # 1. Correo Principal
        if settings.ALERT_EMAIL_PRIMARY:
            _enviar_smtp(settings.ALERT_EMAIL_PRIMARY, asunto_base, cuerpo_html)

        # 2. Reenvío automático al Correo de Recuperación / Respaldo
        if settings.ALERT_EMAIL_RECOVERY:
            _enviar_smtp(
                settings.ALERT_EMAIL_RECOVERY,
                f"[REENVÍO RECUPERACIÓN] {asunto_base}",
                cuerpo_html
            )

        # 3. Difusión a personas suscritas en la BD (recibe_alertas = True)
        db = SessionLocal()
        try:
            suscritos = db.query(PersonaDB).filter(PersonaDB.recibe_alertas == True).all()
            for p in suscritos:
                if p.email and p.email not in [settings.ALERT_EMAIL_PRIMARY, settings.ALERT_EMAIL_RECOVERY]:
                    _enviar_smtp(p.email, asunto_base, cuerpo_html)
        finally:
            db.close()

    except Exception as e:
        print(f" Error en el servicio de correo: {e}")

def enviar_correo_recuperacion(email_destino: str, nombre: str, token: str):
    """
    Envía el enlace de recuperación de cuenta y reenvía copia de auditoría al correo de recuperación.
    """
    enlace = f"{settings.APP_BASE_URL}/?token_recuperacion={token}"
    asunto = "🔐 Recuperación de Acceso - Vigía Sabana Centro"
    cuerpo = f"""
    <div style="font-family: Arial, sans-serif; padding: 18px; border: 1px solid #cbd5e1; border-radius: 8px;">
        <h3>Hola, {nombre}</h3>
        <p>Recibimos una solicitud para restablecer tu contraseña en <strong>Vigía Sabana Centro</strong>.</p>
        <p>Tu código/token de recuperación (válido por 30 minutos) es:</p>
        <p style="font-size: 18px; font-weight: bold; background: #f1f5f9; padding: 10px; border-radius: 6px;">{token}</p>
        <p>O ingresa directamente aquí: <a href="{enlace}">{enlace}</a></p>
    </div>
    """
    try:
        _enviar_smtp(email_destino, asunto, cuerpo)
        if settings.ALERT_EMAIL_RECOVERY:
            _enviar_smtp(
                settings.ALERT_EMAIL_RECOVERY,
                f"[REENVÍO AUDITORÍA RECUPERACIÓN] Usuario: {email_destino}",
                cuerpo
            )
    except Exception as e:
        print(f" Error enviando correo de recuperación: {e}")
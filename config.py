import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    ALERT_EMAIL_PRIMARY: str = os.getenv("ALERT_EMAIL_PRIMARY", "")
    ALERT_EMAIL_RECOVERY: str = os.getenv("ALERT_EMAIL_RECOVERY", "")
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")

settings = Settings()

if not settings.DATABASE_URL:
    raise ValueError(" ERROR: Debes definir DATABASE_URL en el archivo .env")
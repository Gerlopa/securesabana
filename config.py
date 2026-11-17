import os
from dotenv import load_dotenv

load_dotenv()

raw_db_url = os.getenv("DATABASE_URL", "")
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

DATABASE_URL = raw_db_url
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_PRIMARY = os.getenv("ALERT_EMAIL_PRIMARY", "")
ALERT_EMAIL_RECOVERY = os.getenv("ALERT_EMAIL_RECOVERY", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://securesabana.vercel.app")

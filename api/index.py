import os
import sys

# Agrega la carpeta raíz al path para que encuentre app.py, config.py, database.py y email_service.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

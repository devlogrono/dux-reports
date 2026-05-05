import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret")

    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    WTF_CSRF_ENABLED = True
    BCRYPT_LOG_ROUNDS = 13

    # Cookies de sesión: cada navegador/pestaña mantiene su propia sesión aislada
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Activar SECURE solo en producción (HTTPS). Leer desde variable de entorno.
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    # Expiración de la sesión: 8 horas de inactividad
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

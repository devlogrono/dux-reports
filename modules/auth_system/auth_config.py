import streamlit as st

# =================================
# 🔐 FUNCIÓN SEGURA PARA LEER SECRETOS
# =================================

def get_secret(path: str, key: str, default=None):
    """
    Permite leer st.secrets[path][key] sin lanzar errores cuando
    no existe secrets.toml (como en GitHub Actions durante CI).
    """
    try:
        return st.secrets[path].get(key, default)
    except Exception:
        return default


# ============================
# 🔐 CONFIGURACIÓN DE SEGURIDAD
# ============================

# --- JWT ---
JWT_SECRET = get_secret("auth", "jwt_secret", "dev_jwt_secret")
JWT_ALGORITHM = get_secret("auth", "algorithm", "HS256")
JWT_EXP_SECONDS = int(get_secret("auth", "token_expiration", 8 * 3600))  # 8h por defecto

# --- COOKIES ---
COOKIE_SECRET = get_secret("auth", "cookie_secret", "dev_cookie_secret")
COOKIE_NAME = get_secret("auth", "cookie_name", "dev_cookie")
COOKIE_EXP_DAYS = int(get_secret("auth", "cookie_expiration_days", 1))
APP_NAME = get_secret("auth", "app_name", "reports")

# --- SERVER CONFIG ---
COMPONENT_DOMAIN = get_secret("server", "component_domain", "localhost")
SERVER_ENV = get_secret("server", "component_enviroment", "development")

from datetime import datetime, timezone, timedelta
import uuid
import bcrypt
import jwt
import streamlit as st

from modules.auth_system import auth_config
from .cookie_manager import cookie_set, cookie_get, cookie_delete

# ======================================================
# Helpers internos de estado
# ======================================================

def _auth_default_state():
    return {
        "is_logged_in": False,
        "username": "",
        "name": "",
        "rol": "",
        "token": "",
        "session_id": "",
    }


def ensure_state():
    if "auth" not in st.session_state:
        st.session_state["auth"] = _auth_default_state()


def init_app_state():
    ensure_state()

# ======================================================
# JWT
# ======================================================

def create_jwt(name, username, rol, session_id=None):
    if session_id is None:
        session_id = uuid.uuid4().hex

    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=auth_config.JWT_EXP_SECONDS)

    payload = {
        "user": username,
        "name": name,
        "rol": rol,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    return jwt.encode(payload, auth_config.JWT_SECRET, algorithm=auth_config.JWT_ALGORITHM)


def decode_jwt(token):
    try:
        return jwt.decode(token, auth_config.JWT_SECRET, algorithms=[auth_config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        st.warning("Tu sesión ha expirado. Vuelve a iniciar sesión.")
        return None
    except Exception:
        return None


# ======================================================
# BOOTSTRAP: Recuperar sesión desde cookie (doble ciclo)
# ======================================================

def bootstrap_auth_from_cookie():
    """
    Proceso en 2 ciclos para restaurar sesión desde cookie
    y manejar logout sin errores.
    """

    ensure_state()

    #st.text("Inicializando autenticación...")

    # =====================================================
    # (A) MANEJO DE LOGOUT EN 2 CICLOS - DEBE IR PRIMERO
    # =====================================================
    if st.session_state.get("_logout_pending"):

        #st.text("Logout pendiente, verificando cookie...")

        # Preguntar si la cookie sigue existiendo
        token = cookie_get(auth_config.COOKIE_NAME)
        #st.text(f"DEBUG logout → cookie_get devuelve: {token}")

        # CICLO 1 después del logout: el iframe aún no procesó el delete
        if token:
            #st.text("Cookie aún existe, esperando siguiente ciclo...")
            st.stop()

        # CICLO 2: cookie YA fue eliminada
        #st.text("Cookie eliminada. Limpiando sesión...")

        st.session_state["_logout_pending"] = False
        st.session_state["auth"] = _auth_default_state()
        st.session_state["_auth_bootstrap_done"] = True
        st.session_state["_auth_cookie_checked"] = False

        #st.text("Logout completado.")
        #return
        st.switch_page("app.py")

    # =====================================================
    # (B) FLUJO NORMAL DE BOOTSTRAP
    # =====================================================

    # Si ya se ejecutó bootstrap, no repetir
    if st.session_state.get("_auth_bootstrap_done"):
        #st.text("Bootstrap ya completado previamente.")
        return

    # Pedimos la cookie (primer ciclo devuelve None)
    cookie_token = cookie_get(auth_config.COOKIE_NAME)
    #st.text(f"DEBUG cookie_token: {cookie_token}, name: {auth_config.COOKIE_NAME}")

    # Primer ciclo: el componente aún no devolvió cookie
    if not cookie_token and not st.session_state.get("_auth_cookie_checked"):
        st.session_state["_auth_cookie_checked"] = True
        #st.text("Primer ciclo: esperando cookie del componente...")
        st.stop()

    # Segundo ciclo: ahora sí debería existir valor
    if isinstance(cookie_token, str) and cookie_token.strip():
        payload = decode_jwt(cookie_token)
        if payload:
            st.session_state["auth"].update({
                "is_logged_in": True,
                "username": payload["user"],
                "name": payload.get("name", ""),
                "rol": payload["rol"],
                "token": cookie_token,
                "session_id": payload["sid"],
            })
            #st.text("Sesión restaurada desde cookie")

    # Marcamos que ya hicimos bootstrap
    st.session_state["_auth_bootstrap_done"] = True
    #st.text("Bootstrap completado.")


# ======================================================
# get_current_user (YA SIN LEER COOKIES)
# ======================================================

def get_current_user():
    """
    SOLO usa session_state.
    El bootstrap ya restauró la sesión desde cookie si era necesario.
    """
    ensure_state()

    token = st.session_state["auth"].get("token")
    if not token:
        return None

    payload = decode_jwt(token)
    if not payload:
        logout()
        return None

    return payload


def validate_login():
    return get_current_user() is not None


# ======================================================
# Logout real
# ======================================================

def logout():
    ensure_state()

    # 1) Marcar que hay un logout en curso
    st.session_state["_logout_pending"] = True

    # 2) Pedir al componente que borre la cookie en el navegador
    cookie_delete(auth_config.COOKIE_NAME)

    # 3) Resetear flags de bootstrap para que pueda re-ejecutarse
    st.session_state["_auth_bootstrap_done"] = False
    st.session_state["_auth_cookie_checked"] = False

    # 4) Detener aquí este ciclo. El siguiente ciclo lo gestionará bootstrap_auth_from_cookie
    st.stop()



# ======================================================
# Login desde auth_ui
# ======================================================

def validate_access(password, user):
    """Valida contraseña, permisos y registra la sesión."""
    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        st.error("Credenciales incorrectas")
        return

    permisos = [p.strip() for p in user.get("permissions", "").split(",")]
    #st.text(f"DEBUG permisos del usuario: {permisos}")
    if auth_config.APP_NAME not in permisos:
        st.error("No tienes permiso para acceder a esta app")
        return

    name = f"{user.get('name','')}".strip() #{user.get('lastname','')}".strip()
    # Crear token
    token = create_jwt(name, user["email"], user["role_name"])
    payload = decode_jwt(token)

    # Registrar sesión en memoria + cookie
    st.session_state["auth"].update({
        "is_logged_in": True,
        "username": payload["user"],
        "name": name,
        "rol": payload["rol"],
        "token": token,
        "session_id": payload["sid"]
    })

    # Guardar cookie real del navegador
    cookie_set(auth_config.COOKIE_NAME, token, days=auth_config.COOKIE_EXP_DAYS)

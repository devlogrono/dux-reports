import pytest

# Mock Streamlit.session_state
class MockSessionState(dict):
    pass

class MockStreamlit:
    session_state = MockSessionState()

    def error(self, msg):
        self.last_error = msg

st = MockStreamlit()

# Importamos el módulo real y sustituimos st
import modules.auth_system.auth_core as auth_core
auth_core.st = st

def test_init_app_state():
    """
    ensure_state / init_app_state deben crear el diccionario auth completo.
    """
    st.session_state.clear()

    auth_core.init_app_state()

    assert "auth" in st.session_state
    auth = st.session_state["auth"]

    assert auth["is_logged_in"] is False
    assert auth["username"] == ""
    assert auth["token"] == ""
    assert "session_id" in auth


def test_validate_access_wrong_password(monkeypatch):
    """
    validate_access debe fallar si bcrypt.checkpw devuelve False.
    """

    st.session_state.clear()
    auth_core.init_app_state()

    # Mock bcrypt a siempre devolver False
    monkeypatch.setattr(auth_core.bcrypt, "checkpw", lambda pw, ph: False)

    user = {
        "email": "test@test.com",
        "name": "Test",
        "role_name": "Coach",
        "permissions": "template",
        "password_hash": "HASH"
    }

    auth_core.validate_access("badpass", user)

    assert st.session_state["auth"]["is_logged_in"] is False
    assert hasattr(st, "last_error")
    assert "incorrectas" in st.last_error.lower()


def test_validate_access_no_permission(monkeypatch):
    """
    validate_access debe fallar si el usuario no tiene permiso para esta app.
    """

    st.session_state.clear()
    auth_core.init_app_state()

    # Mock bcrypt para que la contraseña sea válida
    monkeypatch.setattr(auth_core.bcrypt, "checkpw", lambda pw, ph: True)

    # Usuario SIN permiso para esta app
    user = {
        "email": "test@test.com",
        "name": "Test",
        "role_name": "Coach",
        "permissions": "OtraApp",  # No incluye APP_NAME
        "password_hash": "HASH"
    }

    auth_core.validate_access("1234", user)

    assert st.session_state["auth"]["is_logged_in"] is False
    assert "permiso" in st.last_error.lower()


def test_validate_access_success(monkeypatch):
    """
    validate_access debe registrar sesión, crear token, actualizar auth.
    """

    st.session_state.clear()
    auth_core.init_app_state()

    # Hacemos que bcrypt siempre valide
    monkeypatch.setattr(auth_core.bcrypt, "checkpw", lambda pw, ph: True)

    # Mock de cookie_set para no depender del navegador
    monkeypatch.setattr(auth_core, "cookie_set", lambda *args, **kw: None)

    # Mock de JWT para un valor estable
    monkeypatch.setattr(auth_core, "create_jwt", lambda name, user, rol: "FAKE_TOKEN")
    monkeypatch.setattr(auth_core, "decode_jwt", lambda token: {
        "user": "admin@test.com",
        "name": "Admin",
        "rol": "Coach",
        "sid": "12345"
    })

    user = {
        "email": "admin@test.com",
        "name": "Admin",
        "role_name": "Coach",
        "permissions": auth_core.auth_config.APP_NAME,
        "password_hash": "HASH"
    }

    auth_core.validate_access("1234", user)

    auth = st.session_state["auth"]

    assert auth["is_logged_in"] is True
    assert auth["username"] == "admin@test.com"
    assert auth["rol"] == "Coach"
    assert auth["token"] == "FAKE_TOKEN"
    assert auth["session_id"] == "12345"

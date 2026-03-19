import streamlit as st
from modules.auth_system.auth_core import bootstrap_auth_from_cookie, init_app_state, validate_login
from modules.auth_system.auth_ui import login_view, menu
import uuid

def init_config():
    # Streamlit page config
    st.set_page_config(page_title="Dux Logroño - Template", page_icon="assets/images/logo_transparente.png", layout="wide")

    # Generar un ID único por navegador/pestaña
    if "client_session_id" not in st.session_state:
        st.session_state["client_session_id"] = uuid.uuid4().hex

    # ============================================================
    # 🔐 AUTENTICACIÓN
    # ============================================================
    init_app_state()
    bootstrap_auth_from_cookie()
    is_valid = validate_login()

    if not is_valid or not st.session_state["auth"]["is_logged_in"]:
        login_view()
        st.stop()

    menu()
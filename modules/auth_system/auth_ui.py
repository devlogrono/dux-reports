import streamlit as st
from modules.db.db_login import load_user_from_db
from modules.auth_system.auth_core import logout, validate_access
from modules.util.util import right_caption, set_background_image_local
from modules.i18n.i18n import t, language_selector

def login_view() -> None:
    """Renderiza el formulario de inicio de sesión."""

    set_background_image_local("assets/images/fondo.jpg")

    _, col2, _ = st.columns([2, 1.5, 2])
    with col2:
        st.markdown("""
            <style>
                [data-testid="stSidebar"], 
                [data-testid="stBaseButton-headerNoPadding"] { display: none !important; }
            </style>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.image("assets/images/banner.png")

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Usuario", value="")
            password = st.text_input("Contraseña", type="password", value="")
            submitted = st.form_submit_button("Iniciar sesión", type="primary")

        right_caption("Template")

        if submitted:
            user_data = load_user_from_db(username)
            if not user_data:
                st.error("Usuario no encontrado o inactivo.")
                return
            validate_access(password, user_data)
        

def menu():
    if not st.session_state["auth"].get("is_logged_in", False):
        return  # no mostrar menú si no hay sesión
    
    with st.sidebar:
        st.logo("assets/images/banner.png", size="large")
        lang = language_selector()
        #st.session_state["lang"] = lang
        st.subheader(f'Rol: {st.session_state["auth"]["rol"].capitalize()} :material/admin_panel_settings:')
        st.write(f"{t('Hola')} **:blue-background[{st.session_state['auth']['name'].capitalize()}]** ")

        st.page_link("app.py", label=t("Inicio"), icon=":material/home:")
        st.subheader(t("Modo :material/dashboard:"))
        st.page_link("pages/registro.py", label=t("Registro"), icon=":material/article_person:")
        st.subheader(t("Análisis y Estadísticas :material/query_stats:"))
        st.page_link("pages/individual.py", label=t("Individual"), icon=":material/accessible_menu:")
        st.page_link("pages/grupal.py", label=t("Grupal"), icon=":material/groups:")

        if st.session_state["auth"]["rol"].lower() in ["admin", "developer"]:
            st.subheader(t("Administración :material/settings:"))
            st.page_link("pages/admin.py", label=t("Registros"), icon=":material/docs:")
        if st.session_state["auth"]["rol"].lower() in ["developer"]:
            st.page_link("pages/developer.py", label=t("Developer"), icon=":material/user_attributes:")

        if st.session_state["auth"]["rol"].lower() in ["developer"]:
            if st.button(t("Limpiar cache & reiniciar"), type="tertiary", icon=":material/refresh:"):
                    st.cache_data.clear()
                    st.cache_resource.clear()

                    st.success("Cache cleared successfully.")
                    st.rerun()
                    
        if st.button(t("Cerrar Sesión"), type="tertiary", icon=":material/logout:"):
            logout()
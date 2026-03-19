import time
import streamlit as st
from modules.db.db_records import search_existing_record, upsert_record_db
from modules.schema import new_base_record
from modules.ui.check_in_ui import checkin_form
from modules.ui.check_out_ui import checkout_form
from modules.i18n.i18n import t
from modules.ui.ui_components import preview_record

# ===============================
# 🔸 Diálogo de confirmación de registro
# ===============================
@st.dialog(t("Confirmar registro"), width="small")
def dialog_confirmar_registro(record, jugadora, tipo):
    nombre = jugadora["nombre_jugadora"]
    modo = t("Check-in") if tipo == "Check-in" else t("Check-out")

    st.warning(
        f"{t('¿Desea confirmar el registro de')} **{modo}** "
        f"{t('para la jugadora')} **{nombre}**?"
    )

    _, col2, col3 = st.columns([1.6, 1, 1])

    with col2:
        if st.button(t(":material/cancel: Cancelar")):
            st.rerun()

    with col3:
        if st.button(t(":material/check: Confirmar"), type="primary"):
            modo_db = "checkin" if tipo == "Check-in" else "checkout"
            success = upsert_record_db(record, modo_db)

            if success:
                st.session_state["submitted"] = True
                st.session_state[f"redirect_{st.session_state['client_session_id']}"] = True
            else:
                st.session_state["save_error"] = True

            st.rerun()

def template_form(jugadora, tipo, turno):
    """
    Lógica completa y segura para crear, validar y guardar template/RPE.
    Versión corregida para evitar reruns globales y conflictos entre usuarios.
    """

    # ---------------------------------------
    # 1. Validación inicial
    # ---------------------------------------
    if not jugadora:
        st.info(t("Selecciona una jugadora para continuar."))
        return
    
    # ---------------------------------------
    # 2. Crear record base
    # ---------------------------------------
    record = new_base_record(
        id_jugadora=str(jugadora["id_jugadora"]),
        username=st.session_state["auth"]["name"].lower(),
        tipo="checkin" if tipo == "Check-in" else "checkout",
    )
    #preview_record(record)
    record["turno"] = turno or ""

    # ID seguro por navegador
    session_id = st.session_state["client_session_id"]
    redirect_key = f"redirect_{session_id}"

    # ---------------------------------------
    # ---------------------------------------
    form_key = f"form_template_{session_id}"

    #with st.form(key=form_key, border=False):

    # ---- Check-in ----
    if tipo == "Check-in":
        record, is_valid, validation_msg = checkin_form(record, jugadora["genero"])

    # ---- Check-out ----
    else:
        record, is_valid, validation_msg = checkout_form(record)

        # ---- Botón seguro ----
        #submitted = st.form_submit_button(t("Guardar"))

    # ---------------------------------------
    # 5. Procesamiento del guardado
    # ---------------------------------------
    #st.dataframe(jugadora)
    if st.button(f":material/save: {t('Guardar')}", key="btn_reg_template", disabled=not is_valid):
        dialog_confirmar_registro(record, jugadora, tipo)
        #preview_record(record)

    # ---------------------------------------
    # 6. Vista de previsualización (solo developers)
    # ---------------------------------------
    if st.session_state["auth"]["rol"].lower() == "developer":
        st.divider()
        if st.checkbox(t("Previsualización")):
            preview_record(record)

    if st.session_state.pop("save_error", False):
        st.error(t("Error al guardar el registro."))

    if st.session_state.get("submitted"):
        st.success(t("Registro guardado correctamente."))

    # ---------------------------------------
    # 7. Redirección segura SOLO para este navegador
    # ---------------------------------------
    if st.session_state.get(redirect_key):
        del st.session_state[redirect_key]
        st.session_state["target_page"] = "registro"
        time.sleep(2)  # Pequeña pausa para evitar conflictos
        st.switch_page("pages/switch.py")
        #st.rerun()
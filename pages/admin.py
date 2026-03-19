import streamlit as st
import modules.app_config.config as config
config.init_config()

from modules.db.db_absences import load_active_absences_db
from modules.db.db_catalogs import load_catalog_list_db
from modules.ui.ui_components import selection_header, filtrar_registros
from modules.i18n.i18n import t
from modules.ui.absents_ui import absents_summary
from modules.db.db_competitions import load_competitions_db
from modules.db.db_players import load_players_db
from modules.db.db_records import delete_record, get_records_db

if st.session_state["auth"]["rol"].lower() not in ["admin", "developer"]:
    st.switch_page("app.py")
    
st.header(t("Administrador de :red[registros]"), divider="red")

# Load reference data
jug_df = load_players_db()
comp_df = load_competitions_db()
template_df = get_records_db()
tipo_ausencia_df = load_catalog_list_db("tipo_ausencia", as_df=True)
ausencias_df = load_active_absences_db(activas=False)
#st.dataframe(template_df)

@st.dialog(t("Eliminar registros filtrados"), width="small")
def dialog_eliminar_todos_filtrados(ids_todos):
    st.error(
        t("Esta acción eliminará TODOS los registros mostrados en la tabla.")
    )

    st.write(
        t("Para confirmar, escriba la palabra") + " **eliminar**"
    )

    confirm_text = st.text_input(
        t("Confirmación"),
        placeholder="eliminar"
    )

    _, col2, col3 = st.columns([1.8, 1, 1])

    with col2:
        if st.button(t(":material/cancel: Cancelar")):
            st.rerun()

    with col3:
        if confirm_text.strip().lower() == "eliminar":
            if st.button(
                t(":material/delete: Eliminar todos"),
                type="primary"
            ):
                deleted_by = st.session_state["auth"]["name"].lower()
                exito, mensaje = delete_record(ids_todos, deleted_by)

                if exito:
                    st.session_state["reload_flag"] = True
                    st.session_state["admin_delete_all"] = True
                else:
                    st.session_state["save_error"] = mensaje

                st.rerun()
        else:
            st.button(
                t(":material/delete: Eliminar todos"),
                disabled=True
            )


# ===============================
# 🔸 Diálogo de confirmación
# ===============================
@st.dialog(t("Confirmar"), width="small")
def dialog_eliminar():
    st.warning(f"¿{t('Está seguro de eliminar')} {len(ids_seleccionados)} {t('elemento')}(s)?")

    _, col2, col3 = st.columns([1.8, 1, 1])
    with col2:
        if st.button(t(":material/cancel: Cancelar")):
            st.rerun()
    with col3:
        if st.button(t(":material/delete: Eliminar"), type="primary"):
            deleted_by = st.session_state["auth"]["name"].lower()
            exito, mensaje = delete_record(ids_seleccionados, deleted_by)

            if exito:
                # Marcar para recarga
                st.session_state["reload_flag"] = True

            st.rerun()


records, jugadora, tipo, turno, start, end = selection_header(jug_df, comp_df, template_df, modo="reporte")

if records.empty:
    st.error(t("No se encontraron registros"))
    st.stop()

tab1, tab2 = st.tabs([ "template :material/check_in_out:", "Ausencias :material/event_busy:"])

with tab1:

    disabled = records.columns.tolist()

    columna = t("seleccionar")

    # --- Agregar columna de selección si no existe ---
    if columna not in records.columns:
        records.insert(0, columna, False)

    #records_vista = records.drop("id", axis=1)

    df_edited = st.data_editor(records, 
            column_config={
                columna: st.column_config.CheckboxColumn(columna, default=False)},   
            num_rows="fixed", hide_index=True, disabled=disabled)

    ids_seleccionados = df_edited.loc[df_edited[columna], "id"].tolist()

    if st.session_state["auth"]["rol"].lower() in ["developer"]:
        st.write(t("Registros seleccionados:"), ids_seleccionados)

    #st.dataframe(records, hide_index=True)
    # save_if_modified(records, df_edited)
    csv_data = records.to_csv(index=False).encode("utf-8")

    exito, mensaje = False, ""
    

    if st.session_state.get("reload_flag") and exito:     
        st.success(mensaje)
        st.session_state["reload_flag"] = False

    col1, col2, col3, col4, _ = st.columns([1.6, 1.8, 2, 1, 1])
    with col1:
        # --- Botón principal para abrir el diálogo ---
        if st.button(t(":material/delete: Eliminar seleccionados"), disabled=len(ids_seleccionados) == 0):
            dialog_eliminar()
    with col2:
        st.download_button(
                label=t(":material/download: Descargar registros en CSV"),
                data=csv_data, file_name="registros_template.csv", mime="text/csv")

    if st.session_state["auth"]["rol"].lower() in ["developer"]:
        with col3:
                # Convertir a JSON (texto legible, sin índices)
                json_data = records.to_json(orient="records", force_ascii=False, indent=2)
                json_bytes = json_data.encode("utf-8")

                # Botón de descarga
                st.download_button(
                    label=t(":material/download: Descargar registros en JSON"),
                    data=json_bytes, file_name="registros_template.json", mime="application/json"
                )
        with col4:
            if st.button(
                t(":material/delete_forever: Eliminar Todos los registros"),
                disabled=records.empty):
                dialog_eliminar_todos_filtrados(records["id"].tolist())

with tab2:

    ausencias_df_filtrado = filtrar_registros(
        ausencias_df,
        jugadora_opt=jugadora,
        turno=turno,
        modo="ausencias",
        tipo=tipo,
        start=start,
        end=end,
    )

    if ausencias_df_filtrado.empty:
        st.error(t("No se encontraron registros"))
        st.stop()
        
    absents_summary(ausencias_df_filtrado)

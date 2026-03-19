
import streamlit as st
import datetime
import time
from modules.db.db_absences import delete_absences, insert_absence
from modules.i18n.i18n import t

def get_checkins(records_df, fecha):
    """Devuelve array de id_jugadora con CHECK-IN en la fecha y turno indicados."""
    return records_df[
        (records_df["tipo"].str.lower() == "checkin") &
        (records_df["fecha_sesion"] == fecha)
    ]["id_jugadora"].unique()

def get_checkouts(records_df, fecha):
    """Devuelve array de id_jugadora con CHECK-OUT en la fecha y turno indicados."""
    return records_df[
        (records_df["tipo"].str.lower() == "checkout") &
        (records_df["fecha_sesion"] == fecha)
    ]["id_jugadora"].unique()

def filtrar_jugadoras_ausentes(jug_df, ausencias_df):

    # Jugadoras del plantel seleccionado
    #jugadoras_plantel = jug_df[jug_df["plantel"] == codigo_plantel]

    # Si no hay ausencias → retornar todas las jugadoras del plantel
    if ausencias_df is None or ausencias_df.empty or "id_jugadora" not in ausencias_df.columns:
        return jug_df

    # Lista de jugadoras ausentes hoy
    ausentes_hoy = ausencias_df["id_jugadora"].unique()

    # Jugadoras disponibles (no ausentes)
    disponibles = jug_df[
        ~jug_df["id_jugadora"].isin(ausentes_hoy)
    ]

    return disponibles

def filtrar_jugadoras_disponibles(jug_df, ausencias_df, template_df):

    hoy = datetime.date.today()

    # Listas de jugadoras que han registrado algo hoy
    checkins = get_checkins(template_df, hoy)
    checkouts = get_checkouts(template_df, hoy)

    jugadoras_con_registro = set(checkins) | set(checkouts)   # unión de ambas
    #st.text(f"Jugadoras con registro hoy: {hoy}")
    #st.dataframe(jugadoras_con_registro)
    # Si no hay ausencias → retornar jugadoras sin registros
    if ausencias_df is None or ausencias_df.empty:
        # devolvemos solo las jugadoras que NO tienen ningún registro
        return jug_df[
            ~jug_df["id_jugadora"].isin(jugadoras_con_registro)
        ]

    # Jugadoras marcadas como ausentes en la base
    ausentes_hoy = set(ausencias_df["id_jugadora"].unique())

    # 🔥 CORRECCIÓN CRÍTICA:
    # Jugadoras con registro NO pueden ser ausentes
    ausentes_filtrados = ausentes_hoy - jugadoras_con_registro

    # Jugadoras disponibles = todas menos las ausentes REALES
    disponibles = jug_df[
        ~jug_df["id_jugadora"].isin(ausentes_filtrados)
    ]

    # Ahora filtramos las que YA hicieron ambos check-ins/check-outs (no deben aparecer)
    disponibles_sin_registro_hoy = disponibles[
        ~disponibles["id_jugadora"].isin(jugadoras_con_registro)
    ]

    return disponibles_sin_registro_hoy

@st.fragment
def checkout_inputs(comp_df, jug_df, tipo_ausencia_df, ausencias_df, template_df):

    # --- Fila principal de filtros ---
    col1, col2, col3 = st.columns([1.5, 1.5, 1])
    #st.dataframe(jug_df)
    with col1:
        competiciones_options = comp_df.to_dict("records")
        competicion = st.selectbox(
            t("Plantel"),
            options=competiciones_options,
            format_func=lambda x: f'{x["nombre"]} ({x["codigo"]})',
            index=3,
            key="aus_competicion",
        )

    with col2:
        jugadora_opt = None
        if not jug_df.empty:

            codigo_comp = competicion["codigo"]

            jugadoras_disponibles_df = filtrar_jugadoras_disponibles(jug_df, ausencias_df, template_df)
            
            
            jug_df_filtrado = jugadoras_disponibles_df[jugadoras_disponibles_df["plantel"] == codigo_comp]
            jugadoras_options = jug_df_filtrado.to_dict("records")

            jugadora_opt = st.selectbox(
                t("Jugadora"),
                options=jugadoras_options,
                format_func=lambda x: x["nombre_jugadora"] if isinstance(x, dict) else "",
                index=None,
                placeholder=t("Seleccione una Jugadora"),
                key="aus_jugadora",
            )

    with col3:
        turno = st.selectbox(
            "Turno (opcional)",
            ["Todos", "Turno 1", "Turno 2", "Turno 3"],
            key="aus_turno",
        )

    with col1:
        fecha_inicio = st.date_input(
            "Fecha inicio",
            datetime.date.today(),
            key="aus_fecha_inicio"
        )

    with col2:
        fecha_fin = st.date_input(
            "Fecha fin",
            datetime.date.today(),
            key="aus_fecha_fin"
        )

    with col3:
        # --- Motivo y observaciones ---
        motivo_options = tipo_ausencia_df.to_dict("records")

        motivo_opt = st.selectbox(
            "Motivo de ausencia",
            options=motivo_options,
            format_func=lambda x: x["nombre"],
            key="aus_motivo"
        )

    observacion = st.text_area(
        "Observaciones (opcional)",
        key="aus_observacion"
    )

    error = False

    # 1. Validación de fechas
    if fecha_fin < fecha_inicio:
        st.error(f":material/error: {t('La fecha final no puede ser menor que la fecha inicial.')}")
        error = True

    # 2. Validación de jugadora seleccionada
    if jugadora_opt is None:
        st.error(f":material/error: {t('Selecciona una jugadora para continuar.')}")
        error = True

    if motivo_opt is None:
        st.error(f":material/error: {t('Selecciona un motivo de ausencia para continuar.')}")
        error = True

    # --- Botón de guardar ---
    if st.button(f":material/save: {t('Registrar ausencia')}", key="btn_reg_ausencia", disabled=error):

        # Obtener id_jugadora real si jugadoras_list tiene nombres
        # Ajusta esto si usas un DataFrame
        id_jugadora = jugadora_opt["id_jugadora"]

        # Obtener motivo_id dependiendo de tu estructura
        motivo_id = motivo_opt["id"]

        result = insert_absence(
            id_jugadora=id_jugadora,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            motivo_id=motivo_id,
            turno=turno, #None if turno == "Todos" else 
            observacion=observacion
        )

        if result:
            st.success(t(":material/done_all: Registro guardado/actualizado correctamente."))
            time.sleep(4)
            st.rerun()

def absents_form(comp_df, jug_df, tipo_ausencia_df, ausencias_df, template_df):
    checkout_inputs(comp_df, jug_df, tipo_ausencia_df, ausencias_df, template_df)

def absents_summary(records):
    #st.markdown(":material/event_busy: Ausencias registradas")
    disabled = records.columns.tolist()

    columna = t("seleccionar")

    # --- Agregar columna de selección si no existe ---
    if columna not in records.columns:
        records.insert(0, columna, False)

    #records_vista = records.drop("id", axis=1)

    df_edited = st.data_editor(records, 
            column_config={
                columna: st.column_config.CheckboxColumn(columna, default=False)},   
            num_rows="fixed", hide_index=True, disabled=disabled, key="aus_summary")

    ids_seleccionados = df_edited.loc[df_edited[columna], "id"].tolist()

    if st.session_state["auth"]["rol"].lower() in ["developer"]:
        st.write(t("Registros seleccionados:"), ids_seleccionados)

    #st.dataframe(records, hide_index=True)
    # save_if_modified(records, df_edited)
    csv_data = records.to_csv(index=False).encode("utf-8")

    exito, mensaje = False, ""
    # ===============================
    # 🔸 Diálogo de confirmación
    # ===============================
    @st.dialog(t("Confirmar"), width="small")
    def dialog_eliminar():
        st.warning(f"¿{t('Está seguro de eliminar')} {len(ids_seleccionados)} {t('elemento')}(s)?")

        _, col2, col3 = st.columns([1.8, 1, 1])
        with col2:
            if st.button(t(":material/cancel: Cancelar"), key="cancel_delete_absents"):
                st.rerun()
        with col3:
            if st.button(t(":material/delete: Eliminar"), type="primary", key="confirm_delete_absents"):
                exito, mensaje = delete_absences(ids_seleccionados)

                if exito:
                    # Marcar para recarga
                    st.session_state["reload_flag"] = True

                st.rerun()

    if st.session_state.get("reload_flag") and exito:     
        st.success(mensaje)
        st.session_state["reload_flag"] = False

    col1, col2, col3, _, _ = st.columns([1.6, 1.8, 2, 1, 1])
    with col1:
        # --- Botón principal para abrir el diálogo ---
        if st.button(t(":material/delete: Eliminar seleccionados"), disabled=len(ids_seleccionados) == 0, key="btn_delete_absents"):
            dialog_eliminar()
    with col2:
        st.download_button(
                label=t(":material/download: Descargar registros en CSV"),
                data=csv_data, file_name="ausencias.csv", mime="text/csv",
                key="download_csv_absents")

    if st.session_state["auth"]["rol"].lower() in ["developer"]:
        with col3:
                # Convertir a JSON (texto legible, sin índices)
                json_data = records.to_json(orient="records", force_ascii=False, indent=2)
                json_bytes = json_data.encode("utf-8")

                # Botón de descarga
                st.download_button(
                    label=t(":material/download: Descargar registros en JSON"),
                    data=json_bytes, file_name="ausencias.json", mime="application/json",
                    key="download_json_absents"
                )
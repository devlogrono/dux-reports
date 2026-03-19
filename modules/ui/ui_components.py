import pandas as pd
import streamlit as st
import datetime
import json
from modules.util.key_builder import KeyBuilder
from modules.util.records_util import resolver_jugadora_final
from modules.util.util import get_date_range_input
from modules.i18n.i18n import t
from modules.schema import OPCIONES_TURNO
from modules.util.key_builder import KeyBuilder

def selection_header(jug_df: pd.DataFrame, comp_df: pd.DataFrame, records_df: pd.DataFrame = None, modo: str = "registro") -> pd.DataFrame:
    """
    Muestra los filtros principales (Competición, Jugadora, Turno, Tipo/Fechas)
    y retorna el DataFrame de registros filtrado según las selecciones.
    """

    kb = KeyBuilder()

    col1, col2, col3, col4 = st.columns([3, 2, 1.5, 2])

    # --- Selección de competición ---
    with col1:
        competiciones_options = comp_df.to_dict("records")
        competicion = st.selectbox(
            t("Plantel"),
            options=competiciones_options,
            format_func=lambda x: f'{x["nombre"]} ({x["codigo"]})',
            index=3,
        )
        #st.session_state["competicion"] = competiciones_options.index(competicion)

    # --- Selección de jugadora ---
    with col2:
        jugadora_opt = None
        disabled_jugadores = True if modo == "reporte_grupal" else False

        if not jug_df.empty:
            codigo_comp = competicion["codigo"]
            jug_df_filtrado = jug_df[jug_df["plantel"] == codigo_comp]

            # Nombres estables (strings)
            jugadora_nombres = (
                jug_df_filtrado["nombre_jugadora"]
                .astype(str)
                .sort_values()
                .tolist()
            )

            # Resolver índice (permite vacío)
            jugadora_index = None
            if (
                "nombre_jugadora" in st.session_state
                and st.session_state["nombre_jugadora"] in jugadora_nombres
            ):
                jugadora_index = jugadora_nombres.index(
                    st.session_state["nombre_jugadora"]
                )

            jugadora_nombre = st.selectbox(
                t("Jugadora"),
                options=jugadora_nombres,
                format_func=lambda x: f"{jugadora_nombres.index(x) + 1} - {x}",
                index=None,          # None → selector vacío
                placeholder=t("Seleccione una Jugadora"),
                disabled=disabled_jugadores,
                key="jugadora_selector"
            )

            # Persistir estado SOLO si hay selección
            if jugadora_nombre:
                st.session_state["nombre_jugadora"] = jugadora_nombre
            else:
                st.session_state.pop("nombre_jugadora", None)

            # Reconstruir objeto completo solo si hay selección
            if "nombre_jugadora" in st.session_state:
                jugadora_opt = jug_df_filtrado[
                    jug_df_filtrado["nombre_jugadora"].astype(str)
                    == st.session_state["nombre_jugadora"]
                ].iloc[0].to_dict()

        else:
            st.warning(
                ":material/warning: No hay jugadoras cargadas para esta competición."
            )

    # --- Selección de turno ---
    with col3:
        turno_traducido = st.selectbox(
            t("Turno"),
            list(OPCIONES_TURNO.values()),
            index=0
        )
        turno = next(k for k, v in OPCIONES_TURNO.items() if v == turno_traducido)
        #st.session_state.get("turno_idx", 0)
        #st.session_state["turno_idx"] = ["Turno 1", "Turno 2", "Turno 3"].index(turno)

    # --- Tipo o rango de fechas según modo ---
    tipo, start, end = None, None, None
    with col4:
        if modo == "registro":
            tipo = st.radio(
                t("Tipo de registro"),
                options=["Check-in", "Check-out"], horizontal=True,
                index=0 
            )
            #if st.session_state.get("tipo") is None else ["Check-in", "Check-out"].index(st.session_state["tipo"])
            #st.session_state["tipo"] = tipo

        else:  # modo == "reporte"
            hoy = datetime.date.today()
            hace_15_dias = hoy - datetime.timedelta(days=15)

            start_default = hace_15_dias 
            end_default = hoy

            start, end = get_date_range_input(t("Rango de fechas"), start_default=start_default, end_default=end_default)

    if modo == "registro":
        return jugadora_opt, tipo, turno
    
    # ==================================================
    # 🧮 FILTRADO DEL DATAFRAME
    # ==================================================
    #st.text(t("Filtrando registros..."))
    df_filtrado = filtrar_registros(
        records_df,
        jugadora_opt=jugadora_opt,
        turno=turno,
        modo=modo,
        tipo=tipo,   # solo si modo="registros"
        start=start,
        end=end,
    )

    return df_filtrado, jugadora_opt, tipo, turno, start, end

def filtrar_registros(
    records_df: pd.DataFrame,
    jugadora_opt: dict | None = None,
    turno: str = "Todos",
    modo: str = "registros",
    tipo: str | None = None,
    start=None,
    end=None,
) -> pd.DataFrame:
    """
    Filtra el DataFrame de registros según los criterios seleccionados.

    Parámetros:
        records_df: DataFrame original.
        jugadora_opt: dict con datos de la jugadora seleccionada (o None).
        turno: "Todos", "Turno 1", "Turno 2", "Turno 3".
        modo: "registros" o "reporte".
        tipo: string del tipo de registro (solo si modo="registros").
        start: fecha inicio (solo si modo="reporte").
        end: fecha fin (solo si modo="reporte").

    Retorna:
        DataFrame filtrado.
    """

    df_filtrado = records_df.copy()

    if df_filtrado.empty:
        return df_filtrado

    # -------------------------
    # Filtrar por jugadora
    # -------------------------
    if jugadora_opt:
        df_filtrado = df_filtrado[
            df_filtrado["id_jugadora"] == jugadora_opt["id_jugadora"]
        ]

    # -------------------------
    # Filtrar por turno
    # -------------------------
    if turno != "Todos":
        df_filtrado = df_filtrado[df_filtrado["turno"] == turno]

    # -------------------------
    # MODO: registros
    # -------------------------
    if modo == "registros" and tipo:
        df_filtrado = df_filtrado[
            df_filtrado["tipo"].str.lower() == tipo.lower()
        ]

    # -------------------------
    # MODO: reporte (rango de fechas)
    # -------------------------
    elif (modo == "reporte" or modo == "reporte_grupal") and start and end:

        # Normalizar tipos de fecha
        if pd.api.types.is_datetime64_any_dtype(df_filtrado["fecha_sesion"]):
            df_filtrado["fecha_sesion"] = df_filtrado["fecha_sesion"].dt.date

        # Normalizar start y end si vienen como Timestamp
        if hasattr(start, "to_pydatetime"):
            start = start.date()
        if hasattr(end, "to_pydatetime"):
            end = end.date()

        df_filtrado = df_filtrado[
            (df_filtrado["fecha_sesion"] >= start)
            & (df_filtrado["fecha_sesion"] <= end)
        ]

    # ===========================================================
    # MODO: AUSENCIAS (usa fecha_inicio y fecha_fin)
    # Detecta solapamiento de intervalos
    # ===========================================================
    elif modo == "ausencias" and start and end:

        # Comprobar columnas esperadas
        if not {"fecha_inicio", "fecha_fin"}.issubset(df_filtrado.columns):
            return df_filtrado

        # Normalizar tipos
        if pd.api.types.is_datetime64_any_dtype(df_filtrado["fecha_inicio"]):
            df_filtrado["fecha_inicio"] = df_filtrado["fecha_inicio"].dt.date
        if pd.api.types.is_datetime64_any_dtype(df_filtrado["fecha_fin"]):
            df_filtrado["fecha_fin"] = df_filtrado["fecha_fin"].dt.date

        if hasattr(start, "to_pydatetime"):
            start = start.date()
        if hasattr(end, "to_pydatetime"):
            end = end.date()

        # Regla de solapamiento:
        # inicio <= fin_filtro AND fin >= inicio_filtro
        df_filtrado = df_filtrado[
            (df_filtrado["fecha_inicio"] <= end)
            & (df_filtrado["fecha_fin"] >= start)
        ]

    return df_filtrado

def get_checkins(records_df, turno: str, fecha):
    """Devuelve array de id_jugadora con CHECK-IN en la fecha y turno indicados."""
    return records_df[
        (records_df["tipo"] == "checkin") &
        (records_df["turno"] == turno.lower()) &
        (records_df["fecha_sesion"] == fecha)
    ]["id_jugadora"].unique()

def get_checkouts(records_df, turno: str, fecha):
    """Devuelve array de id_jugadora con CHECK-OUT en la fecha y turno indicados."""
    return records_df[
        (records_df["tipo"] == "checkout") &
        (records_df["turno"] == turno.lower()) &
        (records_df["fecha_sesion"] == fecha)
    ]["id_jugadora"].unique()

def preview_record(record: dict) -> None:
    #st.subheader("Previsualización")
    # Header with key fields
    jug = record.get("id_jugadora", "-")
    fecha = record.get("fecha_sesion", "-")
    turno = record.get("turno", "-")
    tipo = record.get("tipo", "-")
    st.markdown(f"**Jugadora:** {jug}  |  **Fecha:** {fecha}  |  **Turno:** {turno}  |  **Tipo:** {tipo}")
    with st.expander("Ver registro JSON", expanded=True):
        st.code(json.dumps(record, ensure_ascii=False, indent=2), language="json")

def selection_header_registro(jug_df: pd.DataFrame, comp_df: pd.DataFrame, records_df: pd.DataFrame = None):
    session_id = st.session_state["client_session_id"]

    col_tipo, col_turno, col_plantel, col_jugadora = st.columns([1.6, 1, 2, 2])

    # 1) Tipo
    with col_tipo:
        opciones_tipo = ["Check-in", "Check-out"]
        tipo = st.radio(
            t("Tipo de registro"),
            options=opciones_tipo,
            horizontal=True,
            index=opciones_tipo.index(st.session_state.get("tipo_registro", "Check-in")),
            key=f"tipo_registro__{session_id}"
        )
        st.session_state["tipo_registro"] = tipo

    # 2) Turno
    with col_turno:
        opciones = list(OPCIONES_TURNO.values())[1:]
        turno_traducido = st.selectbox(
            t("Turno"),
            opciones,
            index=opciones.index(st.session_state.get("turno_select", opciones[0])),
            key=f"turno_select__{session_id}"
        )
        turno = next(k for k, v in OPCIONES_TURNO.items() if v == turno_traducido)
        st.session_state["turno_select"] = turno

    # 3) Plantel
    with col_plantel:
        comp_options = comp_df.to_dict("records")
        comp_select = st.selectbox(
            t("Plantel"),
            options=comp_options,
            format_func=lambda x: x["nombre"],
            index=3,
            key=f"plantel_select__{session_id}"
        )
        codigo_comp = comp_select["codigo"]

    # Context key (ESTABLE) para selección de jugadora
    # IMPORTANTE: incluye session_id + plantel + tipo + turno
    ctx_key = f"{session_id}__{codigo_comp}__{tipo.lower()}__{str(turno).lower()}"

    # Keys estables del widget
    widget_key_jugadora = f"jugadora_select__{ctx_key}"
    state_key_locked = f"last_player_id__{ctx_key}"

    # 4) Jugadoras filtradas
    with col_jugadora:
        jug_df_filtrado = jug_df[jug_df["plantel"] == codigo_comp].copy()

        if records_df is not None and not records_df.empty:
            df = records_df.copy()
            df["tipo"] = df["tipo"].astype(str).str.lower()
            df["turno"] = df["turno"].astype(str).str.lower()

            hoy = datetime.date.today()
            checkins = get_checkins(df, turno, hoy)
            checkouts = get_checkouts(df, turno, hoy)

            if tipo.lower() == "check-in":
                excluir = set(checkins).union(set(checkouts))
                jug_df_filtrado = jug_df_filtrado[~jug_df_filtrado["id_jugadora"].isin(excluir)]
            else:
                mostrar = set(checkins) - set(checkouts)
                jug_df_filtrado = jug_df_filtrado[jug_df_filtrado["id_jugadora"].isin(mostrar)]

        if jug_df_filtrado.empty:
            st.session_state[state_key_locked] = None
            st.session_state[widget_key_jugadora] = None
            st.error(f"No hay jugadoras disponibles para registrar {tipo}")
            st.stop()

        jugadoras = jug_df_filtrado.to_dict("records")
        map_jugadoras = {str(j["id_jugadora"]): j for j in jugadoras}
        opciones_ids = list(map_jugadoras.keys())

        # --- PRESELECCIÓN ROBUSTA ---
        # 1) preferir locked_id si existe y es válido
        locked_id = st.session_state.get(state_key_locked)
        if locked_id not in opciones_ids:
            locked_id = None

        # 2) si widget tiene valor previo, usarlo si sigue válido
        widget_prev = st.session_state.get(widget_key_jugadora)
        if widget_prev in opciones_ids:
            default_id = widget_prev
        elif locked_id in opciones_ids:
            default_id = locked_id
        else:
            #print("no hay nada valido")
            default_id = opciones_ids[0]  # fallback solo si no hay nada válido

        # sincroniza estado del widget antes de renderizar para evitar "vacío"
        st.session_state[widget_key_jugadora] = default_id

        # index coherente (sin placeholder que produzca None)
        default_index = opciones_ids.index(default_id)

        jugadora_labels = {
            jug_id: f"{i + 1} - {map_jugadoras[jug_id]['nombre_jugadora']}"
            for i, jug_id in enumerate(opciones_ids)
        }

        jugadora_id = st.selectbox(
            t("Jugadora"),
            options=opciones_ids,
            #format_func=lambda x: map_jugadoras[x]["nombre_jugadora"],
            format_func=lambda x: jugadora_labels[x],
            index=None, #default_index,
            key=widget_key_jugadora
        )

        jugadora_header = map_jugadoras.get(jugadora_id)

    # Resolver final (bloqueo por contexto)
    jugadora_final = resolver_jugadora_final(
        jugadora_header=jugadora_header,
        jug_df_filtrado=jug_df_filtrado,
        jug_df=jug_df,
        tipo=tipo,
        ctx_key=ctx_key
    )

    return jugadora_final, tipo, turno, jug_df_filtrado

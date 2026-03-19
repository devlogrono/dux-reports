import json
import streamlit as st
import datetime
import pandas as pd
from modules.util.io_files import load_catalog_list
from modules.db.db_catalogs import load_catalog_list_db
from modules.schema import DIAS_SEMANA
from modules.i18n.i18n import t
from modules.app_config.styles import template_COLOR_NORMAL, template_COLOR_INVERTIDO
from modules.util.key_builder import KeyBuilder

def validate_checkin(record: dict) -> tuple[bool, str]:
    # Required 1..5
    for field in ["recuperacion", "fatiga", "sueno", "stress", "dolor"]:
        value = record.get(field)
        if value is None:
            return False, f"Completa el campo '{field}'."
        if not (1 <= int(value) <= 5):
            return False, f"El campo '{field}' debe estar entre 1 y 5."
    # Dolor parts if dolor > 1
   
    if int(record.get("dolor", 0)) > 1:
        if record.get("id_zona_segmento_dolor") is None:
            return False, t("Selecciona al menos una parte del cuerpo con dolor.")

    return True, ""

@st.fragment
def checkin_inputs(record: dict, genero: str):
    NA = "No Aplica"

    kb = KeyBuilder()   # ← GENERADOR DE KEYS ÚNICO
    
    if "dia_plus" not in st.session_state:
        st.session_state["dia_plus"] = "MD+1"  # valor por defecto

    if "dia_minor" not in st.session_state:
        st.session_state["dia_minor"] = "MD-6"  # valor por defecto

    segmentos_corporales_df = load_catalog_list_db("segmentos_corporales", as_df=True)
    map_segmentos_nombre_a_id = dict(zip(segmentos_corporales_df["nombre"], segmentos_corporales_df["id"]))
    segmentos_corporales_list = segmentos_corporales_df["nombre"].tolist()

    zonas_segmento_df = load_catalog_list_db("zonas_segmento", as_df=True)
    map_zonas_segmento_nombre_a_id = dict(zip(zonas_segmento_df["nombre"], zonas_segmento_df["id"]))
    zonas_segmento_list = zonas_segmento_df["nombre"].tolist()

    zonas_anatomicas_df = load_catalog_list_db("zonas_anatomicas", as_df=True)
    map_zonas_anatomicas_nombre_a_id = dict(zip(zonas_anatomicas_df["nombre"], zonas_anatomicas_df["id"]))
    zonas_anatomicas_list = zonas_anatomicas_df["nombre"].tolist()

    lateralidades = load_catalog_list("lateralidades")

    tipo_carga_df = load_catalog_list_db("tipo_carga", as_df=True)
    map_tipo_carga_nombre_a_id = dict(zip(tipo_carga_df["nombre"], tipo_carga_df["id"]))
    tipo_carga_list = tipo_carga_df["nombre"].tolist()

    estimulos_readaptacion_df = load_catalog_list_db("estimulos_readaptacion", as_df=True)
    map_estimulos_readaptacion_nombre_a_id = dict(zip(estimulos_readaptacion_df["nombre"], estimulos_readaptacion_df["id"]))
    estimulos_readaptacion_list = estimulos_readaptacion_df["nombre"].tolist()

    tipo_condicion_df = load_catalog_list_db("tipo_condicion", as_df=True)
    map_tipo_condicion_nombre_a_id = dict(zip(tipo_condicion_df["nombre"], tipo_condicion_df["id"]))
    tipo_condicion_list = tipo_condicion_df["nombre"].tolist()

    with st.container():
        st.markdown(t("**Check-in diario (pre-entrenamiento)**"))
        mostrar_tabla_referencia_template()

        # --- Variables principales ---
        c1, c2, c3, c4, c5 = st.columns(5)
        #c1, c2 = st.columns([0.8,4])
        with c1:
            record["recuperacion"] = st.number_input(t("**Recuperación** :red[:material/arrow_upward_alt:] (:green[**1**] - :red[**5**])"), 
                                                     min_value=1, max_value=5, step=1, key=kb.key("recuperacion_input"), 
                                                     help=t("1 = Totalmente recuperado · 5 = Muy mal recuperado")) 
        with c2:
            record["fatiga"] = st.number_input(t("**Energía** :red[:material/arrow_upward_alt:] (:green[**1**] - :red[**5**])"), 
                                               min_value=1, max_value=5, step=1, key=kb.key("fatiga_input"), 
                                               help=t("1 = Energía Máxima · 5 = Sin Energía")) 
        with c3:
            record["sueno"] = st.number_input(t("**Sueño** :red[:material/arrow_upward_alt:] (:green[**1**] - :red[**5**])"), 
                                              min_value=1, max_value=5, step=1, key=kb.key("sueno_input"),
                                              help=t("1 = Excelente calidad . 5 = Muy mala calidad")) 
        with c4:
            record["stress"] = st.number_input(t("**Estrés** :red[:material/arrow_upward_alt:] (:green[**1**] - :red[**5**])"), 
                                               min_value=1, max_value=5, step=1, key=kb.key("stress_input"),
                                               help=t("1 = Relajado . 5 = Nivel de estrés muy alto")) 
        with c5:
            record["dolor"] = st.number_input(t("**Dolor** :red[:material/arrow_upward_alt:] (:green[**1**] - :red[**5**])"), 
                                              min_value=1, max_value=5, step=1, key=kb.key("dolor_input"), 
                                              help=t("1 = Sin dolor . 5 = Dolor severo"))

        col1, col2, col3 = st.columns([1,2,1])
        # --- Dolor corporal ---
        record["id_zona_segmento_dolor"] = None
        record["zonas_anatomicas_dolor"] = None
        record["lateralidad"] = None
        
        #st.write(record.get("dolor", 0))
        if int(record.get("dolor", 0)) > 1:

            with col1:
                zona_cuerpo = st.selectbox(t("Zona anatómica *"), zonas_segmento_list, index=None,
                                        placeholder=t("Selecciona una opción"), key=kb.key("zona_cuerpo")) #{st.session_state['form_version']}
                
            with col2:
                if zona_cuerpo:
                    zonas_segmento_id = map_zonas_segmento_nombre_a_id.get(zona_cuerpo)
                    record["id_zona_segmento_dolor"] = zonas_segmento_id
                    zonas_anatomicas_filtrados = zonas_anatomicas_df[zonas_anatomicas_df["zona_id"] == zonas_segmento_id]
                    zonas_anatomicas_list = zonas_anatomicas_filtrados["nombre"].tolist()
                else:
                    zonas_anatomicas_list = []

                zonas_anatomicas_dolor = st.multiselect(
                    "Estructura anatómica", options=zonas_anatomicas_list, 
                    placeholder="Selecciona una o varias partes con dolor",
                    key=kb.key("anatómica_dolor")
                )

                if zonas_anatomicas_dolor:
                    zonas_anatomicas_dolor_ids = [
                        map_zonas_anatomicas_nombre_a_id.get(nombre) for nombre in zonas_anatomicas_dolor
                    ]
                    record["zonas_anatomicas_dolor"] = json.dumps(zonas_anatomicas_dolor_ids)

            with col3:
                lateralidad = st.selectbox(t("Lateralidad"), lateralidades, index=0, key=kb.key("lateralidad")) #{st.session_state['form_version']}
                
                if lateralidad:
                    record["lateralidad"] = lateralidad

            st.caption(t(":red[Los campos marcados con * son obligatorios.]"))
        # else:
        #     record["id_zona_segmento_dolor"] = None
        #     record["zonas_anatomicas_dolor"] = None
        #     record["lateralidad"] = None

    st.divider()
    st.markdown(t("**Periodización táctica**"))

    # Días previos al partido (MD-14 a MD0)
    opciones_minor = [f"MD-{i}" for i in range(14, 0, -1)] + ["MD0"]
    opciones_minor += ["VACACIONES - "]

    # Días posteriores al partido (MD0 a MD+14)
    opciones_plus = ["MD0"] + [f"MD+{i}" for i in range(1, 15)]
    opciones_plus += ["VACACIONES + "]

    colA, colB, colC, colD, colE  = st.columns([1,1,1,2,2])
    with colA:
        fecha_sesion = datetime.date.today()
        dia_semana = fecha_sesion.strftime("%A")
        dia_semana_es = DIAS_SEMANA.get(dia_semana, dia_semana)
        st.text_input(t("Día de la sesión"), dia_semana_es, disabled=True)
    with colB:

        #opciones_plus = ["MD0", "MD+1", "MD+2", "MD+3", "MD+4", "MD+5", "MD+6", "MD+7"]
        dia_plus = st.selectbox(
            t("MD+"),
            options=opciones_plus,
            index=opciones_plus.index(st.session_state.get("dia_plus", 1)),
            key=kb.key("select_dia_plus")
        )

        st.session_state["dia_plus"] = dia_plus 
        
    with colC:
        #opciones_minor = ["MD-7", "MD-6", "MD-5", "MD-4", "MD-3", "MD-2", "MD-1", "MD0"]
        dia_minor = st.selectbox(
            "MD-",
            options=opciones_minor,
            index=opciones_minor.index(st.session_state.get("dia_minor", 1)),
            key=kb.key("select_dia_minor")
        )

        st.session_state["dia_minor"] = dia_minor
    with colD:
        # 1. Obtener índice guardado
        idx = st.session_state.get("id_tipo_carga", 0)

        # 2. Normalizar índice
        if not isinstance(idx, int) or idx < 0 or idx >= len(tipo_carga_list):
            idx = 0

        # Debug
        #st.text(f"Índice guardado (real): {idx}")

        # 3. Selectbox
        tipo_estimulo = st.selectbox(
            t("Tipos de carga"),
            tipo_carga_list,
            index=idx,
            key=kb.key("select_tipo_estimulo")
        )

        # 4. Asignar ID real del valor seleccionado
        tipo_estimulo_id = map_tipo_carga_nombre_a_id.get(tipo_estimulo)
        record["id_tipo_carga"] = tipo_estimulo_id

        # 5. Guardar en session_state **el índice**, no el ID
        st.session_state["id_tipo_carga"] = tipo_carga_list.index(tipo_estimulo)
        #st.text(f'Índice guardado (session_state): {st.session_state["id_tipo_carga"]}')

    with colE:
        disabled_selector = False
        if tipo_estimulo != "Readaptación":
            estimulos_readaptacion_list = [NA]
            disabled_selector = True

        tipo_readaptacion = st.selectbox(t("Rehabilitación/readaptación"), estimulos_readaptacion_list, index=0,
        disabled=disabled_selector, key=kb.key("select_tipo_readaptacion"))
        tipo_readaptacion_id = map_estimulos_readaptacion_nombre_a_id.get(tipo_readaptacion)
        record["id_tipo_readaptacion"] = tipo_readaptacion_id

    #-- Tipo de condición ---
    colF, colG = st.columns([1.5,3])
    with colF:
        tipo_condicion = st.selectbox(t("Jugadora condicionada por:"), tipo_condicion_list, 
                                      index=len(tipo_condicion_list) - 1, 
                                      key=kb.key("select_tipo_condicion"))
        tipo_condicion_id = map_tipo_condicion_nombre_a_id.get(tipo_condicion)
        record["id_tipo_condicion"] = tipo_condicion_id
        #st.caption(t("Selecciona la condición física actual de la jugadora"))
    
    periodizacion_tactica = dia_plus + " / " + dia_minor
    record["periodizacion_tactica"] = periodizacion_tactica
    
    if genero == "F":
        st.divider()
        record["en_periodo"] = st.checkbox(t("Te encuentras en periodo de menstruación"))
        st.caption(t("Esta información ayuda a gestionar las cargas con respecto a la fisiología femenina"))

    # --- Observación libre ---
    record["observacion"] = st.text_area(t("Observaciones"), value="")
    is_valid, msg = validate_checkin(record)
    return record, is_valid, msg

def checkin_form(record: dict, genero: str) -> tuple[dict, bool, str]:
    """Formulario de Check-in (template pre-entrenamiento) con ICS y periodización táctica adaptativa."""

    record, is_valid, msg = checkin_inputs(record, genero)
    return record, is_valid, msg

def mostrar_tabla_referencia_template():
    """Tabla de referencia (1-5) con la misma escala para todas las métricas:
       1 = mejor estado (verde), 5 = peor estado (rojo).
    """

    data = {
        t("Variable"): [
            t("Recuperación"),
            t("Energía"),
            t("Sueño"),
            t("Estrés"),
            t("Dolor")
        ],
        "1": [
            t("Totalmente recuperado"),
            t("Energía muy alta"),
            t("Excelente sueño"),
            t("Muy relajado / Sin estrés"),
            t("Sin dolor")
        ],
        "2": [
            t("Buena recuperación"),
            t("Buena energía"),
            t("Buen descanso"),
            t("Relajado"),
            t("Molestias leves")
        ],
        "3": [
            t("Recuperación normal"),
            t("Energía normal"),
            t("Sueño adecuado"),
            t("Estrés moderado"),
            t("Dolor leve")
        ],
        "4": [
            t("Baja recuperación"),
            t("Fatigado"),
            t("Mala calidad de sueño"),
            t("Estrés alto"),
            t("Dolor moderado")
        ],
        "5": [
            t("Muy mala recuperación"),
            t("Extremadamente cansado"),
            t("Sueño muy malo / Insomnio"),
            t("Muy estresado / Irritable"),
            t("Dolor severo")
        ]
    }

    df_ref = pd.DataFrame(data).set_index(t("Variable"))

    # --- Aplicar colores correctos (1=verde, 5=rojo) ---
    def color_by_col(col):
        if col.name not in ["1", "2", "3", "4", "5"]:
            return [""] * len(col)

        result = []
        for _ in df_ref.index:
            nivel = int(col.name)
            color = template_COLOR_INVERTIDO[nivel]  # ← AHORA 1=verde, 5=rojo
            result.append(
                f"background-color:{color}; color:white; text-align:center; font-weight:bold;"
            )
        return result

    styled_df = df_ref.style.apply(color_by_col, subset=["1", "2", "3", "4", "5"], axis=0)

    with st.expander(t("Ver tabla de referencia de escalas (1-5)")):
        st.dataframe(styled_df, hide_index=False)
        st.caption(t(
            "**Interpretación de colores:**\n"
            "- **1 (verde)** = mejor estado.\n"
            "- **5 (rojo)** = peor estado."
        ))

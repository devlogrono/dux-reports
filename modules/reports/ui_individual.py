import streamlit as st
import pandas as pd
import numpy as np
from .metrics import compute_rpe_metrics, RPEFilters
from modules.util.util import (get_photo, clean_image_url, calcular_edad)
from modules.i18n.i18n import t

from .plots_individuales import (
    grafico_rpe_ua,
    grafico_duracion_rpe,
    grafico_acwr,
    grafico_template,
    tabla_template_individual
)

def player_block_dux(jugadora_seleccionada: dict, unavailable="N/A"):
    """Muestra el bloque visual con la información principal de la jugadora."""

    # Validar jugadora seleccionada
    if not jugadora_seleccionada or not isinstance(jugadora_seleccionada, dict):
        st.info(t("Selecciona una jugadora para continuar."))
        st.stop()
    
    #st.dataframe(jugadora_seleccionada)
    # Extraer información básica
    nombre_completo = jugadora_seleccionada.get("nombre_jugadora", unavailable).strip().upper()
    #apellido = jugadora_seleccionada.get("apellido", "").strip().upper()
    #nombre_completo = f"{nombre.capitalize()}"
    id_jugadora = jugadora_seleccionada.get("id_jugadora", unavailable)
    posicion = jugadora_seleccionada.get("posicion", unavailable)
    pais = jugadora_seleccionada.get("nacionalidad", unavailable)
    fecha_nac = jugadora_seleccionada.get("fecha_nacimiento", unavailable)
    genero = jugadora_seleccionada.get("genero", "")
    competicion = jugadora_seleccionada.get("plantel", "")
    dorsal = jugadora_seleccionada.get("dorsal", "")
    url_drive = jugadora_seleccionada.get("foto_url", "")

    dorsal_number = f":red[/ Dorsal #{int(dorsal)}]" if pd.notna(dorsal) else ""

    # Calcular edad
    edad_texto, fnac = calcular_edad(fecha_nac)

    # Color temático
    #color = "violet" if genero.upper() == "F" else "blue"

    # Icono de género
    if genero.upper() == "F":
        genero_icono = ":material/girl:"
        profile_image = "female"
    elif genero.upper() == "H":
        genero_icono = ":material/boy:"
        profile_image = "male"
    else:
        genero_icono = ""
        profile_image = "profile"

    # Bloque visual
    st.markdown(f"### {nombre_completo.title()} {dorsal_number}")
    #st.markdown(f"##### **_:red[Identificación:]_** _{id_jugadora}_ | **_:red[País:]_** _{pais.upper()}_")

    col1, col2, col3 = st.columns([1.6, 2, 2])

    with col1:
        if pd.notna(url_drive) and url_drive and url_drive != "No Disponible":
            direct_url = clean_image_url(url_drive)
            #st.text(direct_url)
            response = get_photo(direct_url)
            if response and response.status_code == 200 and 'image' in response.headers.get("Content-Type", ""):
                st.image(response.content, width=300)
            else:
                st.image(f"assets/images/{profile_image}.png", width=300)
        else:
            st.image(f"assets/images/{profile_image}.png", width=300)

    with col2:
        #st.markdown(f"**:material/sports_soccer: Competición:** {competicion}")
        #st.markdown(f"**:material/cake: Fecha Nac.:** {fecha_nac}")

        st.metric(label=t(":red[:material/id_card: Identificación]"), value=f"{id_jugadora}", border=True)
        st.metric(label=t(":red[:material/sports_soccer: Plantel]"), value=f"{competicion}", border=True)
        st.metric(label=t(":red[:material/cake: F. Nacimiento]"), value=f"{fecha_nac}", border=True)
                    
    with col3:
        #st.markdown(f"**:material/person: Posición:** {posicion.capitalize()}")
        #st.markdown(f"**:material/favorite: Edad:** {edad if edad != unavailable else 'N/A'} años")

        st.metric(label=t(":red[:material/globe: País]"), value=f"{pais if pais else 'N/A'}", border=True)
        st.metric(label=t(":red[:material/person: Posición]"), value=f"{posicion.capitalize() if posicion else 'N/A'}", border=True)
        st.metric(label=t(":red[:material/favorite: Edad]"), value=f"{edad_texto}", border=True)
          
    #st.divider()


def metricas(df: pd.DataFrame, jug_sel, turno_sel, start, end) -> None:
    """Página de análisis individual de cargas y RPE por jugadora."""

    # --- Calcular métricas generales ---
    flt = RPEFilters(jugadores=jug_sel or None, turnos=turno_sel or None, start=start, end=end)
    metrics = compute_rpe_metrics(df, flt)

    # --- Validar datos ---
    if df is None or df.empty:
        st.info(t("No hay registros disponibles para análisis individual."))
        return

    # --- Resumen general ---
    st.divider()
    st.markdown(t("### **Resumen de carga individual**"))
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        st.metric(t("Minutos último día"), value=(f"{metrics['minutos_sesion']:.0f}" if pd.notna(metrics['minutos_sesion']) else "-"))
        st.metric(t("Carga mes"), help=t("Control de mesociclo"), value=(f"{metrics['carga_mes']:.0f}" if metrics["carga_mes"] is not None else "-"))
    with k2:
        st.metric(t("UA total último día"), help=t("Intensidad del entrenamiento o partido"), value=(f"{metrics['ua_total_dia']:.0f}" if metrics["ua_total_dia"] is not None else "-"))
        st.metric(t("Carga media mes"), help=t("Control de mesociclo"), value=(f"{metrics['carga_media_mes']:.2f}" if metrics["carga_media_mes"] is not None else "-"))
    with k3:
        st.metric(t("Carga semana"), help=t("Volumen del microciclo"), value=(f"{metrics['carga_semana']:.0f}" if metrics["carga_semana"] is not None else "-"))
        st.metric(t("Fatiga aguda (7d)"), help=t("Estrés agudo"), value=(f"{metrics['fatiga_aguda']:.0f}" if metrics["fatiga_aguda"] is not None else "-"))
    with k4:
        st.metric(t("Carga media semana"), help=t("Control semanal equilibrado"), value=(f"{metrics['carga_media_semana']:.2f}" if metrics["carga_media_semana"] is not None else "-"))
        st.metric(t("Fatiga crónica (28d)"), help=t("Nivel de adaptación (Media)"), value=(f"{metrics['fatiga_cronica']:.1f}" if metrics["fatiga_cronica"] is not None else "-"))
    with k5:
        st.metric(t("Monotonía semana"), help=t("Detectar sesiones demasiado parecidas"), value=(f"{metrics['monotonia_semana']:.2f}" if metrics["monotonia_semana"] is not None else "-"))
        st.metric(t("Adaptación"), help=t("Balance entre fatiga aguda y crónica"), value=(f"{metrics['adaptacion']:.2f}" if metrics["adaptacion"] is not None else "-"))
    with k6:
        st.metric(t("Variabilidad semanal"), help=t("Índice de variabilidad semanal"), value=(f"{metrics['variabilidad_semana']:.2f}" if metrics["variabilidad_semana"] is not None else "-"))
        st.metric(t("ACWR"), help=t("Relación entre fatiga aguda y crónica"), value=(f"{metrics['acwr']:.2f}" if metrics["acwr"] is not None else "-"))

    resumen = _get_resumen_tecnico_carga(metrics)
    st.markdown(resumen, unsafe_allow_html=True)

    #st.dataframe(df)
    #tabla_template_individual(df)

def _get_resumen_tecnico_carga(metrics: dict) -> str:
    """
    Genera un resumen técnico con interpretación y colores visuales
    (rojo = riesgo, naranja = medio, verde = óptimo).
    Devuelve un texto formateado en HTML para st.markdown().
    """

    def color_text(text, color):
        return f"<b style='color:{color}'>{text}</b>"

    # --- valores base ---
    carga_semana = metrics.get("carga_semana", 0) or 0
    carga_mes = metrics.get("carga_mes", 0) or 0
    fatiga_aguda = metrics.get("fatiga_aguda", 0) or 0
    fatiga_cronica = metrics.get("fatiga_cronica", 0) or 0
    acwr = metrics.get("acwr")
    monotonia = metrics.get("monotonia_semana")
    adaptacion = metrics.get("adaptacion")
    ua_total_dia = metrics.get("ua_total_dia", 0) or 0
    minutos_dia = metrics.get("minutos_sesion", 0) or 0

    # --- CARGA SEMANAL ---
    if carga_semana > 2500:
        carga_estado = color_text(t("alta"), "#E53935")  # rojo
    elif carga_semana >= 1500:
        carga_estado = color_text(t("moderada"), "#FB8C00")  # naranja
    else:
        carga_estado = color_text(t("baja"), "#43A047")  # verde

    # --- FATIGA AGUDA ---
    if fatiga_aguda > 2000:
        estado_fatiga = color_text(t("elevada"), "#E53935")
    elif fatiga_aguda >= 1000:
        estado_fatiga = color_text(t("controlada"), "#FB8C00")
    else:
        estado_fatiga = color_text(t("baja"), "#43A047")

    # --- ACWR ---
    if acwr is None:
        riesgo = color_text(t("sin datos suficientes"), "#757575")
    elif acwr > 1.5:
        riesgo = color_text(t("riesgo alto de sobrecarga"), "#E53935")
    elif acwr < 0.8:
        riesgo = color_text(t("subcarga o falta de estímulo"), "#FB8C00")
    else:
        riesgo = color_text(t("relación óptima entre carga aguda y crónica"), "#43A047")

    # --- MONOTONÍA ---
    if monotonia is None:
        variabilidad = color_text(t("sin datos de variabilidad"), "#757575")
    elif monotonia > 1.8:
        variabilidad = color_text(t("poca variabilidad entre sesiones"), "#E53935")
    elif monotonia >= 1.5:
        variabilidad = color_text(t("variabilidad moderada"), "#FB8C00")
    else:
        variabilidad = color_text(t("buena variabilidad semanal"), "#43A047")

    # --- ADAPTACIÓN ---
    if adaptacion is None:
        estado_adapt = color_text(t("no disponible"), "#757575")
    elif adaptacion < 0:
        estado_adapt = color_text(t("negativa (predomina la fatiga)"), "#E53935")
    elif adaptacion == 0:
        estado_adapt = color_text(t("neutral"), "#FB8C00")
    else:
        estado_adapt = color_text(t("positiva (asimilación adecuada del entrenamiento)"), "#43A047")

    # --- construir resumen con colores ---
    resumen = (f"{t(':material/description: **Resumen técnico:**')} <div style='text-align: justify;'> {t('En el último día registrado se completaron')} " 
    f"{color_text(f'{minutos_dia:.0f} minutos', '#43A047')} {t('de sesión con una carga interna de')} " f"{color_text(f'{ua_total_dia:.0f} UA', '#43A047')}. "
    f"{t('La carga semanal actual es')} {carga_estado} " 
    f"({color_text(f'{carga_semana:.0f} UA', '#607D8B')}) {t('y la carga mensual acumulada asciende a')} " 
    f"{color_text(f'{carga_mes:.0f} UA', '#607D8B')}. " 
    f"{t('La fatiga aguda es')} {estado_fatiga}, {t('mientras que la fatiga crónica se mantiene en')} " 
    f"{color_text(f'{fatiga_cronica:.1f} UA', '#607D8B')} {t('de media')}, {t('indicando una adaptación')} {estado_adapt}. " 
    f"{t('El índice ACWR sugiere')} {riesgo}, {t('y la monotonía semanal refleja')} {variabilidad}." 
    f"</div>" )

    return resumen


def calcular_semaforo_riesgo(df: pd.DataFrame) -> tuple[str, str, float, float]:
    """
    Calcula el semáforo de riesgo basándose en ACWR (carga aguda/crónica)
    y la percepción de fatiga (1–5).

    Retorna:
        icono (str): 🟢🟠🔴⚪️
        descripcion (str): texto interpretativo
        acwr (float): índice carga aguda/crónica
        fatiga (float): último valor de fatiga
    """

    if "ua" not in df.columns:
        return "⚪️", "Sin datos de carga (UA).", np.nan, np.nan

    # Convertir UA a numérico
    df["ua"] = pd.to_numeric(df["ua"], errors="coerce")
    df = df.dropna(subset=["ua"])

    df = df.copy()
    
    # Calcular carga aguda (últimos 7 días) y crónica (últimos 28 días)
    df["acute7"] = df["ua"].rolling(7, min_periods=3).mean()
    df["chronic28"] = df["ua"].rolling(28, min_periods=7).mean()
    df["acwr"] = df["acute7"] / df["chronic28"]
    df = df.dropna(subset=["acwr"])

    # Últimos valores
    last_acwr = df["acwr"].iloc[-1] if not df.empty else np.nan
    last_fatiga = df["fatiga"].iloc[-1] if "fatiga" in df.columns else np.nan

    # Lógica de riesgo
    if pd.isna(last_acwr) and pd.isna(last_fatiga):
        return "⚪️", t("Sin datos suficientes para evaluar riesgo."), np.nan, np.nan
    if last_acwr > 1.5 or (not pd.isna(last_fatiga) and last_fatiga >= 4):
        return "🔴", t("Riesgo alto de sobrecarga o fatiga acumulada."), last_acwr, last_fatiga
    elif 1.3 <= last_acwr <= 1.5 or (not pd.isna(last_fatiga) and 3 <= last_fatiga < 4):
        return "🟠", t("Riesgo moderado; controlar volumen y recuperación."), last_acwr, last_fatiga
    elif 0.8 <= last_acwr < 1.3 and (pd.isna(last_fatiga) or last_fatiga < 3):
        return "🟢", t("Riesgo bajo; zona óptima de carga y adaptación."), last_acwr, last_fatiga
    else:
        return "⚪️", t("Carga muy baja; posible desadaptación o falta de estímulo."), last_acwr, last_fatiga

def graficos_individuales(df: pd.DataFrame):
    """Gráficos individuales para análisis de carga, bienestar y riesgo."""
    if df is None or df.empty:
        st.info("No hay datos disponibles para graficar.")
        return

    df_player = df.copy().sort_values("fecha_sesion")

    #st.divider()
    st.markdown(t("### **Gráficos**"))

    tabs = st.tabs([
        t("template"),
        t("Fatiga y ACWR"),
        t("RPE y UA"),
        t("Duración vs RPE"),
        t("Lesiones")
    ])

    with tabs[0]: 
        tabla_template_individual(df_player)
        st.divider()
        grafico_template(df_player)
    with tabs[1]: 
        grafico_acwr(df_player)
    with tabs[2]: 
        grafico_rpe_ua(df_player)
    with tabs[3]: 
        grafico_duracion_rpe(df_player)

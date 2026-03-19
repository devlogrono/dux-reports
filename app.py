import streamlit as st

from modules.db.db_absences import load_active_absences_db
from modules.db.db_competitions import load_competitions_db
from modules.db.db_players import load_players_db
from modules.db.db_records import get_records_db
from modules.ui.absents_ui import filtrar_jugadoras_ausentes
from modules.util.util import clean_df, data_format
from modules.ui.ui_app import (
    get_default_period,
    filter_df_by_period,
    calc_metric_block,
    calc_alertas,
    render_metric_cards,
    generar_resumen_periodo,
    show_interpretation,
    mostrar_resumen_tecnico,
    get_pendientes_check
)

from modules.i18n.i18n import t
import modules.app_config.config as config
config.init_config()

st.header(t("Resumen de :red[1er Equipo]"), divider="red")
#st.session_state.clear()
# ============================================================
# 📦 CARGA DE DATOS
# ============================================================
df = get_records_db()
#st.dataframe(df)

if df.empty:
    st.warning(t("No hay registros disponibles."))
    st.stop()

df = data_format(df)
jug_df = load_players_db()
#st.dataframe(jug_df)
 
#jug_df = jug_df[jug_df["plantel"] == "1FF"]
   
comp_df = load_competitions_db()
ausencias_df = load_active_absences_db()

# ============================================================
# INTERFAZ PRINCIPAL
# ============================================================

# --- Fila principal de filtros ---
col1, col2, _ = st.columns([2, 1.5, 1])

with col1:
    default_period = get_default_period(df)

    # Diccionario clave interna → texto traducido
    OPCIONES_PERIODO = {
        "Hoy": t("Hoy"),
        "Último día": t("Último día"),
        "Semana": t("Semana"),
        "Mes": t("Mes")
    }

    periodo_traducido = st.radio(
        t("Periodo:"),
        list(OPCIONES_PERIODO.values()),horizontal=True,
        index=list(OPCIONES_PERIODO.keys()).index(default_period))

    periodo = next(k for k, v in OPCIONES_PERIODO.items() if v == periodo_traducido)
    df_periodo, articulo = filter_df_by_period(df, periodo)

#st.dataframe(df, hide_index=True)
#st.dataframe(df_periodo, hide_index=True)

# Cálculos principales
template_prom, chart_template, delta_template = calc_metric_block(df_periodo, periodo, "template_score", "mean")
rpe_prom, chart_rpe, delta_rpe = calc_metric_block(df_periodo, periodo, "rpe", "mean")
ua_total, chart_ua, delta_ua = calc_metric_block(df_periodo, periodo, "ua", "sum")
alertas_count, total_jugadoras, alertas_pct, chart_alertas, delta_alertas = calc_alertas(df_periodo, df, periodo)

# ============================================================
# 💠 TARJETAS DE MÉTRICAS
# ============================================================
render_metric_cards(template_prom, delta_template, chart_template, rpe_prom, delta_rpe, chart_rpe, ua_total, delta_ua, chart_ua, alertas_count, total_jugadoras, alertas_pct, chart_alertas, delta_alertas, articulo)

# ============================================================
# 📋 INTERPRETACIÓN Y RESUMEN TÉCNICO
# ============================================================
show_interpretation(template_prom, rpe_prom, ua_total, alertas_count, alertas_pct, delta_ua, total_jugadoras)

mostrar_resumen_tecnico(template_prom, rpe_prom, ua_total, alertas_count, total_jugadoras)

# ============================================================
# 📊 REGISTROS DEL PERIODO
# ============================================================

st.divider()
st.markdown(t("**Registros del periodo seleccionado**") + f"(:blue-background[{periodo_traducido}])")

# --- Fila principal de filtros ---
col1, col2, _ = st.columns([1.5, 1.5, 1])

with col1:
    competiciones_options = comp_df.to_dict("records")
    competicion = st.selectbox(
        t("Plantel"),
        options=competiciones_options,
        format_func=lambda x: f'{x["nombre"]} ({x["codigo"]})',
        index=3,
        key="aus_competicion",
    )
  
codigo_comp = competicion["codigo"]
jug_df = jug_df[jug_df["plantel"] == codigo_comp]
df_periodo = df_periodo[df_periodo["id_jugadora"].isin(jug_df["id_jugadora"])]

   
tabs = st.tabs([
        t(":material/physical_therapy: Indicadores de bienestar y carga"),
        t(":material/description: Registros detallados"),
        t(":material/report_problem: Pendientes de registro")
    ])

if df_periodo.empty:
    st.info(t("No hay registros disponibles en este periodo."))
    st.stop()

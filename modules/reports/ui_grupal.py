
import streamlit as st
import pandas as pd
from modules.i18n.i18n import t
from .plots_grupales import (plot_carga_semanal, plot_rpe_promedio, tabla_resumen)

def group_dashboard(df_filtrado: pd.DataFrame):
    """Panel grupal con gráficos y tablas agregadas."""

    #st.subheader(":material/group: Resumen grupal de cargas", divider=True)
    if df_filtrado.empty:
        st.info(t("No hay datos disponibles para el periodo seleccionado."))
        st.stop()

    st.divider()
    tabs = st.tabs([
        t(":material/monitor_weight: Carga y esfuerzo"),
        t(":material/trending_up: Índices de control"),
        t(":material/table_chart: Resumen tabular"),
    ])

    with tabs[0]:
        plot_carga_semanal(df_filtrado)
    with tabs[1]: 
        plot_rpe_promedio(df_filtrado)
    with tabs[2]: 
        tabla_resumen(df_filtrado)

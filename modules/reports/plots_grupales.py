# src/plots_grupales.py
import streamlit as st
import pandas as pd
import plotly.express as px
from modules.app_config import styles
from modules.i18n.i18n import t

# ============================================================
# 🧭 Función auxiliar de fecha
# ============================================================
def _ensure_fecha(df: pd.DataFrame) -> pd.DataFrame:
    """Asegura columna 'fecha_sesion' y añade 'semana', 'anio' y 'rango_semana'."""
    df = df.copy()
    if "fecha_sesion" not in df.columns:
        st.warning("El DataFrame no contiene la columna 'fecha_sesion'.")
        return df

    df["fecha_sesion"] = pd.to_datetime(df["fecha_sesion"], errors="coerce")
    df["anio"] = df["fecha_sesion"].dt.year
    df["semana"] = df["fecha_sesion"].dt.isocalendar().week

    # Etiqueta más amigable: rango de lunes a domingo
    df["inicio_semana"] = df["fecha_sesion"] - pd.to_timedelta(df["fecha_sesion"].dt.weekday, unit="d")
    df["fin_semana"] = df["inicio_semana"] + pd.Timedelta(days=6)
    df["rango_semana"] = df["inicio_semana"].dt.strftime("%d %b") + "–" + df["fin_semana"].dt.strftime("%d %b")

    return df


# ============================================================
# 📊 Carga semanal (UA)
# ============================================================
def plot_carga_semanal(df: pd.DataFrame):
    """Evolución semanal de la carga total y media del grupo."""
    df = _ensure_fecha(df)
    if df.empty or df["ua"].isna().all():
        st.info("No hay datos de carga disponibles.")
        return

    weekly = (
        df.groupby(["anio", "semana", "rango_semana"], as_index=False)
        .agg(
            carga_total=("ua", "sum"),
            carga_media=("ua", "mean"),
            rpe_prom=("rpe", "mean"),
        )
    )

    fig = px.line(
        weekly,
        x="rango_semana",
        y="carga_total",
        markers=True,
        title=t("Carga total semanal (UA)"),
        color_discrete_sequence=[styles.BRAND_PRIMARY],
    )
    fig.update_traces(line=dict(width=3))
    fig.update_layout(
        xaxis_title=t("Semana"),
        yaxis_title=t("Carga (UA)"),
        plot_bgcolor="white",
        font_color=styles.BRAND_TEXT,
    )
    st.plotly_chart(fig, use_container_width=False)

    columnas_visibles = [
        "rango_semana", 
        "carga_total", 
        "carga_media", 
        "rpe_prom"
    ]

    st.dataframe(
        weekly[columnas_visibles].rename(
            columns={
                "rango_semana": "Semana",
                "carga_total": "Carga total (UA)",
                "carga_media": "Carga media (UA)",
                "rpe_prom": "RPE promedio",
            }
        ),
        hide_index=True,
    )


# ============================================================
# 📉 RPE promedio diario
# ============================================================
def plot_rpe_promedio(df: pd.DataFrame):
    """Promedio de RPE diario del grupo."""
    df = _ensure_fecha(df)
    if "rpe" not in df.columns:
        st.warning("No se encontró la columna RPE.")
        return

    daily = df.groupby("fecha_sesion", as_index=False)["rpe"].mean()

    fig = px.bar(
        daily,
        x="fecha_sesion",
        y="rpe",
        title=t("RPE promedio diario"),
        color="rpe",
        color_continuous_scale=[
            styles.SEMAFORO["verde_oscuro"],
            styles.SEMAFORO["amarillo"],
            styles.SEMAFORO["rojo"],
        ],
    )
    fig.update_layout(
        xaxis_title=t("Fecha"),
        yaxis_title=t("RPE promedio"),
        plot_bgcolor="white",
        font_color=styles.BRAND_TEXT,
        coloraxis_colorbar=dict(title="RPE"),
    )
    st.plotly_chart(fig, use_container_width=False)


# ============================================================
# ⚙️ Monotonía y fatiga aguda
# ============================================================
def plot_monotonia_fatiga(df: pd.DataFrame):
    """Calcula y muestra el índice de monotonía y fatiga aguda por microciclo."""
    df = _ensure_fecha(df)
    if "ua" not in df.columns:
        st.warning("No se encontró la columna UA.")
        return

    weekly = (
        df.groupby(["anio", "semana"], as_index=False)["ua"]
        .agg(["sum", "std", "mean"])
        .reset_index()
        .rename(columns={"sum": "carga_total", "std": "desv_std", "mean": "media"})
    )
    weekly["monotonia"] = weekly["media"] / weekly["desv_std"].replace(0, pd.NA)
    weekly["fatiga_aguda"] = weekly["carga_total"] * weekly["monotonia"]

    fig = px.line(
        weekly,
        x="semana",
        y=["monotonia", "fatiga_aguda"],
        markers=True,
        title=t(":material/stacked_line_chart: Monotonía y Fatiga Aguda"),
        color_discrete_map={
            "monotonia": styles.SEMAFORO["naranja"],
            "fatiga_aguda": styles.SEMAFORO["rojo"],
        },
    )
    fig.update_layout(
        xaxis_title=t("Semana"),
        yaxis_title=t("Valor del índice"),
        plot_bgcolor="white",
        font_color=styles.BRAND_TEXT,
    )
    st.plotly_chart(fig, use_container_width=False)


# ============================================================
# 📈 Relación Carga Aguda : Crónica (ACWR)
# ============================================================
def plot_acwr(df: pd.DataFrame):
    """Calcula la relación ACWR y pinta zonas de referencia con colores del semáforo."""
    df = _ensure_fecha(df)
    if "ua" not in df.columns:
        st.warning("No se encontró la columna UA.")
        return

    weekly = df.groupby(["anio", "semana"], as_index=False)["ua"].sum()
    weekly.rename(columns={"ua": "carga"}, inplace=True)

    # Carga aguda (semana actual) vs carga crónica (media de 3 previas)
    weekly["acwr"] = weekly["carga"] / weekly["carga"].rolling(4, min_periods=2).mean().shift(1)

    fig = px.line(
        weekly,
        x="semana",
        y="acwr",
        markers=True,
        title=t(":material/analytics: Relación Carga Aguda : Crónica (ACWR)"),
        color_discrete_sequence=[styles.SEMAFORO["verde_oscuro"]],
    )

    # --- Zonas semafóricas de referencia ---
    fig.add_hrect(
        y0=0.8, y1=1.3,
        fillcolor=styles.SEMAFORO["verde_claro"], opacity=0.2, line_width=0
    )
    fig.add_hrect(
        y0=1.3, y1=1.5,
        fillcolor=styles.SEMAFORO["amarillo"], opacity=0.2, line_width=0
    )
    fig.add_hrect(
        y0=1.5, y1=2.0,
        fillcolor=styles.SEMAFORO["rojo"], opacity=0.2, line_width=0
    )

    fig.update_layout(
        xaxis_title=t("Semana"),
        yaxis_title=t("ACWR"),
        plot_bgcolor="white",
        font_color=styles.BRAND_TEXT,
    )
    st.plotly_chart(fig, use_container_width=False)

def tabla_resumen(df_filtrado):
    # df_filtrado["jugadora"] = (
    #     df_filtrado["nombre"].fillna("") + " " + df_filtrado["apellido"].fillna("")
    # ).str.strip()

    resumen = (
        df_filtrado.groupby(["nombre_jugadora"], as_index=False)
        .agg(
            carga_total=("ua", "sum"),
            rpe_promedio=("rpe", "mean"),
            sesiones=("ua", "count"),
        )
        .sort_values("carga_total", ascending=False)
    )

    resumen["carga_total"] = resumen["carga_total"].round(0)
    resumen["rpe_promedio"] = resumen["rpe_promedio"].round(2)
    resumen = resumen.fillna(0)
    resumen.index = resumen.index + 1

    st.dataframe(
        resumen.rename(
            columns={
                "nombre_jugadora": "Jugadora",
                "carga_total": "Carga total (UA)",
                "rpe_promedio": "RPE promedio",
                "sesiones": "Nº sesiones",
            }
        ),
    )
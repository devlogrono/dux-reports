from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
from typing import Optional

@dataclass
class RPEFilters:
    jugadores: Optional[list[str]] = None
    turnos: Optional[list[str]] = None
    start: Optional[date] = None
    end: Optional[date] = None

def _prepare_checkout_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    # Keep only checkOut with UA available
    if "tipo" in out.columns:
        out = out[out["tipo"] == "checkOut"]
    # Ensure UA numeric
    if "ua" in out.columns:
        out["ua"] = pd.to_numeric(out["ua"], errors="coerce")
    else:
        out["ua"] = np.nan
    # Ensure fecha_dia exists
    if "fecha" in out.columns and "fecha_sesion" not in out.columns:
        out["fecha_sesion"] = pd.to_datetime(out["fecha_sesion"], errors="coerce").dt.date
    return out.dropna(subset=["fecha_sesion", "ua"])

def _daily_loads(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula las cargas diarias sumando UA (RPE × minutos) y minutos de sesión
    por fecha_sesion. Devuelve un DataFrame con ambas métricas.
    """
    if df.empty:
        return pd.DataFrame(columns=["fecha_sesion", "ua_total", "minutos_total"])

    # --- asegurar columnas necesarias ---
    if "ua" not in df.columns:
        df["ua"] = 0
    if "minutos_sesion" not in df.columns:
        df["minutos_sesion"] = 0

    # --- agrupar ---
    grp = (
        df.groupby("fecha_sesion", as_index=False)[["ua", "minutos_sesion"]]
        .sum(min_count=1)  # evita NaN si todos son NaN
        .rename(columns={"ua": "ua_total", "minutos_sesion": "minutos_total"})
        .sort_values("fecha_sesion")
    )

    return grp

def _current_week_range(end_day: date) -> tuple[date, date]:
    # Monday to Sunday containing end_day
    weekday = end_day.weekday()  # Monday=0
    start = end_day - timedelta(days=weekday)
    end = start + timedelta(days=6)
    return start, end

def _month_range(end_day: date) -> tuple[date, date]:
    start = end_day.replace(day=1)
    if start.month == 12:
        next_month_start = start.replace(year=start.year + 1, month=1, day=1)
    else:
        next_month_start = start.replace(month=start.month + 1, day=1)
    end = next_month_start - timedelta(days=1)
    return start, end

def compute_rpe_metrics(df_raw: pd.DataFrame, flt: RPEFilters) -> dict:
    df = _prepare_checkout_df(df_raw)
    #st.dataframe(df)
    
    #df = _apply_filters(df, flt)
    
    res: dict = {
        "ua_total_dia": None,
        "minutos_sesion": None,
        "carga_semana": None,
        "carga_mes": None,
        "carga_media_semana": None,
        "carga_media_mes": None,
        "monotonia_semana": None,
        "fatiga_aguda": None,
        "fatiga_cronica": None,
        "adaptacion": None,
        "acwr": None,
        "variabilidad_semana": None,
        "daily_table": pd.DataFrame(),
    }

    if df.empty:
        return res

    daily = _daily_loads(df)
    
    res["daily_table"] = daily

    # Determine reference end date
    end_day = flt.end or daily["fecha_sesion"].max()

    # Week metrics (use the week containing end_day)
    week_start, week_end = _current_week_range(end_day)
    daily_week = daily[(daily["fecha_sesion"] >= week_start) & (daily["fecha_sesion"] <= week_end)]
    semana_sum = daily_week["ua_total"].sum() if not daily_week.empty else 0.0
    semana_mean = daily_week["ua_total"].mean() if not daily_week.empty else 0.0
    semana_std = daily_week["ua_total"].std(ddof=0) if len(daily_week) > 1 else 0.0
    res["carga_semana"] = float(semana_sum)
    res["carga_media_semana"] = float(semana_mean)
    res["monotonia_semana"] = float(semana_mean / semana_std) if semana_std and semana_std > 0 else None
    res["variabilidad_semana"] = float(semana_std) if semana_std is not None else None

    # st.dataframe(daily)
    # st.dataframe(daily_week)

    # Day metric (exact end_day)
    day_row = daily[daily["fecha_sesion"] == end_day]
    #st.dataframe(day_row)
    res["ua_total_dia"] = float(day_row["ua_total"].iloc[0]) if not day_row.empty else 0.0

    # Month metrics (calendar month of end_day)
    m_start, m_end = _month_range(end_day)
    daily_month = daily[(daily["fecha_sesion"] >= m_start) & (daily["fecha_sesion"] <= m_end)]
    mes_sum = daily_month["ua_total"].sum() if not daily_month.empty else 0.0
    mes_mean = daily_month["ua_total"].mean() if not daily_month.empty else 0.0
    res["carga_mes"] = float(mes_sum)
    res["carga_media_mes"] = float(mes_mean)

    # Acute/Chronic fatigue and derived indices
    # Acute = sum last 7 days ending at end_day
    last7_start = end_day - timedelta(days=6)
    daily_last7 = daily[(daily["fecha_sesion"] >= last7_start) & (daily["fecha_sesion"] <= end_day)]
    fatiga_aguda = daily_last7["ua_total"].sum() if not daily_last7.empty else 0.0
    res["fatiga_aguda"] = float(fatiga_aguda)

    # Chronic = average daily load over last 28 days
    last28_start = end_day - timedelta(days=27)
    daily_last28 = daily[(daily["fecha_sesion"] >= last28_start) & (daily["fecha_sesion"] <= end_day)]
    fatiga_cronica = daily_last28["ua_total"].mean() if not daily_last28.empty else 0.0
    res["fatiga_cronica"] = float(fatiga_cronica)

    # Adaptation index (example): chronic - acute/7 (normalize acute per day)
    res["adaptacion"] = float(fatiga_cronica - (fatiga_aguda / 7.0))

    # ACWR (acute:chronic) using mean-per-day normalization
    # Avoid divide-by-zero
    res["acwr"] = float((fatiga_aguda / 7.0) / fatiga_cronica) if fatiga_cronica else None
    res["minutos_sesion"] = float(day_row["minutos_total"].iloc[0]) if not day_row.empty else 0.0
    return res

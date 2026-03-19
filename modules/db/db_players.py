import pandas as pd
import streamlit as st
from modules.db.db_client import query
from modules.schema import MAP_POSICIONES

@st.cache_data(ttl=36000, show_spinner=False)
def load_players_db() -> pd.DataFrame | None:
    """
    Carga jugadoras desde la base de datos (futbolistas + informacion_futbolistas).
    """

    sql = """
        SELECT 
            f.id,
            f.identificacion AS id_jugadora,
            f.nombre,
            f.apellido,
            f.competicion AS plantel,
            f.fecha_nacimiento,
            f.genero,
            i.posicion,
            i.dorsal,
            i.nacionalidad,
            i.altura,
            i.peso,
            i.foto_url,
            i.foto_url_drive
        FROM futbolistas f
        LEFT JOIN informacion_futbolistas i 
            ON f.identificacion = i.identificacion
        WHERE f.genero = 'F' and f.id_estado = 1
        ORDER BY f.nombre ASC;
    """

    rows = query(sql)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    #st.dataframe(df)
    
    # Normalización
    df["nombre"] = df["nombre"].astype(str).str.strip().str.title()
    df["apellido"] = df["apellido"].astype(str).str.strip().str.title()

    df["nombre_jugadora"] = (df["nombre"] + " " + df["apellido"]).str.strip().str.upper()

    orden = [
        "id", "id_jugadora", "nombre_jugadora", "nombre", "apellido", "posicion", "plantel",
        "dorsal", "nacionalidad", "altura", "peso", "fecha_nacimiento",
        "genero", "foto_url"
    ]
    df = df[[c for c in orden if c in df.columns]]

    df["posicion"] = df["posicion"].map(MAP_POSICIONES).fillna(df["posicion"])

    df = df.drop(columns=["nombre", "apellido"], errors="ignore")

    return df

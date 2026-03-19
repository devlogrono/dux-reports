import pandas as pd
import streamlit as st
from modules.db.db_client import query

@st.cache_data(ttl=36000, show_spinner=False)
def load_competitions_db():
    """
    Carga competiciones desde la base de datos (tabla 'plantel').
    """

    sql = """
        SELECT 
            id,
            nombre,
            codigo
        FROM plantel
        ORDER BY nombre ASC;
    """

    rows = query(sql)
    if not rows:
        st.error("No se encontraron registros en la tabla 'plantel'.")
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    df["nombre"] = df["nombre"].astype(str).str.strip().str.title()
    df["codigo"] = df["codigo"].astype(str).str.strip().str.upper()

    orden = ["id", "nombre", "codigo"]
    df = df[[c for c in orden if c in df.columns]]

    return df

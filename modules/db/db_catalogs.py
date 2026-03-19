import pandas as pd
import streamlit as st
from modules.db.db_client import query

@st.cache_data(ttl=36000, show_spinner=False)
def load_catalog_list_db(table_name, as_df=False):
    """
    Carga un catálogo desde la base de datos usando el cliente centralizado.
    - table_name: nombre de la tabla a consultar.
    - as_df: True para DataFrame, False para lista de dicts.
    """

    sql = f"SELECT * FROM {table_name} ORDER BY id;"

    rows = query(sql)

    # Si hubo error, query() devuelve None
    if not rows:
        if as_df:
            return pd.DataFrame()
        return []

    df = pd.DataFrame(rows)

    if as_df:
        return df
    return df.to_dict(orient="records")

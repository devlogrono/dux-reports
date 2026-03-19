import streamlit as st
import mysql.connector
from mysql.connector import pooling

@st.cache_resource(show_spinner=False)
def init_connection():
    """Inicializa un pool de conexiones MySQL usando st.secrets."""
    db_config = st.secrets["connections"]["mysql"]

    pool = pooling.MySQLConnectionPool(
        pool_name="main_pool",
        pool_size=15,
        pool_reset_session=True,
        host=db_config["host"],
        user=db_config["username"],
        password=db_config["password"],
        database=db_config["database"],
        port=db_config["port"],
        auth_plugin="mysql_native_password"
    )
    return pool

def get_connection():
    """Obtiene una conexión activa desde el pool."""
    pool = init_connection()
    try:
        conn = pool.get_connection()
        return conn
    except mysql.connector.Error as e:
        st.error(f":material/warning: Error al conectar con MySQL: {e}")
        return None

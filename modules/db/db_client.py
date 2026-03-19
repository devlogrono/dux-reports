import streamlit as st
from modules.db.db_connection import get_connection

# ============================================================
#  🔹 FUNCIÓN GENÉRICA PARA EJECUTAR SELECT
# ============================================================

def query(sql: str, params=None, fetch="all"):
    """
    Executes a SELECT query using a pooled MySQL connection.

    Args:
        sql (str): SQL query.
        params (tuple | dict | None): Query parameters.
        fetch (str): "all", "one", or None.

    Returns:
        list[dict] | dict | True | None:
            - list of rows (dict) if fetch="all"
            - single row (dict) if fetch="one"
            - True for no-fetch operations
            - None on error
    """
    try:
        conn = get_connection()
        if conn is None:
            return None

        cursor = conn.cursor(dictionary=True)

        cursor.execute(sql, params)

        if fetch == "all":
            result = cursor.fetchall()
        elif fetch == "one":
            result = cursor.fetchone()
        else:
            conn.commit()
            result = True

        return result

    except Exception as e:
        st.error(f"Error ejecutando operación: {e} - SQL: {sql}")
        return None

    finally:
        try:
            cursor.close()
        except:
            pass
        try:
            conn.close()  # Vuelve al pool, no cierra la conexión física
        except:
            pass

# ============================================================
#  🔹 FUNCIÓN GENÉRICA PARA EJECUTAR INSERT / UPDATE / DELETE
# ============================================================

def execute(sql: str, params=None):

    """
    Executes an INSERT, UPDATE, or DELETE query.

    Args:
        sql (str): SQL statement.
        params (tuple | dict | None): Query parameters.

    Returns:
        bool: True if committed successfully, False on error.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return True
    
    except Exception as e:
        st.error(f"Error ejecutando operación: {e}")
        return False
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

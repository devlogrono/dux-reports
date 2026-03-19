import pandas as pd
import streamlit as st
from modules.db.db_client import query, execute

def load_active_absences_db(activas: bool = True):
    """
    Carga ausencias desde la BD.
    - activas=False → devuelve todas
    - activas=True → solo las activas hoy
    """

    base_sql = """
        SELECT 
            a.id,
            a.id_jugadora,
            f.nombre,
            f.apellido,
            f.competicion AS plantel,
            a.fecha_inicio,
            a.fecha_fin,
            ta.nombre AS motivo_nombre,
            a.turno,
            a.observacion,
            a.usuario
        FROM ausencias a
        LEFT JOIN futbolistas f 
            ON a.id_jugadora = f.identificacion
        LEFT JOIN tipo_ausencia ta
            ON a.motivo_id = ta.id
        WHERE f.genero = 'F' AND f.id_estado = 1
    """

    if activas:
        base_sql += "AND CURDATE() BETWEEN a.fecha_inicio AND a.fecha_fin"

    rows = query(base_sql)
    df = pd.DataFrame(rows or [])

    if df.empty:
        return df

    # Filtrado por developer
    rol = st.session_state["auth"]["rol"].lower()
    if rol == "developer":
        df = df[df["usuario"] == "developer"]
    else:
        df = df[df["usuario"] != "developer"]

    return df

def insert_absence(id_jugadora, fecha_inicio, fecha_fin, motivo_id, turno, observacion):

    sql = """
        INSERT INTO ausencias 
            (id_jugadora, fecha_inicio, fecha_fin, motivo_id, turno, observacion, usuario)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    params = (
        id_jugadora,
        fecha_inicio,
        fecha_fin,
        motivo_id,
        turno,
        observacion,
        st.session_state["auth"]["name"].lower()
    )

    ok = execute(sql, params)

    return ok

def delete_absences(ids: list[int]) -> tuple[bool, str]:
    """
    Elimina registros de la tabla 'ausencias'.
    """
    if not ids:
        return False, "No se proporcionaron IDs de ausencias."

    placeholders = ",".join(["%s"] * len(ids))

    sql = f"""
        DELETE FROM ausencias
        WHERE id IN ({placeholders})
    """

    ok = execute(sql, tuple(ids))

    if ok:
        return True, f"Se eliminaron {len(ids)} registro(s) correctamente."
    
    return False, "Error al eliminar ausencias."

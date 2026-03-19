import streamlit as st
import pandas as pd
import json
import datetime

from modules.db.db_catalogs import load_catalog_list_db
from modules.db.db_client import query, execute

def get_records_db(as_df: bool = True):
    """
    Carga registros, con joins ya incluidos.
    """

    zonas_anatomicas_df = load_catalog_list_db("zonas_anatomicas", as_df=True)
    map_zonas = dict(zip(zonas_anatomicas_df["id"], zonas_anatomicas_df["nombre"]))

    sql = """
        SELECT 
            w.id,
            w.id_jugadora,
            f.nombre,
            f.apellido,
            f.competicion AS plantel,
            w.fecha_sesion,
            w.tipo,
            w.turno,
            w.recuperacion,
            w.fatiga AS energia,
            w.sueno,
            w.stress,
            w.dolor,
            zs.nombre AS zona_segmento,
            w.zonas_anatomicas_dolor,
            w.lateralidad_dolor,
            w.periodizacion_tactica,
            ec.nombre AS tipo_carga,
            er.nombre AS rehabilitación_readaptación,
            tc.nombre AS condicion,
            w.minutos_sesion,
            w.rpe,
            w.ua,
            w.en_periodo,
            w.observacion,
            w.fecha_hora_registro,
            w.usuario
        FROM template AS w
        LEFT JOIN futbolistas f ON w.id_jugadora = f.identificacion
        LEFT JOIN tipo_carga ec ON w.id_tipo_carga = ec.id
        LEFT JOIN estimulos_readaptacion er ON w.id_tipo_readaptacion = er.id
        LEFT JOIN tipo_condicion tc ON w.id_condicion = tc.id
        LEFT JOIN zonas_segmento zs ON w.id_zona_segmento_dolor = zs.id
        WHERE f.genero = 'F' and f.id_estado = 1
        AND w.estatus_id <= 2
        ORDER BY w.fecha_hora_registro DESC;
    """

    rows = query(sql)
    if not rows:
        return pd.DataFrame() if as_df else []

    df = pd.DataFrame(rows)

    # Procesar JSON
    df["zonas_anatomicas_dolor"] = df["zonas_anatomicas_dolor"].apply(
        lambda x: json.loads(x) if isinstance(x, str) and x.strip().startswith("[") else []
    )

    df["zonas_anatomicas_dolor"] = df["zonas_anatomicas_dolor"].apply(
        lambda ids: [map_zonas.get(i, f"ID {i}") for i in ids]
    )

    # Convertir fechas
    df["fecha_sesion"] = pd.to_datetime(df["fecha_sesion"], errors="coerce").dt.date
    df["fecha_hora_registro"] = pd.to_datetime(df["fecha_hora_registro"], errors="coerce")

    # Filtrar por rol
    rol = st.session_state["auth"]["rol"].lower()
    if rol == "developer":
        df = df[df["usuario"] == "developer"]
    else:
        df = df[df["usuario"] != "developer"]

    # Columna nombre_jugadora
    df.insert(2, "nombre_jugadora", (df["nombre"] + " " + df["apellido"]).str.strip().str.upper())

    df = df.drop(columns=["nombre", "apellido"], errors="ignore")
    
    return df if as_df else df.to_dict("records")
      
def upsert_record_db(record: dict, modo: str = "checkin") -> bool:

    usuario_actual = st.session_state["auth"]["name"].lower()

    # Fecha normalizada
    fecha_sesion = record.get("fecha_sesion")
    if isinstance(fecha_sesion, str):
        fecha_sesion = datetime.date.fromisoformat(fecha_sesion)

    # Buscar si existe
    existing = search_existing_record(record)

    # ============================
    # UPDATE
    # ============================
    if existing:
        if modo.lower() == "checkout":
            sql = """
                UPDATE template
                SET 
                    tipo = 'checkOut',
                    minutos_sesion = %(minutos_sesion)s,
                    rpe = %(rpe)s,
                    ua = %(ua)s,
                    modified_by = %(modified_by)s,
                    estatus_id = 2,
                    updated_at = NOW()
                WHERE id = %(id)s;
            """
            params = {
                "minutos_sesion": record.get("minutos_sesion"),
                "rpe": record.get("rpe"),
                "ua": record.get("ua"),
                "modified_by": usuario_actual,
                "id": existing["id"],
            }

        else:
            st.rerun()
        return execute(sql, params)

    # ============================
    # INSERT (solo checkin)
    # ============================
    if modo.lower() == "checkout":
        st.warning("No existe un check-in previo.")
        return False

    sql = """
        INSERT INTO template (
            id_jugadora, fecha_sesion, tipo, turno, periodizacion_tactica,
            id_tipo_carga, id_tipo_readaptacion, recuperacion, fatiga, sueno,
            stress, dolor, id_zona_segmento_dolor, zonas_anatomicas_dolor, lateralidad_dolor,
            minutos_sesion, rpe, ua, en_periodo, observacion, usuario
        ) VALUES (
            %(id_jugadora)s, %(fecha_sesion)s, %(tipo)s, %(turno)s, %(periodizacion_tactica)s,
            %(id_tipo_carga)s, %(id_tipo_readaptacion)s, %(recuperacion)s, %(fatiga)s, %(sueno)s,
            %(stress)s, %(dolor)s, %(id_zona_segmento_dolor)s, CAST(%(zonas_anatomicas_dolor)s AS JSON),
            %(lateralidad)s, %(minutos_sesion)s, %(rpe)s, %(ua)s,
            %(en_periodo)s, %(observacion)s, %(usuario)s
        );
    """

    params = dict(record)
    params["fecha_sesion"] = fecha_sesion

    return execute(sql, params)

def search_existing_record(record):

    fecha_sesion = record.get("fecha_sesion")
    if isinstance(fecha_sesion, str):
        fecha_sesion = datetime.date.fromisoformat(fecha_sesion)

    rol = st.session_state["auth"]["rol"].lower()
    usuario_condition = (
        "usuario = 'developer'"
        if rol == "developer"
        else "usuario != 'developer'"
    )

    sql = f"""
        SELECT id FROM template
        WHERE id_jugadora = %s
          AND fecha_sesion = %s
          AND turno = %s
          AND estatus_id <= 2
          AND {usuario_condition}
        LIMIT 1;
    """

    params = (
        record["id_jugadora"],
        fecha_sesion,
        record["turno"]
    )

    rows = query(sql, params)
    return rows[0] if rows else None

def delete_record(ids: list[int], deleted_by: str) -> tuple[bool, str]:
    """
    Soft-delete: marca registros de template como eliminados (estatus_id = 3).
    """
    if not ids:
        return False, "No se proporcionaron IDs de template."

    placeholders = ",".join(["%s"] * len(ids))

    sql = f"""
        UPDATE template
        SET 
            estatus_id = 3,
            deleted_at = NOW(),
            deleted_by = %s
        WHERE id IN ({placeholders})
    """

    params = tuple([deleted_by] + ids)

    ok = execute(sql, params)

    if ok:
        return True, f"Se eliminaron {len(ids)} registro(s) correctamente."
    else:
        return False, "Error al eliminar los registros."

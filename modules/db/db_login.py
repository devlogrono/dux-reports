import pandas as pd
import streamlit as st
from modules.db.db_client import query

def load_user_from_db(email: str):
    """
    Obtiene un usuario desde la base de datos según su email.
    Retorna un dict con los datos del usuario o None si no existe.
    """

    sql = """
    SELECT 
        u.id,
        u.email,
        u.password_hash,
        u.name,
        u.lastname,
        r.name AS role_name,
        s.name AS state_name,
        GROUP_CONCAT(p.name ORDER BY p.name SEPARATOR ', ') AS permissions
    FROM users u
    INNER JOIN roles r ON u.role_id = r.id
    INNER JOIN role_permissions rp ON r.id = rp.role_id
    INNER JOIN permissions p ON rp.permission_id = p.id
    INNER JOIN state_user s ON u.state_id = s.id
    WHERE u.email = %s
    GROUP BY 
        u.id, u.email, u.password_hash, u.name, u.lastname, r.name, s.name;
    """

    rows = query(sql, (email,))
    if not rows:
        return None

    return rows[0]

def _load_all_users():

    sql = """
    SELECT 
        u.id,
        u.email,
        u.password_hash,
        u.name,
        u.lastname,
        r.name AS role_name,
        s.name AS state_name,
        GROUP_CONCAT(p.name ORDER BY p.name SEPARATOR ', ') AS permissions
    FROM users u
    INNER JOIN roles r ON u.role_id = r.id
    INNER JOIN role_permissions rp ON r.id = rp.role_id
    INNER JOIN permissions p ON rp.permission_id = p.id
    INNER JOIN state_user s ON u.state_id = s.id
    GROUP BY 
        u.id, u.email, u.password_hash, u.name, u.lastname, r.name, s.name
    ORDER BY 
        u.name, u.lastname;
        """

    rows = query(sql)
    return pd.DataFrame(rows or [])

# Esta SÍ se puede cachear sin problemas
@st.cache_data(ttl=3600, show_spinner=False)
def load_all_users_from_db():
    return _load_all_users()

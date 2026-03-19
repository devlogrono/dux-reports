import streamlit as st
import math
import re
import numpy as np
import requests
import pandas as pd
from urllib.parse import urlparse, urlunparse
import unicodedata
import datetime
from dateutil.relativedelta import relativedelta  # pip install python-dateutil
from datetime import date, timedelta
import re
import base64

def normalize_text(s):
    """Limpia texto eliminando tildes, espacios invisibles y normalizando Unicode."""
    if not isinstance(s, str):
        return ""
    s = s.strip().upper()
    s = unicodedata.normalize("NFKC", s)  # Normaliza forma Unicode
    return s

def get_photo(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Verifica si hubo un error (por ejemplo, 404 o 500)
    except requests.exceptions.RequestException:
        response = None  # Si hay un error, no asignamos nada a response

    return response

def centered_text(text : str):
        st.markdown(f"<h3 style='text-align: center;'>{text}</span></h3>",unsafe_allow_html=True)

def right_caption(text: str):
    st.markdown(
        f"""
        <p style='text-align: right; font-size: 0.85rem; color: #666;'>
            {text}
        </p>
        """,
        unsafe_allow_html=True
    )

def data_format(df: pd.DataFrame):
    # 1. Filtrar garantizando copia
    df = df[df["plantel"] == "1FF"].copy()

    # 2. Conversión segura a datetime
    df["fecha_sesion"] = pd.to_datetime(df["fecha_sesion"], errors="coerce")

    # 3. Nuevas columnas derivadas
    df["fecha_dia"] = df["fecha_sesion"].dt.date
    df["semana"] = df["fecha_sesion"].dt.isocalendar().week
    df["mes"] = df["fecha_sesion"].dt.month

    # 4. Volver a dejar fecha_sesion como date (sin warnings)
    df["fecha_sesion"] = df["fecha_sesion"].dt.date

    # 5. template score
    df["template_score"] = (
        df[["recuperacion", "energia", "sueno", "stress", "dolor"]]
        .sum(axis=1)
    )

    return df

def clean_df(records):
    columnas_excluir = [
        "template_score",
        "fecha_hora_registro",
        "fecha_dia",
        "semana",
        "mes",
    ]
    
    # --- eliminar columnas si existen ---
    df_traducido = records.drop(columns=[col for col in columnas_excluir if col in records.columns])

    #cols = list(df_filtrado.columns)

    # # 2️⃣ Crear un diccionario de renombre limpio → traducido
    # rename_dict = {
    #     col: t(col.replace("_", " ").capitalize())   # elimina "_" y traduce
    #     for col in cols
    # }

    # rename_dict = {
    #     "id_jugadora": t("Idenficación"),
    #     "nombre_jugadora": t("Jugadora"),
    #     "fecha_sesion": t("Fecha"),
    #     "Tipo": t("Tipo"),
    #     "Recuperacion": t("Recuperación"),
    #     "Energia": t("Energía"),
    #     "Sueno": t("Sueño"),
    #     "Estrés": t("Estrés"),
    #     "Dolor": t("Dolor"),
    #     "template_score": t("template Score"),
    # }

    #st.text(rename_dict)

    # 3️⃣ Aplicar el renombre al DataFrame
    #df_traducido = df_filtrado.rename(columns=rename_dict)

    #orden = ["fecha_lesion", "nombre_jugadora", "posicion", "plantel" ,"id_lesion", "lugar", "segmento", "zona_cuerpo", "zona_especifica", "lateralidad", "tipo_lesion", "tipo_especifico", "gravedad", "tipo_tratamiento", "personal_reporta", "estado_lesion", "sesiones"]
    
    # Solo mantener columnas que realmente existen
    #orden_existentes = [c for c in orden if c in df_filtrado.columns]

    #df_filtrado = df_filtrado[orden_existentes + [c for c in df_filtrado.columns if c not in orden_existentes]]
        
    #df_filtrado = df_filtrado[orden + [c for c in df_filtrado.columns if c not in orden]]

    #df_filtrado = df_filtrado.sort_values("fecha_hora_registro", ascending=False)
    df_traducido.reset_index(drop=True, inplace=True)
    df_traducido.index = df_traducido.index + 1
    return df_traducido

def ordenar_df(df: pd.DataFrame, columna: str, ascendente: bool = True) -> pd.DataFrame:
    """
    Ordena un DataFrame por una columna dada y reinicia los índices.

    Parámetros:
        df (pd.DataFrame): DataFrame a ordenar.
        columna (str): Nombre de la columna por la cual ordenar.
        ascendente (bool): True para ascendente, False para descendente.

    Retorna:
        pd.DataFrame: DataFrame ordenado y con índices reiniciados.
    """
    if columna not in df.columns:
        raise ValueError(f"La columna '{columna}' no existe en el DataFrame.")

    df_ordenado = df.sort_values(by=columna, ascending=ascendente, na_position="last").reset_index(drop=True)
    df_ordenado.reset_index(drop=True, inplace=True)

    # Hacer que los índices comiencen desde 1
    df_ordenado.index = df_ordenado.index + 1
    return df_ordenado

def calcular_edad(fecha_nac):
    try:
        # Si viene como string -> convertir
        if isinstance(fecha_nac, str):
            fnac = datetime.datetime.strptime(fecha_nac, "%Y-%m-%d").date()
        elif isinstance(fecha_nac, datetime.date):
            fnac = fecha_nac
        else:
            return "N/A", None

        hoy = datetime.date.today()
        diff = relativedelta(hoy, fnac)

        edad_anos = diff.years
        edad_meses = diff.months

        edad_texto = f"{edad_anos} años y {edad_meses} meses"
        return edad_texto, fnac

    except Exception as e:
        return f"Error: {e}", None

def clean_image_url(url: str) -> str:
    """
    Limpia y normaliza URLs de imágenes:
    - Si es de Google Drive, la convierte a formato directo de descarga/visualización.
    - Si tiene parámetros (como '?size=...' o '&lossy=1'), los elimina.
    - Si ya es una URL limpia, la devuelve igual.
    """

    if not url or not isinstance(url, str):
        return ""

    # --- 1️⃣ Caso Google Drive ---
    if "drive.google.com" in url:
        # Caso A: /file/d/<ID>/view?usp=sharing
        match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?id={file_id}"

        # Caso B: open?id=<ID>
        match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?id={file_id}"

        # Si no encuentra ID, devuelve sin cambios
        return url

    # --- 2️⃣ Caso URLs con parámetros (ej. cdn.resfu.com) ---
    parsed = urlparse(url)
    # Elimina los parámetros de consulta (?size=...&lossy=...)
    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))

    return clean_url

def get_drive_direct_url(url: str) -> str:
    """
    Convierte un enlace de Google Drive en un enlace directo para visualizar o descargar la imagen.

    Args:
        url (str): Enlace de Google Drive (por ejemplo, 'https://drive.google.com/file/d/.../view?usp=sharing')

    Returns:
        str: Enlace directo usable en st.image o <img src="...">
    """
    if not url:
        return ""

    # Detectar si contiene el patrón de ID
    if "drive.google.com" not in url:
        raise ValueError("La URL no parece ser de Google Drive")

    # Buscar el ID del archivo
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError("No se pudo extraer el ID del archivo de la URL")

    file_id = match.group(1)
    return f"https://drive.google.com/uc?export=view&id={file_id}"

def parse_fecha(value):
    """
    Convierte un valor en objeto datetime.date de forma segura.

    Acepta:
        - str en formato ISO ('YYYY-MM-DD' o 'YYYY-MM-DDTHH:MM:SS')
        - datetime.date
        - datetime.datetime
        - None o vacío

    Devuelve:
        datetime.date | None
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None

    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        # Ya es un objeto date
        return value

    if isinstance(value, datetime.datetime):
        # Extraer solo la parte de fecha
        return value.date()

    if isinstance(value, str):
        try:
            # Intentar formato ISO estándar
            return datetime.date.fromisoformat(value.split("T")[0])
        except Exception:
            try:
                # Intentar otros formatos comunes (por compatibilidad)
                return datetime.datetime.strptime(value, "%Y-%m-%d").date()
            except Exception:
                return None

    # Si no es ningún tipo compatible
    return None

def is_valid(value):
    """Devuelve True si el valor no es None, vacío ni NaN."""
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    if isinstance(value, (float, np.floating)) and math.isnan(value):
        return False
    if pd.isna(value):  # cubre np.nan, pd.NaT y similares
        return False
    return True

def to_date(value):
    """Convierte una cadena o datetime a date (YYYY-MM-DD)."""
    if isinstance(value, datetime.date):
        return value
    try:
        return pd.to_datetime(value, errors="coerce").date()
    except Exception:
        return None

def get_date_range_input(
    label: str,
    start_default: date,
    end_default: date,
    max_days: int = 15,
    max_value: date | None = None
) -> tuple[date, date]:
    """
    Selector de rango de fechas con lógica automática.

    - Si el usuario selecciona una sola fecha, la segunda se establece
      automáticamente a (fecha_inicio + max_days), sin pasar de 'max_value' (por defecto: hoy).
    - Si no selecciona ninguna fecha, se usan los valores por defecto.
    - Si selecciona dos fechas, se usan tal cual.

    Parámetros:
        label (str): Título del control.
        start_default (date): Fecha inicial por defecto.
        end_default (date): Fecha final por defecto.
        max_days (int): Días adicionales si solo se elige la fecha inicial (por defecto: 15).
        max_value (date | None): Fecha máxima seleccionable (por defecto: hoy).

    Retorna:
        tuple[date, date]: (fecha_inicio, fecha_fin)
    """
    if max_value is None:
        max_value = date.today()

    # Mostrar control
    rango = st.date_input(
        label,
        value=(start_default, end_default),
        max_value=max_value
    )

    # --- Normalizar resultado ---
    if isinstance(rango, tuple) and len(rango) == 2:
        start, end = rango
    elif isinstance(rango, (list, tuple)) and len(rango) == 1:
        start = rango[0]
        end = min(start + timedelta(days=max_days), max_value)
    elif isinstance(rango, date):
        start = rango
        end = min(start + timedelta(days=max_days), max_value)
    else:
        start, end = start_default, end_default

    return start, end

def set_background_image(image_url: str, fixed: bool = False, overlay: float = 0.0):
    """
    Aplica una imagen de fondo a toda la app Streamlit.

    Parámetros:
        image_url (str): URL o ruta local de la imagen.
        fixed (bool): Si True, el fondo queda fijo (efecto parallax).
        overlay (float): Oscurecer fondo (0.0 = sin overlay, 0.0–1.0).
    """

    attachment = "fixed" if fixed else "scroll"

    overlay_css = ""
    if overlay > 0:
        overlay_css = f"""
        [data-testid="stAppViewContainer"]::before {{
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,{overlay});
            z-index: 0;
        }}
        [data-testid="stAppViewContainer"] > * {{
            position: relative;
            z-index: 1;
        }}
        """

    css = f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background-image: url("{image_url}");
        background-size: cover;
        background-repeat: no-repeat;
        background-position: center center;
        background-attachment: {attachment};
    }}

    [data-testid="stHeader"] {{
        background: rgba(0,0,0,0);
    }}

    {overlay_css}
    </style>
    """

    st.markdown(css, unsafe_allow_html=True)

def set_background_image_local(image_path: str, fixed: bool = False, overlay: float = 0.0):
    """
    Aplica una imagen de fondo local a toda la app Streamlit usando Base64.
    
    Parámetros:
        image_path (str): Ruta de la imagen local. Ej: "assets/images/banner.jpg"
        fixed (bool): Si True, fondo con efecto parallax (fixed).
        overlay (float): Oscurecer fondo (0.0 = sin overlay, 0.0–1.0 máximo).
    """

    # Convertir imagen local a Base64
    with open(image_path, "rb") as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode()

    attachment = "fixed" if fixed else "scroll"

    overlay_css = ""
    if overlay > 0:
        overlay_css = f"""
        [data-testid="stAppViewContainer"]::before {{
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,{overlay});
            z-index: 0;
        }}
        [data-testid="stAppViewContainer"] > * {{
            position: relative;
            z-index: 1;
        }}
        """

    css = f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background-image: url("data:image/jpg;base64,{img_base64}");
        background-size: cover;
        background-repeat: no-repeat;
        background-position: center center;
        background-attachment: {attachment};
    }}

    [data-testid="stHeader"] {{
        background: rgba(0,0,0,0);
    }}

    {overlay_css}
    </style>
    """

    st.markdown(css, unsafe_allow_html=True)

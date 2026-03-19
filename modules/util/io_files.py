import os
import json
import pandas as pd

from pathlib import Path
from pathlib import Path

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Ruta base común para todos los catálogos
CATALOG_DIR = Path("data/catalogos")

def load_catalog_list(name: str, key: str | None = None, field: str = "nombre", as_df: bool = False):
    """
    Carga un catálogo JSON desde la carpeta base.

    Parámetros:
    ----------
    name : str
        Nombre del archivo sin extensión (.json).
        Ej: "segmentos_corporales" -> lee data/catalogos/segmentos_corporales.json
    key : str | None
        Clave raíz del JSON (por defecto igual al nombre del archivo).
        Ej: "zonas_anatomicas", "tratamientos", etc.
    field : str
        Campo que se extrae para la lista (por defecto 'nombre').
    as_df : bool
        Si True, devuelve un DataFrame en lugar de una lista.

    Retorna:
    --------
    list[str] o pandas.DataFrame
    """

    # Ruta completa al archivo
    path = CATALOG_DIR / f"{name}.json"

    if not path.exists():
        raise FileNotFoundError(f"No se encontró el catálogo: {path}")

    # Cargar datos
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Determinar estructura: con o sin clave raíz
    key = key or name
    items = data.get(key, data) if isinstance(data, dict) else data

    if not isinstance(items, list):
        raise ValueError(f"Estructura inesperada en {name}.json")

    # Devuelve DataFrame o lista simple
    if as_df:
        return pd.DataFrame(items)
    else:
        return [item[field] for item in items if field in item]
 

import datetime
from modules.i18n.i18n import t

# Diccionario de equivalencias
MAP_POSICIONES = {
    "POR": "Portera",
    "DEF": "Defensa",
    "MC": "Centro",
    "DEL": "Delantera"
}

# === Diccionario para traducir días ===
DIAS_SEMANA = {
    "Monday": "Lunes",
    "Tuesday": "Martes",
    "Wednesday": "Miércoles",
    "Thursday": "Jueves",
    "Friday": "Viernes",
    "Saturday": "Sábado",
    "Sunday": "Domingo"
}

OPCIONES_TURNO = {
    "Todos": t("Todos"),
    "Turno 1": t("Turno 1"),
    "Turno 2": t("Turno 2"),
    "Turno 3": t("Turno 3")
}

def new_base_record(id_jugadora: str, username: str, tipo: str) -> dict:
    """Create a base record structure with defaults.

    tipo: 'checkIn' | 'checkOut'
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d")
    return {
        "id_jugadora": id_jugadora,
        #"nombre": nombre_jugadora,
        "fecha_sesion": now,
        "tipo": tipo,
        "turno": "",
        # Check-in fields
        "periodizacion_tactica": "",
        "id_tipo_carga": "",
        "id_tipo_condicion": "",
        "id_tipo_readaptacion": "",
        "recuperacion": None,
        "fatiga": None,
        "sueno": None,
        "stress": None,
        "dolor": None,
        "id_zona_segmento_dolor": None,
        "zonas_anatomicas_dolor": [],
        "lateralidad": None,
        # Check-out fields
        "minutos_sesion": None,
        "rpe": None,
        "ua": None,
        # Extras
        "en_periodo": False,
        "observacion": "",
        "fecha_hora_registro": datetime.datetime.now().isoformat(),
        "usuario": username
    }



from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from dux import db
from dux.common.physical.queries import (
    get_physical_competitions,
    get_physical_full_records,
    get_physical_overview_stats,
    get_physical_players,
    get_physical_records,
)
from dux.common.physical.transforms import build_record_antropometrico


def build_physical_index_context(plantel: str | None = None) -> dict[str, Any]:
    """
    Construye el contexto de la pantalla inicial de Physical.
    """
    competitions = get_physical_competitions()
    stats = get_physical_overview_stats(plantel=plantel)
    recent_records = get_physical_records(plantel=plantel, limit=15)
    raw_records = get_physical_full_records(plantel=plantel)
    records = [build_record_antropometrico(record) for record in raw_records]
    alert_summary = _build_inicio_alerts(records)

    selected_competition = None
    if plantel:
        selected_competition = next(
            (c for c in competitions if str(c.get("codigo")) == str(plantel)),
            None,
        )

    return {
        "competitions": competitions,
        "plantel": plantel,
        "selected_competition": selected_competition,
        "stats": stats,
        "recent_records": recent_records,
        "alert_summary": alert_summary,
        "alert_cards": alert_summary["cards"],
        "recent_worsening_rows": alert_summary["worsening_rows"],
    }


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _coerce_date_value(value):
    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return value


def _calculate_age(value) -> int | None:
    birth_date = _coerce_date_value(value)
    if birth_date is None:
        return None
    today = datetime.today().date()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def normalize_player_photo_url(foto_url=None, foto_url_drive=None) -> str | None:
    def normalize(value) -> str | None:
        if value is None:
            return None
        url = str(value).strip()
        if not url or url.lower() in {"no disponible", "none", "null", "nan", "-"}:
            return None

        drive_match = re.search(r"drive\.google\.com/file/d/([^/]+)", url)
        if drive_match:
            return f"https://drive.google.com/uc?export=view&id={drive_match.group(1)}"

        drive_id_match = re.search(r"[?&]id=([^&]+)", url)
        if "drive.google.com" in url and drive_id_match:
            return f"https://drive.google.com/uc?export=view&id={drive_id_match.group(1)}"

        if re.fullmatch(r"[-\w]{20,}", url):
            return f"https://drive.google.com/uc?export=view&id={url}"

        return url

    direct_url = normalize(foto_url)
    if direct_url:
        return direct_url
    return normalize(foto_url_drive)


def _clean_image_url(value) -> str | None:
    if not value:
        return None
    return normalize_player_photo_url(foto_url=value)


def get_physical_player_photo_sources(identificacion: str) -> dict[str, Any]:
    """
    Lee las URLs de foto de informacion_futbolistas para servirlas desde backend.
    """
    sql = text(
        """
        SELECT foto_url, foto_url_drive
        FROM informacion_futbolistas
        WHERE identificacion = :identificacion
        LIMIT 1;
        """
    )
    row = db.session.execute(sql, {"identificacion": identificacion}).mappings().first()
    return dict(row) if row else {}


def _sort_records(records: list[dict[str, Any]], reverse: bool = True) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda r: (
            _coerce_date_value(r.get("fecha_medicion")) is not None,
            _coerce_date_value(r.get("fecha_medicion")),
            _coerce_date_value(r.get("created_at")) is not None,
            _coerce_date_value(r.get("created_at")),
            r.get("id_isak") or 0,
        ),
        reverse=reverse,
    )


def _latest_records_by_player(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_by_player: dict[Any, dict[str, Any]] = {}

    for record in _sort_records(records, reverse=True):
        player_id = record.get("identificacion") or record.get("nombre_jugadora")
        if player_id and player_id not in latest_by_player:
            latest_by_player[player_id] = record

    return list(latest_by_player.values())


def _records_by_player(records: list[dict[str, Any]]) -> dict[Any, list[dict[str, Any]]]:
    records_by_player: dict[Any, list[dict[str, Any]]] = {}
    for record in records:
        player_id = record.get("identificacion") or record.get("nombre_jugadora")
        if player_id:
            records_by_player.setdefault(player_id, []).append(record)
    return records_by_player


def _player_options_from_records(
    records: list[dict[str, Any]],
    player_info_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    player_info_by_id = player_info_by_id or {}
    options = []
    for record in _latest_records_by_player(records):
        player_id = record.get("identificacion") or record.get("nombre_jugadora")
        if not player_id:
            continue
        info = player_info_by_id.get(str(player_id), {})
        options.append(
            {
                "id": str(player_id),
                "nombre": str(info.get("nombre_jugadora") or record.get("nombre_jugadora") or player_id).strip(),
                "plantel": info.get("plantel") or record.get("plantel"),
                "fecha_ultima": record.get("fecha_medicion"),
            }
        )

    return sorted(options, key=lambda item: item["nombre"])


def _count_alert(records: list[dict[str, Any]], metric: str, threshold: float, operator: str) -> int:
    total = 0
    for record in records:
        value = _safe_float(record.get(metric))
        if value is None:
            continue
        if operator == "gt" and value > threshold:
            total += 1
        elif operator == "lt" and value < threshold:
            total += 1
    return total


def _worsening_changes(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, str]:
    changes = {}

    grasa_curr = _safe_float(current.get("ajuste_adiposa_pct"))
    grasa_prev = _safe_float(previous.get("ajuste_adiposa_pct"))
    if grasa_curr is not None and grasa_prev is not None and grasa_curr > grasa_prev:
        changes["grasa"] = f"+{grasa_curr - grasa_prev:.1f}"

    musculo_curr = _safe_float(current.get("ajuste_muscular_pct"))
    musculo_prev = _safe_float(previous.get("ajuste_muscular_pct"))
    if musculo_curr is not None and musculo_prev is not None and musculo_curr < musculo_prev:
        changes["musculo"] = f"{musculo_curr - musculo_prev:.1f}"

    pliegues_curr = _safe_float(current.get("suma_6_pliegues_mm"))
    pliegues_prev = _safe_float(previous.get("suma_6_pliegues_mm"))
    if pliegues_curr is not None and pliegues_prev is not None and pliegues_curr > pliegues_prev:
        changes["pliegues"] = f"+{pliegues_curr - pliegues_prev:.1f}"

    imo_curr = _safe_float(current.get("idx_musculo_oseo"))
    imo_prev = _safe_float(previous.get("idx_musculo_oseo"))
    if imo_curr is not None and imo_prev is not None and imo_curr < imo_prev:
        changes["imo"] = f"{imo_curr - imo_prev:.2f}"

    return changes


def _build_inicio_alerts(records: list[dict[str, Any]]) -> dict[str, Any]:
    latest_records = _latest_records_by_player(records)
    pairs = _player_comparison_pairs(records, "ultima")
    previous_records = [pair["previous"] for pair in pairs]

    alert_defs = [
        {
            "key": "grasa_elevada",
            "title": "Grasa elevada",
            "help": "Jugadoras con porcentaje de grasa superior a 24%.",
            "metric": "ajuste_adiposa_pct",
            "threshold": 24,
            "operator": "gt",
        },
        {
            "key": "musculo_bajo",
            "title": "Musculo bajo",
            "help": "Jugadoras con porcentaje muscular inferior a 40%.",
            "metric": "ajuste_muscular_pct",
            "threshold": 40,
            "operator": "lt",
        },
        {
            "key": "pliegues_elevados",
            "title": "Pliegues elevados",
            "help": "Jugadoras con suma de 6 pliegues superior a 90 mm.",
            "metric": "suma_6_pliegues_mm",
            "threshold": 90,
            "operator": "gt",
        },
        {
            "key": "imo_mejorable",
            "title": "IMO mejorable",
            "help": "Jugadoras con indice musculo / oseo inferior a 3.5.",
            "metric": "idx_musculo_oseo",
            "threshold": 3.5,
            "operator": "lt",
        },
    ]

    cards = []
    for alert in alert_defs:
        current_count = _count_alert(
            latest_records,
            alert["metric"],
            alert["threshold"],
            alert["operator"],
        )
        previous_count = _count_alert(
            previous_records,
            alert["metric"],
            alert["threshold"],
            alert["operator"],
        )
        delta = current_count - previous_count
        cards.append(
            {
                "key": alert["key"],
                "title": alert["title"],
                "value": current_count,
                "delta": delta,
                "help": alert["help"],
                "tone": "danger" if current_count else "success",
            }
        )

    worsening_rows = []
    for pair in pairs:
        changes = _worsening_changes(pair["current"], pair["previous"])
        if not changes:
            continue
        worsening_rows.append(
            {
                "identificacion": pair.get("identificacion"),
                "jugadora": pair.get("nombre_jugadora") or pair.get("identificacion") or "",
                "n_metricas": len(changes),
                "grasa": changes.get("grasa"),
                "musculo": changes.get("musculo"),
                "pliegues": changes.get("pliegues"),
                "imo": changes.get("imo"),
            }
        )

    worsening_rows = sorted(
        worsening_rows,
        key=lambda row: (-row["n_metricas"], str(row["jugadora"])),
    )

    cards.append(
        {
            "key": "empeoramiento_reciente",
            "title": "Empeoramientos",
            "value": len(worsening_rows),
            "delta": None,
            "help": "Jugadoras cuya ultima medicion empeora respecto a la anterior en alguna variable clave.",
            "tone": "danger" if worsening_rows else "success",
        }
    )

    return {
        "cards": cards,
        "worsening_rows": worsening_rows,
        "latest_players": len(latest_records),
        "players_with_previous": len(pairs),
    }


def _records_from_last_months(records: list[dict[str, Any]], months: int = 6) -> list[dict[str, Any]]:
    dated_records = [r for r in records if _coerce_date_value(r.get("fecha_medicion")) is not None]
    if not dated_records:
        return []

    max_date = max(_coerce_date_value(r["fecha_medicion"]) for r in dated_records)
    limit_date = max_date - timedelta(days=months * 30)

    return [r for r in dated_records if _coerce_date_value(r["fecha_medicion"]) >= limit_date]


def _period_records(records: list[dict[str, Any]], periodo: str) -> tuple[list[dict[str, Any]], str]:
    if periodo == "historico":
        return _records_from_last_months(records), "ultimos 6 meses"

    return _latest_records_by_player(records), "ultima medicion"


def _metric_value(records: list[dict[str, Any]], metric: str, periodo: str) -> float | None:
    if periodo != "historico":
        return _mean([_safe_float(r.get(metric)) for r in records])

    values_by_player: dict[Any, list[float]] = {}
    for record in records:
        player_id = record.get("identificacion") or record.get("nombre_jugadora")
        value = _safe_float(record.get(metric))
        if player_id and value is not None:
            values_by_player.setdefault(player_id, []).append(value)

    player_means = [_mean(values) for values in values_by_player.values()]
    return _mean(player_means)


def _metric_delta(records: list[dict[str, Any]], metric: str, periodo: str) -> tuple[list[float], float | None]:
    comparable: list[tuple[float, float]] = []

    records_by_player: dict[Any, list[dict[str, Any]]] = {}
    for record in records:
        player_id = record.get("identificacion") or record.get("nombre_jugadora")
        if player_id:
            records_by_player.setdefault(player_id, []).append(record)

    for player_records in records_by_player.values():
        valid_records = [
            r for r in _sort_records(player_records, reverse=True)
            if _safe_float(r.get(metric)) is not None
        ]

        if periodo == "historico":
            valid_records = _sort_records(valid_records, reverse=False)

        if len(valid_records) < 2:
            continue

        if periodo == "historico":
            previous = _safe_float(valid_records[0].get(metric))
            current = _safe_float(valid_records[-1].get(metric))
        else:
            current = _safe_float(valid_records[0].get(metric))
            previous = _safe_float(valid_records[1].get(metric))

        if previous is not None and current is not None:
            comparable.append((previous, current))

    if not comparable:
        return [], None

    previous_mean = _mean([previous for previous, _ in comparable])
    current_mean = _mean([current for _, current in comparable])

    if previous_mean is None or current_mean is None:
        return [], None

    if previous_mean == 0:
        return [previous_mean, current_mean], 0

    return [previous_mean, current_mean], ((current_mean - previous_mean) / previous_mean) * 100


def _metric_status(metric: str, value: float | None) -> tuple[str, str, str]:
    if value is None:
        return "Sin datos", "secondary", "No hay datos suficientes para valorar esta metrica."

    if metric == "peso_medio":
        return "Descriptivo", "secondary", "Indicador de la masa corporal total media del equipo."

    if metric == "grasa_media":
        if value < 14:
            return "Muy bajo", "warning", "Vigilar disponibilidad energetica y contexto fisiologico."
        if value <= 20:
            return "Adecuado", "success", "Rango funcional para futbol femenino."
        if value <= 24:
            return "Moderado", "warning", "Con margen de optimizacion."
        return "Elevado", "danger", "Por encima del perfil deseado de rendimiento."

    if metric == "musculo_medio":
        if value < 40:
            return "Bajo", "warning", "Nivel de masa muscular mejorable para el alto rendimiento."
        if value <= 45:
            return "Adecuado", "success", "Buen nivel de desarrollo muscular para la categoria."
        return "Excelente", "excellent", "Perfil muscular muy favorable para potencia y proteccion estructural."

    if metric == "imo_medio":
        if value < 3.5:
            return "Bajo", "warning", "Relacion musculo / oseo por desarrollar."
        if value <= 4.2:
            return "Adecuado", "success", "Relacion favorable para el rendimiento."
        return "Excelente", "excellent", "Perfil estructural muy favorable."

    if metric == "pliegues_media":
        if value < 50:
            return "Excelente", "excellent", "Perfil de alta competicion."
        if value <= 70:
            return "Adecuado", "success", "Rango funcional para la mayoria de posiciones."
        if value <= 90:
            return "Moderado", "warning", "Con margen de ajuste nutricional y de carga."
        return "Elevado", "danger", "Fuera del rango objetivo de rendimiento."

    return "Descriptivo", "secondary", ""


def _reference_ranges() -> list[dict[str, Any]]:
    return [
        {
            "key": "grasa",
            "label": "% Grasa",
            "items": [
                {"status": "Muy bajo", "range": "<14%", "class": "warning", "interpretation": "Vigilar disponibilidad energetica y contexto fisiologico."},
                {"status": "Adecuado", "range": "14-20%", "class": "success", "interpretation": "Rango funcional para futbol femenino."},
                {"status": "Moderado", "range": "20-24%", "class": "warning", "interpretation": "Con margen de optimizacion."},
                {"status": "Elevado", "range": ">24%", "class": "danger", "interpretation": "Por encima del perfil deseado de rendimiento."},
            ],
        },
        {
            "key": "musculo",
            "label": "% Muscular",
            "items": [
                {"status": "Bajo", "range": "<40%", "class": "warning", "interpretation": "Nivel de masa muscular mejorable para el alto rendimiento."},
                {"status": "Adecuado", "range": "40-45%", "class": "success", "interpretation": "Buen nivel de desarrollo muscular para la categoria."},
                {"status": "Excelente", "range": ">45%", "class": "excellent", "interpretation": "Perfil muscular muy favorable para potencia y proteccion estructural."},
            ],
        },
        {
            "key": "imo",
            "label": "Indice M/O",
            "items": [
                {"status": "Bajo", "range": "<3.5", "class": "warning", "interpretation": "Relacion musculo / oseo por desarrollar."},
                {"status": "Adecuado", "range": "3.5-4.2", "class": "success", "interpretation": "Relacion favorable para el rendimiento."},
                {"status": "Excelente", "range": ">4.2", "class": "excellent", "interpretation": "Perfil estructural muy favorable."},
            ],
        },
        {
            "key": "pliegues",
            "label": "6 pliegues",
            "items": [
                {"status": "Excelente", "range": "<50 mm", "class": "excellent", "interpretation": "Perfil de alta competicion."},
                {"status": "Adecuado", "range": "50-70 mm", "class": "success", "interpretation": "Rango funcional para la mayoria de posiciones."},
                {"status": "Moderado", "range": "70-90 mm", "class": "warning", "interpretation": "Con margen de ajuste nutricional y de carga."},
                {"status": "Elevado", "range": ">90 mm", "class": "danger", "interpretation": "Fuera del rango objetivo de rendimiento."},
            ],
        },
    ]


def _individual_metric_config() -> list[dict[str, Any]]:
    return [
        {"key": "peso", "source": "peso_bruto_kg", "label": "Peso", "unit": "kg", "decimals": 1},
        {"key": "talla", "source": "talla_corporal_cm", "label": "Talla", "unit": "cm", "decimals": 1},
        {"key": "grasa", "source": "ajuste_adiposa_pct", "label": "% Grasa", "unit": "%", "decimals": 1},
        {"key": "musculo", "source": "ajuste_muscular_pct", "label": "% Muscular", "unit": "%", "decimals": 1},
        {"key": "imo", "source": "idx_musculo_oseo", "label": "Indice M/O", "unit": "", "decimals": 2},
        {"key": "pliegues", "source": "suma_6_pliegues_mm", "label": "Suma 6 pliegues", "unit": "mm", "decimals": 1},
        {"key": "masa_osea", "source": "masa_osea_kg", "label": "Masa osea", "unit": "kg", "decimals": 1},
        {"key": "n_mediciones", "source": None, "label": "N mediciones", "unit": "", "decimals": 0},
    ]


def _metric_delta_pct(current_value: float | None, previous_value: float | None) -> float | None:
    if current_value is None or previous_value is None or previous_value == 0:
        return None
    return ((current_value - previous_value) / previous_value) * 100


def _individual_metric_status(metric_key: str, value: float | None) -> tuple[str, str, str]:
    if metric_key in {"peso", "talla", "masa_osea", "n_mediciones"}:
        if value is None:
            return "Sin datos", "secondary", "No hay datos suficientes para valorar esta metrica."
        return "Descriptivo", "secondary", "Variable descriptiva; interpretar en contexto individual y evolutivo."

    status_map = {
        "grasa": "grasa_media",
        "musculo": "musculo_medio",
        "imo": "imo_medio",
        "pliegues": "pliegues_media",
    }
    return _metric_status(status_map.get(metric_key, metric_key), value)


def _build_individual_kpis(
    latest_record: dict[str, Any] | None,
    previous_record: dict[str, Any] | None,
    total_measurements: int = 0,
) -> list[dict[str, Any]]:
    kpis = []
    for config in _individual_metric_config():
        if config["key"] == "n_mediciones":
            current_value = float(total_measurements)
            previous_value = None
            delta = None
        else:
            current_value = _safe_float(latest_record.get(config["source"])) if latest_record else None
            previous_value = _safe_float(previous_record.get(config["source"])) if previous_record else None
            delta = _metric_delta_pct(current_value, previous_value)
        status, status_class, interpretation = _individual_metric_status(config["key"], current_value)
        kpis.append(
            {
                **config,
                "value": current_value,
                "previous_value": previous_value,
                "delta_pct": delta,
                "status": status,
                "status_class": status_class,
                "interpretation": interpretation,
            }
        )
    return kpis


def _build_individual_interpretation(kpis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = ["peso", "talla", "masa_osea", "grasa", "musculo", "pliegues", "imo"]
    by_key = {metric["key"]: metric for metric in kpis}
    return [by_key[key] for key in order if key in by_key]


def _format_record_date_label(record: dict[str, Any]) -> str:
    date_value = _coerce_date_value(record.get("fecha_medicion"))
    if date_value is not None:
        return date_value.strftime("%d/%m/%Y")
    return str(record.get("fecha_medicion") or record.get("id_isak") or "")


def _perfil_group_interpretation(group: str | None) -> str:
    if group == "G1":
        return "Perfil favorable, con baja adiposidad subcutanea y buena relacion musculo-osea. Compatible con una composicion corporal eficiente para el rendimiento."
    if group == "G2":
        return "Perfil con buena base muscular, aunque con margen de mejora en adiposidad subcutanea. El foco principal estaria en optimizar la composicion corporal sin comprometer la masa funcional."
    if group == "G3":
        return "Perfil ligero, con baja adiposidad pero menor desarrollo relativo en la relacion musculo-osea. Puede existir margen de mejora estructural y de fuerza."
    if group == "G4":
        return "Perfil menos favorable, con mayor adiposidad subcutanea y menor relacion musculo-osea relativa. El foco estaria en mejorar composicion corporal y desarrollo funcional."
    return "Sin datos suficientes."


def _build_individual_perfil_antropometrico_chart(
    records: list[dict[str, Any]],
    selected_player_id: str | None,
) -> dict[str, Any]:
    chart = _build_perfil_antropometrico_chart(records)
    highlighted = None

    for point in chart["points"]:
        is_highlighted = False
        source_id = point.get("identificacion")
        if selected_player_id and source_id is not None:
            is_highlighted = str(source_id) == str(selected_player_id)
        point["highlighted"] = is_highlighted
        if is_highlighted:
            highlighted = point

    return {
        **chart,
        "highlighted": highlighted,
        "interpretation": _perfil_group_interpretation(highlighted.get("grupo") if highlighted else None)
        #"caption": "Perfil antropometrico individual dentro del grupo, destacando la ultima medicion disponible de la jugadora.",
    }


def _trend_sentence(metric: str, delta: float | None) -> str | None:
    if delta is None:
        return None

    if metric == "grasa":
        if abs(delta) < 1:
            return f"Estabilidad del porcentaje graso ({delta:+.1f} pp)"
        if delta > 0:
            label = "Ligero aumento" if abs(delta) < 2 else "Aumento marcado"
            return f"{label} del porcentaje graso ({delta:+.1f} pp)"
        label = "Ligera reduccion" if abs(delta) < 2 else "Reduccion marcada"
        return f"{label} del porcentaje graso ({delta:+.1f} pp)"

    if abs(delta) < 0.8:
        return f"Estabilidad del peso corporal ({delta:+.1f} kg)"
    if delta > 0:
        label = "Ligero aumento" if abs(delta) < 1.5 else "Aumento marcado"
        return f"{label} del peso corporal ({delta:+.1f} kg)"
    label = "Ligera reduccion" if abs(delta) < 1.5 else "Reduccion marcada"
    return f"{label} del peso corporal ({delta:+.1f} kg)"


def _build_individual_peso_grasa_chart(player_records: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_records = _sort_records(player_records, reverse=False)
    points = []

    for record in sorted_records:
        peso = _safe_float(record.get("peso_bruto_kg"))
        grasa = _safe_float(record.get("ajuste_adiposa_pct"))
        if peso is None and grasa is None:
            continue
        points.append(
            {
                "fecha": _format_record_date_label(record),
                "peso": round(peso, 4) if peso is not None else None,
                "grasa": round(grasa, 4) if grasa is not None else None,
            }
        )

    valid_peso = [point["peso"] for point in points if point["peso"] is not None]
    valid_grasa = [point["grasa"] for point in points if point["grasa"] is not None]
    has_enough_data = len(points) >= 2 and len(valid_peso) >= 2 and len(valid_grasa) >= 2

    trends = {
        "last_vs_previous": [],
        "first_vs_last": [],
    }
    if has_enough_data:
        last = points[-1]
        previous = points[-2]
        first = points[0]
        trends["last_vs_previous"] = [
            sentence for sentence in (
                _trend_sentence("grasa", last["grasa"] - previous["grasa"] if last["grasa"] is not None and previous["grasa"] is not None else None),
                _trend_sentence("peso", last["peso"] - previous["peso"] if last["peso"] is not None and previous["peso"] is not None else None),
            )
            if sentence
        ]
        trends["first_vs_last"] = [
            sentence for sentence in (
                _trend_sentence("grasa", last["grasa"] - first["grasa"] if last["grasa"] is not None and first["grasa"] is not None else None),
                _trend_sentence("peso", last["peso"] - first["peso"] if last["peso"] is not None and first["peso"] is not None else None),
            )
            if sentence
        ]

    weight_range = None
    if valid_peso:
        peso_min = min(valid_peso)
        peso_max = max(valid_peso)
        margin = max(0.5, (peso_max - peso_min) * 0.8)
        weight_range = [round(peso_min - margin, 2), round(peso_max + margin, 2)]

    return {
        "points": points,
        "has_enough_data": has_enough_data,
        "weight_range": weight_range,
        "caption": "Evolucion historica del peso corporal y del porcentaje de grasa. Permite contextualizar si los cambios de peso se acompanan de una mejora o empeoramiento de la composicion corporal.",
        "trends": trends,
    }


def build_physical_individual_context(
    plantel: str | None = None,
    jugadora: str | None = None,
    periodo: str = "ultima",
) -> dict[str, Any]:
    """
    Contexto read-only de la primera vista individual de Physical.
    """
    if periodo not in {"ultima", "historico"}:
        periodo = "ultima"

    competitions = get_physical_competitions()
    player_info = get_physical_players(plantel=plantel)
    player_info_by_id = {
        str(player.get("identificacion")): player
        for player in player_info
        if player.get("identificacion")
    }
    raw_records = get_physical_full_records(plantel=plantel)
    records = [build_record_antropometrico(record) for record in raw_records]
    players = _player_options_from_records(records, player_info_by_id)

    selected_player_id = str(jugadora) if jugadora else (players[0]["id"] if players else None)
    if selected_player_id and players and selected_player_id not in {player["id"] for player in players}:
        selected_player_id = players[0]["id"]

    records_by_player = _records_by_player(records)
    player_records = records_by_player.get(selected_player_id, []) if selected_player_id else []

    if not player_records and selected_player_id is not None:
        for player_id, candidate_records in records_by_player.items():
            if str(player_id) == selected_player_id:
                player_records = candidate_records
                selected_player_id = str(player_id)
                break

    player_records = _sort_records(player_records, reverse=True)
    latest_record = player_records[0] if player_records else None
    previous_record = player_records[1] if len(player_records) > 1 else None
    period_records = _records_from_last_months(player_records) if periodo == "historico" else ([latest_record] if latest_record else [])

    selected_player = None
    if selected_player_id:
        selected_player = next(
            (player for player in players if player["id"] == str(selected_player_id)),
            None,
        )

    selected_player_info = player_info_by_id.get(str(selected_player_id), {}) if selected_player_id else {}
    if selected_player is None and latest_record:
        selected_player = {
            "id": str(latest_record.get("identificacion") or latest_record.get("nombre_jugadora")),
            "nombre": str(latest_record.get("nombre_jugadora") or "").strip(),
            "plantel": latest_record.get("plantel"),
            "fecha_ultima": latest_record.get("fecha_medicion"),
        }

    if selected_player:
        player_photo_url = normalize_player_photo_url(
            foto_url=selected_player_info.get("foto_url"),
            foto_url_drive=selected_player_info.get("foto_url_drive"),
        )
        selected_player = {
            **selected_player,
            "dorsal": selected_player_info.get("dorsal"),
            "nacionalidad": selected_player_info.get("nacionalidad"),
            "posicion": selected_player_info.get("posicion"),
            "fecha_nacimiento": selected_player_info.get("fecha_nacimiento"),
            "edad": _calculate_age(selected_player_info.get("fecha_nacimiento")),
            "foto_url": _clean_image_url(selected_player_info.get("foto_url")),
            "foto_url_drive": _clean_image_url(selected_player_info.get("foto_url_drive")),
            "player_photo_url": player_photo_url,
        }
    else:
        player_photo_url = None

    individual_kpis = _build_individual_kpis(latest_record, previous_record, len(player_records))
    individual_charts = {
        "perfil_antropometrico": _build_individual_perfil_antropometrico_chart(records, selected_player_id),
        "peso_grasa": _build_individual_peso_grasa_chart(player_records),
    }

    return {
        "competitions": competitions,
        "plantel": plantel,
        "periodo": periodo,
        "period_label": "ultimos 6 meses" if periodo == "historico" else "ultima medicion",
        "players": players,
        "selected_player_id": selected_player_id,
        "selected_player": selected_player,
        "player_photo_url": player_photo_url,
        "player_records": player_records,
        "period_records": period_records,
        "latest_record": latest_record,
        "previous_record": previous_record,
        "individual_kpis": individual_kpis,
        "individual_charts": individual_charts,
        "interpretation_rows": _build_individual_interpretation(individual_kpis),
        "reference_ranges": _reference_ranges(),
    }


def _build_group_metrics(
    records: list[dict[str, Any]],
    all_records: list[dict[str, Any]],
    periodo: str,
) -> list[dict[str, Any]]:
    metric_config = [
        ("peso_medio", "peso_bruto_kg", "Peso medio del grupo", "kg", 1),
        ("grasa_media", "ajuste_adiposa_pct", "Porcentaje de grasa medio", "%", 1),
        ("musculo_medio", "ajuste_muscular_pct", "Porcentaje muscular medio", "%", 1),
        ("imo_medio", "idx_musculo_oseo", "Indice musculo / oseo medio", "", 2),
        ("pliegues_media", "suma_6_pliegues_mm", "Suma 6 pliegues", "mm", 1),
    ]

    metrics = []
    delta_base = records if periodo == "historico" else all_records

    for key, source, label, unit, decimals in metric_config:
        value = _metric_value(records, source, periodo)
        trend, delta = _metric_delta(delta_base, source, periodo)
        status, status_class, interpretation = _metric_status(key, value)
        metrics.append(
            {
                "key": key,
                "source": source,
                "label": label,
                "value": value,
                "unit": unit,
                "decimals": decimals,
                "delta": delta,
                "trend": trend,
                "status": status,
                "status_class": status_class,
                "interpretation": interpretation,
            }
        )

    return metrics


def _build_technical_summary(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    return {metric["key"]: metric for metric in metrics}


def _perfil_cuadrante(x_value: float, y_value: float) -> tuple[str, str]:
    if x_value <= 70 and y_value >= 3.80:
        return "G1", "#2ECC71"
    if x_value > 70 and y_value >= 3.80:
        return "G2", "#F1C40F"
    if x_value <= 70 and y_value < 3.80:
        return "G3", "#F39C12"
    return "G4", "#E74C3C"


def _build_perfil_antropometrico_chart(records: list[dict[str, Any]]) -> dict[str, Any]:
    plot_records = _latest_records_by_player(records)
    points = []

    for record in plot_records:
        x_value = _safe_float(record.get("suma_6_pliegues_mm"))
        y_value = _safe_float(record.get("idx_musculo_oseo"))
        if x_value is None or y_value is None:
            continue

        group, color = _perfil_cuadrante(x_value, y_value)
        player_name = str(record.get("nombre_jugadora") or "").strip()
        points.append(
            {
                "identificacion": record.get("identificacion"),
                "jugadora": player_name,
                "x": round(x_value, 2),
                "y": round(y_value, 4),
                "grupo": group,
                "color": color,
                "label": f"{player_name.title()} ({x_value:.1f}; {y_value:.2f})",
            }
        )

    counts = {group: 0 for group in ("G1", "G2", "G3", "G4")}
    for point in points:
        counts[point["grupo"]] += 1

    y_values = [point["y"] for point in points]
    y_min = min(3.2, min(y_values) - 0.1) if y_values else 3.2
    y_max = max(4.5, max(y_values) + 0.1) if y_values else 4.5

    return {
        "points": points,
        "counts": counts,
        "x_cut": 70,
        "y_cut": 3.80,
        "x_range": [30, 150],
        "y_range": [round(y_min, 2), round(y_max, 2)],
    }


def _distribucion_metric_config() -> dict[str, dict[str, Any]]:
    return {
        "peso_bruto_kg": {"label": "Peso (kg)", "descriptiva": True},
        "talla_corporal_cm": {"label": "Talla (cm)", "descriptiva": True},
        "suma_6_pliegues_mm": {"label": "Suma 6 pliegues (mm)", "descriptiva": False},
        "ajuste_adiposa_pct": {"label": "% Grasa", "descriptiva": False},
        "ajuste_muscular_pct": {"label": "% Muscular", "descriptiva": False},
        "masa_osea_kg": {"label": "Masa osea (kg)", "descriptiva": True},
        "idx_musculo_oseo": {"label": "Indice musculo-oseo", "descriptiva": False},
    }


def _distribution_color(metric: str, value: float) -> str:
    if metric == "ajuste_adiposa_pct":
        if value < 14:
            return "#F1C40F"
        if value <= 20:
            return "#2ECC71"
        if value <= 24:
            return "#F39C12"
        return "#E74C3C"

    if metric == "ajuste_muscular_pct":
        if value < 40:
            return "#F39C12"
        if value <= 45:
            return "#2ECC71"
        return "#27AE60"

    if metric == "idx_musculo_oseo":
        if value < 3.5:
            return "#F39C12"
        if value <= 4.2:
            return "#2ECC71"
        return "#27AE60"

    if metric == "suma_6_pliegues_mm":
        if value < 50:
            return "#27AE60"
        if value <= 70:
            return "#2ECC71"
        if value <= 90:
            return "#F39C12"
        return "#E74C3C"

    return "#4A6FBF"


def _distribution_reference(metric: str) -> dict[str, Any] | None:
    references = {
        "ajuste_adiposa_pct": {"value": 20, "label": "Limite adecuado"},
        "ajuste_muscular_pct": {"value": 40, "label": "Referencia minima"},
        "idx_musculo_oseo": {"value": 3.5, "label": "Referencia minima"},
        "suma_6_pliegues_mm": {"value": 70, "label": "Limite adecuado"},
    }
    return references.get(metric)


def _distribution_buckets(metric: str, values: list[float]) -> list[dict[str, Any]]:
    bucket_defs = {
        "ajuste_adiposa_pct": [
            ("Muy bajo", "#F1C40F", lambda v: v < 14),
            ("Adecuado", "#2ECC71", lambda v: 14 <= v <= 20),
            ("Moderado", "#F39C12", lambda v: 20 < v <= 24),
            ("Elevado", "#E74C3C", lambda v: v > 24),
        ],
        "ajuste_muscular_pct": [
            ("Bajo", "#F39C12", lambda v: v < 40),
            ("Adecuado", "#2ECC71", lambda v: 40 <= v <= 45),
            ("Excelente", "#27AE60", lambda v: v > 45),
        ],
        "idx_musculo_oseo": [
            ("Bajo", "#F39C12", lambda v: v < 3.5),
            ("Adecuado", "#2ECC71", lambda v: 3.5 <= v <= 4.2),
            ("Excelente", "#27AE60", lambda v: v > 4.2),
        ],
        "suma_6_pliegues_mm": [
            ("Excelente", "#27AE60", lambda v: v < 50),
            ("Adecuado", "#2ECC71", lambda v: 50 <= v <= 70),
            ("Moderado", "#F39C12", lambda v: 70 < v <= 90),
            ("Elevado", "#E74C3C", lambda v: v > 90),
        ],
    }

    return [
        {"label": label, "color": color, "count": sum(1 for value in values if check(value))}
        for label, color, check in bucket_defs.get(metric, [])
    ]


def _build_distribucion_corporal_chart(records: list[dict[str, Any]]) -> dict[str, Any]:
    plot_records = _latest_records_by_player(records)
    metrics = {}

    for metric, config in _distribucion_metric_config().items():
        points = []
        for record in plot_records:
            value = _safe_float(record.get(metric))
            if value is None:
                continue

            points.append(
                {
                    "jugadora": str(record.get("nombre_jugadora") or "").strip(),
                    "value": round(value, 4),
                    "color": _distribution_color(metric, value),
                }
            )

        if not points:
            continue

        points = sorted(points, key=lambda item: item["value"])
        values = [point["value"] for point in points]
        mean_value = _mean(values)

        metrics[metric] = {
            "key": metric,
            "label": config["label"],
            "descriptiva": config["descriptiva"],
            "caption": (
                "Distribucion individual del grupo con valores minimo, maximo y promedio."
                if config["descriptiva"]
                else "Distribucion individual del grupo respecto a rangos de referencia y valores extremos."
            ),
            "points": points,
            "summary": {
                "mean": mean_value,
                "min": min(values),
                "max": max(values),
            },
            "reference": _distribution_reference(metric),
            "buckets": _distribution_buckets(metric, values),
        }

    default_metric = next(iter(metrics), None)
    return {
        "default_metric": default_metric,
        "metrics": metrics,
    }


def _summary_cell_class(column_key: str, value: float | None) -> str:
    if value is None:
        return ""

    if column_key == "grasa_media":
        if value < 14:
            return "cell-warning-soft"
        if value <= 20:
            return "cell-success"
        if value <= 24:
            return "cell-warning"
        return "cell-danger"

    if column_key == "musculo_media":
        if value < 40:
            return "cell-danger"
        if value <= 45:
            return "cell-success"
        return "cell-success-strong"

    if column_key == "pliegues_media":
        if value < 50:
            return "cell-success-strong"
        if value <= 70:
            return "cell-success"
        if value <= 90:
            return "cell-warning"
        return "cell-danger"

    if column_key == "imo_media":
        if value < 3.5:
            return "cell-warning"
        if value <= 4.2:
            return "cell-success"
        return "cell-success-strong"

    return ""


def _build_resumen_grupal_table(records: list[dict[str, Any]]) -> dict[str, Any]:
    records_by_player: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        player_name = str(record.get("nombre_jugadora") or "").strip()
        if player_name:
            records_by_player.setdefault(player_name, []).append(record)

    columns = [
        {"key": "jugadora", "label": "Jugadora", "decimals": None},
        {"key": "peso_medio", "label": "Peso medio (kg)", "decimals": 2},
        {"key": "grasa_media", "label": "% Grasa media", "decimals": 2},
        {"key": "musculo_media", "label": "% Muscular medio", "decimals": 2},
        {"key": "pliegues_media", "label": "6 Pliegues medios (mm)", "decimals": 2},
        {"key": "imo_media", "label": "Indice M/O medio", "decimals": 2},
        {"key": "n_mediciones", "label": "N mediciones", "decimals": 0},
    ]
    rows = []

    for player_name, player_records in records_by_player.items():
        row = {
            "jugadora": player_name,
            "peso_medio": _mean([_safe_float(r.get("peso_bruto_kg")) for r in player_records]),
            "grasa_media": _mean([_safe_float(r.get("ajuste_adiposa_pct")) for r in player_records]),
            "musculo_media": _mean([_safe_float(r.get("ajuste_muscular_pct")) for r in player_records]),
            "pliegues_media": _mean([_safe_float(r.get("suma_6_pliegues_mm")) for r in player_records]),
            "imo_media": _mean([_safe_float(r.get("idx_musculo_oseo")) for r in player_records]),
            "n_mediciones": len(player_records),
        }
        row["cells"] = {
            column["key"]: _summary_cell_class(column["key"], row.get(column["key"]))
            for column in columns
        }
        rows.append(row)

    rows = sorted(
        rows,
        key=lambda row: (
            row["peso_medio"] is None,
            row["peso_medio"] if row["peso_medio"] is not None else 0,
            row["jugadora"],
        ),
    )

    return {
        "columns": columns,
        "rows": rows,
        "sort_options": [
            {"key": "peso_medio", "label": "Peso medio (kg)", "higher_better": None},
            {"key": "grasa_media", "label": "% Grasa media", "higher_better": False},
            {"key": "musculo_media", "label": "% Muscular medio", "higher_better": True},
            {"key": "pliegues_media", "label": "6 Pliegues medios (mm)", "higher_better": False},
            {"key": "imo_media", "label": "Indice M/O medio", "higher_better": True},
            {"key": "n_mediciones", "label": "N mediciones", "higher_better": True},
        ],
    }


def _comparison_metric_config() -> dict[str, dict[str, Any]]:
    return {
        "peso_bruto_kg": {
            "label": "Peso",
            "full_label": "Peso (kg)",
            "positive_good": None,
        },
        "ajuste_adiposa_pct": {
            "label": "Grasa",
            "full_label": "% Grasa",
            "positive_good": False,
        },
        "ajuste_muscular_pct": {
            "label": "Musculo",
            "full_label": "% Muscular",
            "positive_good": True,
        },
        "suma_6_pliegues_mm": {
            "label": "Pliegues",
            "full_label": "Suma 6 pliegues",
            "positive_good": False,
        },
        "idx_musculo_oseo": {
            "label": "IMO",
            "full_label": "Indice musculo-oseo",
            "positive_good": True,
        },
    }


def _delta_color(metric: str, delta: float) -> str:
    positive_good = _comparison_metric_config()[metric]["positive_good"]
    if positive_good is None:
        return "#4A6FBF"
    if delta == 0:
        return "#7F8C8D"
    is_good = delta > 0 if positive_good else delta < 0
    return "#2ECC71" if is_good else "#E74C3C"


def _player_comparison_pairs(records: list[dict[str, Any]], periodo: str) -> list[dict[str, Any]]:
    records_by_player: dict[Any, list[dict[str, Any]]] = {}
    for record in records:
        player_id = record.get("identificacion") or record.get("nombre_jugadora")
        if record.get("fecha_medicion") is not None and player_id:
            records_by_player.setdefault(player_id, []).append(record)

    pairs = []
    for player_records in records_by_player.values():
        sorted_records = _sort_records(player_records, reverse=True)
        if len(sorted_records) < 2:
            continue

        current = sorted_records[0]
        previous = sorted_records[1] if periodo == "ultima" else _sort_records(player_records, reverse=False)[0]

        if current.get("id_isak") == previous.get("id_isak"):
            continue

        pairs.append(
            {
                "identificacion": current.get("identificacion"),
                "nombre_jugadora": current.get("nombre_jugadora") or previous.get("nombre_jugadora"),
                "current": current,
                "previous": previous,
            }
        )

    return pairs


def _metric_delta_from_pairs(pairs: list[dict[str, Any]], metric: str) -> dict[str, Any] | None:
    comparable = []
    for pair in pairs:
        prev_value = _safe_float(pair["previous"].get(metric))
        curr_value = _safe_float(pair["current"].get(metric))
        if prev_value is None or curr_value is None:
            continue
        comparable.append((prev_value, curr_value))

    if not comparable:
        return None

    prev_mean = _mean([prev for prev, _ in comparable])
    curr_mean = _mean([curr for _, curr in comparable])
    if prev_mean is None or curr_mean is None or prev_mean == 0:
        delta_pct = 0
    else:
        delta_pct = ((curr_mean - prev_mean) / prev_mean) * 100

    return {
        "previous_mean": prev_mean,
        "current_mean": curr_mean,
        "delta_pct": delta_pct,
        "n": len(comparable),
    }


def _build_comparacion_mediciones_chart(records: list[dict[str, Any]], periodo: str) -> dict[str, Any]:
    pairs = _player_comparison_pairs(records, periodo)
    metrics = []

    for metric, config in _comparison_metric_config().items():
        delta = _metric_delta_from_pairs(pairs, metric)
        if delta is None:
            continue

        metrics.append(
            {
                "key": metric,
                "label": config["label"],
                "full_label": config["full_label"],
                "delta_pct": round(delta["delta_pct"], 4),
                "previous_mean": delta["previous_mean"],
                "current_mean": delta["current_mean"],
                "n": delta["n"],
                "color": _delta_color(metric, delta["delta_pct"]),
                "positive_good": config["positive_good"],
            }
        )

    values = [metric["delta_pct"] for metric in metrics]
    max_abs = max([abs(value) for value in values], default=1)
    padding = max(max_abs * 0.15, 1)

    return {
        "metrics": metrics,
        "n_players": len(pairs),
        "caption": (
            "La grafica muestra el cambio porcentual promedio del grupo entre la ultima y la medicion anterior."
            if periodo == "ultima"
            else "La grafica muestra el cambio porcentual promedio del grupo entre la primera y la ultima medicion del periodo."
        ),
        "y_range": [round(min(values, default=0) - padding, 2), round(max(values, default=0) + padding, 2)],
        "axis_title": (
            "Cambio (%) respecto a la medicion anterior"
            if periodo == "ultima"
            else "Cambio (%) respecto al inicio del periodo"
        ),
    }


def _build_cambios_clave(records: list[dict[str, Any]], periodo: str) -> dict[str, Any]:
    pairs = _player_comparison_pairs(records, periodo)
    metrics: dict[str, Any] = {}

    for metric, config in _comparison_metric_config().items():
        rows = []
        for pair in pairs:
            prev_value = _safe_float(pair["previous"].get(metric))
            curr_value = _safe_float(pair["current"].get(metric))
            if prev_value is None or curr_value is None or prev_value == 0:
                continue

            delta_pct = ((curr_value - prev_value) / prev_value) * 100
            delta_abs = curr_value - prev_value
            positive_good = config["positive_good"]
            if positive_good is None:
                score = abs(delta_pct)
            else:
                score = delta_pct if positive_good else -delta_pct

            rows.append(
                {
                    "jugadora": str(pair.get("nombre_jugadora") or pair.get("identificacion") or ""),
                    "valor_inicial": round(prev_value, 4),
                    "valor_final": round(curr_value, 4),
                    "delta_pct": round(delta_pct, 4),
                    "delta_abs": round(delta_abs, 4),
                    "score_mejora": round(score, 4),
                }
            )

        if not rows:
            continue

        top_mejora = sorted(rows, key=lambda row: (-row["score_mejora"], row["jugadora"]))
        top_empeora = sorted(rows, key=lambda row: (row["score_mejora"], row["jugadora"]))

        metrics[metric] = {
            "key": metric,
            "label": config["full_label"],
            "positive_good": config["positive_good"],
            "rows": rows,
            "top_mejora": top_mejora[:10],
            "top_empeora": top_empeora[:10],
        }

    default_metric = "ajuste_adiposa_pct" if "ajuste_adiposa_pct" in metrics else next(iter(metrics), None)
    return {
        "caption": "Ranking de jugadoras con mayor mejora y mayor empeoramiento segun la metrica seleccionada.",
        "default_metric": default_metric,
        "metrics": metrics,
    }


def _record_date(record: dict[str, Any]):
    return _coerce_date_value(record.get("fecha_medicion"))


def _build_evolucion_temporal_chart(records: list[dict[str, Any]]) -> dict[str, Any]:
    dated_records = []
    for record in records:
        fecha = _record_date(record)
        if fecha is not None:
            dated_records.append((fecha, record))

    dated_records = sorted(dated_records, key=lambda item: item[0])
    unique_dates = []
    for fecha, _ in dated_records:
        if fecha not in unique_dates:
            unique_dates.append(fecha)

    date_blocks = {}
    current_block = 1
    previous_date = None
    for fecha in unique_dates:
        if previous_date is not None and (fecha - previous_date).days > 7:
            current_block += 1
        date_blocks[fecha] = current_block
        previous_date = fecha

    metric_config = {
        "ajuste_adiposa_pct": {"label": "% Grasa", "reference": {"value": 20, "label": "Limite optimo"}},
        "ajuste_muscular_pct": {"label": "% Muscular", "reference": {"value": 40, "label": "Referencia minima"}},
        "suma_6_pliegues_mm": {"label": "Suma 6 pliegues", "reference": {"value": 70, "label": "Limite adecuado"}},
        "idx_musculo_oseo": {"label": "Indice musculo-oseo", "reference": {"value": 3.5, "label": "Referencia minima"}},
        "peso_bruto_kg": {"label": "Peso", "reference": None},
    }

    metrics = {}
    for metric, config in metric_config.items():
        blocks: dict[int, dict[str, Any]] = {}
        for fecha, record in dated_records:
            value = _safe_float(record.get(metric))
            if value is None:
                continue
            block_id = date_blocks[fecha]
            block = blocks.setdefault(block_id, {"dates": [], "values": []})
            block["dates"].append(fecha)
            block["values"].append(value)

        if len(blocks) < 2:
            continue

        points = []
        for block_id in sorted(blocks):
            block = blocks[block_id]
            values = block["values"]
            start_date = min(block["dates"])
            end_date = max(block["dates"])
            label = (
                start_date.strftime("%d/%m")
                if start_date == end_date
                else f"{start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')}"
            )
            points.append(
                {
                    "block": block_id,
                    "label": label,
                    "mean": round(_mean(values) or 0, 4),
                    "min": round(min(values), 4),
                    "max": round(max(values), 4),
                    "count": len(values),
                }
            )

        if len(points) < 2:
            continue

        start_mean = points[0]["mean"]
        end_mean = points[-1]["mean"]
        delta_total = ((end_mean - start_mean) / start_mean) * 100 if start_mean else 0
        metrics[metric] = {
            "key": metric,
            "label": config["label"],
            "reference": config["reference"],
            "points": points,
            "summary": {
                "inicio": start_mean,
                "final": end_mean,
                "delta_total": round(delta_total, 4),
                "n_rondas": len(points),
                "n_registros": sum(point["count"] for point in points),
            },
        }

    default_metric = "ajuste_adiposa_pct" if "ajuste_adiposa_pct" in metrics else next(iter(metrics), None)
    return {
        "caption": "Evolucion temporal del promedio grupal por ronda de medicion, con banda de dispersion minima y maxima.",
        "default_metric": default_metric,
        "metrics": metrics,
    }


def _build_perfil_estructural_chart(records: list[dict[str, Any]]) -> dict[str, Any]:
    plot_records = _latest_records_by_player(records)
    raw_points = []

    for record in plot_records:
        envergadura = _safe_float(record.get("envergadura_cm"))
        talla = _safe_float(record.get("talla_corporal_cm"))
        muslo = _safe_float(record.get("perimetro_muslo_maximo"))
        pantorrilla = _safe_float(record.get("perimetro_pantorrilla_maxima"))
        if None in {envergadura, talla, muslo, pantorrilla} or talla == 0 or pantorrilla == 0:
            continue

        raw_points.append(
            {
                "jugadora": str(record.get("nombre_jugadora") or "").strip(),
                "x": envergadura / talla,
                "y": muslo / pantorrilla,
            }
        )

    if not raw_points:
        return {"points": [], "counts": {}, "x_cut": None, "y_cut": None, "x_range": None, "y_range": None}

    x_cut = _mean([point["x"] for point in raw_points]) or 0
    y_cut = _mean([point["y"] for point in raw_points]) or 0
    counts = {group: 0 for group in ("G1", "G2", "G3", "G4")}
    points = []

    for point in raw_points:
        x_value = point["x"]
        y_value = point["y"]
        if x_value >= x_cut and y_value >= y_cut:
            group, color = "G1", "#2ECC71"
        elif x_value < x_cut and y_value >= y_cut:
            group, color = "G2", "#F1C40F"
        elif x_value < x_cut and y_value < y_cut:
            group, color = "G3", "#F39C12"
        else:
            group, color = "G4", "#E74C3C"

        counts[group] += 1
        player_name = point["jugadora"]
        points.append(
            {
                "jugadora": player_name,
                "x": round(x_value, 4),
                "y": round(y_value, 4),
                "grupo": group,
                "color": color,
                "label": f"{player_name.title()} ({x_value:.3f}; {y_value:.3f})",
            }
        )

    x_values = [point["x"] for point in points]
    y_values = [point["y"] for point in points]
    x_min = min(x_values) - 0.02
    x_max = max(x_values) + 0.02
    y_min = min(y_values) - 0.05
    y_max = max(y_values) + 0.05

    return {
        "points": points,
        "counts": counts,
        "x_cut": round(x_cut, 4),
        "y_cut": round(y_cut, 4),
        "x_range": [round(x_min, 4), round(x_max, 4)],
        "y_range": [round(y_min, 4), round(y_max, 4)],
    }


def _build_ratios_estructurales_chart(records: list[dict[str, Any]]) -> dict[str, Any]:
    plot_records = _latest_records_by_player(records)
    ratio_config = {
        "ratio_cintura_cadera": {
            "label": "Ratio cintura / cadera",
            "numerator": "perimetro_cintura_minima",
            "denominator": "perimetro_cadera_maximo",
            "reading": "Valores bajos indican menor cintura relativa respecto a la cadera. Valores altos sugieren mayor predominio central o troncal.",
        },
        "ratio_muslo_pantorrilla": {
            "label": "Ratio muslo / pantorrilla",
            "numerator": "perimetro_muslo_maximo",
            "denominator": "perimetro_pantorrilla_maxima",
            "reading": "Valores altos indican mayor desarrollo relativo del muslo, asociado a produccion de fuerza en tren inferior.",
        },
        "ratio_envergadura_talla": {
            "label": "Ratio envergadura / talla",
            "numerator": "envergadura_cm",
            "denominator": "talla_corporal_cm",
            "reading": "Valores altos indican mayor envergadura relativa, asociada a alcance, cobertura y amplitud gestual.",
        },
        "ratio_tronco_altura": {
            "label": "Ratio tronco / altura",
            "numerator": "talla_sentado_cm",
            "denominator": "talla_corporal_cm",
            "reading": "Valores altos indican mayor proporcion de tronco; valores bajos sugieren mayor longitud relativa de piernas.",
        },
    }

    ratios = {}
    for key, config in ratio_config.items():
        points = []
        for record in plot_records:
            numerator = _safe_float(record.get(config["numerator"]))
            denominator = _safe_float(record.get(config["denominator"]))
            if numerator is None or denominator is None or denominator == 0:
                continue
            points.append(
                {
                    "jugadora": str(record.get("nombre_jugadora") or "").strip(),
                    "value": round(numerator / denominator, 4),
                }
            )

        if not points:
            continue

        points = sorted(points, key=lambda item: item["value"])
        values = [point["value"] for point in points]
        ratios[key] = {
            "key": key,
            "label": config["label"],
            "points": points,
            "summary": {
                "mean": round(_mean(values) or 0, 4),
                "min": min(values),
                "max": max(values),
            },
            "reading": config["reading"],
        }

    default_ratio = "ratio_envergadura_talla" if "ratio_envergadura_talla" in ratios else next(iter(ratios), None)
    return {
        "caption": "Distribucion grupal de ratios estructurales a partir de la ultima medicion disponible de cada jugadora.",
        "default_ratio": default_ratio,
        "ratios": ratios,
    }


def build_physical_grupal_context(plantel: str | None = None, periodo: str = "ultima") -> dict[str, Any]:
    """
    Contexto de la vista grupal read-only.

    Calcula KPIs, deltas e interpretaciones. Despues anadiremos graficos.
    """
    if periodo not in {"ultima", "historico"}:
        periodo = "ultima"

    competitions = get_physical_competitions()
    raw_records = get_physical_full_records(plantel=plantel)
    records = [build_record_antropometrico(record) for record in raw_records]
    period_records, period_label = _period_records(records, periodo)

    total_records = len(records)
    total_players = len({r.get("identificacion") for r in records if r.get("identificacion")})
    period_players = len({r.get("identificacion") for r in period_records if r.get("identificacion")})
    latest_records = _latest_records_by_player(records)
    group_metrics = _build_group_metrics(period_records, records, periodo)
    perfil_antropometrico = _build_perfil_antropometrico_chart(period_records)
    distribucion_corporal = _build_distribucion_corporal_chart(period_records)
    resumen_grupal = _build_resumen_grupal_table(period_records)
    comparison_records = records if periodo == "ultima" else period_records
    comparacion_mediciones = _build_comparacion_mediciones_chart(comparison_records, periodo)
    cambios_clave = _build_cambios_clave(comparison_records, periodo)
    evolucion_temporal = _build_evolucion_temporal_chart(records)
    perfil_estructural = {
        "mapa": _build_perfil_estructural_chart(period_records),
        "ratios": _build_ratios_estructurales_chart(period_records),
    }

    return {
        "competitions": competitions,
        "plantel": plantel,
        "periodo": periodo,
        "period_label": period_label,
        "records": records[:200],
        "latest_records": latest_records,
        "period_records": period_records,
        "group_metrics": group_metrics,
        "grupal_charts": {
            "perfil_antropometrico": perfil_antropometrico,
            "distribucion_corporal": distribucion_corporal,
            "comparacion_mediciones": comparacion_mediciones,
            "evolucion_temporal": evolucion_temporal,
            "perfil_estructural": perfil_estructural,
        },
        "cambios_clave": cambios_clave,
        "resumen_grupal": resumen_grupal,
        "reference_ranges": _reference_ranges(),
        "technical_summary": _build_technical_summary(group_metrics),
        "stats": {
            "total_records": total_records,
            "total_players": total_players,
            "period_records": len(period_records),
            "period_players": period_players,
        },
    }

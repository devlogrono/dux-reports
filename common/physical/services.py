from __future__ import annotations

from datetime import timedelta
from typing import Any

from dux.common.physical.queries import (
    get_physical_competitions,
    get_physical_full_records,
    get_physical_overview_stats,
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


def _sort_records(records: list[dict[str, Any]], reverse: bool = True) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda r: (
            r.get("fecha_medicion") is not None,
            r.get("fecha_medicion"),
            r.get("created_at") is not None,
            r.get("created_at"),
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


def _records_from_last_months(records: list[dict[str, Any]], months: int = 6) -> list[dict[str, Any]]:
    dated_records = [r for r in records if r.get("fecha_medicion") is not None]
    if not dated_records:
        return []

    max_date = max(r["fecha_medicion"] for r in dated_records)
    limit_date = max_date - timedelta(days=months * 30)

    return [r for r in dated_records if r["fecha_medicion"] >= limit_date]


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
        return "Excelente", "success", "Perfil muscular muy favorable para potencia y proteccion estructural."

    if metric == "imo_medio":
        if value < 3.5:
            return "Bajo", "warning", "Relacion musculo / oseo por desarrollar."
        if value <= 4.2:
            return "Adecuado", "success", "Relacion favorable para el rendimiento."
        return "Excelente", "success", "Perfil estructural muy favorable."

    if metric == "pliegues_media":
        if value < 50:
            return "Excelente", "success", "Perfil de alta competicion."
        if value <= 70:
            return "Adecuado", "success", "Rango funcional para la mayoria de posiciones."
        if value <= 90:
            return "Moderado", "warning", "Con margen de ajuste nutricional y de carga."
        return "Elevado", "danger", "Fuera del rango objetivo de rendimiento."

    return "Descriptivo", "secondary", ""


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
        },
        "technical_summary": _build_technical_summary(group_metrics),
        "stats": {
            "total_records": total_records,
            "total_players": total_players,
            "period_records": len(period_records),
            "period_players": period_players,
        },
    }

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
        },
        "cambios_clave": cambios_clave,
        "resumen_grupal": resumen_grupal,
        "technical_summary": _build_technical_summary(group_metrics),
        "stats": {
            "total_records": total_records,
            "total_players": total_players,
            "period_records": len(period_records),
            "period_players": period_players,
        },
    }

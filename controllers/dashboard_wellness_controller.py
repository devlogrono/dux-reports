from datetime import date, timedelta

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError

from dux import cache, db

bp = Blueprint("dashboard_wellness", __name__, url_prefix="/dashboard/wellness")

WELLNESS_COLUMNS = ["recuperacion", "energia", "sueno", "stress", "dolor"]


def _user_cache_key():
    user_id = current_user.id if current_user.is_authenticated else "anon"
    return f"view//{request.path}?{request.query_string.decode()}&_uid={user_id}"


def _as_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_metric(value):
    return round(value, 1) if value is not None else None


def _record_score(row):
    values = [_as_float(row.get(column)) for column in WELLNESS_COLUMNS]
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values)


def _avg(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _selected_days():
    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        days = 30
    return min(max(days, 1), 365)


def _fetch_filter_options():
    sql = """
        SELECT DISTINCT
            f.identificacion AS id_jugadora,
            f.nombre,
            f.apellido,
            f.competicion AS plantel,
            w.tipo
        FROM wellness w
        LEFT JOIN futbolistas f ON w.id_jugadora = f.identificacion
        WHERE (w.estatus_id IS NULL OR w.estatus_id <= 2)
        ORDER BY f.competicion ASC, f.apellido ASC, f.nombre ASC
    """
    rows = db.session.execute(text(sql)).mappings().all()

    planteles = []
    seen_planteles = set()
    jugadoras = []
    seen_jugadoras = set()
    tipos = []
    seen_tipos = set()
    for row in rows:
        plantel = row["plantel"]
        if plantel and plantel not in seen_planteles:
            planteles.append(plantel)
            seen_planteles.add(plantel)

        tipo = row["tipo"]
        if tipo and tipo not in seen_tipos:
            tipos.append(tipo)
            seen_tipos.add(tipo)

        jugadora_id = row["id_jugadora"]
        if not jugadora_id or jugadora_id in seen_jugadoras:
            continue
        nombre_completo = f"{row['apellido'] or ''}, {row['nombre'] or ''}".strip(", ")
        jugadoras.append(
            {
                "id": jugadora_id,
                "nombre": nombre_completo or jugadora_id,
                "plantel": plantel,
            }
        )
        seen_jugadoras.add(jugadora_id)

    return planteles, jugadoras, tipos


def _fetch_wellness_records(planteles, jugadoras, tipos, since, limit=None):
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
            w.minutos_sesion,
            w.rpe,
            w.ua,
            w.observacion,
            w.fecha_hora_registro,
            w.usuario
        FROM wellness w
        LEFT JOIN futbolistas f ON w.id_jugadora = f.identificacion
        WHERE (w.estatus_id IS NULL OR w.estatus_id <= 2)
          AND w.fecha_sesion >= :since
    """
    params = {"since": since}
    bindparams = []

    if planteles:
        sql += " AND f.competicion IN :planteles"
        params["planteles"] = planteles
        bindparams.append(bindparam("planteles", expanding=True))
    if jugadoras:
        sql += " AND w.id_jugadora IN :jugadoras"
        params["jugadoras"] = jugadoras
        bindparams.append(bindparam("jugadoras", expanding=True))
    if tipos:
        sql += " AND w.tipo IN :tipos"
        params["tipos"] = tipos
        bindparams.append(bindparam("tipos", expanding=True))

    sql += " ORDER BY w.fecha_sesion DESC, w.fecha_hora_registro DESC"
    if limit:
        sql += " LIMIT :limit"
        params["limit"] = limit

    statement = text(sql)
    if bindparams:
        statement = statement.bindparams(*bindparams)

    rows = db.session.execute(statement, params).mappings().all()
    records = []
    for row in rows:
        record = dict(row)
        record["nombre_jugadora"] = (
            f"{record.get('apellido') or ''}, {record.get('nombre') or ''}".strip(", ")
            or record.get("id_jugadora")
        )
        record["wellness_score"] = _round_metric(_record_score(record))
        record["rpe"] = _round_metric(_as_float(record.get("rpe")))
        record["ua"] = _round_metric(_as_float(record.get("ua")))
        records.append(record)

    return records


def _is_checkin(record):
    return str(record.get("tipo") or "").lower().replace("-", "") == "checkin"


def _build_alerts(records):
    checkin_records = [record for record in records if _is_checkin(record)]
    base_records = checkin_records or records

    players = {}
    for record in base_records:
        player_key = record.get("id_jugadora") or record.get("nombre_jugadora")
        if not player_key:
            continue
        players.setdefault(player_key, {"nombre": record.get("nombre_jugadora"), "values": []})
        players[player_key]["values"].append(record)

    risky_players = []
    for player in players.values():
        column_means = []
        for column in WELLNESS_COLUMNS:
            column_mean = _avg([_as_float(record.get(column)) for record in player["values"]])
            if column_mean is not None:
                column_means.append(column_mean)

        wellness_mean_1_5 = _avg(column_means)
        pain_mean = _avg([_as_float(record.get("dolor")) for record in player["values"]])
        is_risky = (
            (wellness_mean_1_5 is not None and wellness_mean_1_5 > 3)
            or (pain_mean is not None and pain_mean > 3)
        )
        if is_risky:
            risky_players.append(
                {
                    "nombre": player["nombre"],
                    "prom_w_1_5": _round_metric(wellness_mean_1_5),
                    "dolor_mean": _round_metric(pain_mean),
                }
            )

    total_players = len(players)
    alerts_count = len(risky_players)
    alerts_pct = round((alerts_count / total_players) * 100, 1) if total_players else 0

    return {
        "count": alerts_count,
        "total_jugadoras": total_players,
        "pct": alerts_pct,
        "jugadoras": risky_players,
    }


def _wellness_status(value):
    if value is None:
        return "sin datos"
    if value > 20:
        return "óptimo"
    if value >= 15:
        return "moderado"
    return "en fatiga"


def _rpe_status(value):
    if value in (None, 0):
        return "sin datos"
    if value < 5:
        return "bajo"
    if value <= 7:
        return "moderado"
    return "alto"


def _build_summary(records):
    alerts = _build_alerts(records)
    wellness_average = _round_metric(_avg([r["wellness_score"] for r in records]))
    rpe_average = _round_metric(_avg([r["rpe"] for r in records]))
    return {
        "total": len(records),
        "wellness_promedio": wellness_average,
        "wellness_estado": _wellness_status(wellness_average),
        "rpe_promedio": rpe_average,
        "rpe_estado": _rpe_status(rpe_average),
        "ua_total": _round_metric(sum([r["ua"] or 0 for r in records])),
        "alertas_count": alerts["count"],
        "alertas_total_jugadoras": alerts["total_jugadoras"],
        "alertas_pct": alerts["pct"],
        "alertas_jugadoras": alerts["jugadoras"],
    }


def _date_key(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _build_daily_charts(records):
    daily = {}
    for record in records:
        date_value = record.get("fecha_sesion")
        if not date_value:
            continue
        key = _date_key(date_value)
        daily.setdefault(key, {"wellness": [], "rpe": [], "ua": 0})
        daily[key]["wellness"].append(record.get("wellness_score"))
        daily[key]["rpe"].append(record.get("rpe"))
        daily[key]["ua"] += record.get("ua") or 0

    labels = sorted(daily.keys())
    return {
        "labels": labels,
        "wellness": [_round_metric(_avg(daily[label]["wellness"])) for label in labels],
        "rpe": [_round_metric(_avg(daily[label]["rpe"])) for label in labels],
        "ua": [_round_metric(daily[label]["ua"]) for label in labels],
    }


@bp.get("/")
@login_required
@cache.cached(timeout=3600, make_cache_key=_user_cache_key)
def index():
    selected_planteles = request.args.getlist("plantel")
    selected_jugadoras = request.args.getlist("jugadora")
    selected_tipos = request.args.getlist("tipo")
    days = _selected_days()
    since = date.today() - timedelta(days=days)

    error = None
    planteles = []
    jugadoras = []
    tipos = []
    records = []
    summary = _build_summary(records)
    charts = _build_daily_charts(records)

    try:
        planteles, jugadoras, tipos = _fetch_filter_options()
        records = _fetch_wellness_records(
            selected_planteles,
            selected_jugadoras,
            selected_tipos,
            since,
        )
        summary = _build_summary(records)
        charts = _build_daily_charts(records)
    except SQLAlchemyError:
        db.session.rollback()
        error = "No se pudieron cargar los registros de Wellness."

    return render_template(
        "dashboard/wellness.html",
        error=error,
        planteles=planteles,
        jugadoras=jugadoras,
        tipos=tipos,
        selected_planteles=selected_planteles,
        selected_jugadoras=selected_jugadoras,
        selected_tipos=selected_tipos,
        days=days,
        records=records,
        display_records=records[:200],
        summary=summary,
        charts=charts,
    )

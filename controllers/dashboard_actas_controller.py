from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import text
from dux import db, cache

bp = Blueprint("dashboard_actas", __name__, url_prefix="/dashboard/actas")

@bp.get("/")
@login_required
@cache.cached(timeout=3600, query_string=True)
def index():
    Comp = getattr(__import__('dux.models', fromlist=['Base']).Base.classes, "competiciones", None)
    DiccComp = getattr(__import__('dux.models', fromlist=['Base']).Base.classes, "diccionario_competiciones", None)

    # --- Competiciones y escudos ---
    table = None
    comp_col = None
    escudo_col = None
    if Comp is not None:
        table = Comp.__table__
        comp_col = table.c.get("competicion")
        escudo_col = table.c.get("url_escudo_equipo") or table.c.get("url_escudo_equipo_local")

    competiciones = []
    raw_competiciones = []

    if comp_col is not None:
        try:
            rows_comp = (
                db.session.query(comp_col)
                .filter(comp_col.isnot(None), comp_col != "")
                .distinct()
                .order_by(comp_col.asc())
                .all()
            )
            raw_competiciones = [r[0] for r in rows_comp]
        except Exception:
            pass

    if not raw_competiciones:
        try:
            rows = db.session.execute(text(
                "SELECT DISTINCT competicion FROM competiciones "
                "WHERE competicion IS NOT NULL AND competicion <> '' ORDER BY competicion ASC"
            )).fetchall()
            raw_competiciones = [r[0] for r in rows]
        except Exception:
            pass

    orden_preferido = ["1FF", "3FFF", "1J", "1C", "CFF", "1I", "IFF"]
    ordered_codes = []
    if raw_competiciones:
        ordered_codes = [c for c in orden_preferido if c in raw_competiciones] + sorted(
            [c for c in raw_competiciones if c not in orden_preferido]
        )

    if ordered_codes:
        name_map = {}
        if DiccComp is not None:
            try:
                rows_dicc = (
                    db.session.query(DiccComp.id, DiccComp.nombre_competicion)
                    .filter(DiccComp.id.in_(ordered_codes))
                    .all()
                )
                name_map = {r[0]: (r[1] or r[0]) for r in rows_dicc}
            except Exception:
                pass

        competiciones = [
            {"id": code, "nombre": name_map.get(code, code)} for code in ordered_codes
        ]

    competicion_sel = request.args.get("competicion") or "1FF"
    if competiciones and competicion_sel not in [c["id"] for c in competiciones]:
        competicion_sel = competiciones[0]["id"]
    equipo_sel = request.args.get("equipo") or None

    # --- Escudos ---
    escudos = []

    if escudo_col is not None and comp_col is not None and competicion_sel:
        try:
            nombre_col = table.c.get("nombre_equipo") if table is not None else None
            if nombre_col is not None:
                rows = (
                    db.session.query(escudo_col, nombre_col)
                    .filter(comp_col == competicion_sel, escudo_col.isnot(None), escudo_col != "")
                    .distinct()
                    .order_by(nombre_col.asc())
                    .all()
                )
                escudos = [{"url": r[0], "nombre": r[1] or ""} for r in rows]
            else:
                rows = (
                    db.session.query(escudo_col)
                    .filter(comp_col == competicion_sel, escudo_col.isnot(None), escudo_col != "")
                    .distinct()
                    .order_by(escudo_col.asc())
                    .all()
                )
                escudos = [{"url": r[0], "nombre": ""} for r in rows]
        except Exception:
            pass

    if not escudos and competicion_sel:
        try:
            rows = db.session.execute(text(
                "SELECT DISTINCT url_escudo_equipo, nombre_equipo FROM competiciones "
                "WHERE competicion = :comp AND url_escudo_equipo IS NOT NULL "
                "AND url_escudo_equipo <> '' ORDER BY nombre_equipo ASC"
            ), {"comp": competicion_sel}).fetchall()
            escudos = [{"url": r[0], "nombre": (r[1] or "") if len(r) > 1 else ""} for r in rows]
        except Exception:
            pass

    # --- Métricas de actas ---
    tarjetas = []
    goles = []
    minutos = []
    max_tarjetas_total = 0
    goles_favor_total = 0
    goles_contra_total = 0
    total_tarjetas_equipo = 0
    victorias_total = 0
    empates_total = 0
    derrotas_total = 0

    # --- Diferencia de goles por jornada ---
    diff_jornadas_labels = []
    diff_jornadas_values = []
    diff_jornadas_ticks = []
    equipo_titulo = None
    equipo_id = None
    equipo_info_por_id = {}

    if competicion_sel:
        try:
            if equipo_sel:
                rows_team = db.session.execute(text(
                    "SELECT DISTINCT id_equipo, nombre_equipo FROM competiciones "
                    "WHERE competicion = :comp AND nombre_equipo = :equipo LIMIT 1"
                ), {"comp": competicion_sel, "equipo": equipo_sel}).fetchall()
            else:
                rows_team = db.session.execute(text(
                    "SELECT DISTINCT id_equipo, nombre_equipo FROM competiciones "
                    "WHERE competicion = :comp AND LOWER(nombre_equipo) LIKE :pattern "
                    "ORDER BY nombre_equipo ASC LIMIT 1"
                ), {"comp": competicion_sel, "pattern": "%dux%"}).fetchall()

            if rows_team:
                equipo_id = rows_team[0][0]
                equipo_titulo = equipo_sel if equipo_sel else (rows_team[0][1] if len(rows_team[0]) > 1 else None)
        except Exception:
            pass

    if competicion_sel:
        try:
            rows_eq_info = db.session.execute(text(
                "SELECT DISTINCT id_equipo, nombre_equipo, url_escudo_equipo "
                "FROM competiciones WHERE competicion = :comp AND id_equipo IS NOT NULL"
            ), {"comp": competicion_sel}).fetchall()
            equipo_info_por_id = {
                r[0]: {"nombre": r[1] or "", "escudo": r[2] or ""} for r in rows_eq_info
            }
        except Exception:
            pass

    if equipo_id is not None:
        try:
            rows_j = db.session.execute(text(
                "SELECT jornada, id_equipo_local, id_equipo_visitante, "
                "goles_equipo_local, goles_equipo_visitante "
                "FROM jornadas WHERE id_equipo_local = :eq OR id_equipo_visitante = :eq "
                "ORDER BY jornada ASC"
            ), {"eq": equipo_id}).fetchall()

            for r in rows_j:
                jornada, id_loc, id_vis, g_loc, g_vis = r
                if g_loc in (None, "") or g_vis in (None, ""):
                    continue
                try:
                    g_loc = int(g_loc or 0)
                    g_vis = int(g_vis or 0)
                except Exception:
                    g_loc = g_loc or 0
                    g_vis = g_vis or 0

                gf, gc = (g_loc, g_vis) if id_loc == equipo_id else (g_vis, g_loc)
                diff = gf - gc
                goles_favor_total += gf
                goles_contra_total += gc

                if gf > gc:
                    victorias_total += 1
                elif gf < gc:
                    derrotas_total += 1
                else:
                    empates_total += 1

                diff_jornadas_labels.append(str(jornada))
                diff_jornadas_values.append(diff)

                info_loc = equipo_info_por_id.get(id_loc, {})
                info_vis = equipo_info_por_id.get(id_vis, {})
                diff_jornadas_ticks.append({
                    "label": f"{info_loc.get('nombre','')} {g_loc}-{g_vis} {info_vis.get('nombre','')}".strip(),
                    "loc_escudo": info_loc.get("escudo", ""),
                    "vis_escudo": info_vis.get("escudo", ""),
                    "loc_goles": int(g_loc),
                    "vis_goles": int(g_vis),
                })
        except Exception:
            pass

    # --- Estadísticas por jugador ---
    if equipo_id is not None:
        rows_stats = []
        try:
            rows_stats = db.session.execute(text(
                "SELECT a.jugador, "
                "COALESCE(SUM(a.goles), 0) AS goles, "
                "COALESCE(SUM(a.minutos), 0) AS minutos, "
                "COALESCE(SUM(a.tarjetas_amarillas), 0) AS ta, "
                "COALESCE(SUM(a.tarjetas_rojas), 0) AS tr "
                "FROM jornadas j "
                "JOIN actas a ON a.acta_id = j.acta_id "
                "LEFT JOIN competiciones cl ON j.id_equipo_local = cl.id_equipo "
                "LEFT JOIN competiciones cv ON j.id_equipo_visitante = cv.id_equipo "
                "WHERE ( (j.id_equipo_local = :eq AND cl.competicion = :comp AND a.equipo = cl.nombre_equipo) "
                "     OR (j.id_equipo_visitante = :eq AND cv.competicion = :comp AND a.equipo = cv.nombre_equipo) ) "
                "GROUP BY a.jugador"
            ), {"eq": equipo_id, "comp": competicion_sel}).fetchall()
        except Exception:
            try:
                rows_stats = db.session.execute(text(
                    "SELECT a.jugador, "
                    "COALESCE(SUM(a.goles), 0) AS goles, "
                    "COALESCE(SUM(a.minutos), 0) AS minutos, "
                    "COALESCE(SUM(a.tarjetas_amarillas), 0) AS ta, "
                    "COALESCE(SUM(a.tarjetas_rojas), 0) AS tr "
                    "FROM jornadas j "
                    "JOIN actas a ON a.acta_id = j.acta_id "
                    "LEFT JOIN competiciones cl ON j.id_equipo_local = cl.id_equipo "
                    "LEFT JOIN competiciones cv ON j.id_equipo_visitante = cv.id_equipo "
                    "WHERE ( (j.id_equipo_local = :eq AND a.equipo = cl.nombre_equipo) "
                    "     OR (j.id_equipo_visitante = :eq AND a.equipo = cv.nombre_equipo) ) "
                    "GROUP BY a.jugador"
                ), {"eq": equipo_id}).fetchall()
            except Exception:
                rows_stats = []

        if rows_stats:
            stats = [
                {
                    "jugador": r[0],
                    "goles": int(r[1] or 0),
                    "minutos": int(r[2] or 0),
                    "amarillas": int(r[3] or 0),
                    "rojas": int(r[4] or 0),
                }
                for r in rows_stats
            ]

            tarjetas = sorted(
                [s for s in stats if s["amarillas"] or s["rojas"]],
                key=lambda x: (-(x["amarillas"] + x["rojas"]), -x["rojas"], x["jugador"] or ""),
            )
            try:
                max_tarjetas_total = max((t["amarillas"] + t["rojas"] for t in tarjetas), default=0)
            except Exception:
                max_tarjetas_total = 0
            total_tarjetas_equipo = sum(t["amarillas"] + t["rojas"] for t in tarjetas)

            goles = sorted(
                [{"jugador": s["jugador"], "valor": s["goles"]} for s in stats if s["goles"]],
                key=lambda x: (-(x["valor"] or 0), x["jugador"] or ""),
            )
            minutos = sorted(
                [{"jugador": s["jugador"], "valor": s["minutos"]} for s in stats if s["minutos"]],
                key=lambda x: (-(x["valor"] or 0), x["jugador"] or ""),
            )

    return render_template(
        "dashboard/actas.html",
        escudos=escudos,
        tarjetas=tarjetas,
        goles=goles,
        minutos=minutos,
        competiciones=competiciones,
        competicion_sel=competicion_sel,
        equipo_sel=equipo_sel,
        diff_jornadas_labels=diff_jornadas_labels,
        diff_jornadas_values=diff_jornadas_values,
        diff_jornadas_ticks=diff_jornadas_ticks,
        equipo_titulo=equipo_titulo,
        max_tarjetas_total=max_tarjetas_total,
        goles_favor_total=goles_favor_total,
        goles_contra_total=goles_contra_total,
        total_tarjetas_equipo=total_tarjetas_equipo,
        victorias_total=victorias_total,
        empates_total=empates_total,
        derrotas_total=derrotas_total,
    )

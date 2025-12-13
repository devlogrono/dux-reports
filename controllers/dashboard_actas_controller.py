from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import text
from dux import db
from dux.models import Base

bp = Blueprint("dashboard_actas", __name__, url_prefix="/dashboard/actas")

@bp.get("/")
@login_required
def index():
    # Modelos reflejados
    Comp = getattr(Base.classes, "competiciones", None)
    Acta = getattr(Base.classes, "actas", None)
    DiccComp = getattr(Base.classes, "diccionario_competiciones", None)

    # Debug: qué clases ha reflejado automap
    try:
        class_keys = list(Base.classes.keys())
    except Exception:
        class_keys = []
    print("[dashboard_actas] Base.classes keys:", class_keys)
    print("[dashboard_actas] Comp:", Comp, "Acta:", Acta)

    # --- Competiciones y escudos ---
    table = None
    comp_col = None
    escudo_col = None
    if Comp is not None:
        table = Comp.__table__
        comp_col = table.c.get("competicion")
        escudo_col = table.c.get("url_escudo_equipo") or table.c.get("url_escudo_equipo_local")
        print("[dashboard_actas] columnas competiciones:", list(table.c.keys()))
        print("[dashboard_actas] comp_col:", comp_col, "escudo_col:", escudo_col)

    competiciones = []
    raw_competiciones = []

    # 1) Intento con automap si tenemos columna
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
            print("[dashboard_actas] competiciones via ORM:", raw_competiciones)
        except Exception as exc:
            print("[dashboard_actas] Error leyendo competiciones via ORM:", exc)

    # 2) Fallback con SQL crudo si sigue vacío o no hay Comp
    if not raw_competiciones:
        try:
            sql_comp = text(
                "SELECT DISTINCT competicion "
                "FROM competiciones "
                "WHERE competicion IS NOT NULL AND competicion <> '' "
                "ORDER BY competicion ASC"
            )
            rows = db.session.execute(sql_comp).fetchall()
            raw_competiciones = [r[0] for r in rows]
            print("[dashboard_actas] competiciones via SQL:", raw_competiciones)
        except Exception as exc:
            print("[dashboard_actas] Error leyendo competiciones via SQL:", exc)

    # Orden preferido de competiciones (1FF incluida)
    orden_preferido = ["1FF", "3FFF", "1J", "1C", "CFF", "1I", "IFF"]
    ordered_codes = []
    if raw_competiciones:
        ordered_codes = [c for c in orden_preferido if c in raw_competiciones] + sorted(
            [c for c in raw_competiciones if c not in orden_preferido]
        )

    # Construir lista de competiciones con id (código) y nombre legible
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
            except Exception as exc:
                print("[dashboard_actas] Error leyendo diccionario_competiciones:", exc)

        competiciones = [
            {"id": code, "nombre": name_map.get(code, code)} for code in ordered_codes
        ]

    print("[dashboard_actas] competiciones tras ordenar:", competiciones)

    # Por defecto usar 1FF como competición seleccionada
    competicion_sel = request.args.get("competicion") or "1FF"
    if competiciones and competicion_sel not in [c["id"] for c in competiciones]:
        competicion_sel = competiciones[0]["id"]
    equipo_sel = request.args.get("equipo") or None
    print("[dashboard_actas] competicion_sel final:", competicion_sel, "equipo_sel:", equipo_sel)

    # --- Escudos ---
    escudos = []

    # 1) Intento ORM
    if escudo_col is not None and comp_col is not None and competicion_sel:
        try:
            nombre_col = table.c.get("nombre_equipo") if table is not None else None
            if nombre_col is not None:
                rows = (
                    db.session.query(escudo_col, nombre_col)
                    .filter(
                        comp_col == competicion_sel,
                        escudo_col.isnot(None),
                        escudo_col != "",
                    )
                    .distinct()
                    .order_by(nombre_col.asc())
                    .all()
                )
                escudos = [
                    {"url": r[0], "nombre": r[1] or ""}
                    for r in rows
                ]
            else:
                rows = (
                    db.session.query(escudo_col)
                    .filter(
                        comp_col == competicion_sel,
                        escudo_col.isnot(None),
                        escudo_col != "",
                    )
                    .distinct()
                    .order_by(escudo_col.asc())
                    .all()
                )
                escudos = [
                    {"url": r[0], "nombre": ""}
                    for r in rows
                ]
            print(
                "[dashboard_actas] escudos via ORM (%d) para %s"
                % (len(escudos), competicion_sel)
            )
        except Exception as exc:
            print("[dashboard_actas] Error leyendo escudos via ORM:", exc)

    # 2) Fallback SQL si siguen vacíos
    if not escudos and competicion_sel:
        try:
            sql_esc = text(
                "SELECT DISTINCT url_escudo_equipo, nombre_equipo "
                "FROM competiciones "
                "WHERE competicion = :comp "
                "  AND url_escudo_equipo IS NOT NULL "
                "  AND url_escudo_equipo <> '' "
                "ORDER BY nombre_equipo ASC"
            )
            rows = db.session.execute(sql_esc, {"comp": competicion_sel}).fetchall()
            escudos = [
                {"url": r[0], "nombre": (r[1] or "") if len(r) > 1 else ""}
                for r in rows
            ]
            print(
                "[dashboard_actas] escudos via SQL (%d) para %s"
                % (len(escudos), competicion_sel)
            )
        except Exception as exc:
            print("[dashboard_actas] Error leyendo escudos via SQL:", exc)

    # --- Métricas de actas (tarjetas, goles, minutos) ---
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

    if Acta is not None:
        # -------- Tarjetas (Jugador, TA, TR) --------
        TA = Acta.__table__.c.get("Tarjetas Amarillas")
        TR = Acta.__table__.c.get("Tarjetas Rojas")
        J = Acta.__table__.c.get("Jugador")
        if J is not None and TA is not None and TR is not None:
            q = db.session.query(J, TA, TR).all()
            tarjetas = [
                {"jugador": r[0], "amarillas": r[1] or 0, "rojas": r[2] or 0}
                for r in q
            ]

        # -------- Goles --------
        G = Acta.__table__.c.get("Goles")
        if J is not None and G is not None:
            q = db.session.query(J, G).order_by((G.desc())).limit(30).all()
            goles = [{"jugador": r[0], "valor": r[1] or 0} for r in q]

        # -------- Minutos --------
        M = Acta.__table__.c.get("Minutos")
        if J is not None and M is not None:
            q = db.session.query(J, M).order_by((M.desc())).limit(30).all()
            minutos = [{"jugador": r[0], "valor": r[1] or 0} for r in q]
    else:
        print("[dashboard_actas] Acta es None; se omiten métricas de tarjetas/goles/minutos")

    # --- Diferencia de goles por jornada (bar chart) ---
    diff_jornadas_labels = []
    diff_jornadas_values = []

    # equipo_sel: selección explícita (para resaltar escudos)
    # equipo_titulo: equipo que se muestra en el título / se usa por defecto en el gráfico
    equipo_titulo = None
    equipo_id = None
    if competicion_sel:
        try:
            if equipo_sel:
                sql_team = text(
                    "SELECT DISTINCT id_equipo, nombre_equipo "
                    "FROM competiciones "
                    "WHERE competicion = :comp "
                    "  AND nombre_equipo = :equipo "
                    "LIMIT 1"
                )
                rows_team = db.session.execute(
                    sql_team, {"comp": competicion_sel, "equipo": equipo_sel}
                ).fetchall()
            else:
                # Búsqueda case-insensitive del equipo DUX usando LOWER(nombre_equipo)
                sql_team = text(
                    "SELECT DISTINCT id_equipo, nombre_equipo "
                    "FROM competiciones "
                    "WHERE competicion = :comp "
                    "  AND LOWER(nombre_equipo) LIKE :pattern "
                    "ORDER BY nombre_equipo ASC "
                    "LIMIT 1"
                )
                rows_team = db.session.execute(
                    sql_team, {"comp": competicion_sel, "pattern": "%dux%"}
                ).fetchall()

            if rows_team:
                equipo_id = rows_team[0][0]
                # Para el título del gráfico, si hay selección explícita usamos esa;
                # si no, usamos el nombre del equipo DUX encontrado.
                if equipo_sel:
                    equipo_titulo = equipo_sel
                elif len(rows_team[0]) > 1:
                    equipo_titulo = rows_team[0][1]
            print("[dashboard_actas] equipo_id para diff jornadas:", equipo_id, "equipo_sel:", equipo_sel, "equipo_titulo:", equipo_titulo)
        except Exception as exc:
            print("[dashboard_actas] Error obteniendo equipo_id para diff jornadas:", exc)

    if equipo_id is not None:
        try:
            sql_j = text(
                "SELECT jornada, id_equipo_local, id_equipo_visitante, "
                "       goles_equipo_local, goles_equipo_visitante "
                "FROM jornadas "
                "WHERE id_equipo_local = :eq OR id_equipo_visitante = :eq "
                "ORDER BY jornada ASC"
            )
            rows_j = db.session.execute(sql_j, {"eq": equipo_id}).fetchall()
            print("[dashboard_actas] jornadas encontradas:", len(rows_j))
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

                if id_loc == equipo_id:
                    gf = g_loc
                    gc = g_vis
                else:
                    gf = g_vis
                    gc = g_loc

                diff = gf - gc
                goles_favor_total += gf
                goles_contra_total += gc

                # Contar victorias, empates y derrotas
                if gf > gc:
                    victorias_total += 1
                elif gf < gc:
                    derrotas_total += 1
                else:
                    empates_total += 1

                diff_jornadas_labels.append(str(jornada))
                diff_jornadas_values.append(diff)
        except Exception as exc:
            print("[dashboard_actas] Error calculando diff jornadas:", exc)

    # --- Estadísticas agregadas por jugador (actas filtradas por jornadas) ---
    if equipo_id is not None:
        rows_stats = []
        try:
            # Intento con filtro de competición en jornadas
            sql_stats = text(
                "SELECT a.jugador, "
                "       COALESCE(SUM(a.goles), 0) AS goles, "
                "       COALESCE(SUM(a.minutos), 0) AS minutos, "
                "       COALESCE(SUM(a.tarjetas_amarillas), 0) AS ta, "
                "       COALESCE(SUM(a.tarjetas_rojas), 0) AS tr "
                "FROM jornadas j "
                "JOIN actas a ON a.acta_id = j.acta_id "
                "WHERE (j.id_equipo_local = :eq OR j.id_equipo_visitante = :eq) "
                "  AND j.competicion = :comp "
                "GROUP BY a.jugador"
            )
            rows_stats = db.session.execute(
                sql_stats, {"eq": equipo_id, "comp": competicion_sel}
            ).fetchall()
        except Exception as exc:
            print(
                "[dashboard_actas] Error leyendo stats actas con competicion en jornadas, reintentando sin competicion:",
                exc,
            )
            try:
                sql_stats = text(
                    "SELECT a.jugador, "
                    "       COALESCE(SUM(a.goles), 0) AS goles, "
                    "       COALESCE(SUM(a.minutos), 0) AS minutos, "
                    "       COALESCE(SUM(a.tarjetas_amarillas), 0) AS ta, "
                    "       COALESCE(SUM(a.tarjetas_rojas), 0) AS tr "
                    "FROM jornadas j "
                    "JOIN actas a ON a.acta_id = j.acta_id "
                    "WHERE j.id_equipo_local = :eq OR j.id_equipo_visitante = :eq "
                    "GROUP BY a.jugador"
                )
                rows_stats = db.session.execute(
                    sql_stats, {"eq": equipo_id}
                ).fetchall()
            except Exception as exc2:
                print("[dashboard_actas] Error leyendo stats actas sin competicion:", exc2)
                rows_stats = []

        if rows_stats:
            stats = []
            for r in rows_stats:
                jugador = r[0]
                goles_val = r[1] or 0
                minutos_val = r[2] or 0
                ta_val = r[3] or 0
                tr_val = r[4] or 0
                stats.append(
                    {
                        "jugador": jugador,
                        "goles": int(goles_val),
                        "minutos": int(minutos_val),
                        "amarillas": int(ta_val),
                        "rojas": int(tr_val),
                    }
                )

            # Tarjetas: lista de jugadores con amarillas/rojas, ordenada por total desc
            tarjetas = [
                {
                    "jugador": s["jugador"],
                    "amarillas": s["amarillas"],
                    "rojas": s["rojas"],
                }
                for s in stats
                if s["amarillas"] or s["rojas"]
            ]

            # Orden: 1) mayor total (amarillas+rojas), 2) más rojas, 3) nombre A-Z
            tarjetas.sort(
                key=lambda x: (
                    -(x["amarillas"] + x["rojas"]),
                    -x["rojas"],
                    (x["jugador"] or ""),
                )
            )

            try:
                max_tarjetas_total = max(
                    (t["amarillas"] + t["rojas"] for t in tarjetas),
                    default=0,
                )
            except Exception:
                max_tarjetas_total = 0

            total_tarjetas_equipo = sum(
                (t["amarillas"] + t["rojas"] for t in tarjetas),
                0,
            )

            # Goles: lista de {jugador, valor} ordenada por valor desc y nombre asc
            goles = [
                {"jugador": s["jugador"], "valor": s["goles"]}
                for s in stats
                if s["goles"]
            ]
            goles.sort(
                key=lambda x: (
                    -(x["valor"] or 0),
                    (x["jugador"] or ""),
                )
            )

            # Minutos: lista de {jugador, valor} ordenada por valor desc y nombre asc
            minutos = [
                {"jugador": s["jugador"], "valor": s["minutos"]}
                for s in stats
                if s["minutos"]
            ]
            minutos.sort(
                key=lambda x: (
                    -(x["valor"] or 0),
                    (x["jugador"] or ""),
                )
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
        equipo_titulo=equipo_titulo,
        max_tarjetas_total=max_tarjetas_total,
        goles_favor_total=goles_favor_total,
        goles_contra_total=goles_contra_total,
        total_tarjetas_equipo=total_tarjetas_equipo,
        victorias_total=victorias_total,
        empates_total=empates_total,
        derrotas_total=derrotas_total,
    )

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import text
from dux import db

bp = Blueprint("dashboard_futbolistas", __name__, url_prefix="/dashboard/futbolistas")

@bp.get("/")
@login_required
def index():
    seleccionadas = request.args.getlist('jugadoras')
    seleccionadas_competicion = request.args.getlist('competicion')

    # --- Consulta de futbolistas ---
    sql_futbolistas = "SELECT id, nombre, apellido, competicion FROM futbolistas"
    filtros_f = []
    params_f = {}

    if seleccionadas:
        filtros_f.append("CONCAT(apellido, ', ', nombre) IN :nombres")
        params_f['nombres'] = tuple(seleccionadas)
    if seleccionadas_competicion:
        filtros_f.append("competicion IN :competicion")
        params_f['competicion'] = tuple(seleccionadas_competicion)

    if filtros_f:
        sql_futbolistas += " WHERE " + " AND ".join(filtros_f)

    result_futbolistas = db.session.execute(text(sql_futbolistas), params_f).mappings()
    futbolistas = []
    for r in result_futbolistas:
        futbolistas.append({
            'id': r['id'],
            'nombre': r['nombre'],
            'apellido': r['apellido'],
            'competicion': r['competicion'],
            'nombre_completo': f"{r['apellido']}, {r['nombre']}"
        })

    # --- Obtener todas las competiciones para el filtro ---
    sql_competiciones = "SELECT DISTINCT competicion FROM futbolistas"
    result_competiciones = db.session.execute(text(sql_competiciones))
    competiciones = [r[0] for r in result_competiciones]

    # --- Consulta de partidos ---
    sql_partidos = """
        SELECT CONCAT(f.apellido, ', ', f.nombre) AS nombre_completo, COUNT(a.jugador) AS partidos
        FROM futbolistas f
        LEFT JOIN actas a ON CONCAT(f.apellido, ', ', f.nombre) = a.jugador
    """
    filtros_p = []
    params_p = {}

    if seleccionadas:
        filtros_p.append("CONCAT(f.apellido, ', ', f.nombre) IN :nombres")
        params_p['nombres'] = tuple(seleccionadas)
    if seleccionadas_competicion:
        filtros_p.append("f.competicion IN :competicion")
        params_p['competicion'] = tuple(seleccionadas_competicion)

    if filtros_p:
        sql_partidos += " WHERE " + " AND ".join(filtros_p)

    sql_partidos += " GROUP BY nombre_completo ORDER BY partidos DESC"
    result_partidos = db.session.execute(text(sql_partidos), params_p).mappings()
    participaciones = {r['nombre_completo']: r['partidos'] for r in result_partidos}

    # --- Agregar partidos a cada futbolista ---
    for f in futbolistas:
        f['partidos'] = participaciones.get(f['nombre_completo'], 0)

    return render_template(
        "dashboard/futbolistas.html",
        futbolistas=futbolistas,
        seleccionadas=seleccionadas,
        competiciones=competiciones,
        seleccionadas_competicion=seleccionadas_competicion
    )


@bp.get("/caracteristicas")
@login_required
def caracteristicas():
    """Dashboard de características: distribución de futbolistas por competición.
    Reutiliza los mismos filtros para permitir enfocar por nombres/competición.
    """
    seleccionadas = request.args.getlist('jugadoras')
    seleccionadas_competicion = request.args.getlist('competicion')

    # --- Consulta base de futbolistas para llenar filtros (mismo approach que index) ---
    sql_futbolistas = "SELECT id, nombre, apellido, competicion FROM futbolistas"
    filtros_f = []
    params_f = {}

    if seleccionadas:
        filtros_f.append("CONCAT(apellido, ', ', nombre) IN :nombres")
        params_f['nombres'] = tuple(seleccionadas)
    if seleccionadas_competicion:
        filtros_f.append("competicion IN :competicion")
        params_f['competicion'] = tuple(seleccionadas_competicion)

    if filtros_f:
        sql_futbolistas += " WHERE " + " AND ".join(filtros_f)

    result_fut = db.session.execute(text(sql_futbolistas), params_f).mappings()
    futbolistas = []
    for r in result_fut:
        futbolistas.append({
            'id': r['id'],
            'nombre': r['nombre'],
            'apellido': r['apellido'],
            'competicion': r['competicion'],
            'nombre_completo': f"{r['apellido']}, {r['nombre']}"
        })

    # --- Obtener todas las competiciones para el filtro ---
    sql_competiciones = "SELECT DISTINCT competicion FROM futbolistas"
    result_comp = db.session.execute(text(sql_competiciones))
    competiciones = [r[0] for r in result_comp]

    # --- Distribución de futbolistas por competición (con filtros aplicados) ---
    sql_dist = """
        SELECT competicion, COUNT(*) AS cantidad
        FROM futbolistas
    """
    filtros_d = []
    params_d = {}
    if seleccionadas:
        filtros_d.append("CONCAT(apellido, ', ', nombre) IN :nombres")
        params_d['nombres'] = tuple(seleccionadas)
    if seleccionadas_competicion:
        filtros_d.append("competicion IN :competicion")
        params_d['competicion'] = tuple(seleccionadas_competicion)
    if filtros_d:
        sql_dist += " WHERE " + " AND ".join(filtros_d)
    sql_dist += " GROUP BY competicion ORDER BY cantidad DESC"

    result_dist = db.session.execute(text(sql_dist), params_d).mappings()
    dist_comp = [{'competicion': r['competicion'], 'cantidad': r['cantidad']} for r in result_dist]

    # --- Características adicionales: edad promedio por competición (en meses) y cantidad con reconocimiento médico ---
    # Columnas reales: fecha_nacimiento (DATE), reconocimiento_medico (DATE)
    sql_chars = """
        SELECT
            competicion,
            AVG(TIMESTAMPDIFF(MONTH, fecha_nacimiento, CURDATE())) AS edad_promedio_meses,
            COUNT(reconocimiento_medico) AS con_reconocimiento
        FROM futbolistas
    """
    filtros_ch = []
    params_ch = {}
    if seleccionadas:
        filtros_ch.append("CONCAT(apellido, ', ', nombre) IN :nombres")
        params_ch['nombres'] = tuple(seleccionadas)
    if seleccionadas_competicion:
        filtros_ch.append("competicion IN :competicion")
        params_ch['competicion'] = tuple(seleccionadas_competicion)
    if filtros_ch:
        sql_chars += " WHERE " + " AND ".join(filtros_ch)

    sql_chars += " GROUP BY competicion ORDER BY con_reconocimiento DESC"

    rows_chars = db.session.execute(text(sql_chars), params_ch).mappings()
    edad_prom = [{'competicion': r['competicion'], 'edad_promedio_meses': r['edad_promedio_meses']} for r in rows_chars]
    rec_med = [{'competicion': r['competicion'], 'con_reconocimiento': r['con_reconocimiento']} for r in rows_chars]

    # --- Detalle por futbolista (para gráficos por jugador): edad (en meses) y reconocimiento_medico ---
    sql_players = """
        SELECT
            CONCAT(apellido, ', ', nombre) AS nombre_completo,
            TIMESTAMPDIFF(MONTH, fecha_nacimiento, CURDATE()) AS edad_meses,
            reconocimiento_medico
        FROM futbolistas
    """
    filtros_pl = []
    params_pl = {}
    if seleccionadas:
        filtros_pl.append("CONCAT(apellido, ', ', nombre) IN :nombres")
        params_pl['nombres'] = tuple(seleccionadas)
    if seleccionadas_competicion:
        filtros_pl.append("competicion IN :competicion")
        params_pl['competicion'] = tuple(seleccionadas_competicion)
    if filtros_pl:
        sql_players += " WHERE " + " AND ".join(filtros_pl)

    result_players = db.session.execute(text(sql_players), params_pl).mappings()
    jugadores_detalle = []
    for r in result_players:
        frm = r['reconocimiento_medico']
        # Convertir a timestamp en ms si es datetime/date
        ts = None
        try:
            if frm is not None:
                import datetime
                if isinstance(frm, datetime.datetime):
                    ts = int(frm.timestamp() * 1000)
                elif isinstance(frm, datetime.date):
                    ts = int(datetime.datetime(frm.year, frm.month, frm.day).timestamp() * 1000)
        except Exception:
            ts = None
        jugadores_detalle.append({
            'nombre_completo': r['nombre_completo'],
            'edad_meses': r['edad_meses'],
            'reconocimiento_medico': frm.isoformat() if getattr(frm, 'isoformat', None) else (frm or None),
            'reconocimiento_ts': ts
        })

    return render_template(
        "dashboard/futbolistas_caracteristicas.html",
        futbolistas=futbolistas,
        competiciones=competiciones,
        seleccionadas=seleccionadas,
        seleccionadas_competicion=seleccionadas_competicion,
        dist_comp=dist_comp,
        edad_prom=edad_prom,
        rec_med=rec_med,
        jugadores_detalle=jugadores_detalle
    )

@bp.get("/estadisticas")
@login_required
def estadisticas():
    """Dashboard de estadísticas por usuario desde actas."""
    seleccionadas = request.args.getlist('jugadoras')
    seleccionadas_competicion = request.args.getlist('competicion')

    # --- Consulta base de futbolistas para filtros ---
    sql_futbolistas = "SELECT id, nombre, apellido, competicion FROM futbolistas"
    filtros_f = []
    params_f = {}
    if seleccionadas:
        filtros_f.append("CONCAT(apellido, ', ', nombre) IN :nombres")
        params_f['nombres'] = tuple(seleccionadas)
    if seleccionadas_competicion:
        filtros_f.append("competicion IN :competicion")
        params_f['competicion'] = tuple(seleccionadas_competicion)
    if filtros_f:
        sql_futbolistas += " WHERE " + " AND ".join(filtros_f)

    result_fut = db.session.execute(text(sql_futbolistas), params_f).mappings()
    futbolistas = []
    for r in result_fut:
        futbolistas.append({
            'id': r['id'],
            'nombre': r['nombre'],
            'apellido': r['apellido'],
            'competicion': r['competicion'],
            'nombre_completo': f"{r['apellido']}, {r['nombre']}"
        })

    # --- Opciones de competiciones ---
    sql_competiciones = "SELECT DISTINCT competicion FROM futbolistas"
    result_comp = db.session.execute(text(sql_competiciones))
    competiciones = [r[0] for r in result_comp]

    # --- Agregados por usuario desde actas ---
    sql_stats = """
        SELECT
            CONCAT(f.apellido, ', ', f.nombre) AS nombre_completo,
            COALESCE(SUM(`Goles`), 0)              AS goles,
            COALESCE(SUM(a.goles_penalty), 0)      AS goles_penalty,
            COALESCE(SUM(`Minutos`), 0)            AS minutos,
            COALESCE(SUM(a.tarjetas_amarillas), 0) AS amarillas,
            COALESCE(SUM(a.tarjetas_rojas), 0)     AS rojas
        FROM futbolistas f
        LEFT JOIN actas a ON CONCAT(f.apellido, ', ', f.nombre) = a.jugador
    """
    filtros_s = []
    params_s = {}
    if seleccionadas:
        filtros_s.append("CONCAT(f.apellido, ', ', f.nombre) IN :nombres")
        params_s['nombres'] = tuple(seleccionadas)
    if seleccionadas_competicion:
        filtros_s.append("f.competicion IN :competicion")
        params_s['competicion'] = tuple(seleccionadas_competicion)
    if filtros_s:
        sql_stats += " WHERE " + " AND ".join(filtros_s)
    sql_stats += " GROUP BY nombre_completo ORDER BY goles DESC"

    result_stats = db.session.execute(text(sql_stats), params_s).mappings()
    per_jugador = []
    for r in result_stats:
        per_jugador.append({
            'nombre_completo': r['nombre_completo'],
            'goles': int(r['goles'] or 0),
            'goles_penalty': int(r['goles_penalty'] or 0),
            'minutos': int(r['minutos'] or 0),
            'amarillas': int(r['amarillas'] or 0),
            'rojas': int(r['rojas'] or 0),
        })

    return render_template(
        "dashboard/futbolistas_estadisticas.html",
        futbolistas=futbolistas,
        competiciones=competiciones,
        seleccionadas=seleccionadas,
        seleccionadas_competicion=seleccionadas_competicion,
        per_jugador=per_jugador,
    )


@bp.get("/analisis-equipo")
@login_required
def analisis_equipo():
    """Dashboard de análisis del equipo con único filtro de competición."""
    seleccionadas_competicion = request.args.getlist('plantel') or request.args.getlist('competicion')

    # Opciones de competiciones para el filtro
    sql_competiciones = "SELECT DISTINCT competicion FROM futbolistas"
    result_comp = db.session.execute(text(sql_competiciones))
    competiciones = [r[0] for r in result_comp]

    # Series por jugador (desde actas)
    sql_stats = """
        SELECT
            CONCAT(f.apellido, ', ', f.nombre) AS nombre_completo,
            COALESCE(SUM(`Goles`), 0)              AS goles,
            COALESCE(SUM(`Minutos`), 0)            AS minutos,
            COALESCE(SUM(a.tarjetas_amarillas), 0) AS amarillas,
            COALESCE(SUM(a.tarjetas_rojas), 0)     AS rojas
        FROM futbolistas f
        LEFT JOIN actas a ON CONCAT(f.apellido, ', ', f.nombre) = a.jugador
    """
    filtros_s, params_s = [], {}
    if seleccionadas_competicion:
        filtros_s.append("f.competicion IN :competicion")
        params_s['competicion'] = tuple(seleccionadas_competicion)
    if filtros_s:
        sql_stats += " WHERE " + " AND ".join(filtros_s)
    sql_stats += " GROUP BY nombre_completo"

    rows = db.session.execute(text(sql_stats), params_s).mappings()
    per_jugador = []
    totals = { 'goles': 0, 'amarillas': 0, 'rojas': 0, 'minutos': 0 }
    for r in rows:
        item = {
            'nombre_completo': r['nombre_completo'],
            'goles': int(r['goles'] or 0),
            'minutos': int(r['minutos'] or 0),
            'amarillas': int(r['amarillas'] or 0),
            'rojas': int(r['rojas'] or 0),
        }
        per_jugador.append(item)
        totals['goles'] += item['goles']
        totals['amarillas'] += item['amarillas']
        totals['rojas'] += item['rojas']
        totals['minutos'] += item['minutos']

    # Partidos jugados (aprox) por el equipo: máximo conteo individual
    sql_part = """
        SELECT CONCAT(f.apellido, ', ', f.nombre) AS nombre_completo, COUNT(a.jugador) AS partidos
        FROM futbolistas f
        LEFT JOIN actas a ON CONCAT(f.apellido, ', ', f.nombre) = a.jugador
    """
    filtros_p, params_p = [], {}
    if seleccionadas_competicion:
        filtros_p.append("f.competicion IN :competicion")
        params_p['competicion'] = tuple(seleccionadas_competicion)
    if filtros_p:
        sql_part += " WHERE " + " AND ".join(filtros_p)
    sql_part += " GROUP BY nombre_completo"
    res_part = db.session.execute(text(sql_part), params_p).mappings()
    partidos_jugados = 0
    for r in res_part:
        partidos_jugados = max(partidos_jugados, int(r['partidos'] or 0))

    kpis = {
        'goles_favor': totals['goles'],
        'tarjetas_amarillas': totals['amarillas'],
        'tarjetas_rojas': totals['rojas'],
        'num_jugadores': len(per_jugador),
        'partidos_jugados': partidos_jugados,
    }

    print("DEBUG seleccionadas_competicion:", seleccionadas_competicion, flush=True)
    print("DEBUG per_jugador len:", len(per_jugador), flush=True)
    if per_jugador:
        print("DEBUG per_jugador sample:", per_jugador[:5], flush=True)

    return render_template(
        "dashboard/analisis_equipo.html",
        competiciones=competiciones,
        seleccionadas_competicion=seleccionadas_competicion,
        per_jugador=per_jugador,
        kpis=kpis,
    )
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from sqlalchemy import text
from collections import Counter
from dux import db, cache

bp = Blueprint("dashboard_futbolistas", __name__, url_prefix="/dashboard/futbolistas")


def _user_cache_key():
    user_id = current_user.id if current_user.is_authenticated else "anon"
    return f"view//{request.path}?{request.query_string.decode()}&_uid={user_id}"


@bp.get("/")
@login_required
@cache.cached(timeout=3600, make_cache_key=_user_cache_key)
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

    # --- Opciones de planteles (competición -> nombre legible) ---
    sql_competiciones = """
        SELECT DISTINCT
            f.competicion AS codigo,
            d.nombre_competicion AS nombre
        FROM futbolistas f
        LEFT JOIN diccionario_competiciones d
            ON f.competicion = d.id
        WHERE f.competicion IS NOT NULL
    """
    rows_comp = db.session.execute(text(sql_competiciones)).mappings()
    competiciones = [
        {
            "codigo": r["codigo"],
            "nombre": r["nombre"] or r["codigo"],  # por si alguna competición no está en el diccionario
        }
        for r in rows_comp
    ]

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
@cache.cached(timeout=3600, make_cache_key=_user_cache_key)
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

    # --- Opciones de planteles (competición -> nombre legible) ---
    sql_competiciones = """
        SELECT DISTINCT
            f.competicion AS codigo,
            d.nombre_competicion AS nombre
        FROM futbolistas f
        LEFT JOIN diccionario_competiciones d
            ON f.competicion = d.id
        WHERE f.competicion IS NOT NULL
    """
    rows_comp = db.session.execute(text(sql_competiciones)).mappings()
    competiciones = [
        {
            "codigo": r["codigo"],
            "nombre": r["nombre"] or r["codigo"],  # por si alguna competición no está en el diccionario
        }
        for r in rows_comp
    ]

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
@cache.cached(timeout=3600, make_cache_key=_user_cache_key)
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

    # --- Opciones de planteles (competición -> nombre legible) ---
    sql_competiciones = """
        SELECT DISTINCT
            f.competicion AS codigo,
            d.nombre_competicion AS nombre
        FROM futbolistas f
        LEFT JOIN diccionario_competiciones d
            ON f.competicion = d.id
        WHERE f.competicion IS NOT NULL
    """
    rows_comp = db.session.execute(text(sql_competiciones)).mappings()
    competiciones = [
        {
            "codigo": r["codigo"],
            "nombre": r["nombre"] or r["codigo"],  # fallback a sigla si falta el nombre
        }
        for r in rows_comp
    ]

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
@cache.cached(timeout=3600, make_cache_key=_user_cache_key)
def analisis_equipo():
    """Dashboard de análisis del equipo con único filtro de competición."""
    seleccionadas_competicion = request.args.getlist('plantel') or request.args.getlist('competicion')

    # Opciones de planteles para el filtro (sigla -> nombre legible)
    sql_competiciones = """
        SELECT DISTINCT
            f.competicion AS codigo,
            d.nombre_competicion AS nombre
        FROM futbolistas f
        LEFT JOIN diccionario_competiciones d
            ON f.competicion = d.id
        WHERE f.competicion IS NOT NULL
    """
    rows_comp = db.session.execute(text(sql_competiciones)).mappings()
    competiciones = [
        {
            "codigo": r["codigo"],
            "nombre": r["nombre"] or r["codigo"],  # fallback a sigla si faltara el nombre
        }
        for r in rows_comp
    ]

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

    return render_template(
        "dashboard/analisis_equipo.html",
        competiciones=competiciones,
        seleccionadas_competicion=seleccionadas_competicion,
        per_jugador=per_jugador,
        kpis=kpis,
    )

@bp.get("/sustituciones")
@login_required
@cache.cached(timeout=3600, make_cache_key=_user_cache_key)
def sustituciones():
    """Análisis de las sustituciones por equipo (minutos, top combos, etc.)."""

    # --- Filtros desde la URL ---
    equipo = request.args.get("equipo") or None
    jornada = request.args.get("jornada", type=int)
    lv = request.args.get("lv") or None   # 'L', 'V' o None
    plantel = request.args.get("plantel") or None  # nombre_competicion

    # --- Opciones para los filtros (equipos, jornadas, planteles) ---
    sql_equipos = """
        SELECT DISTINCT equipo
        FROM sustituciones
        WHERE equipo IS NOT NULL
        ORDER BY equipo
    """
    equipos = [r[0] for r in db.session.execute(text(sql_equipos))]

    sql_jornadas = """
        SELECT DISTINCT jornada
        FROM jornadas
        WHERE jornada IS NOT NULL
        ORDER BY jornada
    """
    jornadas = [r[0] for r in db.session.execute(text(sql_jornadas))]

    sql_planteles = """
        SELECT DISTINCT nombre_competicion
        FROM diccionario_competiciones
        ORDER BY nombre_competicion
    """
    planteles = [r[0] for r in db.session.execute(text(sql_planteles))]

    # --- Query base: sustituciones + jornada + condición local/visitante + plantel ---
    sql_base = """
        SELECT
            s.acta_id,
            s.equipo,
            s.sale,
            s.entra,
            s.minuto,
            j.jornada,
            CASE
                WHEN s.equipo = cl.nombre_equipo THEN 'L'
                WHEN s.equipo = cv.nombre_equipo THEN 'V'
                ELSE NULL
            END AS condicion_lv,
            CASE
                WHEN s.equipo = cl.nombre_equipo THEN dcl.nombre_competicion
                WHEN s.equipo = cv.nombre_equipo THEN dcv.nombre_competicion
                ELSE NULL
            END AS plantel
        FROM sustituciones s
        LEFT JOIN jornadas j
            ON s.acta_id = j.acta_id
        LEFT JOIN competiciones cl
            ON j.id_equipo_local = cl.id_equipo
        LEFT JOIN competiciones cv
            ON j.id_equipo_visitante = cv.id_equipo
        LEFT JOIN diccionario_competiciones dcl
            ON cl.competicion = dcl.id
        LEFT JOIN diccionario_competiciones dcv
            ON cv.competicion = dcv.id
        WHERE 1 = 1
    """
    params = {}

    if equipo:
        sql_base += " AND s.equipo = :equipo"
        params["equipo"] = equipo

    if jornada is not None:
        sql_base += " AND j.jornada = :jornada"
        params["jornada"] = jornada

    if lv in ("L", "V"):
        sql_base += """
            AND CASE
                    WHEN s.equipo = cl.nombre_equipo THEN 'L'
                    WHEN s.equipo = cv.nombre_equipo THEN 'V'
                END = :lv
        """
        params["lv"] = lv

    if plantel:
        sql_base += """
            AND CASE
                    WHEN s.equipo = cl.nombre_equipo THEN dcl.nombre_competicion
                    WHEN s.equipo = cv.nombre_equipo THEN dcv.nombre_competicion
                END = :plantel
        """
        params["plantel"] = plantel

    rows = db.session.execute(text(sql_base), params).mappings().all()

    # Si no hay datos, devolvemos algo vacío pero sin romper el template
    if not rows:
        context = {
            "equipos": equipos,
            "jornadas": jornadas,
            "planteles": planteles,
            "equipo_seleccionado": equipo,
            "jornada_seleccionada": jornada,
            "lv_seleccionado": lv,
            "plantel_seleccionado": plantel,
            "minuto_medio": None,
            "minuto_medio_primera": None,
            "minuto_medio_ultima": None,
            "num_medio_sustituciones": None,
            "distribucion_minuto": [],
            "cambios_por_jornada": [],
            "top_parejas": [],
            "top_sustituidos": [],
            "top_banquillo": [],
        }
        return render_template("dashboard/sustituciones.html", **context)

    # --- Métricas principales en Python ---
    minutos = [r["minuto"] for r in rows if r["minuto"] is not None]

    minuto_medio = round(sum(minutos) / len(minutos)) if minutos else None

    # Agrupación por acta para primera/última y nº de cambios
    por_acta = {}
    for r in rows:
        acta_id = r["acta_id"]
        m = r["minuto"] or 0
        if acta_id not in por_acta:
            por_acta[acta_id] = {"count": 1, "min": m, "max": m}
        else:
            por_acta[acta_id]["count"] += 1
            por_acta[acta_id]["min"] = min(por_acta[acta_id]["min"], m)
            por_acta[acta_id]["max"] = max(por_acta[acta_id]["max"], m)

    if por_acta:
        minuto_medio_primera = round(
            sum(v["min"] for v in por_acta.values()) / len(por_acta)
        )
        minuto_medio_ultima = round(
            sum(v["max"] for v in por_acta.values()) / len(por_acta)
        )
        num_medio_sustituciones = round(
            sum(v["count"] for v in por_acta.values()) / len(por_acta), 1
        )
    else:
        minuto_medio_primera = minuto_medio_ultima = num_medio_sustituciones = None

    # Distribución por minuto
    dist_counter = Counter(minutos)
    distribucion_minuto = [
        {"minuto": m, "n": dist_counter[m]} for m in sorted(dist_counter.keys())
    ]

    # Número de cambios por jornada
    jornadas_counter = Counter(r["jornada"] for r in rows if r["jornada"] is not None)
    cambios_por_jornada = [
        {"jornada": j, "n": jornadas_counter[j]} for j in sorted(jornadas_counter.keys())
    ]

    # Top 5 sustituciones (sale -> entra)
    pareja_counter = Counter((r["sale"], r["entra"]) for r in rows)
    top_parejas = []
    for (sale, entra), n in pareja_counter.most_common(5):
        top_parejas.append({"sale": sale, "entra": entra, "n": n})

    # Top 5 jugadores sustituidos (quién sale más)
    sale_counter = Counter(r["sale"] for r in rows)
    top_sustituidos = [
        {"sale": nombre, "n": n} for nombre, n in sale_counter.most_common(5)
    ]

    # --- Top minutos desde el banquillo (desde actas) ---
    sql_banquillo = """
        SELECT
            a.jugador,
            SUM(a.minutos) AS minutos_desde_banquillo
        FROM actas a
        LEFT JOIN jornadas j
            ON a.acta_id = j.acta_id
        LEFT JOIN competiciones cl
            ON j.id_equipo_local = cl.id_equipo
        LEFT JOIN competiciones cv
            ON j.id_equipo_visitante = cv.id_equipo
        LEFT JOIN diccionario_competiciones dcl
            ON cl.competicion = dcl.id
        LEFT JOIN diccionario_competiciones dcv
            ON cv.competicion = dcv.id
        WHERE a.titular = 0
    """
    params_b = {}

    if equipo:
        sql_banquillo += " AND a.equipo = :equipo"
        params_b["equipo"] = equipo

    if jornada is not None:
        sql_banquillo += " AND j.jornada = :jornada"
        params_b["jornada"] = jornada

    if lv in ("L", "V"):
        sql_banquillo += """
            AND CASE
                    WHEN a.equipo = cl.nombre_equipo THEN 'L'
                    WHEN a.equipo = cv.nombre_equipo THEN 'V'
                END = :lv
        """
        params_b["lv"] = lv

    if plantel:
        sql_banquillo += """
            AND CASE
                    WHEN a.equipo = cl.nombre_equipo THEN dcl.nombre_competicion
                    WHEN a.equipo = cv.nombre_equipo THEN dcv.nombre_competicion
                END = :plantel
        """
        params_b["plantel"] = plantel

    sql_banquillo += """
        GROUP BY a.jugador
        ORDER BY minutos_desde_banquillo DESC
        LIMIT 5
    """

    top_banquillo_rows = db.session.execute(text(sql_banquillo), params_b).mappings().all()
    top_banquillo = [
        {"jugador": r["jugador"], "minutos": r["minutos_desde_banquillo"]}
        for r in top_banquillo_rows
    ]

    context = {
        "equipos": equipos,
        "jornadas": jornadas,
        "planteles": planteles,
        "equipo_seleccionado": equipo,
        "jornada_seleccionada": jornada,
        "lv_seleccionado": lv,
        "plantel_seleccionado": plantel,
        "minuto_medio": minuto_medio,
        "minuto_medio_primera": minuto_medio_primera,
        "minuto_medio_ultima": minuto_medio_ultima,
        "num_medio_sustituciones": num_medio_sustituciones,
        "distribucion_minuto": distribucion_minuto,
        "cambios_por_jornada": cambios_por_jornada,
        "top_parejas": top_parejas,
        "top_sustituidos": top_sustituidos,
        "top_banquillo": top_banquillo,
    }

    return render_template("dashboard/sustituciones.html", **context)
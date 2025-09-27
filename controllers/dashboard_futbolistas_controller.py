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
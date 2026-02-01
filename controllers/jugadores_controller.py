"""Jugadores controller: CRUD para la tabla `futbolistas`.
Campos: id (PK, varchar), nombre, apellido, sexo, fecha_nacimiento (date), reconocimiento_medico (date), id_estado (FK a state_user.id)
"""
import math
import uuid
import unicodedata
from datetime import date, datetime
from difflib import get_close_matches
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, case

from dux import db
from dux.models import Base
from dux.security import require_perm

jugadores_bp = Blueprint("jugadores", __name__, url_prefix="/jugadores")


def _model(name: str):
    return getattr(Base.classes, name, None)


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except Exception:
        return None


def _to_date(v) -> date | None:
    """Normaliza a date: acepta None, str (varios formatos), datetime o date."""
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        s = v.strip()
        # Intentos de parseo comunes
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
        try:
            # ISO flexible (p. ej. '2025-09-17')
            return date.fromisoformat(s)
        except Exception:
            return None
    return None


def _normalizar_texto_simple(s: str | None) -> str:
    """Normaliza texto a minúsculas sin tildes ni signos diacríticos."""
    if not s:
        return ""
    s = s.strip().lower()
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.category(c).startswith("M"))


COMPETICION_ORDER = {
    "1FF": 1,
    "3FFF": 2,
    "1J": 3,
    "1C": 4,
    "2C": 5,
    "CFF": 6,
    "1I": 7,
    "IFF": 8,
}


# LISTA
@jugadores_bp.get("/")
@login_required
@require_perm("read_jugador")
def list():  # type: ignore[override]
    F = _model("futbolistas")
    S = _model("state_user")
    I = _model("informacion_futbolistas")
    if not F:
        return "Modelo futbolistas no disponible", 500

    q = request.args.get("q", "").strip()
    competicion = request.args.get("competicion", "1FF").strip()

    genero_col = F.genero.label("genero")

    cols = [
        F.id,
        F.nombre,
        F.apellido,
        genero_col,
    ]
    cols.extend(
        [
            F.fecha_nacimiento,
            F.reconocimiento_medico,
            F.id_estado,
            getattr(F, "competicion", None).label("competicion"),
            S.name.label("estado_nombre"),
            getattr(I, "nacionalidad", None).label("nacionalidad"),
            getattr(I, "posicion", None).label("posicion"),
            getattr(I, "dorsal", None).label("dorsal"),
            getattr(F, "verificado", None).label("verificado"),
        ]
    )

    query = db.session.query(*cols)

    # añade el JOIN (LEFT/OUTER para no romper si falta info):
    if I is not None:
        # usa la clave correcta según tu BD:
        join_cond = None
        if hasattr(I, "id_futbolista") and hasattr(F, "id"):
            join_cond = I.id_futbolista == F.id
        elif hasattr(I, "identificacion") and hasattr(F, "identificacion"):
            join_cond = I.identificacion == F.identificacion
        if join_cond is not None:
            query = query.outerjoin(I, join_cond)

    # (el join con estados ya está)
    query = query.outerjoin(S, F.id_estado == S.id)

    if q:
        like = f"%{q}%"
        filtros = [
            F.nombre.ilike(like),
            F.apellido.ilike(like),
            F.genero.ilike(like),
            S.name.ilike(like),
        ]
        if hasattr(F, "identificacion"):
            filtros.append(getattr(F, "identificacion").ilike(like))
        if I is not None and hasattr(I, "identificacion"):
            filtros.append(getattr(I, "identificacion").ilike(like))
        query = query.filter(or_(*filtros))

    if competicion and hasattr(F, "competicion"):
        query = query.filter(F.competicion == competicion)

    # Ordenamiento personalizado por posición (POR, DEF, MC, DEL) y luego por dorsal
    if I is not None:
        posicion_order = case(
            (getattr(I, "posicion", None) == "POR", 1),
            (getattr(I, "posicion", None) == "DEF", 2),
            (getattr(I, "posicion", None) == "MC", 3),
            (getattr(I, "posicion", None) == "DEL", 4),
            else_=5
        )
        query = query.order_by(
            posicion_order,
            getattr(I, "dorsal", None).is_(None),
            getattr(I, "dorsal", None).asc()
        )
    else:
        query = query.order_by(F.apellido.is_(None), F.apellido.asc(),
                               F.nombre.is_(None), F.nombre.asc())

    page = int(request.args.get("page", 1))
    per_page = 50
    total = query.count()
    rows_db = query.limit(per_page).offset((page - 1) * per_page).all()
    pages = max(1, math.ceil(total / per_page))

    hoy = date.today()

    def edad_ym(dn: date | None) -> str:
        if not dn:
            return ""
        años = hoy.year - dn.year - ((hoy.month, hoy.day) < (dn.month, dn.day))
        meses = (hoy.year - dn.year) * 12 + (hoy.month - dn.month)
        if hoy.day < dn.day:
            meses -= 1
        meses = max(0, meses - años * 12)
        return f"{años} años y {meses} meses"

    rows = []
    for r in rows_db:
        fn = _to_date(r.fecha_nacimiento)
        rm = _to_date(r.reconocimiento_medico)
        vencido = (rm is not None and rm < hoy)
        rows.append({
            "id": r.id,
            "nombre": r.nombre,
            "apellido": r.apellido,
            "dorsal": getattr(r, "dorsal", None),
            "posicion": getattr(r, "posicion", None),
            "genero": r.genero,
            "edad": edad_ym(fn),
            "reconocimiento_medico": rm,     # ya es date o None
            "estado": r.estado_nombre or "",
            "id_estado": r.id_estado,
            "competicion": getattr(r, "competicion", None),
            "vencido": vencido,
            "nacionalidad": getattr(r, "nacionalidad", None),
            "verificado": getattr(r, "verificado", None),
        })

    competiciones = []
    D = getattr(Base.classes, "diccionario_competiciones", None)
    if hasattr(F, "competicion") and D is not None:
        rows_comp = (
            db.session.query(D.id, D.nombre_competicion)
            .join(F, F.competicion == D.id)
            .filter(F.competicion.isnot(None))
            .distinct()
            .order_by(D.nombre_competicion.asc())
            .all()
        )
        competiciones = [{"id": r[0], "nombre": r[1]} for r in rows_comp]
        competiciones.sort(key=lambda c: COMPETICION_ORDER.get(c["id"], 999))
        competiciones.sort(key=lambda c: COMPETICION_ORDER.get(c["id"], 999))

    # Verificar si al menos un jugador tiene cada campo
    mostrar_nacionalidad = any(r["nacionalidad"] for r in rows)
    mostrar_dorsal = any(r["dorsal"] for r in rows)
    mostrar_posicion = any(r["posicion"] for r in rows)

    return render_template(
        "list/jugadores.html",
        rows=rows,
        q=q,
        page=page,
        pages=pages,
        competicion=competicion,
        competiciones=competiciones,
        total=total,
        mostrar_nacionalidad=mostrar_nacionalidad,
        mostrar_dorsal=mostrar_dorsal,
        mostrar_posicion=mostrar_posicion
    )


# Diccionario de países con sus códigos ISO
PAISES_ISO = {
    'España': 'ES', 'Alemania': 'DE', 'Francia': 'FR', 'Italia': 'IT', 'Portugal': 'PT',
    'Inglaterra': 'GB-ENG', 'Reino Unido': 'GB', 'Escocia': 'GB-SCT', 'Gales': 'GB-WLS',
    'Paises Bajos': 'NL', 'Holanda': 'NL', 'Belgica': 'BE', 'Suiza': 'CH', 'Austria': 'AT',
    'Dinamarca': 'DK', 'Suecia': 'SE', 'Noruega': 'NO', 'Finlandia': 'FI', 'Polonia': 'PL',
    'Republica Checa': 'CZ', 'Hungria': 'HU', 'Rumania': 'RO', 'Bulgaria': 'BG', 'Grecia': 'GR',
    'Croacia': 'HR', 'Serbia': 'RS', 'Eslovenia': 'SI', 'Eslovaquia': 'SK', 'Ucrania': 'UA',
    'Rusia': 'RU', 'Turquia': 'TR', 'Brasil': 'BR', 'Argentina': 'AR', 'Uruguay': 'UY',
    'Paraguay': 'PY', 'Chile': 'CL', 'Colombia': 'CO', 'Peru': 'PE', 'Venezuela': 'VE',
    'Ecuador': 'EC', 'Bolivia': 'BO', 'Mexico': 'MX', 'Estados Unidos': 'US', 'Canada': 'CA',
    'Japon': 'JP', 'Corea del Sur': 'KR', 'China': 'CN', 'Australia': 'AU', 'Nueva Zelanda': 'NZ',
    'Marruecos': 'MA', 'Argelia': 'DZ', 'Tunez': 'TN', 'Egipto': 'EG', 'Nigeria': 'NG',
    'Senegal': 'SN', 'Ghana': 'GH', 'Costa de Marfil': 'CI', 'Camerun': 'CM', 'Sudafrica': 'ZA'
}

def _normalizar_pais(pais_input: str) -> tuple[str, str] | None:
    """Convierte nombre de país a código ISO usando fuzzy matching.
    Retorna (nombre_estandarizado, codigo_iso) o None"""
    if not pais_input:
        return None
    
    pais_input = pais_input.strip()
    # Normalizar texto (quitar tildes, minúsculas)
    pais_normalizado = pais_input.lower()
    normalizaciones = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ñ': 'n', 'ü': 'u'
    }
    for orig, repl in normalizaciones.items():
        pais_normalizado = pais_normalizado.replace(orig, repl)
    
    # Crear versión normalizada de los países
    paises_normalizados = {}
    for nombre, iso in PAISES_ISO.items():
        nombre_norm = nombre.lower()
        for orig, repl in normalizaciones.items():
            nombre_norm = nombre_norm.replace(orig, repl)
        paises_normalizados[nombre_norm] = (nombre, iso)
    
    # Buscar coincidencia exacta primero
    if pais_normalizado in paises_normalizados:
        return paises_normalizados[pais_normalizado]
    
    # Fuzzy matching
    matches = get_close_matches(pais_normalizado, paises_normalizados.keys(), n=1, cutoff=0.6)
    if matches:
        return paises_normalizados[matches[0]]
    
    return None

# helper formulario
def _form(row_id: str | None = None):
    F = _model("futbolistas")
    S = _model("state_user")
    I = _model("informacion_futbolistas")
    if not F:
        return "Modelo futbolistas no disponible", 500

    estados = []
    if S:
        rows = db.session.query(S.id, S.name).order_by(S.name.asc()).all()
        estados = [(r.id, r.name) for r in rows]

    row = db.session.get(F, row_id) if row_id else None
    info_row = None
    
    # Cargar información adicional si existe
    if row and I:
        if hasattr(I, "id_futbolista"):
            info_row = db.session.query(I).filter(I.id_futbolista == row.id).first()
        elif hasattr(I, "identificacion") and hasattr(row, "identificacion"):
            info_row = db.session.query(I).filter(I.identificacion == row.identificacion).first()

    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        apellido = (request.form.get("apellido") or "").strip()
        genero_val = (request.form.get("genero") or "").strip()
        id_estado = request.form.get("id_estado")
        fecha_nacimiento = _parse_date(request.form.get("fecha_nacimiento"))
        reconocimiento_medico = _parse_date(request.form.get("reconocimiento_medico"))
        competicion_val = (request.form.get("competicion") or "").strip() if hasattr(F, "competicion") else None
        identificacion_val = (request.form.get("identificacion") or "").strip()
        
        # Nuevos campos de informacion_futbolistas
        dorsal_val = request.form.get("dorsal", "").strip()
        posicion_val = request.form.get("posicion", "").strip()
        nacionalidad_input = request.form.get("nacionalidad", "").strip()
        altura_val = request.form.get("altura", "").strip()
        peso_val = request.form.get("peso", "").strip()

        old_identificacion = getattr(row, "identificacion", None) if row and hasattr(row, "identificacion") else None
        
        # Procesar nacionalidad con fuzzy matching
        nacionalidad_iso = None
        nacionalidad_nombre = None
        if nacionalidad_input:
            resultado = _normalizar_pais(nacionalidad_input)
            if resultado:
                nacionalidad_nombre, nacionalidad_iso = resultado
            else:
                nacionalidad_iso = nacionalidad_input.upper()[:2]  # Fallback: primeras 2 letras en mayúscula

        require_ident = hasattr(F, "identificacion")
        if not nombre or not apellido or (require_ident and not identificacion_val):
            if require_ident:
                flash("Nombre, Apellido y DNI/Pasaporte son obligatorios", "warning")
            else:
                flash("Nombre y Apellido son obligatorios", "warning")
        else:
            try:
                if not row:
                    # Dejar que la BD genere el id (AUTO_INCREMENT)
                    row = F()
                    db.session.add(row)

                row.nombre = nombre
                row.apellido = apellido
                row.genero = genero_val or None
                # Asignar/editar identificacion (DNI/pasaporte) si la columna existe
                if hasattr(row, "identificacion"):
                    if identificacion_val:
                        row.identificacion = identificacion_val
                    elif not getattr(row, "identificacion", None):
                        # Generar identificacion si sigue vacía (fallback UUID)
                        row.identificacion = str(uuid.uuid4())
                row.id_estado = int(id_estado) if id_estado else None
                row.fecha_nacimiento = fecha_nacimiento
                row.reconocimiento_medico = reconocimiento_medico
                if hasattr(F, "competicion"):
                    setattr(row, "competicion", competicion_val or None)
                
                db.session.flush()  # Para obtener el ID si es nuevo
                
                # Actualizar o crear registro en informacion_futbolistas
                if I and row.id:
                    if not info_row:
                        info_row = I()
                        # Enlazar por id_futbolista si existe, si no por identificacion
                        if hasattr(I, "id_futbolista"):
                            setattr(info_row, "id_futbolista", row.id)
                        if hasattr(I, "identificacion") and hasattr(row, "identificacion"):
                            setattr(info_row, "identificacion", row.identificacion)
                        db.session.add(info_row)

                    # Si ya existe info_row y ha cambiado la identificacion, propagar el cambio
                    if info_row and hasattr(I, "identificacion") and hasattr(row, "identificacion"):
                        nueva_identificacion = getattr(row, "identificacion", None)
                        if nueva_identificacion and nueva_identificacion != old_identificacion:
                            setattr(info_row, "identificacion", nueva_identificacion)
                    
                    # Actualizar campos
                    if hasattr(I, "dorsal"):
                        setattr(info_row, "dorsal", int(dorsal_val) if dorsal_val and dorsal_val.isdigit() else None)
                    if hasattr(I, "posicion"):
                        setattr(info_row, "posicion", posicion_val or None)
                    if hasattr(I, "nacionalidad"):
                        setattr(info_row, "nacionalidad", nacionalidad_iso or None)
                    if hasattr(I, "altura"):
                        setattr(info_row, "altura", float(altura_val) if altura_val else None)
                    if hasattr(I, "peso"):
                        setattr(info_row, "peso", float(peso_val) if peso_val else None)

                db.session.commit()
                
                if nacionalidad_nombre and nacionalidad_input.lower() != nacionalidad_nombre.lower():
                    flash(f"Futbolista guardado. Nacionalidad interpretada como: {nacionalidad_nombre}", "success")
                else:
                    flash("Futbolista guardado", "success")
                return redirect(url_for("jugadores.list"))
            except IntegrityError as e:
                db.session.rollback()
                # Mostrar el detalle real del error de BD para saber qué restricción falla
                msg = getattr(e.orig, "args", [str(e)])[0] if getattr(e, "orig", None) else str(e)
                flash(f"Error de integridad en BD: {msg}", "danger")
            except Exception as e:
                db.session.rollback()
                flash(f"Error al guardar: {str(e)}", "danger")

    # calcula edad en años y meses si hay fecha de nacimiento
    edad = None
    if row and row.fecha_nacimiento:
        hoy = date.today()
        dn = row.fecha_nacimiento
        anios = hoy.year - dn.year - ((hoy.month, hoy.day) < (dn.month, dn.day))
        meses_tot = (hoy.year - dn.year) * 12 + (hoy.month - dn.month)
        if hoy.day < dn.day:
            meses_tot -= 1
        meses = max(0, meses_tot - anios * 12)
        edad = f"{anios} años y {meses} meses"
    
    # Obtener nombre del país desde el código ISO
    nacionalidad_display = None
    if info_row and hasattr(info_row, "nacionalidad") and info_row.nacionalidad:
        # Buscar el nombre del país por su código ISO
        for nombre, iso in PAISES_ISO.items():
            if iso == info_row.nacionalidad:
                nacionalidad_display = nombre
                break
        if not nacionalidad_display:
            nacionalidad_display = info_row.nacionalidad  # Mostrar código si no se encuentra

    # Obtener lista de competiciones para el desplegable
    competiciones = []
    D = getattr(Base.classes, "diccionario_competiciones", None)
    if hasattr(F, "competicion") and D is not None:
        rows_comp = (
            db.session.query(D.id, D.nombre_competicion)
            .join(F, F.competicion == D.id)
            .filter(F.competicion.isnot(None))
            .distinct()
            .order_by(D.nombre_competicion.asc())
            .all()
        )
        competiciones = [{"id": r[0], "nombre": r[1]} for r in rows_comp]

    return render_template(
        "records/jugador_form.html", 
        row=row, 
        estados=estados, 
        edad=edad,
        info_row=info_row,
        nacionalidad_display=nacionalidad_display,
        competiciones=competiciones
    )


@jugadores_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_perm("create_jugador")
def new():
    return _form()


@jugadores_bp.route("/<string:row_id>/edit", methods=["GET", "POST"])
@login_required
@require_perm("update_jugador")
def edit(row_id: str):
    return _form(row_id)


@jugadores_bp.post("/check-duplicado")
@login_required
@require_perm("create_jugador")
def check_duplicado():
    F = _model("futbolistas")
    if not F:
        return jsonify({"error": "Modelo futbolistas no disponible"}), 500

    nombre = (request.form.get("nombre") or "").strip()
    apellido = (request.form.get("apellido") or "").strip()
    identificacion_val = (request.form.get("identificacion") or "").strip()

    exists_nombre_apellido = False
    exists_identificacion = False
    identificacion_existente = None
    nombre_existente = None

    if nombre and apellido:
        norm_nombre = _normalizar_texto_simple(nombre)
        norm_apellido = _normalizar_texto_simple(apellido)

        existing = None
        candidatos = (
            db.session.query(F)
            .filter(F.nombre.isnot(None), F.apellido.isnot(None))
            .all()
        )
        for c in candidatos:
            if (
                _normalizar_texto_simple(getattr(c, "nombre", "")) == norm_nombre
                and _normalizar_texto_simple(getattr(c, "apellido", "")) == norm_apellido
            ):
                existing = c
                break

        if existing:
            exists_nombre_apellido = True
            identificacion_existente = getattr(existing, "identificacion", None)

    if identificacion_val and hasattr(F, "identificacion"):
        existing2 = (
            db.session.query(F)
            .filter(getattr(F, "identificacion") == identificacion_val)
            .first()
        )
        if existing2:
            exists_identificacion = True
            nombre_existente = f"{getattr(existing2, 'nombre', '')} {getattr(existing2, 'apellido', '')}".strip()

    return jsonify(
        {
            "exists_nombre_apellido": exists_nombre_apellido,
            "exists_identificacion": exists_identificacion,
            "identificacion_existente": identificacion_existente,
            "nombre_existente": nombre_existente,
        }
    )


@jugadores_bp.post("/<string:row_id>/delete")
@login_required
@require_perm("delete_jugador")
def delete(row_id: str):
    F = _model("futbolistas")
    I = _model("informacion_futbolistas")
    if not F:
        return "Modelo futbolistas no disponible", 500

    row = db.session.get(F, row_id)
    if row:
        # Eliminar información adicional ligada al futbolista
        if I is not None:
            identificacion = getattr(row, "identificacion", None)

            # Si la tabla tiene columna id_futbolista, eliminar por ese campo
            if hasattr(I, "id_futbolista"):
                db.session.query(I).filter(I.id_futbolista == row.id).delete(synchronize_session=False)

            # Si la tabla está enlazada por identificacion, eliminar también por ahí
            if identificacion is not None and hasattr(I, "identificacion"):
                db.session.query(I).filter(I.identificacion == identificacion).delete(synchronize_session=False)

        # Eliminar el propio futbolista
        db.session.delete(row)
        db.session.commit()
        flash("Futbolista eliminado", "info")

    return redirect(url_for("jugadores.list"))


@jugadores_bp.post("/<string:row_id>/toggle-verificado")
@login_required
@require_perm("update_jugador")
def toggle_verificado(row_id: str):
    """Alterna el campo verificado (0/1) de un futbolista.

    Solo accesible para usuarios con permiso de actualización de jugador.
    """
    F = _model("futbolistas")
    if not F:
        return "Modelo futbolistas no disponible", 500

    row = db.session.get(F, row_id)
    if not row or not hasattr(row, "verificado"):
        flash("No se pudo actualizar la verificación del futbolista", "danger")
        return redirect(url_for("jugadores.list"))

    try:
        actual = getattr(row, "verificado") or 0
        nuevo = 0 if int(actual) else 1
    except Exception:
        nuevo = 1 if not getattr(row, "verificado", None) else 0

    setattr(row, "verificado", nuevo)
    db.session.commit()
    flash("Estado de verificación actualizado", "success")
    return redirect(url_for("jugadores.list"))

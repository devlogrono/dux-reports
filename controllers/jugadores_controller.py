"""Jugadores controller: CRUD para la tabla `futbolistas`.
Campos: id (PK, varchar), nombre, apellido, sexo, fecha_nacimiento (date), reconocimiento_medico (date), id_estado (FK a state_user.id)
"""
import math
import uuid
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

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


# LISTA
@jugadores_bp.get("/")
@login_required
@require_perm("read_jugador")
def list():  # type: ignore[override]
    F = _model("futbolistas")
    S = _model("state_user")
    if not F:
        return "Modelo futbolistas no disponible", 500

    q = request.args.get("q", "").strip()
    competicion = request.args.get("competicion", "").strip()

    query = db.session.query(
        F.id,
        F.nombre,
        F.apellido,
        F.sexo,
        F.fecha_nacimiento,
        F.reconocimiento_medico,
        F.id_estado,
        getattr(F, "competicion", None).label("competicion"),
        S.name.label("estado_nombre"),
    ).outerjoin(S, F.id_estado == S.id)

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                F.nombre.ilike(like),
                F.apellido.ilike(like),
                F.sexo.ilike(like),
                S.name.ilike(like),
            )
        )

    if competicion and hasattr(F, "competicion"):
        query = query.filter(F.competicion == competicion)

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
            "sexo": r.sexo,
            "edad": edad_ym(fn),
            "reconocimiento_medico": rm,     # ya es date o None
            "estado": r.estado_nombre or "",
            "id_estado": r.id_estado,
            "competicion": getattr(r, "competicion", None),
            "vencido": vencido,
        })

    competiciones = []
    if hasattr(F, "competicion"):
        competiciones = [
            c[0] for c in db.session.query(F.competicion)
            .filter(F.competicion.isnot(None))
            .distinct().order_by(F.competicion.asc()).all()
        ]

    return render_template(
        "list/jugadores.html",
        rows=rows,
        q=q,
        page=page,
        pages=pages,
        competicion=competicion,
        competiciones=competiciones,
        total=total
    )


# helper formulario
def _form(row_id: str | None = None):
    F = _model("futbolistas")
    S = _model("state_user")
    if not F:
        return "Modelo futbolistas no disponible", 500

    estados = []
    if S:
        estados = db.session.query(S.id, S.name).order_by(S.name.asc()).all()

    row = db.session.get(F, row_id) if row_id else None

    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        apellido = (request.form.get("apellido") or "").strip()
        sexo = (request.form.get("sexo") or "").strip()
        id_estado = request.form.get("id_estado")
        fecha_nacimiento = _parse_date(request.form.get("fecha_nacimiento"))
        reconocimiento_medico = _parse_date(request.form.get("reconocimiento_medico"))
        competicion_val = (request.form.get("competicion") or "").strip() if hasattr(F, "competicion") else None

        if not nombre or not apellido:
            flash("Nombre y Apellido son obligatorios", "warning")
        else:
            try:
                if not row:
                    row = F(id=str(uuid.uuid4()))
                    db.session.add(row)

                row.nombre = nombre
                row.apellido = apellido
                row.sexo = sexo or None
                row.id_estado = int(id_estado) if id_estado else None
                row.fecha_nacimiento = fecha_nacimiento
                row.reconocimiento_medico = reconocimiento_medico
                if hasattr(F, "competicion"):
                    setattr(row, "competicion", competicion_val or None)

                db.session.commit()
                flash("Futbolista guardado", "success")
                return redirect(url_for("jugadores.list"))
            except IntegrityError:
                db.session.rollback()
                flash("Error de integridad (posible duplicado de ID)", "danger")

    return render_template("records/jugador_form.html", row=row, estados=estados)


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


@jugadores_bp.post("/<string:row_id>/delete")
@login_required
@require_perm("delete_jugador")
def delete(row_id: str):
    F = _model("futbolistas")
    if not F:
        return "Modelo futbolistas no disponible", 500
    row = db.session.get(F, row_id)
    if row:
        db.session.delete(row)
        db.session.commit()
        flash("Futbolista eliminado", "info")
    return redirect(url_for("jugadores.list"))

"""Jugadores controller: CRUD para la tabla `jugadores`.
Campos: id (PK, varchar), nombre, apellido, sexo, fecha_nacimiento (date), reconocimiento_medico (date), estado
"""
import math
import uuid
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from dux import db
from dux.models import Base
from dux.security import require_perm

jugadores_bp = Blueprint("jugadores", __name__, url_prefix="/jugadores")


def _model(name: str):
    return getattr(Base.classes, name, None)


# LISTA
@jugadores_bp.get("/")
@login_required
@require_perm("read_jugador")
def list():  # type: ignore[override]
    M = _model("jugadores")
    if not M:
        return "Modelo jugadores no disponible", 500
    q = request.args.get("q", "").strip()
    query = db.session.query(M)
    if q:
        like = f"%{q}%"
        # Filtro por nombre, apellido, sexo y estado
        query = query.filter(
            (M.nombre.ilike(like))
            | (M.apellido.ilike(like))
            | (M.sexo.ilike(like))
            | (M.estado.ilike(like))
        )
    page = int(request.args.get("page", 1))
    per_page = 10
    total = query.count()
    rows = (
        # Emular NULLS LAST en MySQL ordenando por (col IS NULL) y luego por la columna
        query.order_by(M.apellido.is_(None), M.apellido.asc(), M.nombre.is_(None), M.nombre.asc())
        .limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )
    pages = max(1, math.ceil(total / per_page))
    return render_template("list/jugadores.html", rows=rows, q=q, page=page, pages=pages)


# helper formulario

def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except Exception:
        return None


def _form(row_id: str | None = None):
    M = _model("jugadores")
    if not M:
        return "Modelo jugadores no disponible", 500
    row = db.session.get(M, row_id) if row_id else None
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        apellido = (request.form.get("apellido") or "").strip()
        sexo = (request.form.get("sexo") or "").strip()
        estado = (request.form.get("estado") or "").strip()
        fecha_nacimiento = _parse_date(request.form.get("fecha_nacimiento"))
        reconocimiento_medico = _parse_date(request.form.get("reconocimiento_medico"))

        if not nombre or not apellido:
            flash("Nombre y Apellido son obligatorios", "warning")
        else:
            try:
                if not row:
                    row = M(id=str(uuid.uuid4()))
                    db.session.add(row)
                row.nombre = nombre
                row.apellido = apellido
                row.sexo = sexo or None
                row.estado = estado or None
                row.fecha_nacimiento = fecha_nacimiento
                row.reconocimiento_medico = reconocimiento_medico
                db.session.commit()
                flash("Jugador guardado", "success")
                return redirect(url_for("jugadores.list"))
            except IntegrityError:
                db.session.rollback()
                flash("Error de integridad (posible duplicado de ID)", "danger")
    return render_template("records/jugador_form.html", row=row)


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
    M = _model("jugadores")
    if not M:
        return "Modelo jugadores no disponible", 500
    row = db.session.get(M, row_id)
    if row:
        db.session.delete(row)
        db.session.commit()
        flash("Jugador eliminado", "info")
    return redirect(url_for("jugadores.list"))

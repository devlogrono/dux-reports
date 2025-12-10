"""StateUser controller: CRUD for user states."""
import math
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from dux import db
from dux.models import Base
from dux.security import require_perm

state_user_bp = Blueprint("state_user", __name__, url_prefix="/state-users")

def _model(name):
    return getattr(Base.classes, name, None)

# List
@state_user_bp.get("/")
@login_required
@require_perm("read_state_user")
def state_users_list():
    M = _model("state_user")
    if not M:
        return "Modelo state_user no disponible", 500
    q = request.args.get("q", "").strip()
    query = db.session.query(M)
    if q:
        query = query.filter(M.name.ilike(f"%{q}%"))
    page = int(request.args.get("page", 1))
    per_page = 10
    total = query.count()
    rows = query.order_by(M.name).limit(per_page).offset((page-1)*per_page).all()
    pages = math.ceil(total/per_page)
    return render_template("list/state_users.html", rows=rows, q=q, page=page, pages=pages)

# helper

def _form(row_id=None):
    M = _model("state_user")
    if not M:
        return "Modelo state_user no disponible", 500
    row = db.session.get(M, row_id) if row_id else None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("El nombre es obligatorio", "warning")
        else:
            try:
                if not row:
                    row = M(id=None)
                    db.session.add(row)
                row.name = name
                db.session.commit()
                flash("Estado guardado", "success")
                return redirect(url_for("state_user.state_users_list"))
            except IntegrityError:
                db.session.rollback()
                flash("Nombre duplicado", "danger")
    return render_template("records/state_user_form.html", row=row)

@state_user_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_perm("create_state_user")
def new():
    return _form()

@state_user_bp.route("/<int:row_id>/edit", methods=["GET", "POST"])
@login_required
@require_perm("update_state_user")
def edit(row_id):
    return _form(row_id)

@state_user_bp.post("/<int:row_id>/delete")
@login_required
@require_perm("delete_state_user")
def delete(row_id):
    M = _model("state_user")
    if not M:
        return "Modelo state_user no disponible", 500
    row = db.session.get(M, row_id)
    if row:
        # Comprobar si el estado está en uso por algún futbolista
        F = getattr(Base.classes, "futbolistas", None)
        if F is not None and hasattr(F, "id_estado"):
            usados = db.session.query(F).filter(F.id_estado == row.id).count()
            if usados > 0:
                flash(f"No se puede eliminar: el estado está asignado a {usados} futbolista(s)", "danger")
                return redirect(url_for("state_user.state_users_list"))

        db.session.delete(row)
        db.session.commit()
        flash("Estado eliminado", "info")
    return redirect(url_for("state_user.state_users_list"))

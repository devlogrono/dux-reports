"""Roles controller: list and filter roles."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
import uuid
import math
from flask_login import login_required

from dux import db
from dux.models import Base
from dux.security import require_perm

roles_bp = Blueprint("roles", __name__, url_prefix="/roles")


def _get_roles_model():
    return getattr(Base.classes, "roles", None)


@roles_bp.get("/")
@login_required
@require_perm("read_role")
def roles_list():
    Role = _get_roles_model()
    if not Role:
        return "Modelo de roles no disponible", 500

    q = request.args.get("q", "").strip()
    query = db.session.query(Role)
    if q:
        query = query.filter(Role.name.ilike(f"%{q}%"))

    page = int(request.args.get("page", 1))
    total = query.count()
    per_page = 10
    roles = (
        query.order_by(Role.name)
        .limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )
    pages = math.ceil(total / per_page)
    return render_template("list/roles.html", roles=roles, q=q, page=page, pages=pages)


@roles_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_perm("create_role")
def role_new():
    Role = _get_roles_model()
    if not Role:
        return "Modelo de roles no disponible", 500

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("El nombre es obligatorio", "danger")
            return redirect(url_for("roles.role_new"))
        new_role = Role(id=str(uuid.uuid4()), name=name, description=description)
        db.session.add(new_role)
        db.session.commit()
        flash("Rol creado", "success")
        return redirect(url_for("roles.roles_list"))

    return render_template("records/role_form.html", role=None)


@roles_bp.route("/<role_id>/edit", methods=["GET", "POST"])
@login_required
@require_perm("update_role")
def role_edit(role_id):
    Role = _get_roles_model()
    if not Role:
        return "Modelo de roles no disponible", 500
    role = db.session.get(Role, role_id)
    if not role:
        flash("Rol no encontrado", "danger")
        return redirect(url_for("roles.roles_list"))

    if request.method == "POST":
        role.name = request.form.get("name", role.name).strip()
        role.description = request.form.get("description", role.description).strip()
        db.session.commit()
        flash("Rol actualizado", "success")
        return redirect(url_for("roles.roles_list"))

    return render_template("records/role_form.html", role=role)


@roles_bp.post("/<role_id>/delete")
@login_required
@require_perm("delete_role")
def role_delete(role_id):
    Role = _get_roles_model()
    if not Role:
        return "Modelo de roles no disponible", 500
    role = db.session.get(Role, role_id)
    if role:
        # Verificar si algún usuario tiene asignado este rol
        User = getattr(Base.classes, "users", None)
        if User is not None:
            assigned = db.session.query(User).filter(User.role_id == str(role_id)).count()
            if assigned > 0:
                flash(f"No se puede eliminar: el rol está asignado a {assigned} usuario(s)", "danger")
                return redirect(url_for("roles.roles_list"))
        # Eliminar permisos asociados en role_permissions/roles_permissions antes de borrar el rol
        RolePerm = getattr(Base.classes, "role_permissions", None)
        if RolePerm is None:
            RolePerm = getattr(Base.classes, "roles_permissions", None)
        if RolePerm is not None:
            db.session.query(RolePerm).filter(RolePerm.role_id == str(role_id)).delete()
            db.session.flush()
        try:
            db.session.delete(role)
            db.session.commit()
            flash("Rol eliminado", "info")
        except Exception as e:
            db.session.rollback()
            flash("No se puede eliminar el rol: " + str(e.__class__.__name__), "danger")
    return redirect(url_for("roles.roles_list"))

from __future__ import annotations

from flask import Blueprint, render_template, request
from flask_login import login_required

from dux.common.physical.services import (
    build_physical_grupal_context,
    build_physical_index_context,
)

bp = Blueprint("dashboard_physical", __name__, url_prefix="/dashboard/physical")


@bp.get("/")
@login_required
def index():
    plantel = request.args.get("plantel") or None

    context = build_physical_index_context(plantel=plantel)

    return render_template(
        "dashboard/physical/index.html",
        **context,
    )

@bp.get("/grupal")
@login_required
def grupal():
    plantel = request.args.get("plantel") or None
    periodo = request.args.get("periodo") or "ultima"

    context = build_physical_grupal_context(plantel=plantel, periodo=periodo)

    return render_template(
        "dashboard/physical/grupal.html",
        **context,
    )

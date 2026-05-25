from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, Response, abort, render_template, request
from flask_login import login_required

from dux.common.physical.services import (
    build_physical_grupal_context,
    build_physical_index_context,
    build_physical_individual_context,
    get_physical_player_photo_sources,
    normalize_player_photo_url,
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


@bp.get("/individual")
@login_required
def individual():
    plantel = request.args.get("plantel") or None
    jugadora = request.args.get("jugadora") or None
    periodo = request.args.get("periodo") or "ultima"

    context = build_physical_individual_context(plantel=plantel, jugadora=jugadora, periodo=periodo)

    return render_template(
        "dashboard/physical/individual.html",
        **context,
    )


@bp.get("/player-photo/<identificacion>")
@login_required
def player_photo(identificacion):
    sources = get_physical_player_photo_sources(identificacion)
    photo_url = normalize_player_photo_url(
        foto_url=sources.get("foto_url"),
        foto_url_drive=sources.get("foto_url_drive"),
    )

    if not photo_url:
        abort(404)

    try:
        photo_request = Request(
            photo_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urlopen(photo_request, timeout=8) as response:
            status_code = response.getcode()
            content_type = response.headers.get("Content-Type", "")
            content = response.read()
    except (HTTPError, URLError, TimeoutError, OSError):
        abort(404)

    if status_code != 200 or "image" not in content_type.lower():
        abort(404)

    return Response(content, mimetype=content_type)

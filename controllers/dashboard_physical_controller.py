from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from dux.common.physical.registration import (
    build_registration_record_from_form,
    normalize_registration_record,
    save_registration_record,
    split_registration_payload,
    validate_registration_record,
)
from dux.common.physical.services import (
    build_physical_grupal_context,
    build_physical_index_context,
    build_physical_individual_context,
    build_physical_registro_context,
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


@bp.route("/registro", methods=["GET", "POST"])
@login_required
def registro():
    plantel = request.args.get("plantel") or None
    jugadora = request.args.get("jugadora") or None
    posicion = request.args.get("posicion") or None
    tipo_registro = request.args.get("tipo_registro") or "formulario"
    validation_result = None

    if request.method == "POST" and tipo_registro == "formulario":
        action = request.form.get("registration_action") or "validate"
        record = build_registration_record_from_form(request.form, current_user)
        normalized_record = normalize_registration_record(record)
        is_valid, errors = validate_registration_record(normalized_record)
        payload = split_registration_payload(normalized_record) if is_valid else None

        if is_valid and action == "save":
            try:
                save_registration_record(normalized_record)
            except Exception as exc:
                validation_result = {
                    "submitted": True,
                    "action": "save",
                    "is_valid": False,
                    "errors": [f"Error guardando ISAK: {exc}"],
                    "record": normalized_record,
                    "payload": payload,
                }
            else:
                flash("Registro ISAK guardado correctamente.", "success")
                return redirect(
                    url_for(
                        "dashboard_physical.individual",
                        plantel=plantel,
                        jugadora=normalized_record.get("id_jugadora"),
                    )
                )
        else:
            validation_result = {
                "submitted": True,
                "action": action,
                "is_valid": is_valid,
                "errors": errors,
                "record": normalized_record,
                "payload": payload,
            }

    elif request.method == "POST":
        validation_result = {
            "submitted": True,
            "action": "save",
            "is_valid": False,
            "errors": ["El guardado de archivo todavia no esta implementado."],
            "record": {},
            "payload": None,
        }

    context = build_physical_registro_context(
        plantel=plantel,
        jugadora=jugadora,
        posicion=posicion,
        tipo_registro=tipo_registro,
    )

    if validation_result:
        normalized_record = validation_result.get("record") or {}
        for section in context["form_sections"]:
            for field in section["fields"]:
                if field["name"] in normalized_record:
                    field["value"] = normalized_record.get(field["name"])

        context["validation_result"] = validation_result

    return render_template(
        "dashboard/physical/registro.html",
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

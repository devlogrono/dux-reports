from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint("dashboard_wellness", __name__, url_prefix="/dashboard/wellness")


@bp.get("/")
@login_required
def index():
    return render_template("dashboard/wellness.html")

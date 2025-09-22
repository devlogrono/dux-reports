from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint("dashboard_futbolistas", __name__, url_prefix="/dashboard/futbolistas")

@bp.get("/")
@login_required
def index():
    return render_template("dashboard/futbolistas.html")

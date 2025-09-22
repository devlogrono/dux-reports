from flask import Blueprint, render_template
from flask_login import login_required
from dux import db
from dux.models import Base

bp = Blueprint("dashboard_actas", __name__, url_prefix="/dashboard/actas")

@bp.get("/")
@login_required
def index():
    # Modelos reflejados
    Comp = getattr(Base.classes, "competiciones", None)
    Acta = getattr(Base.classes, "actas", None)
    if not Comp or not Acta:
        # Evita petar si falta alguna tabla
        return render_template("dashboard/actas.html",
                               escudos=[],
                               tarjetas=[],
                               goles=[],
                               minutos=[])

    # -------- Escudos únicos (url_escudo_equipo_local) --------
    escudos = []
    try:
        col = Comp.__table__.c["url_escudo_equipo_local"]
        rows = db.session.query(col).filter(col.isnot(None), col != "").distinct().all()
        escudos = [r[0] for r in rows]
    except Exception:
        escudos = []

    # -------- Tarjetas (Jugador, TA, TR) --------
    TA = Acta.__table__.c.get("Tarjetas Amarillas")
    TR = Acta.__table__.c.get("Tarjetas Rojas")
    J  = Acta.__table__.c.get("Jugador")
    tarjetas = []
    if J is not None and TA is not None and TR is not None:
        q = db.session.query(J, TA, TR).all()
        tarjetas = [{"jugador": r[0], "amarillas": r[1] or 0, "rojas": r[2] or 0} for r in q]

    # -------- Goles --------
    G = Acta.__table__.c.get("Goles")
    goles = []
    if J is not None and G is not None:
        q = db.session.query(J, G).order_by((G.desc())).limit(30).all()
        goles = [{"jugador": r[0], "valor": r[1] or 0} for r in q]

    # -------- Minutos --------
    M = Acta.__table__.c.get("Minutos")
    minutos = []
    if J is not None and M is not None:
        q = db.session.query(J, M).order_by((M.desc())).limit(30).all()
        minutos = [{"jugador": r[0], "valor": r[1] or 0} for r in q]

    return render_template("dashboard/actas.html",
                           escudos=escudos,
                           tarjetas=tarjetas,
                           goles=goles,
                           minutos=minutos)

"""Dashboard Controller: muestra KPIs principales."""
from datetime import datetime, timedelta, date

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from dux.common.security import has_perm

from dux import db
from dux.models import Base

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_model(name):
    return getattr(Base.classes, name, None)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@dashboard_bp.get("/")
@login_required
def dashboard_home():
    Prescriptor = _get_model("prescriptors")
    Lead = _get_model("leads")

    # KPIs con valores por defecto en caso faltante
    prescriptores_activos = 0
    leads_matriculados = 0

    if Prescriptor:
        prescriptores_activos = (
            db.session.query(Prescriptor).filter_by(state_id=5).count()
        )

    if Lead:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        leads_matriculados = (
            db.session.query(Lead)
            .filter(Lead.state_id == 3, Lead.created_at >= thirty_days_ago)
            .count()
        )

    return render_template(
        "records/dashboard.html",
        prescriptores_activos=prescriptores_activos,
        leads_matriculados=leads_matriculados,
    )


@dashboard_bp.get("/report")
@login_required
def prescriptor_report():
    """Reporte filtrable de leads / matrículas y comisiones por prescriptor y rango de fechas."""
    Prescriptor = _get_model("prescriptors")
    Lead = _get_model("leads")
    Ledger = _get_model("ledger")
    Commission = _get_model("commissions")

    prescriptor_id = request.args.get("prescriptor_id", default="")
    date_from_str = request.args.get("date_from", "")
    date_to_str = request.args.get("date_to", "")
    date_from = date.fromisoformat(date_from_str) if date_from_str else None
    date_to = date.fromisoformat(date_to_str) if date_to_str else None

    # lista de prescriptores para el select
    prescriptors = []
    label_attr = None
    if Prescriptor is not None:
        for attr in ("squeeze_page_name", "name", "email"):
            if hasattr(Prescriptor, attr):
                label_attr = getattr(Prescriptor, attr)
                break
        order_col = label_attr or Prescriptor.id
        prescriptors = db.session.query(Prescriptor).order_by(order_col).all()

    # --- métricas ---
    lead_count = 0
    conversion_count = 0
    commission_sum = 0.0
    paid_sum = 0.0
    pending_sum = 0.0

    # ---- Chart placeholders (avoid NameError) ----
    month_labels = []
    paid_series = []
    pending_series = []
    lead_series = []
    mat_series = []
    lead_state_labels = []
    lead_state_counts = []
    ledger_state_labels = []
    ledger_state_counts = []

    # ----- Detect prescriptor user -----
    prescriptor_locked = False
    if Prescriptor is not None and current_user.is_authenticated and not has_perm(current_user, "reports_manage"):
        my_presc = None
        # buscar por user_id directo
        if hasattr(Prescriptor, 'user_id'):
            my_presc = db.session.query(Prescriptor).filter(Prescriptor.user_id == current_user.id).first()
        # buscar por email
        if my_presc is None and hasattr(Prescriptor, 'email') and hasattr(current_user, 'email'):
            my_presc = db.session.query(Prescriptor).filter(Prescriptor.email == current_user.email).first()
        if my_presc:
            prescriptor_locked = True
            prescriptor_id = str(my_presc.id)

    # ----- State name mappings -----
    def _state_names(model_name: str):
        M = _get_model(model_name)
        if M is None:
            return {}
        name_col = None
        for c in ("name", "description", "nombre"):
            if hasattr(M, c):
                name_col = getattr(M, c)
                break
        if name_col is None:
            return {}
        rows = db.session.query(M.id, name_col).all()
        return {str(r[0]): str(r[1]) for r in rows}

    lead_state_map = _state_names("state_lead") or _state_names("state_leads") or {}
    ledger_state_map = _state_names("state_ledger") or _state_names("state_ledgers") or {}

    # ---------- Monthly aggregation ----------
    # Determinar rango de meses (por defecto últimos 12)
    from collections import OrderedDict
    import calendar
    today = date.today()
    if date_from and date_to:
        start_month = date_from.replace(day=1)
        end_month = date_to.replace(day=1)
    else:
        end_month = today.replace(day=1)
        start_month = (end_month.replace(day=15) - timedelta(days=365)).replace(day=1)
    months = OrderedDict()
    cur = start_month
    while cur <= end_month:
        label = cur.strftime("%Y-%m")
        months[label] = {
            "leads": 0,
            "mats": 0,
            "paid": 0.0,
            "pending": 0.0,
        }
        # next month
        year = cur.year + (cur.month // 12)
        month = (cur.month % 12) + 1
        cur = cur.replace(year=year, month=month)

    # agrupar leads
    if Lead is not None and hasattr(Lead, "created_at"):
        lq2 = db.session.query(Lead.created_at, Lead.state_id)
        if prescriptor_id and hasattr(Lead, "prescriptor_id"):
            lq2 = lq2.filter(Lead.prescriptor_id == prescriptor_id)
        if date_from:
            lq2 = lq2.filter(Lead.created_at >= start_month)
        if date_to:
            lq2 = lq2.filter(Lead.created_at <= today if not date_to else date_to)
        for created, st in lq2:
            if not created:
                continue
            label = created.strftime("%Y-%m")
            if label not in months:
                continue
            months[label]["leads"] += 1
            if st == 3:
                months[label]["mats"] += 1
            # conteo por estado total
            s_str = str(st)
            if s_str not in lead_state_labels:
                lead_state_labels.append(s_str)
                lead_state_counts.append(1)
            else:
                idx = lead_state_labels.index(s_str)
                lead_state_counts[idx] += 1

    # agrupar ledger movimientos
    if Ledger is not None and hasattr(Ledger, "created_at"):
        lq3 = db.session.query(Ledger.created_at, Ledger.amount, Ledger.sign, Ledger.state_id)
        if prescriptor_id and hasattr(Ledger, "prescriptor_id"):
            lq3 = lq3.filter(Ledger.prescriptor_id.in_([prescriptor_id, str(prescriptor_id)]))
        if date_from:
            lq3 = lq3.filter(Ledger.created_at >= start_month)
        if date_to:
            lq3 = lq3.filter(Ledger.created_at <= today if not date_to else date_to)
        for ct, amt, sign, st in lq3:
            if not ct:
                continue
            label = ct.strftime("%Y-%m")
            if label not in months:
                continue
            val = float(amt) * (1 if sign is None else sign)
            if st == 4:
                months[label]["paid"] += val
            else:
                months[label]["pending"] += val
            # estados ledger
            s_str = str(st)
            if s_str not in ledger_state_labels:
                ledger_state_labels.append(s_str)
                ledger_state_counts.append(1)
            else:
                idx = ledger_state_labels.index(s_str)
                ledger_state_counts[idx] += 1

    month_labels = list(months.keys())

    # reemplazar ids por nombres legibles en labels
    lead_state_labels = [lead_state_map.get(l, l) for l in lead_state_labels]
    ledger_state_labels = [ledger_state_map.get(l, l) for l in ledger_state_labels]
    lead_series = [m["leads"] for m in months.values()]
    mat_series = [m["mats"] for m in months.values()]
    paid_series = [round(m["paid"],2) for m in months.values()]
    pending_series = [round(m["pending"],2) for m in months.values()]

    # ---------- Leads & Matriculaciones ----------
    if Lead is not None:
        q = db.session.query(Lead)
        # columna prescriptor
        if prescriptor_id and hasattr(Lead, 'prescriptor_id'):
            q = q.filter(Lead.prescriptor_id == prescriptor_id)
        elif prescriptor_id and isinstance(prescriptor_id, int) and hasattr(Lead, 'prescriptor_id'):
            q = q.filter(Lead.prescriptor_id == str(prescriptor_id))
        elif prescriptor_id and hasattr(Lead, 'presc_id'):
            q = q.filter(Lead.presc_id == prescriptor_id)
        if date_from:
            q = q.filter(Lead.created_at >= date_from)
        if date_to:
            q = q.filter(Lead.created_at <= date_to)
        lead_count = q.count()
        # conversion = state_id == 3
        conversion_count = q.filter(Lead.state_id == 3).count()

    # ---------- Comisiones (Ledger) ----------
    if Ledger is not None:
        lq = db.session.query(Ledger.amount, Ledger.sign, Ledger.state_id)
        # filtro prescriptor columna
        if prescriptor_id and hasattr(Ledger, 'prescriptor_id'):
            lq = lq.filter(Ledger.prescriptor_id.in_([prescriptor_id, str(prescriptor_id)]))
        # rango fechas sobre created_at si existe
        if date_from and hasattr(Ledger, "created_at"):
            lq = lq.filter(Ledger.created_at >= date_from)
        if date_to and hasattr(Ledger, "created_at"):
            lq = lq.filter(Ledger.created_at <= date_to)
        rows = lq.all()
        for amt, sign, st in rows:
            val = float(amt) * (1 if sign is None else sign)
            commission_sum += val
            if st == 4:
                paid_sum += val
            else:
                pending_sum += val

    # fallback Commission table (legacy)
    elif Commission is not None:
        cq = db.session.query(Commission.amount)
        if prescriptor_id:
            cq = cq.filter(Commission.prescriptor_id == prescriptor_id)
        if date_from:
            cq = cq.filter(Commission.created_at >= date_from)
        if date_to:
            cq = cq.filter(Commission.created_at <= date_to)
        commission_sum = cq.scalar() or 0.0
        paid_sum = commission_sum  # desconocido reparto
        pending_sum = 0.0

    return render_template(
        "list/dashboard_report.html",
        prescriptors=prescriptors,
        label_attr=label_attr.key if label_attr else None,
        presc_sel=prescriptor_id,
        date_from=date_from_str,
        date_to=date_to_str,
        lead_count=lead_count,
        conversion_count=conversion_count,
        commission_sum=commission_sum,
        paid_sum=paid_sum,
        pending_sum=pending_sum,
        month_labels=month_labels,
        paid_series=paid_series,
        pending_series=pending_series,
        lead_series=lead_series,
        mat_series=mat_series,
        lead_state_labels=lead_state_labels,
        lead_state_counts=lead_state_counts,
        ledger_state_labels=ledger_state_labels,
        ledger_state_counts=ledger_state_counts,
        prescriptor_locked=prescriptor_locked,
    )

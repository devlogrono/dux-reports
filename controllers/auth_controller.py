"""Controlador de autenticación.

Define un Blueprint llamado ``auth`` con rutas para login y logout.
"""
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    current_app,
)
from flask_login import login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField
from wtforms.validators import EqualTo
from wtforms.validators import DataRequired, Email, Length

import hashlib
from dux import db, bcrypt
from dux.models import Base


# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# ---------------------------------------------------------------------------
# Formulario de Login
# ---------------------------------------------------------------------------


class LoginForm(FlaskForm):
    email = StringField(
        "Correo electrónico",
        validators=[DataRequired(), Email(), Length(max=255)],
        render_kw={"placeholder": "email@example.com"},
    )
    password = PasswordField(
        "Contraseña", validators=[DataRequired(), Length(min=4, max=255)]
    )
    remember = BooleanField("Recordarme")
    submit = SubmitField("Ingresar")

    class Meta:
        csrf = True


# ---------------------------------------------------------------------------
# Form Forgot / Reset
# ---------------------------------------------------------------------------

class ForgotForm(FlaskForm):
    email = StringField("Correo electrónico", validators=[DataRequired(), Email()], render_kw={"placeholder":"email@example.com"})
    submit = SubmitField("Enviar enlace")

class ContactForm(FlaskForm):
    name = StringField("Nombre", validators=[DataRequired(), Length(max=255)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    message = TextAreaField("Mensaje", validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField("Enviar")

class ResetForm(FlaskForm):
    password = PasswordField("Nueva contraseña", validators=[DataRequired(), Length(min=4,max=255)])
    confirm = PasswordField("Confirmar contraseña", validators=[DataRequired(), EqualTo('password', message='Las contraseñas no coinciden')])
    submit = SubmitField("Restablecer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

def _serializer():
    from flask import current_app
    return URLSafeTimedSerializer(current_app.config.get('SECRET_KEY','dux-secret'))

def _generate_token(email:str):
    return _serializer().dumps(email, salt='pwd-reset')

def _confirm_token(token, max_age=3600):
    try:
        email = _serializer().loads(token, salt='pwd-reset', max_age=max_age)
        return email
    except (BadSignature, SignatureExpired):
        return None

def _get_user_class():
    """Obtiene la clase de usuario reflejada, asumiendo tabla ``users``."""
    return getattr(Base.classes, "users", None)


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------


@auth_bp.get("/forgot")
def forgot_get():
    form = ForgotForm()
    return render_template("layouts/forgot_password.html", form=form)

@auth_bp.post("/forgot")
def forgot_post():
    form = ForgotForm()
    if not form.validate_on_submit():
        flash("Email inválido", "danger");return redirect(url_for('auth.forgot_get'))
    User=_get_user_class();user=db.session.query(User).filter_by(email=form.email.data.lower().strip()).first() if User else None
    if user:
        token=_generate_token(user.email.strip().lower())
        reset_url=url_for('auth.reset_password', token=token, _external=True)
        plain_body=f"Hola,\n\nPara restablecer tu contraseña haz clic en el siguiente enlace:\n{reset_url}\n\nSi no solicitaste esto ignora el mensaje."
        html_body=render_template('emails/reset_password.html', reset_url=reset_url, user=user)
        from dux.common.email_utils import send_simple_mail
        send_simple_mail([user.email],"Restablecer contraseña",html_body, html=True, text_body=plain_body)
    flash("Si el email existe se envió un enlace de recuperación", "info")
    return redirect(url_for('auth.login_get'))

@auth_bp.get("/reset/<token>")
def reset_password(token):
    email=_confirm_token(token)
    if not email:
        flash("Enlace inválido o expirado", "danger");return redirect(url_for('auth.login_get'))
    form=ResetForm()
    return render_template('layouts/reset_password.html', form=form)

@auth_bp.post("/reset/<token>")
def reset_password_post(token):
    email=_confirm_token(token)
    if not email:
        flash("Enlace inválido o expirado", "danger");return redirect(url_for('auth.login_get'))
    form=ResetForm()
    if not form.validate_on_submit():
        flash("Revisa el formulario", "danger");return render_template('layouts/reset_password.html', form=form)
    User=_get_user_class();user=db.session.query(User).filter_by(email=email).first() if User else None
    if not user:
        flash("Usuario no encontrado", "danger");return redirect(url_for('auth.login_get'))
    # Guardar contraseña usando bcrypt
    user.password_hash=bcrypt.generate_password_hash(form.password.data).decode("utf-8");db.session.commit()
    flash("Contraseña actualizada, inicia sesión", "success")
    return redirect(url_for('auth.login_get'))


@auth_bp.get("/login")
def login_get():
    # Si ya está logueado redirigimos
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()
    return render_template("layouts/login.html", form=form)


def _audit_event(user_id, success: bool, event_type: str):
    """Inserta un registro en login_audit."""
    Audit = getattr(Base.classes, "login_audit", None)
    if not Audit:
        return
    ip_addr = request.remote_addr
    record = Audit(user_id=user_id, success=1 if success else 0, ip_addr=ip_addr, event_type=event_type)
    db.session.add(record)
    db.session.commit()


@auth_bp.post("/contact")
def contact_post():
    form = ContactForm(request.form)
    if not form.validate_on_submit():
        flash("Completa todos los campos", "danger");return redirect(url_for('auth.login_get')+"#contact")
    cfg=current_app.config
    admin = cfg.get('CONTACT_EMAIL', cfg.get('MAIL_DEFAULT_SENDER'))
    subject="Contacto"
    plain_body=f"Nombre: {form.name.data}\nEmail: {form.email.data}\nMensaje:\n{form.message.data}"
    html_body=render_template('emails/contact_message.html', name=form.name.data, email=form.email.data, message=form.message.data)
    from dux.common.email_utils import send_simple_mail
    send_simple_mail([admin], subject, html_body, html=True, text_body=plain_body)
    flash("Mensaje enviado, te responderemos pronto", "success")
    return redirect(url_for('auth.login_get'))


@auth_bp.post("/login")
def login_post():
    form = LoginForm(request.form)

    if not form.validate_on_submit():
        flash("Datos de formulario inválidos", "danger")
        return redirect(url_for("auth.login_get"))

    User = _get_user_class()
    if not User:
        flash("Modelo de usuario no disponible", "danger")
        return redirect(url_for("auth.login_get"))

    user = db.session.query(User).filter_by(email=form.email.data).first()

    ok = False
    if user and user.password_hash:
        # Primero intentamos validar como bcrypt
        try:
            ok = bcrypt.check_password_hash(user.password_hash, form.password.data)
        except Exception:
            ok = False

        # Compatibilidad con hashes antiguos en SHA256 (64 caracteres hex)
        if not ok and len(user.password_hash) == 64:
            legacy = hashlib.sha256(form.password.data.encode()).hexdigest()
            if user.password_hash.lower() == legacy:
                ok = True
                # Migrar a bcrypt
                user.password_hash = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
                db.session.commit()

    if ok:
        _audit_event(user.id, True, "LOGIN")
        login_user(user, remember=form.remember.data)
        return redirect("/")

    if user:
        _audit_event(user.id, False, "LOGIN")

    flash("Credenciales incorrectas", "danger")
    return redirect(url_for("auth.login_get"))


@auth_bp.get("/logout")
def logout():
    _audit_event(current_user.id if current_user.is_authenticated else None, True, "LOGOUT")
    logout_user()
    # Cierra la sesión del contexto actual
    db.session.remove()
    # Fuerza cierre del pool completo
    try:
        db.engine.dispose(close=True)
    except Exception:
        current_app.logger.exception("Error disposing engine on logout")
    # flash("Sesión finalizada", "info")
    return redirect(url_for("auth.login_get"))

from modules.ui.check_in_ui import validate_checkin
from modules.ui.check_out_ui import validate_checkout

# ==============================
# ✅ TESTS
# ==============================

def test_checkin_valido_ok():
    """
    Registro completo y dentro de rangos 1-5 debe ser válido.
    """
    record = {
        "recuperacion": 3,
        "fatiga": 2,
        "sueno": 4,
        "stress": 3,
        "dolor": 1,  # dolor bajo, no requiere zona
        "id_zona_segmento_dolor": None,
    }

    ok, msg = validate_checkin(record)
    assert ok is True
    assert msg == ""


def test_checkin_campo_faltante_devuelve_error():
    """
    Si falta algún campo template, debe devolver ok=False y un mensaje claro.
    """
    record = {
        # falta 'recuperacion'
        "fatiga": 2,
        "sueno": 4,
        "stress": 3,
        "dolor": 1,
        "id_zona_segmento_dolor": None,
    }

    ok, msg = validate_checkin(record)
    assert ok is False
    assert "recuperacion" in msg  # "Completa el campo 'recuperacion'."


def test_checkin_valor_fuera_de_rango():
    """
    Si un valor está fuera de 1..5, debe fallar.
    """
    record = {
        "recuperacion": 6,  # fuera de rango
        "fatiga": 2,
        "sueno": 4,
        "stress": 3,
        "dolor": 1,
        "id_zona_segmento_dolor": None,
    }

    ok, msg = validate_checkin(record)
    assert ok is False
    assert "entre 1 y 5" in msg


def test_checkin_dolor_alto_sin_zona_debe_fallar():
    """
    Si dolor > 1, debe exigir id_zona_segmento_dolor.
    """
    record = {
        "recuperacion": 3,
        "fatiga": 2,
        "sueno": 4,
        "stress": 3,
        "dolor": 4,  # dolor alto
        "id_zona_segmento_dolor": None,
    }

    ok, msg = validate_checkin(record)
    assert ok is False
    # Mensaje traducido con t(), comprobamos parte del texto
    assert "parte del cuerpo" in msg or "Selecciona" in msg


def test_checkin_dolor_alto_con_zona_ok():
    """
    Si dolor > 1 y hay zona seleccionada, debe pasar.
    """
    record = {
        "recuperacion": 3,
        "fatiga": 2,
        "sueno": 4,
        "stress": 3,
        "dolor": 4,
        "id_zona_segmento_dolor": 10,
    }

    ok, msg = validate_checkin(record)
    assert ok is True
    assert msg == ""


# ==============================
# ✅ TESTS CHECK-OUT (validate_checkout)
# ==============================

def test_checkout_valido_ok():
    """
    Registro completo de check-out debe ser válido.
    """
    record = {
        "minutos_sesion": 60,
        "rpe": 5,
        "ua": 300,  # 5 * 60
    }

    ok, msg = validate_checkout(record)
    assert ok is True
    assert msg == ""


def test_checkout_minutos_faltan():
    """
    Si minutos_sesion es None o <= 0, debe fallar.
    """
    record = {
        "minutos_sesion": 0,
        "rpe": 5,
        "ua": 0,
    }

    ok, msg = validate_checkout(record)
    assert ok is False
    assert "minutos" in msg


def test_checkout_rpe_fuera_de_rango():
    """
    Si RPE está fuera de 1..10, debe fallar.
    """
    record = {
        "minutos_sesion": 60,
        "rpe": 11,  # fuera de rango
        "ua": 660,
    }

    ok, msg = validate_checkout(record)
    assert ok is False
    assert "RPE" in msg and "entre 1 y 10" in msg


def test_checkout_ua_no_calculado():
    """
    Si UA es None, debe fallar (indica que la app no calculó UA correctamente).
    """
    record = {
        "minutos_sesion": 60,
        "rpe": 5,
        "ua": None,
    }

    ok, msg = validate_checkout(record)
    assert ok is False
    assert "UA" in msg

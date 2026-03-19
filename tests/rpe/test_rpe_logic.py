from modules.ui.check_out_ui import validate_checkout

def test_rpe_valid_ok():
    record = {
        "minutos_sesion": 45,
        "rpe": 5,
        "ua": 225
    }
    ok, msg = validate_checkout(record)
    assert ok is True
    assert msg == ""

def test_rpe_minutos_invalidos():
    record = {
        "minutos_sesion": 0,
        "rpe": 5,
        "ua": 0
    }
    ok, msg = validate_checkout(record)
    assert ok is False
    assert "minutos" in msg.lower()

def test_rpe_fuera_de_rango():
    record = {
        "minutos_sesion": 40,
        "rpe": 15,  # inválido
        "ua": 600
    }
    ok, msg = validate_checkout(record)
    assert ok is False
    assert "rpe" in msg.lower()

def test_rpe_ua_none():
    record = {
        "minutos_sesion": 40,
        "rpe": 7,
        "ua": None
    }
    ok, msg = validate_checkout(record)
    assert ok is False
    assert "ua" in msg.lower()

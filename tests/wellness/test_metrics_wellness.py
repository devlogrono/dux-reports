import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

import pandas as pd

from modules.ui.ui_app import (
    _coerce_numeric,
    calc_trend,
    calc_delta,
    calc_metric_block,
    compute_player_template_means,
)

# ==============================
# ✅ _coerce_numeric
# ==============================

def test_coerce_numeric_convierte_strings_a_numerico():
    df = pd.DataFrame({
        "recuperacion": ["1", "2", None],
        "sueno": [3, "4", "5"],
        "otra": ["x", "y", "z"],
    })

    out = _coerce_numeric(df, ["recuperacion", "sueno"])

    assert out["recuperacion"].dtype.kind in ("i", "f")
    assert out["sueno"].dtype.kind in ("i", "f")
    # La columna no incluida debe mantenerse igual (object)
    assert out["otra"].dtype == df["otra"].dtype


# ==============================
# ✅ calc_trend y calc_delta
# ==============================

def test_calc_trend_mean_y_sum():
    df = pd.DataFrame({
        "semana": [1, 1, 2, 2],
        "ua": [100, 150, 200, 250],
    })

    # media por semana: [125.0, 225.0]
    vals_mean = calc_trend(df, "semana", "ua", agg="mean")
    assert vals_mean == [125.0, 225.0]

    # suma por semana: [250, 450]
    vals_sum = calc_trend(df, "semana", "ua", agg="sum")
    assert vals_sum == [250, 450]


def test_calc_delta_casos_basicos():
    # Menos de 2 valores -> 0
    assert calc_delta([]) == 0
    assert calc_delta([10]) == 0

    # Aumento 10 -> 20 → +100%
    assert calc_delta([10, 20]) == 100.0

    # Disminución 20 -> 10 → -50%
    assert calc_delta([20, 10]) == -50.0


# ==============================
# ✅ calc_metric_block
# ==============================

def test_calc_metric_block_hoy_media():
    df = pd.DataFrame({"ua": [100, 200, 300]})
    valor, chart, delta = calc_metric_block(df, periodo="Hoy", var="ua", agg="mean")

    assert valor == 200.0  # media
    assert chart == [200.0]
    assert delta == 0


def test_calc_metric_block_semana_suma_y_delta():
    df = pd.DataFrame({
        "semana": [1, 1, 2, 2],
        "ua": [100, 150, 200, 250],
    })

    valor, chart, delta = calc_metric_block(df, periodo="Semana", var="ua", agg="sum")

    # chart debe ser la serie por semana: [250, 450]
    assert chart == [250, 450]
    # valor actual es el último
    assert valor == 450
    # delta porcentual entre semana 1 y 2: (450-250)/250 * 100 = 80.0
    assert delta == 80.0


# ==============================
# ✅ compute_player_template_means
# ==============================

def test_compute_player_template_means_df_vacio():
    df_empty = pd.DataFrame(columns=["nombre_jugadora"])
    out = compute_player_template_means(df_empty)

    assert list(out.columns) == ["nombre_jugadora", "prom_w_1_5", "dolor_mean", "en_riesgo"]
    assert out.empty


def test_compute_player_template_means_riesgo_y_no_riesgo():
    df = pd.DataFrame([
        {
            "nombre_jugadora": "A",
            "recuperacion": 4,
            "energia": 4,
            "sueno": 4,
            "stress": 4,
            "dolor": 2,
        },
        {
            "nombre_jugadora": "B",
            "recuperacion": 2,
            "energia": 2,
            "sueno": 2,
            "stress": 2,
            "dolor": 1,
        },
    ])

    out = compute_player_template_means(df)

    assert len(out) == 2

    fila_A = out[out["nombre_jugadora"] == "A"].iloc[0]
    fila_B = out[out["nombre_jugadora"] == "B"].iloc[0]

    # A: promedio > 3 → en_riesgo True
    assert fila_A["prom_w_1_5"] > 3
    assert fila_A["en_riesgo"] == True   # np.True_ OK

    # B: promedio <= 3 y dolor <= 3 → en_riesgo False
    assert fila_B["prom_w_1_5"] <= 3
    assert fila_B["dolor_mean"] <= 3
    assert fila_B["en_riesgo"] == False  # np.False_ OK

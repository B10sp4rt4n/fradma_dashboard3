import pandas as pd

from utils import neon_loader


def test_column_map_includes_forma_pago_and_valor_mxn():
    assert neon_loader._COLUMN_MAP["total"] == "valor_mxn"
    assert neon_loader._COLUMN_MAP["forma_pago"] == "forma_pago"


def test_numeric_conversion_targets_valor_mxn(monkeypatch):
    data = pd.DataFrame(
        {
            "fecha": ["2026-01-01"],
            "valor_mxn": ["1234.56"],
            "tipo_cambio": ["1.0"],
            "subtotal": ["1000"],
            "impuestos": ["160"],
            "cliente": [None],
            "linea_producto": [None],
            "agente": [None],
        }
    )

    for col in ("valor_mxn", "tipo_cambio", "subtotal", "impuestos"):
        data[col] = pd.to_numeric(data[col], errors="coerce")

    for col in ("cliente", "linea_producto", "agente"):
        data[col] = data[col].fillna("Sin dato")

    assert float(data.loc[0, "valor_mxn"]) == 1234.56
    assert data.loc[0, "cliente"] == "Sin dato"
    assert data.loc[0, "linea_producto"] == "Sin dato"
    assert data.loc[0, "agente"] == "Sin dato"

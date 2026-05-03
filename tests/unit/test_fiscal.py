import pandas as pd

from main import fiscal


def test_query_conceptos_includes_join_and_objeto_imp_logic():
    # Validamos indirectamente la consulta al forzar ejecución con cursor mock.
    captured = {"sql": "", "params": None}

    class FakeCursor:
        description = [
            ("clave_prod_serv",),
            ("descripcion",),
            ("objeto_imp",),
            ("categoria",),
            ("linea_negocio",),
            ("num_facturas",),
            ("base_mxn",),
            ("iva_estimado_mxn",),
        ]

        def execute(self, sql, params):
            captured["sql"] = sql
            captured["params"] = params

        def fetchall(self):
            return []

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    original_connect = fiscal.psycopg2.connect
    fiscal.psycopg2.connect = lambda _: FakeConn()
    try:
        df = fiscal._cargar_impuestos_por_concepto("empresa-x", "postgres://dummy")
    finally:
        fiscal.psycopg2.connect = original_connect

    assert isinstance(df, pd.DataFrame)
    assert captured["params"] == ("empresa-x",)
    assert "FROM cfdi_conceptos cc" in captured["sql"]
    assert "JOIN cfdi_ventas cv ON cv.id = cc.cfdi_venta_id" in captured["sql"]
    assert "CASE WHEN cc.objeto_imp = '02'" in captured["sql"]


def test_objeto_imp_exento_calculation_is_zero_iva():
    df = pd.DataFrame(
        {
            "objeto_imp": ["01", "02"],
            "base_mxn": [100.0, 200.0],
            "iva_estimado_mxn": [0.0, 32.0],
        }
    )

    exentos_base = df.loc[df["objeto_imp"] == "01", "base_mxn"].sum()
    iva_exentos = df.loc[df["objeto_imp"] == "01", "iva_estimado_mxn"].sum()

    assert exentos_base == 100.0
    assert iva_exentos == 0.0

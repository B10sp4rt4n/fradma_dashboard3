import pytest

from utils.nl2sql import NL2SQLEngine


@pytest.fixture
def engine_stub():
    engine = object.__new__(NL2SQLEngine)
    return engine


def test_validate_sql_requires_empresa_id_for_tenant_scoped_tables(engine_stub):
    sql = "SELECT * FROM cfdi_ventas LIMIT 10"

    is_valid, err = engine_stub.validate_sql(sql, empresa_id="11111111-1111-1111-1111-111111111111")

    assert is_valid is False
    assert "empresa_id" in err


def test_validate_sql_accepts_empresa_id_filter_for_tenant_scoped_tables(engine_stub):
    empresa_id = "11111111-1111-1111-1111-111111111111"
    sql = (
        "SELECT * FROM cfdi_ventas "
        f"WHERE empresa_id = '{empresa_id}' "
        "ORDER BY fecha_emision DESC LIMIT 10"
    )

    is_valid, err = engine_stub.validate_sql(sql, empresa_id=empresa_id)

    assert is_valid is True
    assert err == "OK"


def test_ensure_tenant_filter_injects_empresa_id_for_cfdi_ventas(engine_stub):
    empresa_id = "11111111-1111-1111-1111-111111111111"

    sql = engine_stub._ensure_tenant_filter(
        "SELECT * FROM cfdi_ventas ORDER BY fecha_emision DESC LIMIT 10",
        empresa_id=empresa_id,
    )

    assert f"empresa_id = '{empresa_id}'" in sql


def test_ensure_tenant_filter_injects_exists_for_cfdi_conceptos_without_join(engine_stub):
    empresa_id = "11111111-1111-1111-1111-111111111111"

    sql = engine_stub._ensure_tenant_filter(
        "SELECT * FROM cfdi_conceptos LIMIT 10",
        empresa_id=empresa_id,
    )

    assert "EXISTS (SELECT 1 FROM cfdi_ventas cv_tenant" in sql
    assert f"cv_tenant.empresa_id = '{empresa_id}'" in sql


def test_ensure_tenant_filter_injects_empresa_id_inside_cfdi_ventas_subquery(engine_stub):
    empresa_id = "11111111-1111-1111-1111-111111111111"

    sql = engine_stub._ensure_tenant_filter(
        "SELECT COUNT(*) AS total_conceptos "
        "FROM cfdi_conceptos "
        "WHERE cfdi_venta_id IN ("
        "SELECT id FROM cfdi_ventas WHERE fecha_emision >= '2024-01-01'"
        ") LIMIT 1000;",
        empresa_id=empresa_id,
    )

    assert f"cfdi_ventas.empresa_id = '{empresa_id}'" in sql
    assert f") AND cfdi_ventas.empresa_id = '{empresa_id}'" not in sql
    assert f"SELECT id FROM cfdi_ventas WHERE fecha_emision >= '2024-01-01' AND cfdi_ventas.empresa_id = '{empresa_id}'" in sql


def test_inject_and_condition_ignores_within_group_clauses(engine_stub):
    sql = (
        "SELECT COUNT(*) AS total_facturas, "
        "ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY total)::numeric, 2) AS percentil_25 "
        "FROM cfdi_ventas WHERE fecha_emision >= '2024-01-01' LIMIT 1000;"
    )

    updated_sql = engine_stub._inject_and_condition(sql, "tipo_comprobante = 'I'")

    assert "WITHIN GROUP (ORDER BY total)" in updated_sql
    assert "WITHIN GROUP (AND" not in updated_sql
    assert "WHERE fecha_emision >= '2024-01-01' AND tipo_comprobante = 'I' LIMIT 1000" in updated_sql


def test_execute_query_fails_fast_when_tenant_filter_is_missing(engine_stub, monkeypatch):
    monkeypatch.setattr(engine_stub, "validate_sql", lambda sql, empresa_id=None: (False, "Falta filtro obligatorio por empresa_id"))

    with pytest.raises(RuntimeError, match="empresa_id"):
        engine_stub.execute_query("SELECT * FROM cfdi_ventas", empresa_id="11111111-1111-1111-1111-111111111111")

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


def test_execute_query_fails_fast_when_tenant_filter_is_missing(engine_stub, monkeypatch):
    monkeypatch.setattr(engine_stub, "validate_sql", lambda sql, empresa_id=None: (False, "Falta filtro obligatorio por empresa_id"))

    with pytest.raises(RuntimeError, match="empresa_id"):
        engine_stub.execute_query("SELECT * FROM cfdi_ventas", empresa_id="11111111-1111-1111-1111-111111111111")

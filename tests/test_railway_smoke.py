"""
tests/test_railway_smoke.py

Smoke tests mínimos para validar que la app puede desplegarse en Railway.

Criterios:
- Los módulos principales importan sin error.
- utils/config.py detecta variables faltantes correctamente.
- cargar_cfdi_como_df no intenta conectar a BD si no hay URL.
- nl2sql.validate_sql_static rechaza SQL sin filtro de empresa_id.
- Los módulos funcionales no tienen imports rotos en sus dependencias de utils.
"""

import os
import importlib
import pytest


# ============================================================
# 1. Imports de módulos principales sin error
# ============================================================

def test_import_utils_config():
    """utils/config.py importa correctamente."""
    from utils import config
    assert hasattr(config, "validate_environment")
    assert hasattr(config, "REQUIRED_ENV_VARS")
    assert "NEON_DATABASE_URL" in config.REQUIRED_ENV_VARS


def test_import_utils_auth():
    """utils/auth.py importa y expone AuthManager."""
    from utils.auth import AuthManager, UserRole, get_current_user
    assert UserRole.ADMIN == "admin"
    assert UserRole.ANALYST == "analyst"
    assert UserRole.VIEWER == "viewer"


def test_import_utils_neon_loader():
    """utils/neon_loader.py importa sin error."""
    from utils import neon_loader
    assert hasattr(neon_loader, "cargar_cfdi_como_df")


def test_import_utils_nl2sql():
    """utils/nl2sql.py importa y expone NL2SQLEngine."""
    from utils.nl2sql import NL2SQLEngine, validate_sql_static, TENANT_SCOPED_TABLES
    assert "cfdi_ventas" in TENANT_SCOPED_TABLES
    assert callable(validate_sql_static)


def test_import_utils_logger():
    from utils.logger import configurar_logger
    logger = configurar_logger("smoke_test")
    assert logger is not None


# ============================================================
# 2. validate_environment detecta variable faltante
# ============================================================

def test_validate_environment_falla_sin_neon(monkeypatch):
    """validate_environment debe detectar NEON_DATABASE_URL faltante."""
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)

    # Mockear st.stop y st.error para que no corten el test runner
    import streamlit as st
    calls = {"stop": 0, "error": []}

    monkeypatch.setattr(st, "stop", lambda: calls.__setitem__("stop", calls["stop"] + 1))
    monkeypatch.setattr(st, "error", lambda msg: calls["error"].append(msg))

    # Mockear st.secrets para que no tenga NEON_DATABASE_URL
    class _FakeSecrets:
        def get(self, key, default=None):
            return default
    monkeypatch.setattr(st, "secrets", _FakeSecrets(), raising=False)

    from utils import config
    # validate_environment llama st.stop() cuando falta la variable
    config.validate_environment()

    assert calls["stop"] >= 1, "Esperábamos que st.stop() fuera llamado"
    assert any("NEON_DATABASE_URL" in str(msg) for msg in calls["error"]), (
        "El mensaje de error debe mencionar NEON_DATABASE_URL"
    )


def test_validate_environment_pasa_con_neon(monkeypatch):
    """validate_environment pasa cuando NEON_DATABASE_URL está presente."""
    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("APP_ENV", "test")

    import streamlit as st
    monkeypatch.setattr(st, "stop", lambda: pytest.fail("st.stop() no debería llamarse"))
    monkeypatch.setattr(st, "error", lambda msg: pytest.fail(f"st.error no esperado: {msg}"))

    class _FakeSecrets:
        def get(self, key, default=None):
            return default
    monkeypatch.setattr(st, "secrets", _FakeSecrets(), raising=False)

    from utils import config
    result = config.validate_environment()
    assert result["database_url"] == "postgresql://test:test@localhost/test"
    assert result["app_env"] == "test"


# ============================================================
# 3. neon_loader no conecta sin URL
# ============================================================

def test_neon_loader_falla_sin_url(monkeypatch):
    """cargar_cfdi_como_df debe lanzar RuntimeError si no hay URL configurada."""
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)

    import streamlit as st

    class _FakeSecrets:
        def get(self, key, default=None):
            return default
    monkeypatch.setattr(st, "secrets", _FakeSecrets(), raising=False)

    # Limpiar cache de streamlit si existe
    try:
        from utils.neon_loader import cargar_cfdi_como_df
        cargar_cfdi_como_df.clear()
    except Exception:
        pass

    from utils.neon_loader import cargar_cfdi_como_df
    with pytest.raises(RuntimeError, match="NEON_DATABASE_URL"):
        cargar_cfdi_como_df("empresa-uuid-test", neon_url=None)


# ============================================================
# 4. validate_sql_static — seguridad multiempresa
# ============================================================

def test_sql_sin_select_rechazado():
    from utils.nl2sql import validate_sql_static
    ok, msg = validate_sql_static("DELETE FROM cfdi_ventas WHERE 1=1")
    assert not ok


def test_sql_con_select_aceptado():
    from utils.nl2sql import validate_sql_static
    ok, msg = validate_sql_static(
        "SELECT total FROM cfdi_ventas WHERE empresa_id = 'abc'"
    )
    assert ok, f"SQL válido rechazado: {msg}"


def test_sql_multistatement_rechazado():
    from utils.nl2sql import validate_sql_static
    ok, msg = validate_sql_static(
        "SELECT 1; DROP TABLE cfdi_ventas"
    )
    assert not ok


def test_sql_tabla_no_permitida_rechazada():
    from utils.nl2sql import validate_sql_static
    ok, msg = validate_sql_static(
        "SELECT * FROM pg_catalog.pg_tables"
    )
    assert not ok


# ============================================================
# 5. Módulos funcionales — importar sin error (sin Streamlit UI)
# ============================================================

UTIL_MODULES = [
    "utils.constantes",
    "utils.formatos",
    "utils.data_normalizer",
    "utils.data_cleaner",
    "utils.filters",
    "utils.export_helper",
    "utils.cxc_helper",
    "utils.cxc_aging_engine",
    "utils.logger",
    "utils.config",
]


@pytest.mark.parametrize("module_path", UTIL_MODULES)
def test_utils_module_imports(module_path):
    """Cada módulo de utils debe importar sin excepción."""
    mod = importlib.import_module(module_path)
    assert mod is not None

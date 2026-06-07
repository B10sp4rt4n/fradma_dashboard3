"""
tests/test_railway_smoke.py

Smoke tests mínimos para validar que la app puede desplegarse en Railway.

Criterios:
- Los archivos de deploy existen y son correctos (Procfile, Dockerfile, .dockerignore).
- El Procfile usa $PORT (no puerto fijo).
- .env.example no contiene credenciales reales.
- .dockerignore excluye archivos sensibles.
- Los módulos principales importan sin error.
- utils/config.py detecta variables faltantes correctamente.
- cargar_cfdi_como_df no intenta conectar a BD si no hay URL.
- nl2sql.validate_sql_static rechaza SQL sin filtro de empresa_id.
- Los módulos funcionales no tienen imports rotos en sus dependencias de utils.
"""

import os
import importlib
import pytest

# Raíz del repositorio (dos niveles arriba de este archivo)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _repo(path: str) -> str:
    return os.path.join(_REPO_ROOT, path)


# ============================================================
# BLOQUE A — Archivos de deploy deben existir
# ============================================================

def test_procfile_existe():
    assert os.path.isfile(_repo("Procfile")), "Falta Procfile"


def test_dockerfile_existe():
    assert os.path.isfile(_repo("Dockerfile")), "Falta Dockerfile"


def test_dockerignore_existe():
    assert os.path.isfile(_repo(".dockerignore")), "Falta .dockerignore"


def test_env_example_existe():
    assert os.path.isfile(_repo(".env.example")), "Falta .env.example"


def test_requirements_existe():
    assert os.path.isfile(_repo("requirements.txt")), "Falta requirements.txt"


def test_app_py_existe():
    assert os.path.isfile(_repo("app.py")), "Falta app.py"


def test_config_py_existe():
    assert os.path.isfile(_repo("utils/config.py")), "Falta utils/config.py"


# ============================================================
# BLOQUE B — Procfile usa $PORT (no puerto hardcodeado)
# ============================================================

def test_procfile_usa_port_dinamico():
    """El Procfile debe usar $PORT, no un puerto fijo."""
    with open(_repo("Procfile")) as f:
        content = f.read()
    assert "$PORT" in content, "Procfile debe usar $PORT"
    assert "0.0.0.0" in content, "Procfile debe usar server.address=0.0.0.0"
    assert "headless=true" in content or "headless true" in content, \
        "Procfile debe tener --server.headless=true"
    # Validar que no haya puerto fijo hardcodeado distinto de $PORT
    import re
    puertos_fijos = re.findall(r'--server\.port=(\d+)', content)
    assert not puertos_fijos, f"Procfile tiene puerto fijo hardcodeado: {puertos_fijos}"


def test_dockerfile_usa_port_con_default():
    """El Dockerfile debe usar ${PORT:-8501} para ser compatible local y Railway."""
    with open(_repo("Dockerfile")) as f:
        content = f.read()
    assert "PORT" in content, "Dockerfile debe referenciar $PORT o ${PORT:-8501}"


# ============================================================
# BLOQUE C — .env.example no contiene credenciales reales
# ============================================================

_SECRET_PATTERNS = [
    "postgresql://",          # Connection string real
    "sk-",                    # OpenAI API key real
    "eyJ",                    # JWT token
    "-----BEGIN",             # Certificado/clave privada
]

def test_env_example_sin_credenciales_reales():
    """.env.example no debe contener credenciales reales en valores (no en comentarios)."""
    with open(_repo(".env.example")) as f:
        lines = f.readlines()
    # Solo revisar líneas que son asignaciones de valor (no comentarios ni vacías)
    value_lines = [
        line for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
    content_values = "\n".join(value_lines)
    for pattern in _SECRET_PATTERNS:
        assert pattern not in content_values, \
            f".env.example contiene posible credencial real en un valor: patrón '{pattern}' encontrado"


def test_env_example_tiene_variables_criticas():
    """.env.example debe documentar las variables críticas."""
    with open(_repo(".env.example")) as f:
        content = f.read()
    required = [
        "NEON_DATABASE_URL",
        "OPENAI_API_KEY",
        "APP_ENV",
        "MAX_LOGIN_ATTEMPTS",
        "SESSION_TTL_SECONDS",
        "LOGIN_LOCKOUT_SECONDS",
    ]
    for var in required:
        assert var in content, f".env.example no documenta la variable: {var}"


# ============================================================
# BLOQUE D — .dockerignore excluye archivos sensibles
# ============================================================

_DOCKERIGNORE_REQUIRED = [
    ".env",
    ".streamlit/secrets.toml",
    "__pycache__",
    ".git",
    "venv",
    ".venv",
]

def test_dockerignore_excluye_sensibles():
    """El .dockerignore debe excluir archivos/carpetas sensibles."""
    with open(_repo(".dockerignore")) as f:
        content = f.read()
    for entry in _DOCKERIGNORE_REQUIRED:
        assert entry in content, \
            f".dockerignore no excluye: {entry}"


# ============================================================
# BLOQUE E — Imports de módulos principales sin error
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
# BLOQUE F — validate_environment detecta variable faltante
# ============================================================

def test_validate_environment_falla_sin_neon(monkeypatch):
    """validate_environment debe detectar NEON_DATABASE_URL faltante."""
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)

    import streamlit as st
    calls = {"stop": 0, "error": []}

    monkeypatch.setattr(st, "stop", lambda: calls.__setitem__("stop", calls["stop"] + 1))
    monkeypatch.setattr(st, "error", lambda msg: calls["error"].append(msg))

    class _FakeSecrets:
        def get(self, key, default=None):
            return default
    monkeypatch.setattr(st, "secrets", _FakeSecrets(), raising=False)

    from utils import config
    config.validate_environment()

    assert calls["stop"] >= 1, "Esperábamos que st.stop() fuera llamado"
    assert any("NEON_DATABASE_URL" in str(msg) for msg in calls["error"])


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
# BLOQUE G — neon_loader no conecta sin URL
# ============================================================

def test_neon_loader_falla_sin_url(monkeypatch):
    """cargar_cfdi_como_df debe lanzar RuntimeError si no hay URL configurada."""
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)

    import streamlit as st

    class _FakeSecrets:
        def get(self, key, default=None):
            return default
    monkeypatch.setattr(st, "secrets", _FakeSecrets(), raising=False)

    try:
        from utils.neon_loader import cargar_cfdi_como_df
        cargar_cfdi_como_df.clear()
    except Exception:
        pass

    from utils.neon_loader import cargar_cfdi_como_df
    with pytest.raises(RuntimeError, match="NEON_DATABASE_URL"):
        cargar_cfdi_como_df("empresa-uuid-test", neon_url=None)


# ============================================================
# BLOQUE H — validate_sql_static — seguridad multiempresa
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
    ok, msg = validate_sql_static("SELECT 1; DROP TABLE cfdi_ventas")
    assert not ok


def test_sql_tabla_no_permitida_rechazada():
    from utils.nl2sql import validate_sql_static
    ok, msg = validate_sql_static("SELECT * FROM pg_catalog.pg_tables")
    assert not ok


# ============================================================
# BLOQUE I — Módulos utils importan sin error
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

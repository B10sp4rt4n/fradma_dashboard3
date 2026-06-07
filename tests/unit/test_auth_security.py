"""
tests/unit/test_auth_security.py

Tests de las protecciones de seguridad agregadas a utils/auth.py:
- Bloqueo temporal por intentos fallidos (MAX_LOGIN_ATTEMPTS / LOGIN_LOCKOUT_SECONDS)
- Expiración de sesión (SESSION_TTL_SECONDS)
- Logout limpia session_state correctamente
- empresa_id y roles siguen disponibles después del login
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import streamlit as st


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def reset_session_state(monkeypatch):
    """Limpia st.session_state antes de cada test."""
    monkeypatch.setattr(st, "session_state", {}, raising=False)


@pytest.fixture
def auth_manager(monkeypatch):
    """AuthManager con _ensure_schema, _ensure_admin y _ensure_default_empresa mockeados."""
    monkeypatch.setattr("utils.auth.AuthManager._ensure_schema", lambda self: None)
    monkeypatch.setattr("utils.auth.AuthManager._ensure_admin", lambda self: None)
    monkeypatch.setattr("utils.auth.AuthManager._ensure_default_empresa", lambda self: None)
    from utils.auth import AuthManager
    return AuthManager()


# ============================================================
# 1. Constantes configurables
# ============================================================

def test_constantes_por_defecto():
    """Las constantes tienen los valores esperados por defecto."""
    import importlib
    import utils.auth as auth_module
    # Recargar para asegurar valores limpios
    importlib.reload(auth_module)
    assert auth_module.MAX_LOGIN_ATTEMPTS == 5
    assert auth_module.SESSION_TTL_SECONDS == 28800
    assert auth_module.LOGIN_LOCKOUT_SECONDS == 900


def test_constantes_desde_env(monkeypatch):
    """Las constantes se leen desde variables de entorno."""
    monkeypatch.setenv("MAX_LOGIN_ATTEMPTS", "3")
    monkeypatch.setenv("SESSION_TTL_SECONDS", "7200")
    monkeypatch.setenv("LOGIN_LOCKOUT_SECONDS", "300")
    import importlib
    import utils.auth as auth_module
    importlib.reload(auth_module)
    assert auth_module.MAX_LOGIN_ATTEMPTS == 3
    assert auth_module.SESSION_TTL_SECONDS == 7200
    assert auth_module.LOGIN_LOCKOUT_SECONDS == 300
    # Restaurar valores por defecto para no contaminar tests posteriores
    monkeypatch.delenv("MAX_LOGIN_ATTEMPTS")
    monkeypatch.delenv("SESSION_TTL_SECONDS")
    monkeypatch.delenv("LOGIN_LOCKOUT_SECONDS")
    importlib.reload(auth_module)


# ============================================================
# 2. Bloqueo por intentos fallidos — _is_locked_out
# ============================================================

def test_is_locked_out_false_sin_registro(auth_manager):
    """Sin entrada en login_attempts, no hay bloqueo."""
    with patch("utils.auth._get_conn") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.return_value.cursor.return_value = mock_cur
        result = auth_manager._is_locked_out("usuario_nuevo")
    assert result is False


def test_is_locked_out_consulta_usuario_normalizado(auth_manager):
    """_is_locked_out consulta login_attempts con username normalizado."""
    with patch("utils.auth._get_conn") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.return_value.cursor.return_value = mock_cur
        auth_manager._is_locked_out("  USER.TEST  ")

    execute_args = mock_cur.execute.call_args[0]
    assert execute_args[1] == ("user.test",)


def test_is_locked_out_false_bajo_limite(auth_manager):
    """Un solo intento fallido no activa bloqueo."""
    with patch("utils.auth._get_conn") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (1, datetime.utcnow())
        mock_conn.return_value.cursor.return_value = mock_cur
        result = auth_manager._is_locked_out("usuario")
    assert result is False


def test_is_locked_out_true_al_alcanzar_limite(auth_manager, monkeypatch):
    """5 intentos hace 1 minuto activa bloqueo (15 min no expiró)."""
    monkeypatch.setattr(auth_manager, "_clear_failed_attempts", lambda u: None)
    with patch("utils.auth._get_conn") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (5, datetime.utcnow() - timedelta(minutes=1))
        mock_conn.return_value.cursor.return_value = mock_cur
        result = auth_manager._is_locked_out("usuario")
    assert result is True


def test_is_locked_out_false_cuando_bloqueo_expiro(auth_manager, monkeypatch):
    """5 intentos hace 20 minutos desbloquea y limpia contador."""
    clear_calls = []
    monkeypatch.setattr(auth_manager, "_clear_failed_attempts", lambda u: clear_calls.append(u))
    with patch("utils.auth._get_conn") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (5, datetime.utcnow() - timedelta(minutes=20))
        mock_conn.return_value.cursor.return_value = mock_cur
        result = auth_manager._is_locked_out("usuario")
    assert result is False
    assert "usuario" in clear_calls


# ============================================================
# 2b. Bloqueo integrado en authenticate()
# ============================================================

def test_lockout_bloquea_sin_consultar_bd(auth_manager, monkeypatch):
    """Si _is_locked_out retorna True, la BD no es consultada."""
    bd_consultada = []
    monkeypatch.setattr(auth_manager, "_is_locked_out", lambda u: True)
    monkeypatch.setattr(auth_manager, "_log_login", lambda u, **kw: None)

    with patch("utils.auth._get_conn") as mock_conn:
        mock_conn.side_effect = lambda: bd_consultada.append(True) or MagicMock()
        result = auth_manager.authenticate("victima", "cualquier")

    assert result is None
    # La BD solo podría consultarse para _log_login (mockeado), no para la autenticación
    assert len(bd_consultada) == 0


def test_login_incorrecto_registra_intento(auth_manager, monkeypatch):
    """Contraseña incorrecta llama a _record_failed_attempt con el username."""
    intentos = []
    monkeypatch.setattr(auth_manager, "_is_locked_out", lambda u: False)
    monkeypatch.setattr(auth_manager, "_record_failed_attempt", lambda u: intentos.append(u))
    monkeypatch.setattr(auth_manager, "_log_login", lambda u, **kw: None)

    row = {
        "email": "t@t.com", "name": "Tester",
        "password_hash": auth_manager._hash_password("correcta"),
        "role": "analyst", "is_active": True,
        "empresa_id": None, "rfc_empresa": None,
        "empresa_nombre": None, "created_at": None, "last_login": None,
    }

    with patch("utils.auth._get_conn") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = row
        mock_conn.return_value.cursor.return_value = mock_cur
        result = auth_manager.authenticate("tester", "INCORRECTA")

    assert result is None
    assert "tester" in intentos


def test_login_incorrecto_normaliza_usuario_para_lockout(auth_manager, monkeypatch):
    """authenticate normaliza username antes de registrar intento fallido."""
    intentos = []
    monkeypatch.setattr(auth_manager, "_is_locked_out", lambda u: False)
    monkeypatch.setattr(auth_manager, "_record_failed_attempt", lambda u: intentos.append(u))
    monkeypatch.setattr(auth_manager, "_log_login", lambda u, **kw: None)

    with patch("utils.auth._get_conn") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None  # usuario no encontrado
        mock_conn.return_value.cursor.return_value = mock_cur
        result = auth_manager.authenticate("  TESTER  ", "INCORRECTA")

    assert result is None
    assert "tester" in intentos


def test_login_correcto_limpia_intentos(auth_manager, monkeypatch):
    """Login exitoso llama a _clear_failed_attempts para resetear el contador."""
    from utils.auth import UserRole
    limpiezas = []
    fake_state = {}
    monkeypatch.setattr(st, "session_state", fake_state, raising=False)
    monkeypatch.setattr(auth_manager, "_is_locked_out", lambda u: False)
    monkeypatch.setattr(auth_manager, "_clear_failed_attempts", lambda u: limpiezas.append(u))
    monkeypatch.setattr(auth_manager, "_log_login", lambda u, **kw: None)
    monkeypatch.setattr(auth_manager, "get_user_empresas", lambda u: [])

    row = {
        "username": "tester",
        "email": "t@t.com", "name": "Tester",
        "password_hash": auth_manager._hash_password("pass123"),
        "role": UserRole.ANALYST, "is_active": True,
        "empresa_id": "emp-uuid-123", "rfc_empresa": "RFC123",
        "empresa_nombre": "Empresa Test", "created_at": None, "last_login": None,
    }

    with patch("utils.auth._get_conn") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = row
        mock_conn.return_value.cursor.return_value = mock_cur
        result = auth_manager.authenticate("tester", "pass123")

    assert result is not None
    assert "tester" in limpiezas


# ============================================================
# 3. Timestamp de sesión guardado en login exitoso
# ============================================================

def test_login_exitoso_guarda_session_ts(auth_manager, monkeypatch):
    """Login exitoso almacena _session_login_ts y mantiene empresa_id y role."""
    from utils.auth import UserRole
    fake_state = {}
    monkeypatch.setattr(st, "session_state", fake_state, raising=False)
    monkeypatch.setattr(auth_manager, "_is_locked_out", lambda u: False)
    monkeypatch.setattr(auth_manager, "_clear_failed_attempts", lambda u: None)
    monkeypatch.setattr(auth_manager, "_log_login", lambda u, **kw: None)
    monkeypatch.setattr(auth_manager, "get_user_empresas", lambda u: [])

    row = {
        "username": "tester",
        "email": "t@t.com", "name": "Tester",
        "password_hash": auth_manager._hash_password("pass123"),
        "role": UserRole.ANALYST, "is_active": True,
        "empresa_id": "emp-uuid-123", "rfc_empresa": "RFC123",
        "empresa_nombre": "Empresa Test", "created_at": None, "last_login": None,
    }

    with patch("utils.auth._get_conn") as mock_conn:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = row
        mock_conn.return_value.cursor.return_value = mock_cur
        user = auth_manager.authenticate("tester", "pass123")

    assert user is not None
    assert user.empresa_id == "emp-uuid-123"
    assert user.role == UserRole.ANALYST
    assert "_session_login_ts" in fake_state
    assert isinstance(fake_state["_session_login_ts"], datetime)


# ============================================================
# 4. Expiración de sesión — check_session_expiry
# ============================================================

def test_check_session_expiry_sin_sesion(monkeypatch):
    """Sin sesión activa retorna False sin error."""
    monkeypatch.setattr(st, "session_state", {}, raising=False)
    from utils.auth import check_session_expiry
    assert check_session_expiry() is False


def test_check_session_expiry_sesion_vigente(monkeypatch):
    """Sesión de hace 30 minutos (muy por debajo del TTL de 8h) no expira."""
    monkeypatch.setattr(
        st, "session_state",
        {"_session_login_ts": datetime.utcnow() - timedelta(minutes=30)},
        raising=False,
    )
    from utils.auth import check_session_expiry
    assert check_session_expiry() is False


def test_check_session_expiry_sesion_expirada(monkeypatch):
    """Sesión de hace 25 horas expira y limpia session_state."""
    fake_state = {
        "_session_login_ts": datetime.utcnow() - timedelta(hours=25),
        "user": MagicMock(username="test"),
        "empresa_id": "uuid-empresa",
        "df": MagicMock(),
    }
    monkeypatch.setattr(st, "session_state", fake_state, raising=False)
    from utils.auth import check_session_expiry
    result = check_session_expiry()
    assert result is True
    assert "user" not in fake_state
    assert "empresa_id" not in fake_state
    assert "_session_login_ts" not in fake_state


# ============================================================
# 5. Logout
# ============================================================

def test_logout_limpia_claves_sensibles(monkeypatch):
    """logout() elimina todas las claves de sesión sensibles preservando las de UI."""
    fake_state = {
        "user": MagicMock(),
        "_session_login_ts": datetime.utcnow(),
        "empresa_id": "uuid",
        "empresa_nombre": "Empresa SA",
        "rfc_empresa": "RFC001",
        "nl2sql_engine": MagicMock(),
        "nl2sql_messages": ["msg1"],
        "df": MagicMock(),
        "_df_fuente": "cfdi",
        "clave_ui": "valor_que_debe_quedar",
    }
    monkeypatch.setattr(st, "session_state", fake_state, raising=False)
    from utils.auth import logout
    logout()
    assert "user" not in fake_state
    assert "empresa_id" not in fake_state
    assert "_session_login_ts" not in fake_state
    assert "nl2sql_engine" not in fake_state
    assert "df" not in fake_state
    assert fake_state.get("clave_ui") == "valor_que_debe_quedar"


# ============================================================
# 6. Roles — sin cambios por la migración
# ============================================================

def test_user_roles_funcionan():
    """Los métodos de rol del User retornan correctamente tras los cambios."""
    from utils.auth import User, UserRole
    admin = User(username="a", email="a@a.com", name="A", role=UserRole.ADMIN)
    analyst = User(username="b", email="b@b.com", name="B", role=UserRole.ANALYST)
    viewer = User(username="c", email="c@c.com", name="C", role=UserRole.VIEWER)

    assert admin.can_manage_users() is True
    assert analyst.can_manage_users() is False
    assert viewer.can_manage_users() is False
    assert admin.can_use_ai() is True
    assert analyst.can_use_ai() is True
    assert viewer.can_use_ai() is False
    assert admin.can_export() is True
    assert viewer.can_export() is False

"""Tests unitarios para utils/auth.py."""

from types import SimpleNamespace

import pytest

from utils.auth import AuthManager, User, UserRole, get_current_user, require_auth, require_role


@pytest.fixture
def auth_manager(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    db_path = tmp_path / "users_test.db"
    return AuthManager(db_path=str(db_path))


def test_user_permission_helpers_by_role():
    admin = User("admin", "a@test.com", "Admin", UserRole.ADMIN)
    analyst = User("ana", "ana@test.com", "Ana", UserRole.ANALYST)
    viewer = User("view", "view@test.com", "View", UserRole.VIEWER)

    assert admin.can_export() is True
    assert admin.can_use_ai() is True
    assert admin.can_manage_users() is True
    assert admin.can_edit_config() is True

    assert analyst.can_export() is True
    assert analyst.can_use_ai() is True
    assert analyst.can_manage_users() is False
    assert analyst.can_edit_config() is False

    assert viewer.can_export() is False
    assert viewer.can_use_ai() is False
    assert viewer.can_manage_users() is False
    assert viewer.can_edit_config() is False


def test_default_admin_is_created_and_can_authenticate(auth_manager):
    user = auth_manager.authenticate("admin", "fradma2026")

    assert user is not None
    assert user.username == "admin"
    assert user.role == UserRole.ADMIN


def test_verify_password_handles_invalid_hash(auth_manager):
    assert auth_manager._verify_password("secret", "invalid-hash") is False


def test_authenticate_returns_none_for_unknown_user(auth_manager):
    assert auth_manager.authenticate("ghost", "whatever") is None


def test_create_user_and_get_user(auth_manager):
    success, msg = auth_manager.create_user(
        username="analista",
        email="analista@test.com",
        name="Ana",
        password="secreto1",
        role=UserRole.ANALYST,
        created_by="admin",
        notes="equipo finanzas",
    )

    user = auth_manager.get_user("analista")

    assert success is True
    assert "creado exitosamente" in msg.lower()
    assert user is not None
    assert user["email"] == "analista@test.com"
    assert user["created_by"] == "admin"
    assert user["notes"] == "equipo finanzas"
    assert user["is_active"] is True


def test_create_user_validations(auth_manager):
    assert auth_manager.create_user("ab", "a@test.com", "A", "123456", UserRole.ANALYST)[0] is False
    assert auth_manager.create_user("abc", "correo-invalido", "A", "123456", UserRole.ANALYST)[0] is False
    assert auth_manager.create_user("abc", "a@test.com", "", "123456", UserRole.ANALYST)[0] is False
    assert auth_manager.create_user("abc", "a@test.com", "A", "123", UserRole.ANALYST)[0] is False
    assert auth_manager.create_user("abc", "a@test.com", "A", "123456", "otro_rol")[0] is False


def test_create_user_rejects_duplicate_username_and_email(auth_manager):
    auth_manager.create_user("user1", "u1@test.com", "User 1", "123456", UserRole.VIEWER)

    success_user, msg_user = auth_manager.create_user("user1", "u2@test.com", "Otro", "123456", UserRole.VIEWER)
    success_email, msg_email = auth_manager.create_user("user2", "u1@test.com", "Otro", "123456", UserRole.VIEWER)

    assert success_user is False
    assert "ya existe" in msg_user.lower()
    assert success_email is False
    assert "ya está en uso" in msg_email.lower()


def test_list_users_returns_created_users(auth_manager):
    auth_manager.create_user("user1", "u1@test.com", "User 1", "123456", UserRole.VIEWER)
    auth_manager.create_user("user2", "u2@test.com", "User 2", "123456", UserRole.ANALYST)

    users = auth_manager.list_users()
    usernames = {user["username"] for user in users}

    assert {"admin", "user1", "user2"}.issubset(usernames)


def test_update_user_and_missing_user(auth_manager):
    auth_manager.create_user("user1", "u1@test.com", "User 1", "123456", UserRole.VIEWER)

    success, _ = auth_manager.update_user("user1", name="Nuevo Nombre", notes="nota")
    updated = auth_manager.get_user("user1")
    missing_success, missing_msg = auth_manager.update_user("ghost", name="Nada")
    empty_success, empty_msg = auth_manager.update_user("user1", unsupported="x")

    assert success is True
    assert updated["name"] == "Nuevo Nombre"
    assert updated["notes"] == "nota"
    assert missing_success is False
    assert "no encontrado" in missing_msg.lower()
    assert empty_success is False
    assert "no hay campos" in empty_msg.lower()


def test_change_password_success_and_invalid_current(auth_manager):
    auth_manager.create_user("user1", "u1@test.com", "User 1", "123456", UserRole.VIEWER)

    bad_success, bad_msg = auth_manager.change_password("user1", "xxxxxx", "abcdef")
    ok_success, ok_msg = auth_manager.change_password("user1", "123456", "abcdef")
    user = auth_manager.authenticate("user1", "abcdef")

    assert bad_success is False
    assert "actual incorrecta" in bad_msg.lower()
    assert ok_success is True
    assert "actualizada" in ok_msg.lower()
    assert user is not None


def test_change_password_rejects_short_new_password(auth_manager):
    auth_manager.create_user("user1", "u1@test.com", "User 1", "123456", UserRole.VIEWER)

    success, msg = auth_manager.change_password("user1", "123456", "123")

    assert success is False
    assert "al menos 6" in msg.lower()


def test_reset_password_success_and_missing_user(auth_manager):
    auth_manager.create_user("user1", "u1@test.com", "User 1", "123456", UserRole.VIEWER)

    success, msg = auth_manager.reset_password("user1", "abcdef", "admin")
    missing_success, missing_msg = auth_manager.reset_password("ghost", "abcdef", "admin")
    short_success, short_msg = auth_manager.reset_password("user1", "123", "admin")

    assert success is True
    assert "reseteada" in msg.lower()
    assert auth_manager.authenticate("user1", "abcdef") is not None
    assert missing_success is False
    assert "no encontrado" in missing_msg.lower()
    assert short_success is False
    assert "al menos 6" in short_msg.lower()


def test_deactivate_and_activate_user(auth_manager):
    auth_manager.create_user("user1", "u1@test.com", "User 1", "123456", UserRole.VIEWER)

    deactivated, _ = auth_manager.deactivate_user("user1", "admin")
    blocked_login = auth_manager.authenticate("user1", "123456")
    activated, _ = auth_manager.activate_user("user1", "admin")
    allowed_login = auth_manager.authenticate("user1", "123456")

    assert deactivated is True
    assert blocked_login is None
    assert activated is True
    assert allowed_login is not None


def test_deactivate_admin_and_missing_user(auth_manager):
    admin_success, admin_msg = auth_manager.deactivate_user("admin", "admin")
    missing_success, missing_msg = auth_manager.deactivate_user("ghost", "admin")

    assert admin_success is False
    assert "no se puede desactivar" in admin_msg.lower()
    assert missing_success is False
    assert "no encontrado" in missing_msg.lower()


def test_get_login_history_tracks_success_and_failure(auth_manager):
    auth_manager.create_user("user1", "u1@test.com", "User 1", "123456", UserRole.VIEWER)

    auth_manager.authenticate("user1", "badpass")
    auth_manager.authenticate("user1", "123456")

    history = auth_manager.get_login_history("user1", limit=10)

    assert len(history) == 2
    assert all(item["username"] == "user1" for item in history)
    assert sorted(item["success"] for item in history) == [False, True]


def test_get_current_user_reads_streamlit_session(monkeypatch):
    fake_session = {"user": SimpleNamespace(username="ana")}
    monkeypatch.setattr("utils.auth.st.session_state", fake_session, raising=False)

    user = get_current_user()

    assert user.username == "ana"


def test_require_auth_allows_authenticated_user(monkeypatch):
    monkeypatch.setattr("utils.auth.st.session_state", {"user": SimpleNamespace(role=UserRole.ADMIN)}, raising=False)
    stop_calls = []
    monkeypatch.setattr("utils.auth.st.error", lambda message: (_ for _ in ()).throw(AssertionError(message)))
    monkeypatch.setattr("utils.auth.st.stop", lambda: stop_calls.append(True))

    @require_auth
    def protected():
        return "ok"

    assert protected() == "ok"
    assert stop_calls == []


def test_require_auth_blocks_unauthenticated_user(monkeypatch):
    messages = []
    monkeypatch.setattr("utils.auth.st.session_state", {}, raising=False)
    monkeypatch.setattr("utils.auth.st.error", lambda message: messages.append(message))

    def raise_stop():
        raise RuntimeError("stopped")

    monkeypatch.setattr("utils.auth.st.stop", raise_stop)

    @require_auth
    def protected():
        return "ok"

    with pytest.raises(RuntimeError, match="stopped"):
        protected()

    assert any("debes iniciar sesión" in message.lower() for message in messages)


def test_require_role_allows_and_blocks(monkeypatch):
    messages = []
    monkeypatch.setattr("utils.auth.st.error", lambda message: messages.append(message))

    def raise_stop():
        raise RuntimeError("stopped")

    monkeypatch.setattr("utils.auth.st.stop", raise_stop)

    @require_role([UserRole.ADMIN, UserRole.ANALYST])
    def privileged():
        return "allowed"

    monkeypatch.setattr("utils.auth.st.session_state", {"user": SimpleNamespace(role=UserRole.ANALYST)}, raising=False)
    assert privileged() == "allowed"

    monkeypatch.setattr("utils.auth.st.session_state", {"user": SimpleNamespace(role=UserRole.VIEWER)}, raising=False)
    with pytest.raises(RuntimeError, match="stopped"):
        privileged()

    assert any("acceso denegado" in message.lower() for message in messages)
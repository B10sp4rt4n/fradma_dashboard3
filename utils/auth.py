"""
Sistema de autenticación multi-usuario para FRADMA Dashboard.

Proporciona:
- Autenticación con usuario/contraseña
- Roles (admin, analyst, viewer)
- Gestión de usuarios en Neon PostgreSQL (misma BD que los datos)
- Control de acceso basado en roles
- Vinculación usuario ↔ empresa por RFC y empresa_id
"""

import os
import bcrypt
import psycopg2
import psycopg2.extras
from datetime import datetime
from typing import Optional
import streamlit as st
from dataclasses import dataclass, field
from utils.logger import configurar_logger

logger = configurar_logger("auth", nivel="INFO")


def _get_conn():
    """Obtiene conexión a Neon PostgreSQL."""
    return psycopg2.connect(os.environ["NEON_DATABASE_URL"])


class UserRole:
    """Roles disponibles en el sistema"""
    ADMIN = "admin"        # CRUD users, configuración, acceso completo
    ANALYST = "analyst"    # Ver todo, exportar, análisis IA
    VIEWER = "viewer"      # Solo visualizar dashboards


@dataclass
class User:
    """Representa un usuario del sistema"""
    username: str
    email: str
    name: str
    role: str
    empresa_id: Optional[str] = None   # UUID de empresas en Neon (None = superadmin)
    rfc_empresa: Optional[str] = None  # RFC para display/validación
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    def can_export(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.ANALYST]

    def can_use_ai(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.ANALYST]

    def can_manage_users(self) -> bool:
        return self.role == UserRole.ADMIN

    def can_edit_config(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_superadmin(self) -> bool:
        """Superadmin = admin sin empresa asignada → ve todos los datos."""
        return self.role == UserRole.ADMIN and self.empresa_id is None


class AuthManager:
    """Gestor centralizado de autenticación y usuarios — Neon PostgreSQL."""

    def __init__(self, db_path: str = None):
        # db_path ignorado (compatibilidad); siempre usa Neon
        self._ensure_admin()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def _verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception as e:
            logger.error(f"Error verificando password: {e}")
            return False

    def _ensure_admin(self):
        """Crea usuario admin por defecto si no existe en Neon."""
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
            if cur.fetchone()[0] == 0:
                default_password = os.getenv("APP_PASSWORD", "fradma2026")
                cur.execute(
                    """
                    INSERT INTO users (username, email, name, password_hash, role, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    ("admin", "admin@fradma.local", "Administrador",
                     self._hash_password(default_password), UserRole.ADMIN, "system"),
                )
                conn.commit()
                logger.info("Usuario admin creado en Neon")
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error en _ensure_admin: {e}")

    def _log_login(self, username: str, success: bool):
        """Registra intento de login en login_history."""
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO login_history (username, success) VALUES (%s, %s)",
                (username, success),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error registrando login: {e}")

    # ------------------------------------------------------------------
    # Autenticación
    # ------------------------------------------------------------------

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Autentica usuario; retorna User si válido, None si falla."""
        try:
            conn = _get_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT email, name, password_hash, role, is_active,
                       empresa_id::text, rfc_empresa, created_at, last_login
                FROM users WHERE username = %s
                """,
                (username,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error en authenticate: {e}")
            return None

        if not row:
            logger.warning(f"Login fallido: usuario '{username}' no existe")
            self._log_login(username, success=False)
            return None

        if not row["is_active"]:
            logger.warning(f"Login fallido: usuario '{username}' desactivado")
            self._log_login(username, success=False)
            return None

        if not self._verify_password(password, row["password_hash"]):
            logger.warning(f"Login fallido: password incorrecta para '{username}'")
            self._log_login(username, success=False)
            return None

        # Actualizar last_login
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET last_login = NOW() WHERE username = %s", (username,)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error actualizando last_login: {e}")

        self._log_login(username, success=True)
        logger.info(f"Login exitoso: {username} ({row['role']})")

        return User(
            username=username,
            email=row["email"],
            name=row["name"],
            role=row["role"],
            empresa_id=row["empresa_id"],
            rfc_empresa=row["rfc_empresa"],
            created_at=row["created_at"],
            last_login=datetime.now(),
        )

    # ------------------------------------------------------------------
    # CRUD de usuarios
    # ------------------------------------------------------------------

    def create_user(
        self,
        username: str,
        email: str,
        name: str,
        password: str,
        role: str,
        created_by: str = None,
        notes: str = None,
        empresa_id: str = None,
        rfc_empresa: str = None,
    ) -> tuple[bool, str]:
        if not username or len(username) < 3:
            return False, "Username debe tener al menos 3 caracteres"
        if not email or "@" not in email:
            return False, "Email inválido"
        if not name:
            return False, "Nombre es requerido"
        if len(password) < 6:
            return False, "Password debe tener al menos 6 caracteres"
        if role not in [UserRole.ADMIN, UserRole.ANALYST, UserRole.VIEWER]:
            return False, f"Rol inválido: {role}"

        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users
                    (username, email, name, password_hash, role,
                     empresa_id, rfc_empresa, created_by, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (username, email, name, self._hash_password(password),
                 role, empresa_id or None, rfc_empresa or None, created_by, notes),
            )
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"Usuario creado: {username} ({role}) por {created_by}")
            return True, f"Usuario '{username}' creado exitosamente"
        except psycopg2.errors.UniqueViolation as e:
            msg = str(e)
            if "username" in msg:
                return False, f"Username '{username}' ya existe"
            if "email" in msg:
                return False, f"Email '{email}' ya está en uso"
            return False, f"Error de unicidad: {e}"
        except Exception as e:
            logger.error(f"Error creando usuario: {e}")
            return False, f"Error al crear usuario: {e}"

    def list_users(self) -> list[dict]:
        try:
            conn = _get_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT u.username, u.email, u.name, u.role,
                       u.created_at, u.last_login, u.is_active,
                       u.created_by, u.notes,
                       u.empresa_id::text, u.rfc_empresa,
                       e.razon_social AS empresa_nombre
                FROM users u
                LEFT JOIN empresas e ON e.id = u.empresa_id
                ORDER BY u.created_at DESC
                """
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error listando usuarios: {e}")
            return []

    def get_user(self, username: str) -> Optional[dict]:
        users = self.list_users()
        return next((u for u in users if u["username"] == username), None)

    def update_user(self, username: str, **kwargs) -> tuple[bool, str]:
        allowed = ["email", "name", "role", "notes", "empresa_id", "rfc_empresa"]
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False, "No hay campos para actualizar"
        try:
            conn = _get_conn()
            cur = conn.cursor()
            set_clause = ", ".join(f"{k} = %s" for k in updates)
            cur.execute(
                f"UPDATE users SET {set_clause} WHERE username = %s",
                list(updates.values()) + [username],
            )
            if cur.rowcount == 0:
                cur.close(); conn.close()
                return False, f"Usuario '{username}' no encontrado"
            conn.commit()
            cur.close(); conn.close()
            logger.info(f"Usuario actualizado: {username}")
            return True, "Usuario actualizado exitosamente"
        except Exception as e:
            logger.error(f"Error actualizando usuario: {e}")
            return False, f"Error al actualizar: {e}"

    def change_password(self, username: str, old_password: str, new_password: str) -> tuple[bool, str]:
        if not self.authenticate(username, old_password):
            return False, "Password actual incorrecta"
        if len(new_password) < 6:
            return False, "Nueva password debe tener al menos 6 caracteres"
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE username = %s",
                (self._hash_password(new_password), username),
            )
            conn.commit(); cur.close(); conn.close()
            logger.info(f"Password cambiada: {username}")
            return True, "Password actualizada exitosamente"
        except Exception as e:
            return False, f"Error al cambiar password: {e}"

    def reset_password(self, username: str, new_password: str, admin_username: str) -> tuple[bool, str]:
        if len(new_password) < 6:
            return False, "Password debe tener al menos 6 caracteres"
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE username = %s",
                (self._hash_password(new_password), username),
            )
            if cur.rowcount == 0:
                cur.close(); conn.close()
                return False, f"Usuario '{username}' no encontrado"
            conn.commit(); cur.close(); conn.close()
            logger.info(f"Password reseteada: {username} por {admin_username}")
            return True, f"Password reseteada. Nueva: {new_password}"
        except Exception as e:
            return False, f"Error al resetear password: {e}"

    def deactivate_user(self, username: str, admin_username: str) -> tuple[bool, str]:
        if username == "admin":
            return False, "No se puede desactivar el usuario admin principal"
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute("UPDATE users SET is_active = FALSE WHERE username = %s", (username,))
            if cur.rowcount == 0:
                cur.close(); conn.close()
                return False, f"Usuario '{username}' no encontrado"
            conn.commit(); cur.close(); conn.close()
            logger.info(f"Usuario desactivado: {username} por {admin_username}")
            return True, f"Usuario '{username}' desactivado"
        except Exception as e:
            return False, f"Error al desactivar: {e}"

    def activate_user(self, username: str, admin_username: str) -> tuple[bool, str]:
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute("UPDATE users SET is_active = TRUE WHERE username = %s", (username,))
            if cur.rowcount == 0:
                cur.close(); conn.close()
                return False, f"Usuario '{username}' no encontrado"
            conn.commit(); cur.close(); conn.close()
            logger.info(f"Usuario reactivado: {username} por {admin_username}")
            return True, f"Usuario '{username}' reactivado"
        except Exception as e:
            return False, f"Error al reactivar: {e}"

    def get_login_history(self, username: str = None, limit: int = 50) -> list[dict]:
        try:
            conn = _get_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if username:
                cur.execute(
                    """SELECT username, timestamp, success, ip_address, user_agent
                       FROM login_history WHERE username = %s
                       ORDER BY timestamp DESC LIMIT %s""",
                    (username, limit),
                )
            else:
                cur.execute(
                    """SELECT username, timestamp, success, ip_address, user_agent
                       FROM login_history ORDER BY timestamp DESC LIMIT %s""",
                    (limit,),
                )
            rows = cur.fetchall()
            cur.close(); conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error obteniendo historial: {e}")
            return []

    # ------------------------------------------------------------------
    # Helpers de empresas
    # ------------------------------------------------------------------

    def list_empresas(self) -> list[dict]:
        """Lista empresas disponibles para asignar a usuarios."""
        try:
            conn = _get_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT id::text, razon_social, rfc, plan, status FROM empresas ORDER BY razon_social"
            )
            rows = cur.fetchall()
            cur.close(); conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error listando empresas: {e}")
            return []



# ====================================================================
# HELPERS PARA STREAMLIT
# ====================================================================

def get_current_user() -> Optional[User]:
    """Obtiene usuario actual de la sesión"""
    return st.session_state.get('user')


def require_auth(func):
    """
    Decorador para requerir autenticación.
    
    Uso:
        @require_auth
        def mi_pagina():
            user = get_current_user()
            ...
    """
    def wrapper(*args, **kwargs):
        if not get_current_user():
            st.error("❌ Debes iniciar sesión para acceder a esta página")
            st.stop()
        return func(*args, **kwargs)
    return wrapper


def require_role(allowed_roles: list[str]):
    """
    Decorador para requerir rol específico.
    
    Uso:
        @require_role([UserRole.ADMIN, UserRole.ANALYST])
        def admin_panel():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                st.error("❌ Debes iniciar sesión")
                st.stop()
            
            if user.role not in allowed_roles:
                st.error(f"❌ Acceso denegado. Se requiere rol: {', '.join(allowed_roles)}")
                st.stop()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    # Demo del sistema de autenticación
    auth = AuthManager()
    
    print("=== Sistema de Autenticación FRADMA ===\n")
    
    # Test: Autenticar con admin
    print("1. Test login admin...")
    user = auth.authenticate('admin', 'fradma2026')
    if user:
        print(f"   ✅ Login exitoso: {user.name} ({user.role})")
    else:
        print("   ❌ Login fallido")
    
    # Test: Crear usuario
    print("\n2. Test crear usuario...")
    success, msg = auth.create_user(
        username='analista1',
        email='analista@empresa.com',
        name='Juan Analista',
        password='password123',
        role=UserRole.ANALYST,
        created_by='admin'
    )
    print(f"   {'✅' if success else '❌'} {msg}")
    
    # Test: Listar usuarios
    print("\n3. Usuarios en el sistema:")
    users = auth.list_users()
    for u in users:
        status = "✅ Activo" if u['is_active'] else "❌ Inactivo"
        print(f"   - {u['username']}: {u['name']} ({u['role']}) - {status}")
    
    print("\n=== Tests completados ===")

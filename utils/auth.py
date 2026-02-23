"""
Sistema de autenticación multi-usuario para FRADMA Dashboard.

Proporciona:
- Autenticación con usuario/contraseña
- Roles (admin, analyst, viewer)
- Gestión de usuarios en SQLite
- Control de acceso basado en roles
"""

import sqlite3
import bcrypt
from pathlib import Path
from datetime import datetime
from typing import Optional
import streamlit as st
from dataclasses import dataclass
from utils.logger import configurar_logger

logger = configurar_logger("auth", nivel="INFO")


# Directorio para base de datos de usuarios
DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "users.db"


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
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    
    def can_export(self) -> bool:
        """¿Puede exportar reportes?"""
        return self.role in [UserRole.ADMIN, UserRole.ANALYST]
    
    def can_use_ai(self) -> bool:
        """¿Puede usar análisis con IA?"""
        return self.role in [UserRole.ADMIN, UserRole.ANALYST]
    
    def can_manage_users(self) -> bool:
        """¿Puede gestionar usuarios?"""
        return self.role == UserRole.ADMIN
    
    def can_edit_config(self) -> bool:
        """¿Puede editar configuración del sistema?"""
        return self.role == UserRole.ADMIN


class AuthManager:
    """Gestor centralizado de autenticación y usuarios"""
    
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Crea schema de base de datos si no existe"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de usuarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'analyst', 'viewer')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                created_by TEXT,
                notes TEXT
            )
        """)
        
        # Tabla de historial de logins
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (username) REFERENCES users(username)
            )
        """)
        
        # Índices para performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_login_history_username 
            ON login_history(username)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_login_history_timestamp 
            ON login_history(timestamp)
        """)
        
        conn.commit()
        
        # Crear usuario admin por defecto si no existe
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            logger.info("Creando usuario admin por defecto")
            
            # Usar password del .env si existe, sino usar default
            import os
            default_password = os.getenv("APP_PASSWORD", "fradma2026")
            
            cursor.execute("""
                INSERT INTO users (username, email, name, password_hash, role, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                'admin',
                'admin@fradma.local',
                'Administrador',
                self._hash_password(default_password),
                UserRole.ADMIN,
                'system'
            ))
            
            conn.commit()
            logger.info(f"Usuario admin creado con password por defecto")
        
        conn.close()
    
    def _hash_password(self, password: str) -> str:
        """Hash seguro de password con bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verifica password contra hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error verificando password: {e}")
            return False
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        Autentica usuario y retorna objeto User si es válido.
        
        Args:
            username: Nombre de usuario
            password: Contraseña en texto plano
            
        Returns:
            User si autenticación exitosa, None si falla
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT email, name, password_hash, role, is_active, created_at, last_login
                FROM users WHERE username = ?
            """, (username,))
            
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"Login fallido: usuario '{username}' no existe")
                self._log_login(username, success=False)
                return None
            
            email, name, password_hash, role, is_active, created_at, last_login = row
            
            # Verificar si usuario está activo
            if not is_active:
                logger.warning(f"Login fallido: usuario '{username}' está desactivado")
                self._log_login(username, success=False)
                return None
            
            # Verificar password
            if not self._verify_password(password, password_hash):
                logger.warning(f"Login fallido: password incorrecta para '{username}'")
                self._log_login(username, success=False)
                return None
            
            # Login exitoso - actualizar last_login
            cursor.execute("""
                UPDATE users SET last_login = CURRENT_TIMESTAMP 
                WHERE username = ?
            """, (username,))
            
            conn.commit()
            
            self._log_login(username, success=True)
            logger.info(f"Login exitoso: {username} ({role})")
            
            return User(
                username=username,
                email=email,
                name=name,
                role=role,
                created_at=datetime.fromisoformat(created_at) if created_at else None,
                last_login=datetime.now()
            )
        
        finally:
            conn.close()
    
    def _log_login(self, username: str, success: bool):
        """Registra intento de login en historial"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO login_history (username, success)
                VALUES (?, ?)
            """, (username, success))
            
            conn.commit()
        except Exception as e:
            logger.error(f"Error registrando login: {e}")
        finally:
            conn.close()
    
    def create_user(self, username: str, email: str, name: str, 
                   password: str, role: str, created_by: str = None,
                   notes: str = None) -> tuple[bool, str]:
        """
        Crea nuevo usuario.
        
        Args:
            username: Username único
            email: Email único
            name: Nombre completo
            password: Contraseña en texto plano
            role: Rol (admin, analyst, viewer)
            created_by: Username del creador
            notes: Notas opcionales
            
        Returns:
            (success: bool, message: str)
        """
        # Validaciones
        if not username or len(username) < 3:
            return False, "Username debe tener al menos 3 caracteres"
        
        if not email or '@' not in email:
            return False, "Email inválido"
        
        if not name:
            return False, "Nombre es requerido"
        
        if len(password) < 6:
            return False, "Password debe tener al menos 6 caracteres"
        
        if role not in [UserRole.ADMIN, UserRole.ANALYST, UserRole.VIEWER]:
            return False, f"Rol inválido. Debe ser: {UserRole.ADMIN}, {UserRole.ANALYST}, {UserRole.VIEWER}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO users (username, email, name, password_hash, role, created_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                username,
                email,
                name,
                self._hash_password(password),
                role,
                created_by,
                notes
            ))
            
            conn.commit()
            logger.info(f"Usuario creado: {username} ({role}) por {created_by}")
            return True, f"Usuario '{username}' creado exitosamente"
        
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                return False, f"Username '{username}' ya existe"
            elif 'email' in str(e):
                return False, f"Email '{email}' ya está en uso"
            else:
                return False, f"Error de integridad: {e}"
        
        except Exception as e:
            logger.error(f"Error creando usuario: {e}")
            return False, f"Error al crear usuario: {e}"
        
        finally:
            conn.close()
    
    def list_users(self) -> list[dict]:
        """
        Lista todos los usuarios del sistema.
        
        Returns:
            Lista de diccionarios con info de usuarios
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT username, email, name, role, created_at, last_login, 
                       is_active, created_by, notes
                FROM users 
                ORDER BY created_at DESC
            """)
            
            users = []
            for row in cursor.fetchall():
                users.append({
                    'username': row[0],
                    'email': row[1],
                    'name': row[2],
                    'role': row[3],
                    'created_at': row[4],
                    'last_login': row[5],
                    'is_active': bool(row[6]),
                    'created_by': row[7],
                    'notes': row[8]
                })
            
            return users
        
        finally:
            conn.close()
    
    def get_user(self, username: str) -> Optional[dict]:
        """Obtiene información de un usuario específico"""
        users = self.list_users()
        for user in users:
            if user['username'] == username:
                return user
        return None
    
    def update_user(self, username: str, **kwargs) -> tuple[bool, str]:
        """
        Actualiza información de un usuario.
        
        Args:
            username: Usuario a actualizar
            **kwargs: Campos a actualizar (email, name, role, notes)
            
        Returns:
            (success: bool, message: str)
        """
        allowed_fields = ['email', 'name', 'role', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
        
        if not updates:
            return False, "No hay campos para actualizar"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            query = f"UPDATE users SET {set_clause} WHERE username = ?"
            
            cursor.execute(query, list(updates.values()) + [username])
            
            if cursor.rowcount == 0:
                return False, f"Usuario '{username}' no encontrado"
            
            conn.commit()
            logger.info(f"Usuario actualizado: {username} - {updates.keys()}")
            return True, "Usuario actualizado exitosamente"
        
        except Exception as e:
            logger.error(f"Error actualizando usuario: {e}")
            return False, f"Error al actualizar: {e}"
        
        finally:
            conn.close()
    
    def change_password(self, username: str, old_password: str, 
                       new_password: str) -> tuple[bool, str]:
        """
        Cambia password de un usuario (requiere password actual).
        
        Args:
            username: Usuario
            old_password: Password actual
            new_password: Password nueva
            
        Returns:
            (success: bool, message: str)
        """
        # Verificar password actual
        user = self.authenticate(username, old_password)
        if not user:
            return False, "Password actual incorrecta"
        
        # Validar nueva password
        if len(new_password) < 6:
            return False, "Nueva password debe tener al menos 6 caracteres"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users SET password_hash = ? WHERE username = ?
            """, (self._hash_password(new_password), username))
            
            conn.commit()
            logger.info(f"Password cambiada para usuario: {username}")
            return True, "Password actualizada exitosamente"
        
        except Exception as e:
            logger.error(f"Error cambiando password: {e}")
            return False, f"Error al cambiar password: {e}"
        
        finally:
            conn.close()
    
    def reset_password(self, username: str, new_password: str, 
                       admin_username: str) -> tuple[bool, str]:
        """
        Resetea password de un usuario (solo admins).
        
        Args:
            username: Usuario a resetear
            new_password: Nueva password
            admin_username: Admin que ejecuta el reset
            
        Returns:
            (success: bool, message: str)
        """
        if len(new_password) < 6:
            return False, "Password debe tener al menos 6 caracteres"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users SET password_hash = ? WHERE username = ?
            """, (self._hash_password(new_password), username))
            
            if cursor.rowcount == 0:
                return False, f"Usuario '{username}' no encontrado"
            
            conn.commit()
            logger.info(f"Password reseteada para {username} por admin {admin_username}")
            return True, f"Password reseteada exitosamente. Nueva password: {new_password}"
        
        except Exception as e:
            logger.error(f"Error reseteando password: {e}")
            return False, f"Error al resetear password: {e}"
        
        finally:
            conn.close()
    
    def deactivate_user(self, username: str, admin_username: str) -> tuple[bool, str]:
        """
        Desactiva un usuario (soft delete).
        
        Args:
            username: Usuario a desactivar
            admin_username: Admin que ejecuta la acción
            
        Returns:
            (success: bool, message: str)
        """
        if username == 'admin':
            return False, "No se puede desactivar el usuario admin principal"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users SET is_active = 0 WHERE username = ?
            """, (username,))
            
            if cursor.rowcount == 0:
                return False, f"Usuario '{username}' no encontrado"
            
            conn.commit()
            logger.info(f"Usuario desactivado: {username} por {admin_username}")
            return True, f"Usuario '{username}' desactivado exitosamente"
        
        except Exception as e:
            logger.error(f"Error desactivando usuario: {e}")
            return False, f"Error al desactivar: {e}"
        
        finally:
            conn.close()
    
    def activate_user(self, username: str, admin_username: str) -> tuple[bool, str]:
        """Reactiva un usuario desactivado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users SET is_active = 1 WHERE username = ?
            """, (username,))
            
            if cursor.rowcount == 0:
                return False, f"Usuario '{username}' no encontrado"
            
            conn.commit()
            logger.info(f"Usuario reactivado: {username} por {admin_username}")
            return True, f"Usuario '{username}' reactivado exitosamente"
        
        except Exception as e:
            logger.error(f"Error reactivando usuario: {e}")
            return False, f"Error al reactivar: {e}"
        
        finally:
            conn.close()
    
    def get_login_history(self, username: str = None, limit: int = 50) -> list[dict]:
        """
        Obtiene historial de logins.
        
        Args:
            username: Filtrar por usuario (None = todos)
            limit: Máximo de registros
            
        Returns:
            Lista de diccionarios con historial
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if username:
                cursor.execute("""
                    SELECT username, timestamp, success, ip_address, user_agent
                    FROM login_history
                    WHERE username = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (username, limit))
            else:
                cursor.execute("""
                    SELECT username, timestamp, success, ip_address, user_agent
                    FROM login_history
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'username': row[0],
                    'timestamp': row[1],
                    'success': bool(row[2]),
                    'ip_address': row[3],
                    'user_agent': row[4]
                })
            
            return history
        
        finally:
            conn.close()


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

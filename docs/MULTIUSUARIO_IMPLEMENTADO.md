# 👥 Sistema Multi-Usuario Implementado

## 📋 Resumen General

Se ha implementado un sistema completo de autenticación multi-usuario con control de acceso basado en roles (RBAC - Role-Based Access Control) para el Dashboard Fradma.

## 🎯 Roles Implementados

### 1. 👑 Admin (Administrador)
- **Acceso completo** a todas las funcionalidades
- Gestión de usuarios (crear, modificar, desactivar)
- Configuración del sistema
- Exportaciones de reportes
- Análisis con IA
- Visualización de todos los módulos

### 2. 📊 Analyst (Analista)
- Visualización de todos los módulos
- Exportaciones de reportes (Excel, CSV, PDF)
- Análisis con IA
- **NO** puede gestionar usuarios
- **NO** puede modificar configuración del sistema

### 3. 👁️ Viewer (Visualizador)
- Visualización de todos los módulos
- **NO** puede exportar reportes
- **NO** puede usar análisis con IA
- **NO** puede gestionar usuarios
- **NO** puede modificar configuración

## 📂 Archivos Creados/Modificados

### Nuevos Archivos

1. **`utils/auth.py`** (550+ líneas)
   - `AuthManager`: Clase principal de autenticación
   - `User`: Dataclass que representa usuarios
   - `UserRole`: Constantes de roles
   - Base de datos SQLite para usuarios
   - Sistema de login y gestión de sesiones
   - Historial de accesos

2. **`utils/admin_panel.py`** (450+ líneas)
   - `mostrar_panel_usuarios()`: Panel de gestión de usuarios
   - `mostrar_panel_configuracion()`: Configuración de sistema
   - `mostrar_info_usuario()`: Widget de información del usuario en sidebar
   - Interfaz para crear, editar y desactivar usuarios
   - Visualización de historial de login

3. **`docs/MULTIUSUARIO_IMPLEMENTADO.md`** (este archivo)
   - Documentación completa del sistema

### Archivos Modificados

1. **`app.py`**
   - Integración de pantalla de login
   - Navegación con opciones admin condicionales
   - Widget de información de usuario en sidebar
   - Verificación de sesión en cada carga

2. **`main/main_kpi.py`**
   - Restricción de análisis IA según rol
   - Import de `get_current_user()`

3. **`main/ytd_lineas.py`**
   - Restricción de exportaciones según rol
   - Restricción de análisis IA según rol

4. **`main/kpi_cpc.py`**
   - Restricción de exportaciones según rol
   - Restricción de análisis IA según rol
   - Restricción de cartas de cobranza según rol

5. **`main/heatmap_ventas.py`**
   - Restricción de exportaciones según rol

6. **`main/vendedores_cxc.py`**
   - Restricción de exportaciones según rol

7. **`main/reporte_consolidado.py`**
   - Restricción de análisis IA según rol

## 🔐 Base de Datos de Usuarios

### Ubicación
`data/users.db` (SQLite)

### Tablas

#### `users`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| username | TEXT PRIMARY KEY | Nombre de usuario único |
| password_hash | TEXT | Hash bcrypt de la contraseña |
| role | TEXT | admin, analyst, viewer |
| email | TEXT | Email del usuario |
| active | INTEGER | 1 = activo, 0 = desactivado |
| created_at | TEXT | Timestamp de creación |

#### `login_history`
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | INTEGER PRIMARY KEY | ID autoincremental |
| username | TEXT | Usuario que hizo login |
| login_time | TEXT | Timestamp del login |

### Usuario por Defecto
- **Username:** `admin`
- **Password:** `admin123`
- **Rol:** admin
- **Estado:** activo

⚠️ **IMPORTANTE:** Cambiar la contraseña del admin en producción

## 🔒 Funcionalidades de Autenticación

### Login
1. Usuario ingresa username y password
2. Sistema valida credenciales con bcrypt
3. Verifica que el usuario esté activo
4. Crea objeto `User` en `st.session_state['user']`
5. Registra login en `login_history`

### Logout
1. Usuario hace clic en botón "Cerrar Sesión"
2. Se elimina `st.session_state['user']`
3. Se recarga la aplicación mostrando pantalla de login

### Gestión de Sesión
- La sesión persiste mientras el navegador está abierto
- Cada recarga verifica `st.session_state['user']`
- No hay timeout automático (puede implementarse)

## 🛡️ Restricciones por Rol

### Exportaciones (requiere can_export = True)
**Módulos afectados:**
- YTD por Líneas (Excel + CSV)
- KPI CxC (Excel + Cartas de cobranza)
- Heatmap Ventas (Excel)
- Vendedores + CxC (CSV)

**Roles con acceso:** Admin, Analyst  
**Comportamiento:** Si el usuario no tiene permiso, se muestra mensaje de restricción

### Análisis con IA (requiere can_use_ai = True)
**Módulos afectados:**
- KPIs Generales
- YTD por Líneas
- KPI CxC
- Reporte Consolidado

**Roles con acceso:** Admin, Analyst  
**Comportamiento:** Si el usuario no tiene permiso, se muestra mensaje de restricción

### Gestión de Usuarios (requiere can_manage_users = True)
**Módulos afectados:**
- Panel de Gestión de Usuarios
- Panel de Configuración

**Roles con acceso:** Solo Admin  
**Comportamiento:** Opciones solo aparecen en menú si es admin

## 🎨 Interfaz de Usuario

### Pantalla de Login
```
┌─────────────────────────────┐
│    🔐 Inicio de Sesión      │
│                             │
│  Usuario: [___________]     │
│  Contraseña: [_______]      │
│                             │
│  [ Iniciar Sesión ]         │
│                             │
│  ❌ Usuario o contraseña    │
│     incorrectos (si error)  │
└─────────────────────────────┘
```

### Widget de Usuario (Sidebar)
```
┌─────────────────────────────┐
│  👤 admin                    │
│  🎖️ Admin                    │
│  [ Cerrar Sesión ]          │
└─────────────────────────────┘
```

### Menú de Navegación (Admin)
```
🧭 Navegación
○ 🎯 Reporte Ejecutivo
○ 📊 Reporte Consolidado
○ 📈 KPIs Generales
○ 📊 Comparativo Año vs Año
○ 📉 YTD por Línea de Negocio
○ 🔥 Heatmap Ventas
○ 💳 KPI Cartera CxC
○ 👥 Vendedores + CxC
───
○ ⚙️ Gestión de Usuarios
○ 🔧 Configuración
```

### Panel de Gestión de Usuarios (Solo Admin)

#### Tab 1: Lista de Usuarios
- Tabla con todos los usuarios
- Columnas: Usuario, Rol, Email, Estado, Último Login
- Botones: Resetear Password, Desactivar/Activar
- Indicadores visuales de estado

#### Tab 2: Crear Usuario
- Formulario con campos:
  - Username (mín 3 caracteres)
  - Password (mín 6 caracteres)
  - Email (validación de formato)
  - Rol (selector: Admin/Analyst/Viewer)
- Validación en tiempo real
- Mensajes de éxito/error

#### Tab 3: Historial de Accesos
- Tabla con últimos 50 logins
- Columnas: Usuario, Timestamp, Rol
- Estadísticas: Total logins por usuario

## 📊 Métricas del Sistema

### Archivos Modificados: 9
- 2 archivos nuevos en `utils/`
- 1 archivo nuevo en `docs/`
- 6 módulos principales actualizados

### Líneas de Código Agregadas: ~1,500+
- `utils/auth.py`: 550 líneas
- `utils/admin_panel.py`: 450 líneas
- Restricciones en módulos: ~500 líneas

### Roles Protegidos: 3
- Admin (acceso completo)
- Analyst (exportar + IA)
- Viewer (solo visualización)

### Funciones Protegidas: 2
- Exportaciones (8 puntos de restricción)
- Análisis IA (6 puntos de restricción)

## 🧪 Testing

### Escenarios de Prueba Pendientes

1. **Login como Admin**
   - Verificar acceso a todos los módulos
   - Verificar panel de gestión de usuarios visible
   - Verificar exportaciones funcionan
   - Verificar análisis IA funciona

2. **Login como Analyst**
   - Verificar acceso a todos los módulos de análisis
   - Verificar panel de gestión NO visible
   - Verificar exportaciones funcionan
   - Verificar análisis IA funciona

3. **Login como Viewer**
   - Verificar acceso a todos los módulos de visualización
   - Verificar panel de gestión NO visible
   - Verificar exportaciones bloqueadas (mensaje de restricción)
   - Verificar análisis IA bloqueado (mensaje de restricción)

4. **Gestión de Usuarios (Admin)**
   - Crear nuevo usuario
   - Resetear contraseña
   - Desactivar usuario
   - Reactivar usuario
   - Ver historial de accesos

5. **Seguridad**
   - Intentar login con credenciales incorrectas
   - Intentar acceder con usuario desactivado
   - Verificar contraseñas hasheadas con bcrypt
   - Verificar sesión persiste entre recargas

## 🚀 Próximos Pasos

### Inmediato (debe completarse antes de lanzar)
- [ ] Testing manual de todos los roles
- [ ] Cambiar contraseña del usuario admin por defecto
- [ ] Documentar proceso de creación de usuarios inicial
- [ ] Agregar usuario de prueba para cada rol

### Corto Plazo (post-lanzamiento)
- [ ] Implementar timeout de sesión (15-30 min de inactividad)
- [ ] Agregar campo "Nombre completo" a usuarios
- [ ] Agregar filtro de fecha en historial de accesos
- [ ] Implementar paginación en tabla de usuarios
- [ ] Agregar logs de acciones (quién modificó qué)

### Medio Plazo (optimizaciones)
- [ ] Migrar a PostgreSQL (de SQLite)
- [ ] Implementar 2FA (autenticación de dos factores)
- [ ] Agregar recuperación de contraseña por email
- [ ] Implementar permisos granulares por módulo
- [ ] Dashboard de actividad de usuarios (admin)

### Largo Plazo (expansión)
- [ ] Integración con SSO (Google, Microsoft)
- [ ] API REST para gestión de usuarios
- [ ] Multi-tenancy (múltiples organizaciones)
- [ ] Auditoría completa de acciones

## 📝 Notas Técnicas

### Seguridad
- Contraseñas hasheadas con bcrypt (salt automático)
- Sesiones manejadas por Streamlit session_state
- Base de datos SQLite con permisos de archivo 644
- No se almacenan contraseñas en texto plano

### Performance
- Consultas a base de datos optimizadas con índices
- Caché de usuario en session_state (no re-query en cada render)
- Login history limitado a últimos 50 registros por defecto

### Compatibilidad
- Python 3.8+
- Streamlit 1.20+
- bcrypt 4.0+
- SQLite3 (builtin en Python)

### Arquitectura
- Patrón MVC (Model-View-Controller)
- Separación de concerns (auth, UI, business logic)
- Decoradores para protección de funciones (@require_auth, @require_role)
- Dataclasses para representación de datos (User)

## ❓ FAQ

**P: ¿Cómo crear el primer usuario admin?**  
R: El sistema crea automáticamente un usuario `admin/admin123` al inicializar la base de datos. Cambiar contraseña inmediatamente.

**P: ¿Puedo tener más de un admin?**  
R: Sí. El admin puede crear múltiples usuarios con rol admin desde el panel de gestión.

**P: ¿Qué pasa si olvido la contraseña del admin?**  
R: Un admin puede resetear la contraseña de cualquier usuario. Si pierdes acceso de todos los admins, puedes eliminar `data/users.db` para recrear el admin por defecto.

**P: ¿Los usuarios pueden cambiar su propia contraseña?**  
R: No implementado aún. Actualmente solo los admins pueden resetear contraseñas. Próxima mejora.

**P: ¿Hay límite de usuarios?**  
R: No. SQLite soporta millones de registros, aunque para >100 usuarios se recomienda migrar a PostgreSQL.

**P: ¿Puedo desactivar la autenticación?**  
R: No recomendado, pero puedes comentar la verificación de sesión en `app.py` (líneas 50-80).

**P: ¿Los datos están cifrados?**  
R: Las contraseñas sí (bcrypt). Los datos del dashboard siguen siendo procesados en memoria (no persisten). Para cifrado completo, implementar TDE (Transparent Data Encryption) en la base de datos.

## 📚 Referencias

- [Documentación bcrypt](https://pypi.org/project/bcrypt/)
- [Streamlit Session State](https://docs.streamlit.io/library/api-reference/session-state)
- [SQLite Python](https://docs.python.org/3/library/sqlite3.html)
- [Role-Based Access Control (RBAC)](https://en.wikipedia.org/wiki/Role-based_access_control)

---

**Última actualización:** 2026-02-10  
**Versión:** 1.0  
**Autor:** Fradma Development Team

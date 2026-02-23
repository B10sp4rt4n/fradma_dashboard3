# ✅ Checklist de Testing - Sistema Multi-Usuario

## 🎯 Objetivo

Verificar que todas las funcionalidades del sistema multi-usuario funcionen correctamente antes del lanzamiento a producción.

---

## 📋 FASE 1: Testing de Autenticación

### 1.1 Login Exitoso
- [ ] Login con `admin/admin123` funciona
- [ ] Sesión se crea correctamente (`st.session_state['user']` existe)
- [ ] Widget de usuario aparece en sidebar
- [ ] Rol se muestra correctamente (badge verde "Admin")
- [ ] Login se registra en `login_history`

### 1.2 Login Fallido
- [ ] Usuario inexistente muestra error
- [ ] Contraseña incorrecta muestra error
- [ ] Mensaje de error es claro y no revela información sensible
- [ ] No se crea sesión si falla autenticación

### 1.3 Usuario Inactivo
- [ ] Crear usuario y desactivarlo
- [ ] Intentar login con usuario desactivado
- [ ] Verificar mensaje de error apropiado
- [ ] No se permite acceso

### 1.4 Logout
- [ ] Botón "Cerrar Sesión" aparece en sidebar
- [ ] Al hacer clic, sesión se elimina
- [ ] App recarga y muestra pantalla de login
- [ ] Recargar página manual requiere login nuevamente

---

## 📋 FASE 2: Testing de Roles - Admin

### 2.1 Navegación Admin
- [ ] Menú muestra todos los módulos estándar
- [ ] Menú muestra separador "---"
- [ ] Menú muestra "⚙️ Gestión de Usuarios"
- [ ] Menú muestra "🔧 Configuración"
- [ ] Badge en sidebar muestra "🎖️ Admin" en verde

### 2.2 Gestión de Usuarios
- [ ] Accede a "⚙️ Gestión de Usuarios"
- [ ] Pestaña "Lista de Usuarios" visible
- [ ] Pestaña "Crear Usuario" visible
- [ ] Pestaña "Historial de Accesos" visible

#### Crear Usuario
- [ ] Formulario aparece correctamente
- [ ] Validación username < 3 chars muestra error
- [ ] Validación password < 6 chars muestra error
- [ ] Validación passwords no coinciden muestra error
- [ ] Validación email inválido muestra error
- [ ] Crear usuario exitoso muestra mensaje verde
- [ ] Usuario aparece en lista inmediatamente
- [ ] Username duplicado muestra error

#### Lista de Usuarios
- [ ] Tabla muestra todos los usuarios
- [ ] Columnas: Usuario, Rol, Email, Estado, Último Login
- [ ] Estados muestran badges (Activo: verde, Inactivo: rojo)
- [ ] Botones "Resetear Password" y "Desactivar" aparecen

#### Resetear Password
- [ ] Clic en "Resetear Password" abre modal
- [ ] Formulario pide nueva password
- [ ] Validación password < 6 chars funciona
- [ ] Reset exitoso muestra mensaje
- [ ] Puede hacer login con nueva password

#### Desactivar/Activar Usuario
- [ ] Clic en "Desactivar" cambia estado a Inactivo
- [ ] Badge cambia a rojo
- [ ] Usuario no puede hacer login
- [ ] Clic en "Activar" restaura estado Activo
- [ ] Badge cambia a verde
- [ ] Usuario puede hacer login nuevamente

#### Historial de Accesos
- [ ] Tabla muestra últimos logins
- [ ] Columnas: Usuario, Timestamp, Rol
- [ ] Timestamps son recientes y correctos
- [ ] Estadísticas por usuario son correctas

### 2.3 Exportaciones (Admin)
- [ ] **YTD Líneas:** Botón "Descargar Excel" visible y funciona
- [ ] **YTD Líneas:** Botón "Descargar CSV" visible y funciona
- [ ] **KPI CxC:** Botón "Descargar Reporte Excel" visible y funciona
- [ ] **KPI CxC:** Botón "Descargar Carta" visible y funciona
- [ ] **Heatmap:** Botón "Descargar Excel" visible y funciona
- [ ] **Vendedores+CxC:** Botón "Descargar CSV" visible y funciona
- [ ] Archivos descargados contienen datos correctos

### 2.4 Análisis IA (Admin con API key)
- [ ] Configurar OpenAI API Key en sidebar
- [ ] **KPIs Generales:** Sección IA visible
- [ ] **KPIs Generales:** Botón "Generar Análisis" funciona
- [ ] **YTD Líneas:** Sección IA visible y funciona
- [ ] **KPI CxC:** Sección IA visible y funciona
- [ ] **Reporte Consolidado:** Sección IA visible y funciona
- [ ] Insights generados son coherentes y relevantes

---

## 📋 FASE 3: Testing de Roles - Analyst

### 3.1 Crear Usuario Analyst
- [ ] Login como admin
- [ ] Crear usuario con rol "Analyst"
- [ ] Logout y login con nuevo usuario Analyst

### 3.2 Navegación Analyst
- [ ] Menú muestra todos los módulos estándar
- [ ] Menú **NO** muestra "⚙️ Gestión de Usuarios"
- [ ] Menú **NO** muestra "🔧 Configuración"
- [ ] Badge en sidebar muestra "📊 Analyst" en azul

### 3.3 Acceso Denegado (Analyst)
- [ ] Intentar acceder directamente a URL de gestión
- [ ] Verificar mensaje de error "No tienes permisos"
- [ ] No puede ver panel de gestión de usuarios

### 3.4 Exportaciones (Analyst)
- [ ] **YTD Líneas:** Botón "Descargar Excel" visible y funciona
- [ ] **YTD Líneas:** Botón "Descargar CSV" visible y funciona
- [ ] **KPI CxC:** Botón "Descargar Reporte Excel" visible y funciona
- [ ] **KPI CxC:** Botón "Descargar Carta" visible y funciona
- [ ] **Heatmap:** Botón "Descargar Excel" visible y funciona
- [ ] **Vendedores+CxC:** Botón "Descargar CSV" visible y funciona

### 3.5 Análisis IA (Analyst con API key)
- [ ] Configurar OpenAI API Key en sidebar
- [ ] **KPIs Generales:** Sección IA visible y funciona
- [ ] **YTD Líneas:** Sección IA visible y funciona
- [ ] **KPI CxC:** Sección IA visible y funciona
- [ ] **Reporte Consolidado:** Sección IA visible y funciona

---

## 📋 FASE 4: Testing de Roles - Viewer

### 4.1 Crear Usuario Viewer
- [ ] Login como admin
- [ ] Crear usuario con rol "Viewer"
- [ ] Logout y login con nuevo usuario Viewer

### 4.2 Navegación Viewer
- [ ] Menú muestra todos los módulos estándar de visualización
- [ ] Menú **NO** muestra "⚙️ Gestión de Usuarios"
- [ ] Menú **NO** muestra "🔧 Configuración"
- [ ] Badge en sidebar muestra "👁️ Viewer" en gris

### 4.3 Acceso Denegado (Viewer)
- [ ] Intentar acceder a gestión de usuarios
- [ ] Verificar mensaje "No tienes permisos"

### 4.4 Exportaciones Bloqueadas (Viewer)
- [ ] **YTD Líneas:** Botón export **NO** visible
- [ ] **YTD Líneas:** Mensaje restricción aparece
- [ ] **KPI CxC:** Botones export **NO** visibles
- [ ] **KPI CxC:** Mensaje restricción aparece
- [ ] **Heatmap:** Botón export **NO** visible
- [ ] **Heatmap:** Mensaje restricción aparece
- [ ] **Vendedores+CxC:** Botón export **NO** visible
- [ ] **Vendedores+CxC:** Mensaje restricción aparece

### 4.5 Análisis IA Bloqueado (Viewer)
- [ ] **KPIs Generales:** Sección IA **NO** visible
- [ ] **KPIs Generales:** Mensaje restricción aparece
- [ ] **YTD Líneas:** Sección IA **NO** visible
- [ ] **YTD Líneas:** Mensaje restricción aparece
- [ ] **KPI CxC:** Sección IA **NO** visible
- [ ] **KPI CxC:** Mensaje restricción aparece
- [ ] **Reporte Consolidado:** Sección IA **NO** visible
- [ ] **Reporte Consolidado:** Mensaje restricción aparece

### 4.6 Visualizaciones (Viewer)
- [ ] Puede ver dashboard "Reporte Ejecutivo"
- [ ] Puede ver dashboard "Reporte Consolidado"
- [ ] Puede ver dashboard "KPIs Generales"
- [ ] Puede ver dashboard "Comparativo Año vs Año"
- [ ] Puede ver dashboard "YTD por Líneas"
- [ ] Puede ver dashboard "Heatmap Ventas"
- [ ] Puede ver dashboard "KPI CxC"
- [ ] Puede ver dashboard "Vendedores + CxC"
- [ ] Todos los gráficos cargan correctamente
- [ ] Todos los filtros funcionan correctamente

---

## 📋 FASE 5: Testing de Seguridad

### 5.1 Hashing de Contraseñas
- [ ] Abrir `data/users.db` con SQLite browser
- [ ] Ver tabla `users`
- [ ] Verificar columna `password_hash` contiene texto ilegible
- [ ] Verificar NO contiene contraseñas en texto plano
- [ ] Verificar hash tiene prefijo `$2b$` (bcrypt)

### 5.2 Sesiones
- [ ] Login exitoso
- [ ] Recargar página → sesión persiste
- [ ] Cerrar navegador y reabrir → requiere nuevo login
- [ ] Logout → sesión se elimina inmediatamente

### 5.3 Inyección SQL
- [ ] Intentar login con username: `admin' OR '1'='1`
- [ ] Verificar que NO permite acceso (protección activa)

### 5.4 Historial de Login
- [ ] Login 5 veces con usuarios diferentes
- [ ] Verificar historial registra todos los logins
- [ ] Verificar timestamps son precisos
- [ ] Verificar no se registran passwords

---

## 📋 FASE 6: Testing de UI/UX

### 6.1 Pantalla de Login
- [ ] Diseño es limpio y profesional
- [ ] Campos de input son claros
- [ ] Botón "Iniciar Sesión" es llamativo
- [ ] Mensajes de error son amigables
- [ ] Responsive en diferentes tamaños de pantalla

### 6.2 Widget de Usuario
- [ ] Aparece en sidebar superior
- [ ] Username se muestra claramente
- [ ] Badge de rol tiene color apropiado:
  - Admin: verde 🟢
  - Analyst: azul 🔵
  - Viewer: gris ⚫
- [ ] Botón "Cerrar Sesión" es visible

### 6.3 Panel de Gestión
- [ ] Tabs se muestran correctamente
- [ ] Formularios son intuitivos
- [ ] Validaciones muestran mensajes claros
- [ ] Botones tienen iconos apropiados
- [ ] Tablas son legibles

### 6.4 Mensajes de Restricción
- [ ] Mensajes warning (⚠️) son amarillos
- [ ] Mensajes info (💡) son azules
- [ ] Texto es claro y accionable
- [ ] Incluyen sugerencia de contactar admin

---

## 📋 FASE 7: Testing de Performance

### 7.1 Tiempo de Login
- [ ] Login tarda < 1 segundo
- [ ] No hay delays perceptibles

### 7.2 Carga de Usuarios
- [ ] Lista de usuarios carga rápidamente
- [ ] Historial de accesos carga rápidamente

### 7.3 Verificación de Permisos
- [ ] No hay delays al verificar permisos
- [ ] Restricciones se aplican instantáneamente

---

## 📋 FASE 8: Testing de Datos

### 8.1 Base de Datos
- [ ] Archivo `data/users.db` existe
- [ ] Tamaño del archivo es razonable (< 1MB para <100 usuarios)
- [ ] Tabla `users` contiene datos correctos
- [ ] Tabla `login_history` registra eventos

### 8.2 Integridad de Datos
- [ ] Crear 10 usuarios
- [ ] Verificar todos aparecen en lista
- [ ] Verificar datos coinciden con lo ingresado
- [ ] Desactivar 3 usuarios
- [ ] Verificar estado persiste después de recargar

### 8.3 Backup y Restauración
- [ ] Copiar `data/users.db` a backup
- [ ] Eliminar `users.db`
- [ ] App crea nuevo `users.db` con admin default
- [ ] Restaurar backup
- [ ] Verificar usuarios restaurados funcionan

---

## 📋 FASE 9: Testing de Edge Cases

### 9.1 Concurrencia
- [ ] Abrir 2 navegadores con mismo usuario
- [ ] Ambas sesiones funcionan independientemente
- [ ] Logout en una no afecta la otra

### 9.2 Campos Vacíos
- [ ] Intentar crear usuario sin username
- [ ] Intentar crear usuario sin password
- [ ] Intentar crear usuario sin email
- [ ] Verificar validaciones previenen creación

### 9.3 Caracteres Especiales
- [ ] Crear usuario con username: `juan.perez@empresa`
- [ ] Crear usuario con password: `P@ssw0rd!2024`
- [ ] Verificar funcionan correctamente

### 9.4 Límites
- [ ] Crear usuario con username de 50 caracteres
- [ ] Crear usuario con password de 100 caracteres
- [ ] Verificar no hay errores

---

## 📋 FASE 10: Testing de Documentación

### 10.1 Archivos de Docs
- [ ] `docs/MULTIUSUARIO_IMPLEMENTADO.md` existe
- [ ] `docs/GUIA_USUARIO_MULTIUSUARIO.md` existe
- [ ] `docs/TESTING_MULTIUSUARIO.md` existe (este archivo)

### 10.2 Completitud
- [ ] Documentación técnica cubre arquitectura
- [ ] Guía de usuario explica todos los roles
- [ ] Checklist de testing es completo
- [ ] Hay ejemplos y screenshots (si aplica)

---

## 📋 RESUMEN DE RESULTADOS

### Estadísticas

- **Total de tests:** 150+
- **Tests pasados:** _____ / 150
- **Tests fallidos:** _____ / 150
- **Tasa de éxito:** _____ %

### Issues Encontrados

| # | Descripción | Severidad | Estado |
|---|-------------|-----------|--------|
| 1 |             | Alta/Media/Baja | Pendiente/Resuelto |
| 2 |             | Alta/Media/Baja | Pendiente/Resuelto |
| 3 |             | Alta/Media/Baja | Pendiente/Resuelto |

### Notas de Testing

```
Fecha: __________
Tester: __________
Ambiente: Desarrollo / Staging / Producción
Navegador: Chrome / Firefox / Safari / Edge
OS: Windows / macOS / Linux

Comentarios adicionales:
_________________________________
_________________________________
_________________________________
```

---

## ✅ Checklist de Pre-Lanzamiento

Antes de lanzar a producción, verificar:

- [ ] Todos los tests críticos pasaron (100%)
- [ ] Usuario admin default tiene password cambiada
- [ ] Base de datos tiene backup
- [ ] Documentación está actualizada
- [ ] Se crearon al menos 3 usuarios de prueba (1 por rol)
- [ ] Se testeó en múltiples navegadores
- [ ] Performance es aceptable (<2s cargas)
- [ ] No hay mensajes de error en consola del navegador
- [ ] Logs de errores están configurados
- [ ] Se comunicó a usuarios finales sobre nuevo sistema

---

**Fecha de creación:** 2026-02-10  
**Versión:** 1.0  
**Próxima revisión:** Post-lanzamiento (1 semana después)

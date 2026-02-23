# 👤 Guía Rápida de Usuario - Sistema Multi-Usuario

## 🔐 Inicio de Sesión

### Primera Vez (Administradores)
1. **Accede a la aplicación** en tu navegador
2. Verás la pantalla de login
3. Ingresa las credenciales predeterminadas:
   - **Usuario:** `admin`
   - **Contraseña:** `admin123`
4. Haz clic en "Iniciar Sesión"

⚠️ **IMPORTANTE:** Cambia la contraseña del admin inmediatamente después del primer login.

### Usuarios Regulares
1. Solicita credenciales al administrador del sistema
2. Ingresa tu usuario y contraseña
3. Haz clic en "Iniciar Sesión"

## 👥 Tipos de Usuario

### 👑 Administrador (Admin)
**Puede hacer:**
- ✅ Ver todos los reportes y dashboards
- ✅ Exportar datos a Excel/CSV
- ✅ Usar análisis con Inteligencia Artificial
- ✅ Crear, modificar y eliminar usuarios
- ✅ Configurar parámetros del sistema

### 📊 Analista (Analyst)
**Puede hacer:**
- ✅ Ver todos los reportes y dashboards
- ✅ Exportar datos a Excel/CSV
- ✅ Usar análisis con Inteligencia Artificial
- ❌ No puede gestionar usuarios
- ❌ No puede modificar configuración

### 👁️ Visualizador (Viewer)
**Puede hacer:**
- ✅ Ver todos los reportes y dashboards
- ❌ No puede exportar datos
- ❌ No puede usar análisis con IA
- ❌ No puede gestionar usuarios
- ❌ No puede modificar configuración

## 🎯 Funcionalidades por Rol

| Funcionalidad | Admin | Analyst | Viewer |
|--------------|-------|---------|--------|
| Ver dashboards | ✅ | ✅ | ✅ |
| Exportar Excel/CSV | ✅ | ✅ | ❌ |
| Análisis con IA | ✅ | ✅ | ❌ |
| Gestión de usuarios | ✅ | ❌ | ❌ |
| Configuración sistema | ✅ | ❌ | ❌ |

## 📊 Módulos Disponibles

Todos los usuarios ven los siguientes módulos en el menú:

1. **🎯 Reporte Ejecutivo** - Vista consolidada para dirección
2. **📊 Reporte Consolidado** - Dashboard integral por período
3. **📈 KPIs Generales** - Análisis general de ventas
4. **📊 Comparativo Año vs Año** - Comparación interanual
5. **📉 YTD por Línea de Negocio** - Ventas acumuladas del año
6. **🔥 Heatmap Ventas** - Mapa de calor de ventas
7. **💳 KPI Cartera CxC** - Gestión de cuentas por cobrar
8. **👥 Vendedores + CxC** - Cruce ventas × cartera

### Módulos Exclusivos Admin

9. **⚙️ Gestión de Usuarios** - Administrar usuarios del sistema
10. **🔧 Configuración** - Ajustes del sistema

## 🔧 Gestión de Usuarios (Solo Admin)

### Crear Nuevo Usuario

1. En el menú lateral, selecciona **⚙️ Gestión de Usuarios**
2. Ve a la pestaña **"Crear Usuario"**
3. Completa el formulario:
   - **Nombre de usuario:** Mínimo 3 caracteres, sin espacios
   - **Contraseña:** Mínimo 6 caracteres
   - **Confirmar contraseña:** Repite la contraseña
   - **Email:** Email válido del usuario
   - **Rol:** Selecciona Admin, Analyst o Viewer
4. Haz clic en **"Crear Usuario"**
5. Comparte las credenciales con el usuario de forma segura

### Ver Usuarios Activos

1. En **⚙️ Gestión de Usuarios**, pestaña **"Lista de Usuarios"**
2. Verás una tabla con:
   - Usuario
   - Rol
   - Email
   - Estado (Activo/Inactivo)
   - Último Login

### Resetear Contraseña

1. En la lista de usuarios, localiza el usuario
2. Haz clic en **"Resetear Password"**
3. Ingresa la nueva contraseña (mín 6 caracteres)
4. Confirma la nueva contraseña
5. Haz clic en **"Resetear"**
6. Comunica la nueva contraseña al usuario

### Desactivar Usuario

1. En la lista de usuarios, localiza el usuario
2. Haz clic en **"Desactivar"**
3. El usuario no podrá iniciar sesión
4. Sus datos se mantienen en el sistema

### Reactivar Usuario

1. En la lista de usuarios, localiza el usuario inactivo
2. Haz clic en **"Activar"**
3. El usuario podrá volver a iniciar sesión

### Ver Historial de Accesos

1. En **⚙️ Gestión de Usuarios**, pestaña **"Historial de Accesos"**
2. Verás las últimas 50 sesiones iniciadas
3. Columnas: Usuario, Fecha y Hora, Rol

## 📥 Exportaciones (Admin y Analyst)

### Exportar Reportes a Excel

1. Navega al módulo deseado (ej: YTD por Línea de Negocio)
2. Configura los filtros según necesites
3. Desplázate hasta la sección **"📥 Exportar Reporte"**
4. Haz clic en **"📥 Descargar Excel"**
5. El archivo se descargará con la fecha actual

### Exportar Datos Crudos a CSV

1. En el módulo, busca la opción **"📊 Datos Brutos"**
2. Haz clic en **"📥 Descargar CSV"**
3. Obtendrás los datos filtrados en formato CSV

### Exportar Cartas de Cobranza (CxC)

1. En **💳 KPI Cartera CxC**, ve a **"📥 Exportación y Reportes"**
2. Sección **"📄 Plantillas de Cobranza"**
3. Selecciona el cliente
4. Genera la carta
5. Haz clic en **"📄 Descargar Carta (.txt)"**

## 🤖 Análisis con IA (Admin y Analyst)

### Activar IA Premium

1. En el menú lateral, busca **"🎯 IA Analytics Premium"**
2. Ingresa tu **OpenAI API Key** (necesitas cuenta OpenAI)
3. El sistema validará la clave
4. IA se activará para todas las vistas

### Usar Análisis con IA

1. Navega a cualquier módulo que soporte IA:
   - KPIs Generales
   - YTD por Líneas
   - KPI CxC
   - Reporte Consolidado
2. Configura filtros según tu análisis
3. Busca la sección **"🤖 Análisis con IA"**
4. Haz clic en **"🚀 Generar Análisis con IA"**
5. Espera unos segundos mientras la IA procesa
6. Revisa los insights generados

### Qué Hace la IA

- 🔍 **Identifica patrones** en tus datos
- 💡 **Genera insights** sobre tendencias
- ⚠️ **Detecta alertas** y riesgos
- 🎯 **Recomienda acciones** estratégicas
- 📊 **Analiza desempeño** de vendedores/clientes

## 🚪 Cerrar Sesión

1. En el menú lateral superior, verás tu nombre de usuario
2. Haz clic en el botón **"Cerrar Sesión"**
3. Serás redirigido a la pantalla de login
4. Tus datos de sesión se eliminan de forma segura

## ⚠️ Mensajes de Restricción

### "Solo usuarios Analyst o Admin pueden exportar"
- **Causa:** Eres viewer e intentas exportar datos
- **Solución:** Contacta al administrador para solicitar upgrade a Analyst

### "Solo usuarios Analyst o Admin pueden usar IA"
- **Causa:** Eres viewer e intentas usar análisis con IA
- **Solución:** Contacta al administrador para solicitar upgrade a Analyst

### "No tienes permisos para acceder a esta sección"
- **Causa:** Intentas acceder a Gestión de Usuarios sin ser Admin
- **Solución:** Solo administradores pueden gestionar usuarios

## 🔒 Seguridad y Buenas Prácticas

### Contraseñas Seguras

✅ **Hacer:**
- Usar mínimo 8 caracteres
- Combinar mayúsculas, minúsculas y números
- Agregar símbolos especiales (@, #, $, %)
- Cambiar contraseña cada 3 meses

❌ **NO hacer:**
- Usar contraseñas obvias (123456, password)
- Compartir tu contraseña con otros
- Usar la misma contraseña en múltiples sistemas
- Escribir contraseñas en notas/emails

### Protección de Datos

- 🔐 **No compartas tu sesión** - Cierra sesión cuando termines
- 📧 **No envíes credenciales por email sin cifrar**
- 💻 **Usa dispositivos confiables** - Evita computadoras públicas
- 🔄 **Reporta accesos sospechosos** al administrador

## ❓ Preguntas Frecuentes

**P: ¿Cómo cambio mi contraseña?**  
R: Actualmente solo los administradores pueden resetear contraseñas. Solicítalo a tu admin.

**P: ¿Qué hago si olvido mi contraseña?**  
R: Contacta al administrador del sistema para que resetee tu contraseña.

**P: ¿Puedo tener acceso para exportar solo algunos reportes?**  
R: No. Los permisos aplican a todo el sistema. Necesitas rol Analyst para exportar.

**P: ¿Cuánto tiempo dura mi sesión?**  
R: La sesión dura mientras mantengas el navegador abierto. No hay timeout automático.

**P: ¿Puedo usar el sistema desde mi celular?**  
R: Sí, pero la experiencia está optimizada para desktop. Algunos dashboards pueden ser difíciles de leer en móvil.

**P: ¿Los reportes generados con IA son 100% precisos?**  
R: Los insights de IA son sugerencias basadas en patrones. Siempre valida con criterio profesional.

**P: ¿Cuánto cuesta usar IA?**  
R: El sistema usa tu API key de OpenAI. Costos promedio: $0.01-0.05 USD por análisis.

## 🆘 Soporte

Si tienes problemas técnicos o preguntas sobre el sistema:

1. **Administrador del sistema:** Contacta al admin de tu organización
2. **Documentación técnica:** Ver `/docs/MULTIUSUARIO_IMPLEMENTADO.md`
3. **Issues conocidos:** Revisar archivo `README.md`

## 📚 Tutoriales Paso a Paso

### Tutorial 1: Primer Login como Admin

1. Abre el dashboard en tu navegador
2. En "Usuario" escribe: `admin`
3. En "Contraseña" escribe: `admin123`
4. Clic en "Iniciar Sesión"
5. Verás el dashboard principal
6. En el menú lateral, tu nombre aparece en verde: **🎖️ Admin**

### Tutorial 2: Crear tu Primer Usuario Analista

1. En el menú, selecciona **⚙️ Gestión de Usuarios**
2. Clic en pestaña **"Crear Usuario"**
3. Completa:
   - Usuario: `juan.perez`
   - Password: `Welcome2024!`
   - Confirmar: `Welcome2024!`
   - Email: `juan.perez@empresa.com`
   - Rol: **Analyst**
4. Clic en **"Crear Usuario"**
5. Mensaje de éxito ✅
6. Ve a pestaña "Lista de Usuarios" y verifica que aparece

### Tutorial 3: Exportar Reporte YTD (como Analyst)

1. Login con tu usuario Analyst
2. Selecciona **📉 YTD por Línea de Negocio**
3. Espera a que cargue el dashboard
4. Configura filtros si deseas (opcional)
5. Desplázate hasta **"📥 Exportar Reporte"**
6. Clic en **"📥 Descargar Excel"**
7. Archivo `Reporte_YTD_2026_20260210.xlsx` se descarga
8. Abre con Excel y revisa las múltiples hojas

### Tutorial 4: Generar Análisis con IA

1. Login como Admin o Analyst
2. En sidebar, configura tu OpenAI API Key
3. Selecciona **📈 KPIs Generales**
4. Dashboard carga con datos de ventas
5. Desplázate hasta **"🤖 Insights Estratégicos Premium"**
6. Clic en **"🚀 Generar Análisis con IA"**
7. Espera 5-10 segundos
8. Lee insights generados:
   - Patrones identificados
   - Recomendaciones de equipo
   - Oportunidades de mejora
   - Alertas estratégicas

---

**Última actualización:** 2026-02-10  
**Versión:** 1.0  
**Audiencia:** Usuarios finales del sistema

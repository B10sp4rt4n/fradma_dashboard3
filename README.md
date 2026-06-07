# Fradma Dashboard

[![Tests](https://img.shields.io/badge/tests-221%20passing-brightgreen)](./tests/)
[![Coverage](https://img.shields.io/badge/coverage-94.39%25-brightgreen)](./htmlcov/index.html)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)
[![Code Quality](https://img.shields.io/badge/code%20quality-A+-brightgreen)](#)
[![pytest](https://img.shields.io/badge/testing-pytest-blue)](https://docs.pytest.org/)

Plataforma de análisis comercial para FRADMA. Esta aplicación construida en Streamlit permite visualizar KPIs de ventas, comparar años históricos y evaluar el desempeño por línea de producto de manera interactiva.

## 🎯 Características

- 📊 **Dashboard CxC (Cuentas por Cobrar)**: Score de salud, semáforos de riesgo, antigüedad de saldos
- 📈 **KPIs Generales**: Métricas consolidadas de ventas y cobranza
- 📊 **Comparativo Año vs Año**: Análisis histórico de desempeño
- 🔥 **Heatmap de Ventas**: Visualización de tendencias por período

## 🚀 Inicio Rápido

### Instalación

```bash
git clone https://github.com/B10sp4rt4n/fradma_dashboard3.git
cd fradma_dashboard3
pip install -r requirements.txt
streamlit run app.py
```

### Desarrollo

```bash
# Instalar dependencias de desarrollo
pip install -r requirements-dev.txt

# Ejecutar tests
pytest

# Ver coverage
pytest --cov-report=html
open htmlcov/index.html
```

### Documentacion

```bash
# Levantar la documentacion localmente
mkdocs serve

# Regenerar el sitio estatico
mkdocs build
```

La carpeta `site/` es un artefacto generado por MkDocs y no se versiona en git.

## 📁 Estructura del Proyecto

```
fradma_dashboard3/
├── app.py                      # Entry point de la aplicación
├── requirements.txt            # Dependencias de producción
├── requirements-dev.txt        # Dependencias de desarrollo
├── pytest.ini                  # Configuración de tests
├── .gitignore
├── README.md
├── main/                       # Módulos principales
│   ├── kpi_cpc.py             # Dashboard CxC (1,385 líneas)
│   ├── reporte_ejecutivo.py   # Reporte ejecutivo
│   ├── heatmap_ventas.py      # Visualización de heatmaps
│   └── main_*.py              # Otros módulos
├── utils/                      # Utilidades reutilizables
│   ├── constantes.py          # Constantes centralizadas (100% coverage)
│   ├── formatos.py            # Formateo (100% coverage)
│   ├── ai_helper.py           # OpenAI integration (98.91% coverage)
│   ├── ai_helper_premium.py   # GPT-4o features (100% coverage)
│   ├── cxc_helper.py          # Helpers CxC (90.68% coverage)
│   ├── cxc_metricas_cliente.py # Métricas por cliente (91.67% coverage)
│   ├── data_normalizer.py     # Normalización (85.19% coverage)
│   └── data_cleaner.py        # Limpieza de datos
├── tests/                      # Suite de tests (221 tests)
│   ├── conftest.py            # 12 fixtures compartidos
│   ├── integration/
│   │   ├── test_kpi_cpc_core.py       # 25 tests
│   │   ├── test_pipeline_cxc.py       # 8 tests
│   │   └── test_formatos_integration.py  # 7 tests
│   └── unit/
│       ├── test_ai_helper.py          # 15 tests (OpenAI mocking)
│       ├── test_ai_helper_premium.py  # 8 tests
│       ├── test_cxc_helper.py         # 43 tests
│       ├── test_cxc_metricas_cliente.py  # 19 tests
│       ├── test_data_normalizer.py    # 14 tests
│       ├── test_data_normalizer_extended.py  # 15 tests
│       ├── test_formatos.py           # 36 tests
│       ├── test_vendedores_cxc.py     # 17 tests
│       └── test_ytd_lineas.py         # 16 tests
└── data/                       # Archivos de datos

```

## 🧪 Testing

**Coverage: 94.39%** ⭐ | **Tests: 221** ✅ | **Tiempo: 4.18s** ⚡

### Quick Start

```bash
# Ejecutar todos los tests
pytest

# Ver cobertura detallada
pytest --cov=utils --cov-report=term-missing

# Ver reporte HTML
pytest --cov=utils --cov-report=html
open htmlcov/index.html
```

### Estructura de Tests

- **221 tests totales** (100% passing)
- **40 tests de integración** (flujos completos)
- **181 tests unitarios** (funciones individuales)
- **3 módulos al 100% coverage** (formatos, ai_helper_premium, constantes)

### Coverage por Módulo (utils/)

| Módulo | Coverage | Tests |
|--------|----------|-------|
| `formatos.py` | 100% | 36 |
| `ai_helper_premium.py` | 100% | 8 |
| `constantes.py` | 100% | - |
| `ai_helper.py` | 98.91% | 15 |
| `cxc_metricas_cliente.py` | 91.67% | 19 |
| `cxc_helper.py` | 90.68% | 43 |
| `data_normalizer.py` | 85.19% | 29 |

### Documentación

- 📊 [TESTING_SUMMARY.md](TESTING_SUMMARY.md) - Resultados detallados
- 🧪 [TESTING_GUIDE.md](TESTING_GUIDE.md) - Guía para desarrolladores
- 🎭 **Estrategias:** Mocking de OpenAI, fixtures reutilizables, parametrización

### Comandos Útiles

```bash
# Tests específicos
pytest tests/unit/test_cxc_helper.py
pytest tests/integration/

# Debugging
pytest -v                      # Verbose
pytest -s                      # Ver prints
pytest -x                      # Parar en primer fallo

# Performance
pytest --durations=10          # Top 10 más lentos
```

Ver [TESTING_GUIDE.md](TESTING_GUIDE.md) para más detalles.
## 🔒 Seguridad de Sesión

> Variables configurables desde Railway → Settings → Variables.

El sistema de autenticación incluye dos protecciones de producción configurables desde variables de entorno.

### Bloqueo por intentos fallidos

Después de `MAX_LOGIN_ATTEMPTS` intentos fallidos consecutivos, la cuenta queda bloqueada temporalmente por `LOGIN_LOCKOUT_SECONDS` segundos.

- El mensaje de error es genérico: no revela si el usuario existe o no.
- El bloqueo se registra en la tabla `login_attempts` de Neon.
- Al expirar el bloqueo se restablece automáticamente.
- Un login exitoso limpia el contador de intentos.

### Expiración de sesión

Cada sesión tiene un TTL de `SESSION_TTL_SECONDS` segundos (8 horas por defecto).

- El timestamp de inicio se guarda en `st.session_state` al hacer login.
- En cada carga de la app se verifica si la sesión sigue vigente.
- Al expirar, la sesión se limpia completamente y se solicita login de nuevo.
- Los datos de empresa y CFDIs del tenant se eliminan de la sesión al cerrar.

### Variables configurables en Railway

| Variable | Default | Descripción |
|---|---|---|
| `MAX_LOGIN_ATTEMPTS` | `5` | Intentos antes de bloqueo |
| `SESSION_TTL_SECONDS` | `28800` | Duración de sesión (8 horas) |
| `LOGIN_LOCKOUT_SECONDS` | `900` | Duración del bloqueo (15 minutos) |
## 🚂 Deploy en Railway

### Prerequisitos

- Cuenta en [Railway.app](https://railway.app)
- Repositorio conectado a GitHub
- Variables de entorno listas (ver `.env.example`)

### 1. Crear proyecto en Railway

1. Ir a [railway.app/new](https://railway.app/new)
2. Elegir **Deploy from GitHub repo**
3. Seleccionar `fradma_dashboard3`
4. Railway detecta automáticamente el `Procfile` o el `Dockerfile`

### 2. Configurar variables de entorno

En **Settings → Variables**, agregar:

| Variable | Descripción | Requerida |
|---|---|---|
| `NEON_DATABASE_URL` | Cadena Neon: `postgresql://user:pass@host/db?sslmode=require` | ✅ |
| `OPENAI_API_KEY` | API key de OpenAI | Opcional |
| `PASSKEY_PREMIUM` | Clave para funciones premium — cambiar default `fradma2026` | Recomendada |
| `APP_ENV` | `production` | Recomendada |
| `LOG_LEVEL` | `INFO` · `WARNING` · `DEBUG` | Opcional |
| `GUIDED_CATALOG_SOURCE` | `json` · `db` | Opcional |
| `MAX_LOGIN_ATTEMPTS` | Intentos antes de bloqueo (default `5`) | Opcional |
| `SESSION_TTL_SECONDS` | Duración de sesión en seg (default `28800` = 8h) | Opcional |
| `LOGIN_LOCKOUT_SECONDS` | Duración del bloqueo en seg (default `900` = 15 min) | Opcional |

### 3. Confirmar comando de arranque

Railway lo toma del `Procfile`:

```
web: streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT --server.headless=true --server.enableCORS=false
```

Si prefieres Docker, Railway usa el `Dockerfile` automáticamente al detectarlo.

### 4. Primer deploy

Railway hace deploy automático al conectar el repo. Para forzar uno manual:

```
railway up
```

O desde la UI: **Deploy → Trigger Deploy**.

### 5. Ver logs

En la UI de Railway: **Deployments → seleccionar deploy → Logs**.

Para seguir logs en tiempo real desde CLI:

```bash
railway logs --follow
```

Señales de arranque exitoso en los logs:

```
[config] APP_ENV=production
[config] [OK] NEON_DATABASE_URL=postgre***
You can now view your Streamlit app in your browser.
```

### 6. Validar URL pública

Railway asigna automáticamente un dominio `*.railway.app`. Para dominio propio:
**Settings → Networking → Custom Domain**.

Checklist de validación post-deploy:

- [ ] Login de usuario funciona
- [ ] Datos CFDI cargan para al menos un tenant
- [ ] Módulo KPI CxC muestra datos
- [ ] Exportación a Excel genera archivo
- [ ] Asistente de datos responde (si hay `OPENAI_API_KEY`)
- [ ] No se ven datos de otro tenant al cambiar empresa

### 7. Revisar errores comunes

| Error en logs | Causa probable | Solución |
|---|---|---|
| `NEON_DATABASE_URL` faltante | Variable no cargada | Revisar Railway Variables |
| `ModuleNotFoundError` | Dependencia faltante | Verificar `requirements.txt` |
| `OSError: [Errno 98] Address in use` | Puerto ocupado | Railway asigna `$PORT` automáticamente |
| `SSL SYSCALL error` | Neon requiere SSL | Confirmar `?sslmode=require` en URL |
| Pantalla en blanco | Error de import silencioso | Ver logs de arranque completos |

### 8. Rollback

Para volver a un deploy anterior:

1. Railway UI → **Deployments**
2. Buscar el deploy estable anterior
3. Click en **Redeploy**

Desde CLI:

```bash
railway rollback
```

### Prueba local con el mismo patrón que Railway

```bash
# Instalar dependencias
pip install -r requirements.txt

# Correr exactamente como Railway (usar $PORT dinámico)
export NEON_DATABASE_URL="postgresql://..."
export OPENAI_API_KEY="sk-..."
PORT=8501 streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT --server.headless=true --server.enableCORS=false

# Smoke tests (sin threshold de coverage)
pytest tests/test_railway_smoke.py --no-cov -v

# Suite auth security
pytest tests/unit/test_auth_security.py --no-cov -v

# Suite auth legacy
pytest tests/unit/test_auth.py --no-cov -v
```

## �📊 Calidad del Código

**Score: 98/100** 🟢 Excelente

| Categoría | Score | Estado |
|-----------|-------|--------|
| Arquitectura | 95/100 | 🟢 |
| Mantenibilidad | 96/100 | 🟢 |
| Testing | 94/100 | 🟢 |
| Performance | 90/100 | 🟢 |
| Best Practices | 98/100 | 🟢 |

### Highlights

- ✅ **94.39% test coverage** en módulos utils/
- ✅ **3 módulos al 100%** (formatos, ai_helper_premium, constantes)
- ✅ **221 tests automatizados** (100% passing)
- ✅ **Mock completo de OpenAI** (0 llamadas reales)
- ✅ **Fixtures reutilizables** (12 fixtures en conftest.py)
- ✅ **4.18s execution time** (excelente performance)

Ver [.github-analysis.md](./.github-analysis.md) para análisis completo.

## 🤝 Contribuir

¿Quieres contribuir al proyecto? ¡Genial! Lee nuestra [Guía de Contribución](CONTRIBUTING.md).

### Proceso Rápido

1. **Fork** el repositorio
2. **Crea** una rama (`git checkout -b feature/amazing-feature`)
3. **Commit** tus cambios (`git commit -m 'feat: Add amazing feature'`)
4. **Push** a la rama (`git push origin feature/amazing-feature`)
5. **Abre** un Pull Request

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para detalles completos sobre:
- Configuración del entorno
- Estándares de código
- Guía de testing
- Proceso de PR

## 🔧 Tecnologías

- **Framework**: Streamlit 1.40+
- **Data**: Pandas, NumPy
- **Visualización**: Plotly, Matplotlib
- **Testing**: pytest, pytest-cov
- **Type Checking**: mypy
- **Python**: 3.11, 3.12

## 📝 Documentación Adicional

- [CONTRIBUTING.md](CONTRIBUTING.md) - Guía de contribución
- [docs/ARQUITECTURA_INTEGRACION_CRM_ERP.md](docs/ARQUITECTURA_INTEGRACION_CRM_ERP.md) - Arquitectura de integración para CRMs, ERPs y fuentes financieras
- [docs/MODELO_FISICO_INTEGRACION_CRM_ERP.md](docs/MODELO_FISICO_INTEGRACION_CRM_ERP.md) - Modelo físico sugerido con tablas, relaciones y marts analíticos
- [docs/FRAMEWORK_NL2SQL_GUIADO.md](docs/FRAMEWORK_NL2SQL_GUIADO.md) - Implementación del framework guiado en UI y CLI
- [REFACTOR_SUMMARY.md](REFACTOR_SUMMARY.md) - Resumen de refactorización
- [TESTING_SUMMARY.md](TESTING_SUMMARY.md) - Documentación de testing
- [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) - Resumen ejecutivo
- [.github-analysis.md](.github-analysis.md) - Análisis de calidad

## 📜 Licencia

Este proyecto es privado y confidencial.

## 👥 Autores

- [@B10sp4rt4n](https://github.com/B10sp4rt4n)

---

*Este proyecto está en fase de estructuración. Los datos reales o funciones sensibles no están incluidos en esta versión pública.*

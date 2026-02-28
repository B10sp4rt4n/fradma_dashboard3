# Roadmap de Mejoras - Fradma Dashboard V2

**Generado:** 2026-02-17  
**Base:** Evaluación arquitectural completa vs sistemas similares  
**Principio:** Infraestructura se mejora DESPUÉS de validar valor de negocio

---

## Estado Actual (V1.0)

- ✅ 11,079 líneas de código funcionales
- ✅ 35 KPIs calculados, 37 visualizaciones
- ✅ 5 funciones IA Premium (GPT-4o-mini)
- ✅ Sistema de passkey implementado
- ✅ 12 commits en feature/kpi-fixes (bugs corregidos + IA integrada)
- ⚠️ Cobertura tests: 49.5% (82 passed, 2 failed)
- ⚠️ En fase de validación con 1-2 testers

---

## Filosofía de Evolución

> **Excel como fuente NO es deuda técnica — es una decisión de fase deliberada.**  
> Permite:
> - Flexibilidad de fuente (cualquier ERP/CRM exporta Excel)
> - Desacoplamiento intencional (ingesta ≠ persistencia)
> - Zero-config para testers
> - Path claro a producción (cambiar `pd.read_excel()` → `pd.read_sql()`)

---

## Fase 1: Validación con Testers (AHORA)

**Objetivo:** Confirmar que KPIs e insights de IA son accionables y correctos.

### Checklist de Validación

- [ ] **YTD por Líneas** — Proyecciones y análisis ejecutivo IA son útiles
- [ ] **Dashboard CxC** — Score de salud + 5 métodos de fallback funcionan correctamente
- [ ] **KPIs Generales** — Insights de equipo de ventas aportan valor al gerente
- [ ] **Reporte Ejecutivo** — Visión CFO con correlaciones ventas-CxC es accionable
- [ ] **Reporte Consolidado** — Análisis por período detecta tendencias correctamente
- [ ] Validar que IA NO repite métricas ya visibles en dashboards
- [ ] Confirmar que semáforos y alertas tienen umbrales correctos para el negocio

**Entregable:** Lista de ajustes de negocio (cambiar umbrales, agregar/quitar KPIs, mejorar prompts IA)

---

## Fase 2: Estabilización (Post-Validación)

### P0 — Crítico (30-60 min total)

| # | Tarea | Impacto | Esfuerzo | Archivo | Estado |
|---|---|---|---|---|--------|
| 1 | Fijar versiones en `requirements.txt` | Builds reproducibles | 30 min | requirements.txt | ✅ COMPLETADO |
| 2 | Mover passkey a variable de entorno | Seguridad básica | 15 min | app.py | ✅ COMPLETADO |
| 3 | Corregir 2 tests rotos | CI confiable | 1 hora | tests/unit/test_cxc_helper.py | ✅ COMPLETADO |

**Output:** Branch `feature/mejoras-core` con commits atómicos  
**Fecha completado:** 2026-02-17  
**Commits:** `68792d3` (refactor: P0 tasks)

---

### P1 — Importante (1-2 días)

| # | Tarea | Impacto | Esfuerzo | Archivos | Estado |
|---|---|---|---|---|--------|
| 4 | GitHub Actions (lint + pytest) | Prevenir regresiones | 2 horas | .github/workflows/ci.yml | ✅ COMPLETADO |
| 5 | Refactor `kpi_cpc.py` en 5+ funciones | Mantenibilidad | 1 día | main/kpi_cpc.py | ❌ NO HACER |
| 6 | Eliminar duplicación `normalizar_columnas` y `excluir_pagados` | DRY principle | 2 horas | app.py, kpi_cpc.py, cxc_helper.py, data_normalizer.py | ✅ COMPLETADO |
| 7 | Agregar type hints a módulos main/ | Autocomplete + menos bugs | 3 horas | main/*.py | ⏳ PENDIENTE |

**Output P1 completado:** Código más limpio y CI pipeline básico ✅  
**Fecha:** 2026-02-17  
**Commits:** `68792d3` (duplicación), `cbe9a66` (CI/CD)  
**Tests agregados:** +14 tests para `normalizar_columnas()` → Coverage subió 48% → 53%

---

### P2 — Deseable (2-5 días)

| # | Tarea | Impacto | Esfuerzo | Archivos |
|---|---|---|---|---|
| 8 | Dockerfile multi-stage | Deploy consistente | 3 horas | Dockerfile, docker-compose.yml |
| 9 | Subir cobertura tests a 80% | Confiabilidad | 3-5 días | tests/ (+ 40 tests nuevos) |
| 10 | Cache persistente (SQLite local) | Performance con datasets grandes | 1 día | utils/cache_helper.py |
| 11 | Migrar a PostgreSQL (opcional) | Historización + auto-refresh | 2-3 días | app.py, utils/db_connector.py (nuevo) |

**Output:** Sistema production-ready sin multi-usuario

---

### P3 — Nice to Have (1-2 semanas)

| # | Tarea | Impacto | Esfuerzo | Archivos |
|---|---|---|---|---|
| 12 | Autenticación (Streamlit Auth) | Multi-usuario con roles | 2 días | app.py, utils/auth.py (nuevo) |
| 13 | API REST para exportar datos | Integración con otros sistemas | 3 días | api/ (nuevo) |
| 14 | Alertas por email/Slack | Notificaciones proactivas | 2 días | utils/notifications.py (nuevo) |
| 15 | Mobile responsive | Acceso desde tablet/móvil | 1 día | CSS custom en app.py |

**Output:** Sistema enterprise-ready

---

## Fase 3: Escalamiento (Futuro)

### Cuando llegues a >10 usuarios concurrentes o >1M filas

- [ ] Migrar a Streamlit Cloud / AWS ECS
- [ ] Implementar Redis para cache distribuido
- [ ] Separar compute (dashboard) de storage (DB)
- [ ] Agregar Celery para procesamiento asíncrono
- [ ] Implementar data warehouse (Snowflake/BigQuery)

---

## Backlog de Mejoras de Negocio

### Basado en evaluación vs competencia

| Módulo | Mejora Sugerida | Inspiración |
|---|---|---|
| **YTD por Líneas** | Agregar proyección con regresión lineal visual | Power BI "Forecasting" |
| **Dashboard CxC** | Mapa de calor de morosidad por vendedor × cliente | Tableau "Heat Map" |
| **KPIs Generales** | Comparativa vendedor vs promedio del equipo (spider chart) | ChartMogul "Benchmarks" |
| **Reporte Ejecutivo** | Agregar Cash Flow proyectado (ventas futuras - CxC vencida) | CFO Dashboard estándar |
| **Reporte Consolidado** | Breakdown de variación por factor (precio vs volumen vs mix) | Análisis de varianzas contable |
| **Nuevo módulo** | Dashboard de rentabilidad por cliente (si tienes costos) | SaaS LTV/CAC dashboards |

---

## Decisiones Arquitecturales Documentadas

### ¿Por qué Excel y no DB directa?

**Decisión:** Mantener Excel como fuente en V1 y V2 early.

**Razones:**
1. Flexibilidad — Cliente puede conectar cualquier ERP sin API custom
2. Testing — 1-2 testers no justifican infraestructura de BD
3. Desacoplamiento — Capa de ingesta independiente de persistencia
4. Path claro — Migrar a DB es cambiar 1 función, no reescribir la app

**Cuándo cambiar:** Cuando tengas >5 usuarios concurrentes O necesites historización.

---

### ¿Por qué passkey y no OAuth?

**Decisión:** Passkey simple para V1, mover a env var en P0.

**Razones:**
1. No hay multi-usuario en V1 → OAuth es overengineering
2. Costo/beneficio — OAuth toma 2 días vs 15 min el env var
3. El valor está en los KPIs, no en la autenticación (por ahora)

**Cuándo cambiar:** Cuando tengas >3 usuarios con roles diferentes.

---

### ¿Por qué monolito en kpi_cpc.py?

**Decisión:** ❌ NO refactorizar ahora (marcado como P1 #5 NO HACER).

**Razones:**
1. Si el módulo no aporta valor, no importa qué tan limpio esté
2. Testers primero validan funcionalidad, luego optimizamos código
3. 1 día de refactor es barato DESPUÉS de confirmar product-market fit
4. **RIESGO > BENEFICIO** en fase actual:
   - Sistema funciona correctamente (84→98 tests passing)
   - Es código de UI/presentación (Streamlit stateful), no lógica reutilizable
   - 1,600 líneas pero bien organizadas en 14 secciones con comentarios claros
   - Refactor podría romper flujo de `session_state` y cache

**Cuándo refactorizar:**
- Hay bugs recurrentes en secciones específicas
- Necesitas reutilizar secciones en otros reportes
- El performance es un problema real medido

**Fecha evaluado:** 2026-02-17  
**Análisis completo:** Ver sección "Hallazgos Confirmados" commit `68792d3`

**Plan:** Separar en `cxc_salud.py`, `cxc_alertas.py`, `cxc_antiguedad.py`, `cxc_agentes.py`, `cxc_export.py`.

---

## Métricas de Éxito (V2)

| Métrica | V1 Actual | V2 Target |
|---|---|---|
| Cobertura de tests | 49.5% | 80%+ |
| Tests rotos | 2 | 0 |
| Tiempo de deploy | Manual | <5 min (Docker) |
| Código duplicado | ~200 líneas | <50 líneas |
| Líneas por función (max) | 1,500 (kpi_cpc) | 200 |
| Tiene CI/CD | No | Sí (GitHub Actions) |
| Passkey hardcodeada | Sí | No (env var) |
| Tiempo de onboarding | N/A | <10 min (con Docker + README) |

---

## Estimación Total

| Fase | Esfuerzo | Cuándo |
|---|---|---|
| **Fase 1: Validación** | 1-2 semanas | AHORA |
| **Fase 2: P0** | 2 horas | Post-validación inmediato |
| **Fase 2: P1** | 2-3 días | Semana 1 post-validación |
| **Fase 2: P2** | 1-2 semanas | Mes 1 post-validación |
| **Fase 2: P3** | 2-3 semanas | Mes 2-3 (si hay demanda) |
| **Fase 3: Escalamiento** | 1-2 meses | Solo si >10 usuarios concurrentes |

---

## Notas de la Evaluación

**Fortalezas identificadas:**
- Lógica de CxC con 5 métodos de fallback (superior a Power BI genérico)
- IA Premium anti-repetición (no existe en ningún BI estándar)
- Score de Salud adaptado (fórmula propia ponderada)
- Zero-config (sube Excel → dashboard funcional)
- Costo: ~$5/mes vs $70/usuario/mes en Power BI

**Debilidades críticas resueltas:**
- ✅ Sistema Premium IA implementado (5/5 módulos)
- ✅ 21 tooltips + 4 paneles de definiciones
- ✅ Validación de columnas con COLUMNAS_REQUERIDAS.md
- ✅ Bugs de KPIs corregidos
- ✅ Tests rotos → 98/98 tests passing (2026-02-17)
- ✅ Passkey hardcodeada → Movida a env var (2026-02-17)
- ✅ Código duplicado eliminado (2026-02-17)
- ✅ CI/CD con GitHub Actions (2026-02-17)

**Posicionamiento:** Alta personalización + Baja madurez enterprise → ideal para 1-15 usuarios con datos en Excel, hasta validar product-market fit.

---

## Próximos Pasos Inmediatos

1. **Terminar validación con testers** (recopilar feedback sobre KPIs e IA)
2. Type hints en módulos main/ (P1 #7) - 3 horas
3. Subir cobertura tests a 70%+ (P2 #9) - Agregar tests para otras funciones utils/
4. Decidir sobre P2 (Dockerfile, PostgreSQL) según feedback de testers

---

## 📊 Progreso Actual (2026-02-17)

### ✅ Completado

**P0 - Crítico:**
- [x] Versiones fijadas en requirements.txt + requirements-dev.txt
- [x] Passkey a variable de entorno (.env con fallback)
- [x] Tests rotos corregidos (84 → 98 tests passing)

**P1 - Importante:**
- [x] GitHub Actions CI/CD actualizado
- [x] Duplicación `normalizar_columnas` eliminada
- [x] 14 tests nuevos para `normalizar_columnas()` (coverage +5%)
- [x] Badges README actualizados (coverage real 53%)

**Decisiones documentadas:**
- [x] ❌ NO refactorizar kpi_cpc.py (riesgo > beneficio)

### ⏳ Pendiente

**P1:**
- [ ] Type hints en main/ (3 hrs)

**P2:**
- [ ] Subir coverage a 80% (5 días)
- [ ] Dockerfile multi-stage (3 hrs)
- [ ] Cache persistente SQLite (1 día)

**P3:**
- [ ] Autenticación OAuth (2 días)
- [ ] API REST (3 días)
- [ ] Mobile responsive (1 día)

### 📈 Métricas de Progreso

| Métrica | Antes | Ahora | Objetivo P2 |
|---------|-------|-------|-------------|
| **Tests passing** | 84 | 98 | 120+ |
| **Coverage** | 48% | 53% | 80% |
| **Bugs P0** | 3 | 0 | 0 |
| **Código duplicado** | 2 funciones | 0 | 0 |
| **CI/CD** | Manual | Automático | Automático |
| **Versions fijadas** | No | Sí | Sí |
| **Seguridad passkey** | Hardcoded | Env var | OAuth (P3) |

---

*Documento vivo — actualizar conforme evoluciona el producto.*  
**Branch actual:** feature/mejoras-core  
**Listo para:** Merge a main

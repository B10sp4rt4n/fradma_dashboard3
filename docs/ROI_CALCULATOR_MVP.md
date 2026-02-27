# 💰 ROI Calculator MVP - Guía de Uso

**Fecha de implementación:** 27 Febrero 2026  
**Versión:** 1.0 (Fase 1 MVP)  
**Commit:** 041adcf

---

## 🎯 ¿Qué es?

El **ROI Calculator** es un sistema integrado que mide y muestra en tiempo real el **valor que genera cada usuario** al usar la plataforma Fradma Dashboard.

### Beneficios principales:

1. **Justificación de inversión:** Los usuarios ven cuánto ahorran en tiempo y dinero
2. **Reducción de churn:** Los usuarios entienden el valor antes de renovar
3. **Upselling natural:** Muestra el valor potencial con IA Premium
4. **Diferenciador único:** Ningún competidor (Power BI, Tableau, SAP) tiene esto
5. **Gamificación:** Los usuarios quieren ver el número crecer

---

## 🎨 Experiencia de Usuario

### 1. Widget en Sidebar (siempre visible)

Cada usuario ve en el sidebar izquierdo:

```
┌────────────────────────────────┐
│ 💰 Tu ROI ▼                    │
├────────────────────────────────┤
│                                │
│ ⏱️ Hoy                         │
│  2.5 hrs ahorradas             │
│  💵 $1,250                     │
│                                │
│ 📅 Este mes                    │
│  40 hrs  →  $20,000            │
│                                │
│ 📊 Este año                    │
│  360 hrs  →  $180,000          │
│                                │
│ ✨ 3 acción(es) hoy            │
└────────────────────────────────┘
```

### 2. Toast Notifications

Al completar cada acción, aparece una notificación:

```
┌─────────────────────────────────────────┐
│ ✨ Análisis CFDIs completado            │
│ 💰 Ahorraste 2.5 hrs = $1,250 MXN       │
└─────────────────────────────────────────┘
```

---

## 📊 ¿Cómo se calcula el ROI?

### Fórmula

```
Valor Generado = Horas Ahorradas × Costo por Hora del Usuario
```

### Benchmarks de Tiempo Ahorrado

| Acción | Tiempo Manual | Tiempo Fradma | Ahorro |
|--------|---------------|---------------|--------|
| Procesar 100 CFDIs | 5 hrs | 0.1 hrs | **4.9 hrs** |
| Generar Reporte Ejecutivo | 2 hrs | 0.1 hrs | **1.9 hrs** |
| Análisis CxC | 1.5 hrs | 0.1 hrs | **1.4 hrs** |
| Comparativo Año vs Año | 3 hrs | 0.2 hrs | **2.8 hrs** |
| Dashboard Vendedores | 2.5 hrs | 0.1 hrs | **2.4 hrs** |

### Costo por Hora (según rol)

| Rol | Costo/hora (MXN) |
|-----|------------------|
| CEO/Director (admin) | $5,000 |
| CFO | $3,000 |
| Gerente (manager) | $1,500 |
| Contador (accountant) | $500 |
| Analista (analyst) | $300 |
| Usuario estándar | $500 |

**Nota:** El sistema detecta automáticamente el rol del usuario logueado.

---

## 🔧 Módulos Integrados (Fase 1)

### 1. 📦 Ingesta de CFDIs

**Tracking:**
- Se activa al completar el procesamiento de XMLs
- Calcula ahorro según cantidad:
  - 10 CFDIs = 0.5 hrs ahorradas
  - 50 CFDIs = 2.0 hrs ahorradas
  - 100+ CFDIs = 4.9 hrs ahorradas

**Toast:**
```
✨ Análisis CFDIs completado
💰 Ahorraste 2.5 hrs = $1,250 MXN
```

---

### 2. 📊 Reporte Ejecutivo

**Tracking:**
- Se activa al generar el reporte
- Ahorro fijo: 1.9 hrs por reporte

**Toast:**
```
✨ Reporte Ejecutivo generado
💰 Ahorraste 1.9 hrs
```

---

### 3. 💳 KPI Cartera CxC

**Tracking:**
- Se activa al completar el análisis
- Ahorro fijo: 1.4 hrs por análisis

**Toast:**
```
✨ Análisis CxC completado
💰 Ahorraste 1.4 hrs
```

---

## 💡 Casos de Uso Reales

### Caso 1: Contador procesando CFDIs

**Escenario:**
- Rol: Contador ($500/hora)
- Acción: Procesa 250 CFDIs

**Cálculo:**
```
Cantidad: 250 CFDIs = 2.5× lote de 100
Tiempo ahorrado: 4.9 hrs × 2.5 = 12.25 hrs
Valor: 12.25 hrs × $500/hr = $6,125
```

**Resultado visible:**
- Widget se actualiza: "Hoy: 12.25 hrs | $6,125"
- Toast: "💰 Ahorraste 12.25 hrs = $6,125 MXN"

---

### Caso 2: CEO revisando números

**Escenario:**
- Rol: CEO ($5,000/hora)
- Acción: Genera Reporte Ejecutivo

**Cálculo:**
```
Tiempo ahorrado: 1.9 hrs
Valor: 1.9 hrs × $5,000/hr = $9,500
```

**Resultado visible:**
- Widget se actualiza: "Hoy: 1.9 hrs | $9,500"
- Toast: "✨ Reporte Ejecutivo generado · 💰 Ahorraste 1.9 hrs"

**Impacto:** CEO usa el reporte 20 veces al mes = **$190K/mes ahorrado**

---

### Caso 3: CFO analizando cartera

**Escenario:**
- Rol: CFO ($3,000/hora)
- Acción: Analiza CxC

**Cálculo:**
```
Tiempo ahorrado: 1.4 hrs
Valor: 1.4 hrs × $3,000/hr = $4,200
```

**Resultado visible:**
- Widget: "Hoy: 1.4 hrs | $4,200"
- Mes (si usa 2×/semana): 8 análisis × $4,200 = **$33,600/mes**

---

## 📈 Ejemplo de Acumulación

### Usuario típico (Analista - $300/hora)

| Período | Acciones | Horas | Valor |
|---------|----------|-------|-------|
| **Día 1** | 2 análisis CFDIs (100 cada uno) | 9.8 hrs | $2,940 |
| **Día 2** | 1 Reporte Ejecutivo | 1.9 hrs | $570 |
| **Día 3** | 1 Análisis CxC | 1.4 hrs | $420 |
| **Día 4** | 1 Comparativo Año × Año | 2.8 hrs | $840 |
| **Día 5** | 2 CFDIs (50 cada uno) | 4.0 hrs | $1,200 |
| **SEMANA** | 7 acciones | **19.9 hrs** | **$5,970** |
| **MES** | 28 acciones | **79.6 hrs** | **$23,880** |
| **AÑO** | 336 acciones | **955 hrs** | **$286K** |

**VS Costo Fradma:**
- Costo anual: $6,000
- Ahorro: $286,000
- **ROI: 4,666%**

---

## 🔮 Roadmap Futuro

### Fase 2: Persistencia (2-3 semanas)

**Objetivos:**
- Guardar histórico en base de datos PostgreSQL/Neon
- Módulo dedicado "📊 Dashboard ROI" completo
- Gráficas de evolución temporal
- Desagregación por módulo/usuario
- Exportación a PDF para CFO

**Vista previa Dashboard ROI:**
```
┌─────────────────────────────────────────────────────────────┐
│ 💰 TU ROI DASHBOARD                                        │
├─────────────────────────────────────────────────────────────┤
│                                                            │
│ RESUMEN EJECUTIVO                                          │
│ ┌────────────┬────────────┬────────────┬────────────┐     │
│ │ Este Mes   │ Este Año   │ Total      │ ROI        │     │
│ ├────────────┼────────────┼────────────┼────────────┤     │
│ │ $23,880    │ $286,000   │ $450,000   │ 4,666%     │     │
│ └────────────┴────────────┴────────────┴────────────┘     │
│                                                            │
│ AHORRO POR MÓDULO                                          │
│ [Gráfica de barras interactiva]                           │
│                                                            │
│ AHORRO POR USUARIO                                         │
│ [Tabla con ranking]                                        │
│                                                            │
│ RIESGOS EVITADOS (IA Premium)                             │
│ [Lista de alertas detectadas + valor evitado]             │
│                                                            │
│ [📥 Exportar PDF] [📧 Enviar a CFO]                       │
└─────────────────────────────────────────────────────────────┘
```

---

### Fase 3: Gamificación (mes 2)

**Features:**
- 🏆 Leaderboard por equipo
- 🎖️ Badges: "Time Saver Pro", "ROI Master", "Efficiency King"
- 🎯 Metas semanales personalizadas
- 🔔 Notificaciones: "¡Rompiste tu récord!"
- 📊 Comparativa vs promedio empresa

**Impacto esperado:** +40% engagement

---

### Fase 4: Predictivo (Q3 2026)

**Features con ML/IA:**
- 🔮 Proyección ROI próximo trimestre
- 💡 Recomendaciones: "Usa más módulo X para maximizar ROI"
- 📢 Alertas: "15 días sin usar CxC, pierdes $5K/mes"
- 📊 Benchmarking: "Empresas similares ahorran 30% más"

---

## 🚀 Ventaja Competitiva

### Comparativa de mercado

| Feature | Fradma | Power BI | Tableau | SAP Cloud | CONTPAQi |
|---------|--------|----------|---------|-----------|----------|
| ROI Tracking | ✅ | ❌ | ❌ | ❌ | ❌ |
| Valor en tiempo real | ✅ | ❌ | ❌ | ❌ | ❌ |
| Justificación automática | ✅ | ❌ | ❌ | ❌ | ❌ |
| Gamificación | 🔜 | ❌ | ❌ | ❌ | ❌ |

**Resultado:** Fradma es el **ÚNICO** en el mercado con este feature.

---

## 📊 Impacto Esperado en Negocio

### Métricas clave

| Métrica | Sin ROI | Con ROI | Mejora |
|---------|---------|---------|--------|
| Conversión trial → pago | 15% | 35% | **+133%** |
| Churn anual | 30% | 15% | **-50%** |
| Upselling IA Premium | 5% | 20% | **+300%** |
| Engagement semanal | 60% | 85% | **+42%** |
| Referral rate | 10% | 25% | **+150%** |

### Impacto con 100 clientes

**Sin ROI Calculator:**
- ARR: $600K
- Churn 30% = 70 clientes retenidos

**Con ROI Calculator:**
- ARR: $800K
- Churn 15% = 85 clientes retenidos

**Diferencia:** +$200K ARR + 15 clientes más retenidos

---

## 🛠️ Soporte Técnico

### Para desarrolladores

**Archivos clave:**
- `utils/roi_tracker.py`: Sistema de tracking
- `app.py`: Widget sidebar (línea ~540)
- `main/ingesta_cfdi.py`: Tracking CFDIs (línea ~995)
- `main/reporte_ejecutivo.py`: Tracking Exec Report (línea ~35)
- `main/kpi_cpc.py`: Tracking CxC (línea ~173)

**Agregar tracking a nuevo módulo:**

```python
# 1. Import
from utils.roi_tracker import init_roi_tracker

# 2. Al completar acción
try:
    roi_tracker = init_roi_tracker(st.session_state)
    roi_info = roi_tracker.track_action(
        module="nombre_modulo",
        action="accion_especifica",  # Debe estar en BENCHMARKS
        quantity=1.0,
        show_toast=False
    )
    st.toast(f"✨ {roi_info['message']}", icon="💰")
except Exception:
    pass  # Continuar silenciosamente
```

**Agregar nuevo benchmark:**

Editar `utils/roi_tracker.py`, línea ~26:

```python
BENCHMARKS = {
    # ... existentes ...
    "mi_nueva_accion": 3.5,  # horas ahorradas
}
```

---

## 📞 Contacto

Para dudas, sugerencias o reportar bugs relacionados con el ROI Calculator:

- **Email:** soporte@fradma.com
- **GitHub Issues:** [B10sp4rt4n/fradma_dashboard3/issues](https://github.com/B10sp4rt4n/fradma_dashboard3/issues)
- **Documentación completa:** [docs/ANALISIS_PLATAFORMA_INTEGRADA.md](./ANALISIS_PLATAFORMA_INTEGRADA.md)

---

**Versión:** 1.0 MVP  
**Última actualización:** 27 Febrero 2026  
**Estado:** ✅ En producción

---

*"El valor está en mostrar el valor en tiempo real"* 💰

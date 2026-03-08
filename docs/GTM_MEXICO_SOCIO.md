# Plan de Go-To-Market México
## CIMA Fiscal Intelligence Platform

**Clasificación:** Confidencial — Para revisión de socios potenciales  
**Fecha:** Marzo 2026  
**Versión:** 1.0

---

## Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Contexto del Producto](#2-contexto-del-producto)
3. [Oportunidad de Mercado](#3-oportunidad-de-mercado)
4. [Estrategia de Entrada](#4-estrategia-de-entrada)
5. [Fases de Ejecución](#5-fases-de-ejecución)
6. [Modelo de Ingresos y Pricing](#6-modelo-de-ingresos-y-pricing)
7. [Proyección Financiera Conservadora](#7-proyección-financiera-conservadora)
8. [Riesgos y Mitigaciones](#8-riesgos-y-mitigaciones)
9. [Lo Que No Haremos](#9-lo-que-no-haremos)
10. [Rol del Socio Estratégico](#10-rol-del-socio-estratégico)
11. [Criterios de Éxito por Fase](#11-criterios-de-éxito-por-fase)

---

## 1. Resumen Ejecutivo

CIMA Fiscal Intelligence Platform es la primera solución en México que combina ingesta automática de CFDI, BI en tiempo real y consulta en lenguaje natural sobre datos fiscales propios. Opera sobre la infraestructura documental que toda empresa mexicana ya produce obligatoriamente: la factura electrónica.

El plan que se presenta a continuación es un go-to-market de 12 meses, conservador en metas y sin depender de capital externo para las Fases 1 y 2. La Fase 3 puede acelerarse significativamente con el apoyo de un socio estratégico con red de contactos en el ecosistema contable o empresarial mexicano.

| Métrica | Meta Mes 6 | Meta Mes 12 |
|---|---|---|
| Clientes activos | 20 | 50 |
| MRR (MXN) | $32,000 | $70,000 |
| ARR proyectado | $384,000 | **$840,000** |
| Despachos contables asociados | 2 | 5 |
| Churn mensual objetivo | < 10% | < 7% |

---

## 2. Contexto del Producto

### ¿Qué es CIMA?

CIMA es una plataforma SaaS que convierte los archivos XML del CFDI (Comprobante Fiscal Digital por Internet) en inteligencia de negocio accionable. El flujo completo es:

```
ZIP con XMLs fiscales
        ↓
Parser CFDI 4.0 / Pagos 2.0
        ↓
Base de datos PostgreSQL en la nube (Neon)
        ↓
Dashboards automáticos (KPIs, CxC, Ventas, Heatmaps)
        ↓
Análisis en lenguaje natural ("¿quiénes son mis 5 mejores clientes este año?")
        ↓
Reporte PDF ejecutivo con un clic
```

No requiere ERP, no requiere integración técnica, no requiere capacitación avanzada. El contador o el dueño sube sus XMLs y en menos de 5 minutos tiene su dashboard operativo.

### Estado Actual del Producto

| Módulo | Estado |
|---|---|
| Parser CFDI 4.0 + Complementos de Pago | ✅ Producción |
| 9 dashboards analíticos | ✅ Producción |
| NL2SQL con GPT-4o (Data Assistant) | ✅ Producción |
| Reporte PDF ejecutivo automatizado | ✅ Producción |
| Multi-empresa / multi-usuario | ✅ Producción |
| Exportación Excel y CSV | ✅ Producción |
| 538 tests automatizados (68% cobertura) | ✅ CI/CD activo |

Nivel de madurez: **3.7 / 5.0** en modelo de madurez FIP. MVP avanzado, listo para primeros clientes de pago.

---

## 3. Oportunidad de Mercado

### El Problema Real

En México, más de **6 millones de empresas** están obligadas a emitir CFDI. Cada XML contiene datos estructurados de clientes, montos, fechas, impuestos y forma de pago. Sin embargo, el 94% de las PYME no extrae ningún valor analítico de esos datos: los archivan, los entregan al contador, y siguen tomando decisiones comerciales con hojas de cálculo.

El ERP gestiona la operación. El SAT recibe los comprobantes. Nadie convierte esos datos en inteligencia. Ese vacío es donde opera CIMA.

### Contexto Fiscal como Ventaja Competitiva

El CFDI es el único documento en México que:
- Es **vinculante fiscalmente** (no se puede alterar retroactivamente)
- Contiene **datos relacionales estructurados** (emisor, receptor, conceptos, impuestos, método de pago)
- Se emite **en tiempo real** por ley desde 2022 (CFDI 4.0)
- Permite **reconciliación directa con el SAT** sin depender de sistemas externos

Ningún Power BI, Tableau o Metabase trabaja de forma nativa con datos fiscales mexicanos. CIMA sí.

### Tamaño de Mercado Addressable

| Segmento | Universo México | Disposición a Pagar | Valor Potencial |
|---|---|---|---|
| PYME B2B manufactura/distribución (20-150 emp.) | ~185,000 empresas | $1,200–$2,800 MXN/mes | TAM ~$3,700M MXN/año |
| Despachos contables (modelo partner) | ~45,000 despachos | $700/empresa × 8 empresas = $5,600 MXN/mes | TAM ~$3,024M MXN/año |
| Medianas empresas (150-500 emp.) | ~28,000 empresas | $5,000–$12,000 MXN/mes | TAM ~$2,016M MXN/año |

**SAM Realista Año 1–3:** Empresas con RFC activo, más de $5M MXN en facturación anual, en sectores B2B de manufactura, distribución y servicios profesionales: aproximadamente **85,000 empresas** en el mercado primario.

---

## 4. Estrategia de Entrada

### Principio Rector

> No vender BI. Vender control financiero sobre los datos que la empresa ya tiene y ya produce.

El mensaje no es "aquí tienes un dashboard bonito". Es: "tus CFDI ya contienen toda esta información — hasta ahora no la estabas leyendo".

### Canal Principal: El Contador Externo

El contador o despacho contable es el **gatekeeper natural** de la adopción tecnológica en la PYME mexicana. Sus clientes confían en él para decisiones de software fiscal. Un despacho que atiende 20 empresas representa 20 prospectos calificados en una sola relación comercial.

La estrategia de canal se estructura como **Contador Partner**:

- El despacho recibe un portal con su marca para entregar a sus clientes
- Acceso propio gratuito (herramienta de trabajo para el contador mismo)
- 20% de comisión recurrente mensual por cada empresa activa que refiera
- Mínimo 5 empresas activas para mantener estatus Partner

Este modelo convierte al contador de posible bloqueador a promotor activo.

### Segmentación por Orden de Ataque

| Prioridad | Segmento | Razón |
|---|---|---|
| **1** | Despachos contables con 10–50 clientes PYME | Efecto multiplicador, ciclo de ventas corto |
| **2** | PYME B2B distribución/manufactura 20–100 empleados | Dolor activo: reportes manuales en Excel, CxC sin control |
| **3** | Dueños de PYME que ya usan Aspel o CONTPAQi pero no obtienen analítica | Transición natural, sin reemplazar sistemas existentes |

---

## 5. Fases de Ejecución

### Fase 1 — Validación y Primeros Logos (Meses 1–3)

**Objetivo:** 5 empresas pagando, producto validado con datos reales de clientes.

**Acciones:**

1. **3 clientes directos** vía red de contactos del equipo fundador. Precio introductorio $999 MXN/mes durante los primeros 6 meses. Sin acceso gratuito — quien no paga no adopta.
2. **2 despachos contables** en modalidad prueba técnica. Se les instala el portal con sus logos, se les asigna acceso a CIMA para 5 de sus clientes. Tarifa: $500 MXN/empresa/mes, mínimo 5 empresas = $2,500 MXN/mes por despacho.
3. **Onboarding personalizado** de 90 minutos (Teams o presencial) + soporte por WhatsApp Business directo, tiempo de respuesta < 4 horas en horario hábil.
4. **Documentación del caso de uso:** al menos 1 ficha de caso real (empresa anonimizada) con métricas concretas de tiempo ahorrado y hallazgos encontrados.

**No hacer en esta fase:** redes sociales, publicidad pagada, eventos, ni expandir características antes de tener retroalimentación de los primeros clientes.

**Indicador de éxito principal:** NPS ≥ 50 con los primeros 5 clientes al final del mes 3.

---

### Fase 2 — Canal Contadores (Meses 4–6)

**Objetivo:** 20 empresas activas, programa Partner formalizado.

**Acciones:**

1. **Lanzamiento formal del Programa Contador Partner** con materiales: kit de presentación, comisiones documentadas, SLA de soporte.
2. **Prospección activa de 30 despachos** en una ciudad inicial (se recomienda Monterrey o Guadalajara por densidad industrial y concentración de PYME B2B). Meta: 4–5 despachos activos al final de Fase 2.
3. **Desarrollo del caso de éxito completo:** documento de 1–2 páginas con datos reales del cliente Fase 1 (nombre y sector anonimizados, cifras verificables). Este documento es la herramienta de ventas principal para los despachos.
4. **Precio normalizado en MXN con opción de pago anual** (ver sección 6).
5. **Alerta semanal por email:** reporte automatizado al cliente con resumen de la semana ("sus ventas esta semana fueron $X, sus 3 mejores clientes fueron..."). Este automatismo crea hábito de uso sin esfuerzo del usuario.

**Indicador de éxito principal:** 20 empresas con datos activos, churn mensual < 10%.

---

### Fase 3 — Escala Controlada (Meses 7–12)

**Objetivo:** 50 empresas activas, $70,000 MXN MRR, presencia regional establecida.

**Acciones:**

1. **Contenido orgánico en LinkedIn:** 3 publicaciones semanales con insights de datos fiscales mexicanos (basados en datos anonimizados de la base de clientes: "¿Cuántas PYME tienen más del 40% de sus ventas concentradas en 1 cliente?"). Posiciona a CIMA como autoridad en inteligencia fiscal, no como vendedor de software.
2. **Webinar mensual gratuito:** "Cómo leer tu CFDI como un CFO" — 45 minutos, conversión directa a demo individual.
3. **Alianza con 1 asociación empresarial** con base de PYME manufacturera o distribuidora: CANACINTRA, COPARMEX o una cámara sectorial. El acuerdo incluye acceso preferencial para sus agremiados a cambio de difusión.
4. **Exportador de datos desde Aspel SAE / CONTPAQi:** aunque sea mediante exportación manual de XML, crear una guía paso a paso para los clientes de estos ERPs. Reduce la fricción de onboarding en el 60% de las PYME que los usan.
5. **Incorporar 2 despachos en segunda ciudad.**

**Indicador de éxito principal:** 50 empresas activas, 3+ despachos Partner activos, CAC < $3,000 MXN.

---

## 6. Modelo de Ingresos y Pricing

### Estructura de Planes (en MXN, mercado México)

| Plan | Precio Mensual | Precio Anual | Perfil |
|---|---|---|---|
| **Starter** | $1,200 MXN/mes | $12,000 MXN/año | 1–3 usuarios, hasta 500 CFDIs/mes, 5 dashboards base |
| **Pro** | $2,800 MXN/mes | $28,800 MXN/año | Usuarios ilimitados, NL2SQL Data Assistant, exportación PDF, alertas automáticas |
| **Partner** *(despachos)* | $700 MXN/empresa/mes | $7,200 MXN/empresa/año | Requiere mínimo 5 empresas activas, portal con logo del despacho, comisión 20% |

### Mix de Ingresos Esperado (Mes 12)

| Plan | Clientes | MRR |
|---|---|---|
| Pro (60%) | 30 | $84,000 |
| Starter (30%) | 15 | $18,000 |
| Partner — 3 despachos × 5 emp. promedio | 5 despachos × 5 emp. = 25 | ~$8,750 |
| **Total** | **~50 empresas** | **~$70,000 MXN** |

> Nota: El plan anual ofrece 2 meses gratis (descuento del 17%). Se proyecta que el 40% de los clientes elijan la modalidad anual a partir del mes 6, mejorando el flujo de caja y reduciendo el churn.

---

## 7. Proyección Financiera Conservadora

### Supuestos del Modelo

- Crecimiento de clientes: +3 netos en meses 1–3, +5 netos en meses 4–6, +5 netos en meses 7–12
- Churn mensual: 10% en Fase 1, 7% en Fase 2, 5% en Fase 3
- Precio promedio por empresa: $1,400 MXN/mes (blended entre planes)
- Costo de infraestructura: < $2,000 MXN/mes (Neon PostgreSQL + OpenAI API + Streamlit Cloud)
- CAC Fase 1–2: < $1,500 MXN (venta directa / referidos)
- CAC Fase 3: < $3,000 MXN (contenido + canal)

### Tabla de Proyección Mensual

| Mes | Clientes Activos | MRR (MXN) | MRR Acumulado | Margen Bruto Est. |
|---|---|---|---|---|
| 1 | 3 | $4,200 | $4,200 | ~85% |
| 2 | 5 | $7,000 | $11,200 | ~85% |
| 3 | 5 | $7,000 | $18,200 | ~85% |
| 4 | 8 | $11,200 | $29,400 | ~85% |
| 5 | 14 | $19,600 | $49,000 | ~85% |
| 6 | 20 | $28,000 | $77,000 | ~85% |
| 7 | 26 | $36,400 | $113,400 | ~87% |
| 8 | 32 | $44,800 | $158,200 | ~87% |
| 9 | 38 | $53,200 | $211,400 | ~87% |
| 10 | 43 | $60,200 | $271,600 | ~88% |
| 11 | 47 | $65,800 | $337,400 | ~88% |
| **12** | **50** | **$70,000** | **$407,400** | **~88%** |

**ARR al mes 12:** ~$840,000 MXN (~$42,000 USD al tipo de cambio actual)  
**Ingresos acumulados año 1:** ~$407,400 MXN (~$20,370 USD)  
**Margen bruto estimado:** 85–88% (modelo SaaS con infraestructura serverless de bajo costo)

### Análisis de Unit Economics (Mes 12)

| Métrica | Valor |
|---|---|
| ARPU mensual (blended) | $1,400 MXN |
| CAC promedio (blended) | $2,200 MXN |
| LTV estimado (24 meses, churn 5%) | $26,600 MXN |
| LTV / CAC | **12.1x** |
| Payback period | ~2 meses |

---

## 8. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| El contador externo percibe la herramienta como amenaza a su rol | **Alta** | Alto | Posicionar como herramienta que el contador entrega a sus clientes, no que los clientes usan sin él. El contador mantiene control y gana comisión. |
| La PYME no adopta por falta de hábito de uso digital | **Alta** | Medio | Alertas automáticas semanales por email con resumen de datos. El cliente recibe valor sin necesidad de ingresar a la plataforma activamente. |
| Churn elevado en los primeros meses por curva de aprendizaje | **Media** | Alto | Sesión de onboarding obligatoria. Check-in proactivo a los 14 y 30 días. No se considera cliente "activo" hasta que cargó su primer dataset. |
| El precio en dólares genera fricción en mercado PYME | **Alta** | Medio | Toda comunicación comercial en México en MXN. Precio anual disponible desde el inicio para anclar percepción de valor mensual menor. |
| Entrada de competidor con mayor presupuesto de marketing | **Media** | Medio | El moat está en la especialización fiscal mexicana (CFDI, reglas SAT, lógica de complementos de pago) y en la base de datos de clientes enriquecida. Difícil de replicar rápido. |
| Dependencia de API de OpenAI (costo y disponibilidad) | **Baja** | Medio | Arquitectura permite conmutar a modelos alternativos (Claude, Gemini, Llama local). El NL2SQL es el módulo más sensible; se mantiene caché de consultas frecuentes. |

---

## 9. Lo Que No Haremos

Estas decisiones son tan importantes como las que sí se ejecutan:

- **No publicidad pagada antes del mes 6.** Sin métricas de conversión probadas, cualquier inversión en ads es capital quemado.
- **No freemium.** En México el acceso gratuito no genera adopción sostenida; genera soporte sin retorno y distorsiona la percepción de valor.
- **No expansión a LATAM antes del mes 12.** Colombia, Perú y Argentina tienen estándares fiscales distintos al CFDI. Cada país requiere un parser diferente. El foco total en México durante el año 1 es no negociable.
- **No desarrollo de app móvil.** La PYME mexicana reporta en escritorio. La plataforma es responsive; una app nativa no agrega valor en esta etapa.
- **No intentar reemplazar el ERP.** CIMA vive al lado del ERP, no en su lugar. El mensaje de venta nunca enfrenta herramientas existentes: las complementa.

---

## 10. Rol del Socio Estratégico

Este plan puede ejecutarse de forma autónoma con los recursos actuales del equipo hasta el mes 6. La aceleración en Fase 3 y la reducción significativa del CAC dependen de un factor externo: **acceso a red**.

Un socio estratégico puede aportar en tres dimensiones:

### Dimensión 1 — Red Comercial
- Acceso a despachos contables o asociaciones empresariales con base de PYME B2B
- Presentación institucional de CIMA como solución recomendada o respaldada
- Valor estimado: reducción del CAC en un 60% y aceleración de +15 clientes en Fase 3

### Dimensión 2 — Validación de Mercado
- Conocimiento sectorial de los segmentos objetivo (manufactura, distribución, servicios profesionales B2B)
- Retroalimentación sobre pricing y posicionamiento con base en interacción directa con compradores del perfil objetivo
- Valor estimado: reduce el riesgo de iterar en producto sin dirección clara

### Dimensión 3 — Capital de Crecimiento (Opcional)
- Un ticket de inversión entre $300,000 y $800,000 MXN permitiría contratar 1 persona de ventas/soporte en Fase 3 y financiar las actividades de contenido y eventos regionales
- Retorno proyectado: el modelo alcanza $840K MXN ARR al mes 12 sin inversión; con $500K MXN de inversión en Fase 3 el potencial se estima en $1.8–2.2M MXN ARR al mes 18

### Lo que no se pide al socio
- No se requiere inversión para las Fases 1 y 2
- No se cede control operativo ni decisiones de producto
- La relación preferred es **partner comercial con participación en ingresos o equity minoritario**, no deuda

---

## 11. Criterios de Éxito por Fase

### Fase 1 (Mes 3)
- [ ] 5 empresas con datos cargados y acceso activo
- [ ] NPS ≥ 50 medido con encuesta directa
- [ ] Al menos 1 caso de uso documentado con métricas reales
- [ ] Churn < 10% mensual

### Fase 2 (Mes 6)
- [ ] 20 empresas activas
- [ ] 2 despachos Partner activos con ≥ 5 empresas cada uno
- [ ] MRR ≥ $28,000 MXN
- [ ] CAC < $1,500 MXN (venta directa/referidos)
- [ ] Churn < 10% mensual

### Fase 3 (Mes 12)
- [ ] 50 empresas activas
- [ ] 5 despachos Partner activos
- [ ] MRR ≥ $70,000 MXN
- [ ] CAC < $3,000 MXN
- [ ] Churn < 5% mensual
- [ ] 1 alianza institucional activa (cámara o asociación empresarial)
- [ ] LTV/CAC ≥ 10x

---

## Apéndice — Tecnología Disponible Hoy

| Capacidad | Detalle |
|---|---|
| Parser CFDI 4.0 | Extrae 30+ campos de cada XML; soporta comprobantes de ingreso, egreso, traslado y complementos de pago |
| Base de datos fiscal | PostgreSQL en Neon (serverless); schema normalizado con 6 tablas y 9 vistas analíticas |
| Dashboards preconstruidos | KPIs ejecutivos, CxC con antigüedad 30/60/90/120+, YTD por líneas, Heatmap de ventas, Análisis de vendedores, Módulo comparativo multi-período |
| Data Assistant (NL2SQL) | Preguntas en español → SQL seguro → resultado visualizado en gráfica o tabla; filtros fiscales integrados |
| Reportes PDF | Generación automática con KPIs, gráfica y tabla de datos en un clic |
| Multi-empresa / roles | Selección de empresa, roles admin/usuario, panel de administración |
| CI/CD | 538 tests automatizados, GitHub Actions, cobertura 68% |

---

*Documento preparado por el equipo CIMA Analytics — Marzo 2026*  
*Para mayor información o solicitar demo: contacto directo con el equipo fundador*

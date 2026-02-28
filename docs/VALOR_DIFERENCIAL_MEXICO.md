# Valor Diferencial en el Mercado Mexicano

> **"El primer BI mexicano que habla CFDI"**
> Sube tus facturas. Ve tus métricas. Pregunta con lenguaje natural.

---

## Pipeline Completo (nadie lo ofrece integrado en México)

```
CFDI XML → Parser 4.0 → Neon Cloud DB → Clientes auto-extraídos → BI Dashboards → NL2SQL con IA → Wiki/KB
```

---

## Mapa Competitivo México

| Capacidad | Fradma Dashboard | CONTPAQi / Aspel | Bind ERP / Alegra | Facturama | Power BI / Tableau | ChatGPT genérico |
|---|---|---|---|---|---|---|
| Ingesta CFDI 4.0 masiva (ZIP) | **Sí** | Solo los que emite | Parcial | Solo emisión | No | No |
| Parser XML → DB estructurada | **Automático** | Interno, cerrado | Interno | No | No | No |
| Auto-extracción de clientes | **UPSERT acumulativo** | Manual | Manual | No | No | No |
| BI sobre datos fiscales reales | **Integrado** | Reportes básicos | Reportes básicos | No | Sí, pero manual | No |
| NL2SQL sobre TUS datos | **GPT-4o → SQL → Neon** | No | No | No | Copilot (limitado) | No tiene tus datos |
| Knowledge Base empresarial | **Integrado** | No | No | No | No | No |
| Nube serverless (Neon) | **Sí** | On-premise | SaaS cerrado | SaaS cerrado | Nube separada | N/A |
| Costo infraestructura | **~$0-25 USD/mes** | $3,000-15,000 MXN/año | $500-2,000 MXN/mes | $400-1,500 MXN/mes | $10-70 USD/mes | $20 USD/mes |

---

## 3 Ventajas que Nadie Tiene en México

### 1. CFDI como fuente de verdad para BI (no el ERP)

- En México, las empresas dependen del ERP para reportes. Pero el CFDI es el documento fiscal vinculante.
- Fradma Dashboard toma el CFDI como input primario → los datos son 100% reconciliables con el SAT.
- **Implicación:** auditorías, declaraciones, y análisis de ventas desde una sola fuente verificable.

### 2. Clientes auto-construidos desde facturación real

- `clientes_master` se llena solo: RFC, razón social, régimen fiscal, domicilio fiscal, total histórico, conteo de facturas, primera/última venta.
- Ningún CRM en México construye el padrón de clientes desde los CFDIs. Son mundos separados.
- **Implicación:** CRM fiscal automático sin captura manual.

### 3. "Pregúntale a tus datos" en español sobre información fiscal mexicana

- NL2SQL que entiende: "¿Cuánto le vendimos a Grupo Bimbo en 2025?" → SQL → resultado.
- Power BI Copilot hace algo similar pero: (a) no ingesta CFDIs, (b) requiere modelado manual, (c) cuesta 10x más.
- ChatGPT no tiene tus datos. El asistente de Fradma sí.

---

## Segmento de Mercado y Sizing

| Segmento | Empresas en México | Dolor que resuelve |
|---|---|---|
| PyMEs con +100 facturas/mes | ~500,000 | No tienen BI, todo es Excel |
| Despachos contables | ~45,000 | Manejan múltiples empresas, necesitan consolidación |
| Distribuidoras / mayoristas | ~80,000 | Necesitan análisis por cliente/producto desde CFDI |
| Empresas con +$10M MXN facturación | ~150,000 | Pagan Power BI + ERP pero no tienen integración CFDI→BI |

---

## Categoría de Producto

**Fiscal Intelligence Platform** — No es ERP, no es BI genérico, no es chatbot. Es la intersección de los tres, nativa para el ecosistema fiscal mexicano (CFDI 4.0 + SAT).

---

## Pricing Sugerido

| Tier | Precio MXN/mes | Incluye |
|---|---|---|
| Starter | $499 | 1 empresa, 500 CFDIs/mes, BI básico |
| Pro | $1,499 | 3 empresas, ilimitado, NL2SQL, KB |
| Despacho | $3,999 | 20 empresas, multi-usuario, API |

### Comparativa de costo

- **CONTPAQi** (solo contabilidad): $1,200-5,000/año
- **Power BI Pro**: ~$170 USD/mes (~$3,400 MXN)
- **Ambos combinados**: ~$5,000-8,000 MXN/mes
- **Fradma Dashboard Pro**: $1,499 MXN/mes (hace más, cuesta menos)

---

## Resumen Ejecutivo

Fradma Dashboard es la **primera plataforma de inteligencia fiscal en México** que:

1. **Ingesta masiva** de CFDIs 4.0 directamente desde ZIP
2. **Extrae automáticamente** clientes, montos y conceptos a una base de datos cloud
3. **Genera dashboards de BI** sobre datos fiscales reales (no datos de ERP)
4. **Permite preguntar en lenguaje natural** sobre tus propios datos fiscales
5. **Mantiene una base de conocimiento** empresarial integrada

Todo esto en una sola plataforma, a una fracción del costo de las alternativas fragmentadas existentes.

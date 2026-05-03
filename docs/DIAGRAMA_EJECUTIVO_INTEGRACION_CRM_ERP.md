# Diagrama Ejecutivo de Integracion CRM ERP

## Objetivo

Mostrar en una sola pagina la historia ejecutiva de la integracion futura: de donde vienen los datos, como se consolidan y que valor entregan al negocio.

## Vista Ejecutiva

## Vista SVG Renderizada

![Diagrama ejecutivo CRM ERP](assets/diagrams/diagrama_ejecutivo_integracion_crm_erp.svg)

```mermaid
flowchart LR
    A[Sistemas Comerciales y Operativos<br/>CRM ERP CFDI Bancos] --> B[Conectores]
    B --> C[Raw y Trazabilidad]
    C --> D[Normalizacion y Matching]
    D --> E[Modelo Unificado]
    E --> F[Dashboards Ejecutivos]
    E --> G[Alertas y Cobranza]
    E --> H[Forecast y ROI]

    I[Objetivo<br/>una sola version confiable del negocio] --> E
    J[Beneficios<br/>menos trabajo manual mas control mejor decision] --> F

    classDef source fill:#1f3c5c,color:#fff,stroke:#0d2238
    classDef process fill:#2f6b4f,color:#fff,stroke:#1d4d37
    classDef output fill:#5a3d7a,color:#fff,stroke:#3b2752
    classDef note fill:#7a5c2e,color:#fff,stroke:#533d1b

    class A source
    class B,C,D,E process
    class F,G,H output
    class I,J note
```

## Lectura de Negocio

1. Los datos no entran directo al dashboard; pasan primero por una capa controlada de integracion.
2. La trazabilidad raw evita perder contexto y permite auditar cualquier cifra publicada.
3. La normalizacion y el matching convierten multiples sistemas en una sola version confiable del cliente, producto, vendedor, factura y pago.
4. El modelo unificado habilita analitica transversal: ventas, pipeline, cobranza, cartera, forecast y ROI.
5. El resultado final es menos trabajo manual, mas consistencia y mejor velocidad de decision.

## Archivos Exportados

Los renders exportados de este diagrama deben vivir en:

- docs/assets/diagrams/diagrama_ejecutivo_integracion_crm_erp.svg
- docs/assets/diagrams/diagrama_ejecutivo_integracion_crm_erp.png
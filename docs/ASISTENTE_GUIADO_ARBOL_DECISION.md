# Asistente Guiado: Arbol de Decision y Catalogo Base

## Objetivo

Reducir ambiguedad y riesgo operativo reemplazando el flujo de lenguaje natural por un catalogo finito de consultas guiadas, parametrizadas y validadas.

Principios de diseno:

- Maximo 20 casos productivos iniciales.
- Sin interpretacion libre de texto.
- Solo opciones validas por dominio.
- Periodos guiados y consistentes.
- SQL predefinido por template, no generado por IA.
- Reglas de tenant, periodo y perfil aplicadas de forma deterministica.

## Arbol de decision

```mermaid
flowchart TD
    A[Inicio: elegir dominio] --> B[Ventas]
    A --> C[Productos]
    A --> D[Clientes]
    A --> E[Cobranza]
    A --> F[Fiscal]

    B --> B1[Resumen ejecutivo]
    B --> B2[Tendencia]
    B --> B3[Ranking]
    B --> B4[Distribucion]
    B --> B5[Concentracion]

    C --> C1[Precios]
    C --> C2[Ranking de productos]
    C --> C3[Mix y participacion]
    C --> C4[Volumen]

    D --> D1[Ranking clientes]
    D --> D2[Recurrencia]
    D --> D3[Concentracion]
    D --> D4[Crecimiento]

    E --> E1[Pendientes]
    E --> E2[Pagadas]
    E --> E3[Parciales]
    E --> E4[Antiguedad]

    F --> F1[Resumen fiscal]
    F --> F2[Impuestos y retenciones]
    F --> F3[Egresos y devoluciones]

    B1 --> P[Elegir periodo]
    B2 --> P
    B3 --> P
    B4 --> P
    B5 --> P
    C1 --> P
    C2 --> P
    C3 --> P
    C4 --> P
    D1 --> P
    D2 --> P
    D3 --> P
    D4 --> P
    E1 --> P
    E2 --> P
    E3 --> P
    E4 --> P
    F1 --> P
    F2 --> P
    F3 --> P

    P --> P1[Todo]
    P --> P2[Este ano]
    P --> P3[Ultimos 12 meses]
    P --> P4[Ultimos 6 meses]
    P --> P5[Rango personalizado]

    P1 --> G[Filtros compatibles]
    P2 --> G
    P3 --> G
    P4 --> G
    P5 --> G

    G --> G1[Metodo de pago]
    G --> G2[Tipo de comprobante]
    G --> G3[Top N]
    G --> G4[Cliente]
    G --> G5[Producto]
    G --> G6[Agrupacion]

    G1 --> H[Ejecutar template SQL validado]
    G2 --> H
    G3 --> H
    G4 --> H
    G5 --> H
    G6 --> H

    H --> I[Render fijo: KPI + grafica + tabla + exportacion]
```

## Estructura de navegacion sugerida

1. Dominio
2. Analisis
3. Periodo
4. Filtros opcionales
5. Resultado

## Dominios y 20 casos cerrados

### Ventas

1. Resumen ejecutivo de ventas
2. Ventas por mes
3. Top clientes por ventas
4. Top productos por ventas
5. Concentracion de clientes

### Productos

6. Estadisticas de precios unitarios
7. Top productos por facturacion
8. Productos de menor venta
9. Participacion por producto

### Clientes

10. Ranking de clientes
11. Clientes recurrentes
12. Clientes nuevos por periodo
13. Crecimiento por cliente

### Cobranza

14. Facturas pendientes de cobro
15. Facturas pagadas
16. Facturas parcialmente pagadas
17. Antiguedad de cartera

### Fiscal

18. Resumen fiscal de ingresos
19. Impuestos trasladados y retenidos
20. Egresos y notas de credito

## Parametros comunes

- period_mode: todo | este_ano | ultimos_12_meses | ultimos_6_meses | rango_personalizado
- start_date
- end_date
- top_n
- metodo_pago
- tipo_comprobante
- cliente
- producto
- agrupacion: mensual | trimestral | anual | total

## Reglas de validacion de UX

- El usuario nunca escribe la consulta.
- Si una opcion no aplica al dominio, no se muestra.
- Si una opcion requiere serie temporal, se fuerza agrupacion temporal valida.
- Si una opcion requiere volumen minimo, se muestra aviso de insuficiencia de datos.
- Si una opcion depende de datos no implementados, no se incluye en el catalogo inicial.

## Reglas de validacion tecnica

- Cada caso tiene un template SQL unico.
- Cada caso define tablas permitidas.
- Cada caso define filtros compatibles.
- Los filtros de tenant y periodo se insertan en puntos explicitamente definidos por template.
- Cada caso define grafica por defecto y fallback a tabla.

## Recomendacion de implementacion

Fase 1:

- Implementar el catalogo JSON.
- Construir selector de dominio -> analisis -> periodo -> filtros.
- Resolver template SQL por id.
- Reusar render actual de KPIs, tablas, graficas y exportacion.

Fase 2:

- Agregar disponibilidad condicional por perfil.
- Agregar textos ejecutivos predefinidos por caso.
- Agregar tracking de uso por opcion.

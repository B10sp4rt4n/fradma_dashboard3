# 📋 Guía de Columnas Requeridas - Dashboard Fradma

Esta guía especifica todas las columnas necesarias para el correcto funcionamiento de cada módulo del dashboard. Úsala para:
- **Mapear datos** desde CRMs, ERPs o sistemas externos
- **Diagnosticar errores** cuando falta información
- **Diseñar exports** desde sistemas fuente

---

## 📊 Estructura General

### Convenciones
- ✅ **Obligatoria**: Sin esta columna, el módulo no funciona
- ⚠️ **Recomendada**: El módulo funciona pero con funcionalidad limitada
- 🔄 **Variantes**: Nombres alternativos que el sistema detecta automáticamente
- 📝 **Default**: Valor usado si la columna no existe

---

## 1️⃣ Módulo: YTD por Líneas de Negocio

### Archivo: Reporte de Ventas

| Columna | Status | Tipo | Variantes Aceptadas | Propósito | Ejemplo |
|---------|--------|------|---------------------|-----------|---------|
| `fecha` | ✅ Obligatoria | Date/DateTime | - | Fecha de la transacción para agrupar por período | `2025-01-15`, `15/01/2025` |
| `ventas_usd` | ✅ Obligatoria | Numeric | `ventas_usd_con_iva`, `ventas_usd_sin_iva`, `importe`, `valor_usd`, `monto_usd`, `total_usd`, `valor`, `venta` | Monto de la venta en dólares | `1250.50` |
| `linea_de_negocio` | ✅ Obligatoria | Text | `linea_negocio`, `linea_producto`, `linea` | Línea de producto/negocio para segmentación | `Zerust`, `REPI`, `EZ-Kote` |
| `vendedor` | ⚠️ Recomendada | Text | `agente`, `ejecutivo`, `vendedor_asignado` | Vendedor responsable (para filtros) | `Juan Pérez`, `VEND_001` |
| `cliente` | ⚠️ Recomendada | Text | `razon_social`, `deudor`, `nombre_cliente` | Cliente que realizó la compra (para análisis top clientes) | `ACME Corp`, `Cliente 123` |
| `producto` | 🔄 Opcional | Text | `descripcion_producto`, `sku`, `articulo` | Producto vendido (para análisis top productos) | `Producto A`, `SKU-12345` |

#### Notas Importantes:
- **Formato de fecha**: Detecta automáticamente formatos comunes (YYYY-MM-DD, DD/MM/YYYY, etc.)
- **Moneda**: Todos los montos deben estar en USD. Si vienen en MXN, el sistema buscará columna `tc` (tipo de cambio)
- **Comparación YTD**: Requiere al menos 2 años de datos para mostrar crecimiento año anterior

---

## 2️⃣ Módulo: Dashboard CxC (Cuentas por Cobrar)

### Archivo: CXC VIGENTES + CXC VENCIDAS (hojas de Excel)

#### Columnas Críticas

| Columna | Status | Tipo | Variantes Aceptadas | Propósito | Ejemplo |
|---------|--------|------|---------------------|-----------|---------|
| `saldo_adeudado` | ✅ Obligatoria | Numeric | `saldo`, `saldo_adeudo`, `adeudo`, `importe`, `monto`, `total`, `saldo_usd` | Monto pendiente de pago | `5000.00` |
| `cliente` | ✅ Obligatoria | Text | `razon_social`, `deudor`, `nombre_cliente` | Cliente deudor (para agrupación) | `ACME Corp` |
| `fecha` | ✅ Obligatoria | Date | `fecha_factura`, `fecha_emision` | Fecha de emisión de la factura | `2025-01-10` |
| `factura` | ⚠️ Recomendada | Text | `numero_factura`, `folio`, `documento` | Número de factura (para trazabilidad) | `A-1234`, `FAC-20250110-001` |

#### Columnas para Cálculo de Vencimiento

**Opción 1: Días de crédito** (recomendado)
| Columna | Status | Tipo | Variantes Aceptadas | Default | Ejemplo |
|---------|--------|------|---------------------|---------|---------|
| `dias_de_credito` | ⚠️ Recomendada | Integer | `dias_de_credit`, `dias_credito`, `dias_credit`, `plazo_dias` | 30 días | `30`, `45`, `60` |
| `fecha_de_pago` | ⚠️ Recomendada | Date | `fecha_pago`, `fecha_tentativa_de_pago`, `fecha_tentativa_de_pag`, `fecha_vencimiento` | Calculado como `fecha + dias_de_credito` | `2025-02-09` |

**Opción 2: Columnas pre-calculadas**
| Columna | Status | Tipo | Cálculo | Ejemplo |
|---------|--------|------|---------|---------|
| `dias_restantes` | 🔄 Opcional | Integer | Días hasta vencimiento (positivo = vigente, negativo = vencido) | `15`, `-10` |
| `dias_vencido` | 🔄 Opcional | Integer | Días de atraso (solo si está vencida) | `0`, `45`, `120` |

#### Columnas de Clasificación

| Columna | Status | Tipo | Variantes Aceptadas | Propósito | Ejemplo |
|---------|--------|------|---------------------|-----------|---------|
| `estatus` | ⚠️ Recomendada | Text | `status`, `pagado` | Estado de pago (para excluir pagadas) | `Pagado`, `Pendiente`, `Vencida` |
| `vendedor` | 🔄 Opcional | Text | `agente`, `ejecutivo` | Vendedor responsable (análisis por agente) | `María López` |
| `linea_de_negocio` | 🔄 Opcional | Text | `linea_negocio`, `linea_producto` | Línea de negocio (análisis de morosidad por línea) | `Zerust` |

#### Columnas Adicionales (Opcionales)

| Columna | Tipo | Propósito | Ejemplo |
|---------|------|-----------|---------|
| `moneda` | Text | Identificar moneda original | `USD`, `MXN` |
| `t.c.` o `tc` | Numeric | Tipo de cambio para conversión | `20.50` |
| `orden_de_compra` | Text | Referencia OC del cliente | `OC-2025-001` |
| `zona` | Text | Zona geográfica del cliente | `Norte`, `Centro` |

#### Notas Importantes:
- **Cálculo de vencimiento**: Si no existen `dias_restantes` o `dias_vencido`, el sistema calcula:
  - `vencimiento = fecha_de_pago (o fecha + dias_de_credito)`
  - `dias_overdue = hoy - vencimiento`
  - Negativo = vigente, Positivo = vencido
- **Estatus "Pagado"**: Variantes detectadas: `pagado`, `paid`, `cancelado`, `cerrado`, `liquidado`, `finiquitado`
- **Hojas de Excel**: El módulo busca automáticamente hojas llamadas `CXC VIGENTES` y `CXC VENCIDAS`
- **Default días de crédito**: Si no existe la columna, usa 30 días (estándar B2B México)

---

## 3️⃣ Módulo: KPIs Generales

### Archivo: Reporte de Ventas

| Columna | Status | Tipo | Variantes Aceptadas | Propósito | Ejemplo |
|---------|--------|------|---------------------|-----------|---------|
| `fecha` | ✅ Obligatoria | Date | - | Fecha de transacción (para filtros por año) | `2025-02-10` |
| `valor_usd` | ✅ Obligatoria | Numeric | `ventas_usd`, `ventas_usd_con_iva`, `importe` | Valor de la venta | `850.00` |
| `agente` | ⚠️ Recomendada | Text | `vendedor`, `ejecutivo` | Vendedor (para ranking y eficiencia) | `Carlos Gómez` |
| `linea_producto` | 🔄 Opcional | Text | `linea_de_negocio`, `linea` | Línea de producto (filtro opcional) | `Schutze` |

#### Columnas Calculadas Automáticamente:
- **anio**: Extraído de `fecha` (año de la transacción)
- **ticket_promedio**: `total_ventas / operaciones`
- **operaciones**: Conteo de registros por vendedor

#### Notas Importantes:
- **Normalización automática**: Si encuentras `vendedor` en lugar de `agente`, el sistema lo renombra internamente
- **Clasificación de vendedores**: Usa mediana de ticket promedio y operaciones para segmentar en 4 cuadrantes

---

## 4️⃣ Módulo: Reporte Ejecutivo

### Archivos: Reporte de Ventas + CxC

Combina columnas de **Módulo YTD** y **Módulo CxC**. No requiere columnas adicionales.

#### Columnas Específicas del Módulo:

| Columna | Archivo | Status | Propósito |
|---------|---------|--------|-----------|
| `fecha` | Ventas | ✅ Obligatoria | Calcular variación mensual |
| `valor_usd` | Ventas | ✅ Obligatoria | Total de ventas |
| `cliente` | Ventas | ⚠️ Recomendada | Contar clientes activos |
| `saldo_adeudado` | CxC | ✅ Obligatoria | Cartera total |
| `dias_vencido` | CxC | ⚠️ Recomendada | Clasificación de cartera crítica |

#### KPIs Calculados:
- **Salud General**: Combina score de ventas (50%) + score de cartera (50%)
- **Índice de Liquidez**: `(Vigente + Ventas Mes) / Cartera Crítica`
- **Eficiencia Operativa**: `Total Ventas / Cartera Total`

---

## 5️⃣ Módulo: Heatmap de Ventas

### Archivo: Reporte de Ventas

| Columna | Status | Tipo | Variantes | Propósito | Ejemplo |
|---------|--------|------|-----------|-----------|---------|
| `fecha` | ✅ Obligatoria | Date | - | Agrupar por mes del año | `2025-03-15` |
| `ventas_usd` | ✅ Obligatoria | Numeric | `valor_usd`, `importe` | Monto de ventas | `1200.00` |
| `linea_de_negocio` | ⚠️ Recomendada | Text | `linea` | Segmentar heatmap por línea | `Ultra Plast` |
| `vendedor` | 🔄 Opcional | Text | `agente` | Filtro por vendedor | `Ana Martínez` |

#### Nota:
- El heatmap muestra ventas por mes (eje X) vs línea de negocio (eje Y)
- Colores: gradiente de verde (bajo) a rojo (alto)

---

## 📐 Formatos de Datos Aceptados

### Fechas
**Formatos detectados automáticamente:**
- `YYYY-MM-DD` (ISO 8601) - ejemplo: `2025-01-15`
- `DD/MM/YYYY` - ejemplo: `15/01/2025`
- `MM/DD/YYYY` - ejemplo: `01/15/2025`
- `DD-MM-YYYY` - ejemplo: `15-01-2025`
- Excel serial dates (números de 5-6 dígitos)

**Recomendación**: Usar `YYYY-MM-DD` para evitar ambigüedad

### Números
**Formatos aceptados:**
- Punto como decimal: `1250.50`
- Coma como separador de miles: `1,250.50`
- Sin símbolos de moneda: `1250` (no `$1250`)

**Evitar:**
- Símbolos de moneda ($, €)
- Comas como decimales (notación europea)
- Texto en celdas numéricas

### Texto
- **Case-insensitive**: `ZERUST`, `Zerust`, `zerust` se tratan igual
- **Sin acentos**: Normalizado internamente (Pérez → Perez)
- **Caracteres especiales**: Permitidos pero pueden causar problemas en exports

---

## 🔍 Sistema de Detección Automática

El dashboard implementa **detección flexible de columnas**:

### 1. Normalización de Nombres
```
Input: "Ventas USD (con IVA)"
Sistema detecta: ventas_usd_con_iva
Mapea a: ventas_usd ✅
```

### 2. Búsqueda por Variantes
El sistema prueba en orden:
1. Nombre exacto (`vendedor`)
2. Primera variante (`agente`)
3. Segunda variante (`ejecutivo`)
4. Tercera variante (`vendedor_asignado`)

### 3. Normalización de Texto
- Convierte a minúsculas
- Elimina acentos (á → a)
- Reemplaza espacios por guiones bajos
- Elimina caracteres especiales

**Ejemplo:**
```
Input: "Razón Social del Cliente"
Normalizado: "razon_social_del_cliente"
Detectado como: cliente ✅
```

---

## ⚠️ Errores Comunes y Soluciones

### Error: "No se encontró la columna 'ventas_usd'"
**Causas:**
- Columna con nombre diferente
- Columna vacía o sin datos
- Tipo de dato incorrecto (texto en lugar de número)

**Soluciones:**
1. Renombrar columna a uno de los nombres aceptados
2. Verificar que los datos sean numéricos
3. Revisar si hay espacios extra en el header

### Error: "No se pudo parsear la fecha"
**Causas:**
- Formato de fecha no reconocido
- Texto en columna de fecha
- Fechas inválidas (ej: 32/13/2025)

**Soluciones:**
1. Usar formato `YYYY-MM-DD`
2. Asegurar que todas las celdas son tipo Date en Excel
3. Eliminar filas con fechas inválidas

### Error: "Módulo CxC requiere hojas 'CXC VIGENTES' y 'CXC VENCIDAS'"
**Causas:**
- Excel no tiene las hojas con esos nombres exactos
- Nombres con variaciones (espacios extra, mayúsculas/minúsculas)

**Soluciones:**
1. Renombrar hojas exactamente como: `CXC VIGENTES` y `CXC VENCIDAS`
2. Alternativamente: combinar ambas en una sola hoja con columna `estatus`

---

## 🛠️ Checklist de Validación Pre-Carga

Antes de subir tu archivo, verifica:

### Para Reporte de Ventas:
- [ ] Columna `fecha` existe y tiene formato de fecha
- [ ] Columna `ventas_usd` (o variante) existe y es numérica
- [ ] Columna `linea_de_negocio` existe
- [ ] No hay filas completamente vacías
- [ ] Headers están en la fila 1
- [ ] No hay celdas mezcladas (merged cells) en headers

### Para CxC:
- [ ] Archivo Excel tiene hojas `CXC VIGENTES` y `CXC VENCIDAS`
- [ ] Columna `saldo_adeudado` existe y es numérica
- [ ] Columna `cliente` existe
- [ ] Columna `fecha` existe
- [ ] Si no hay `dias_de_credito`, existe `fecha_de_pago` o `fecha_vencimiento`
- [ ] Facturas pagadas tienen `estatus = "Pagado"` o fueron eliminadas

---

## 📊 Ejemplo de Estructura de Archivos

### Reporte de Ventas (Excel/CSV)
```
| fecha      | ventas_usd | linea_de_negocio | vendedor      | cliente        | producto  |
|------------|------------|------------------|---------------|----------------|-----------|
| 2025-01-15 | 1250.50    | Zerust          | Juan Pérez    | ACME Corp      | ZR-100    |
| 2025-01-16 | 850.00     | REPI            | María López   | Beta Industries| REP-200   |
| 2025-01-17 | 2100.00    | EZ-Kote         | Carlos Gómez  | Gamma LLC      | EZK-300   |
```

### CxC VIGENTES (Hoja Excel)
```
| cliente        | saldo_adeudado | fecha      | dias_de_credito | factura    | vendedor   |
|----------------|----------------|------------|-----------------|------------|------------|
| ACME Corp      | 5000.00        | 2025-01-10 | 30              | A-1234     | Juan Pérez |
| Beta Industries| 3500.00        | 2025-01-20 | 45              | B-5678     | María López|
```

### CxC VENCIDAS (Hoja Excel)
```
| cliente     | saldo_adeudado | fecha      | dias_de_credito | factura | dias_vencido | vendedor     |
|-------------|----------------|------------|-----------------|---------|--------------|--------------|
| Gamma LLC   | 8000.00        | 2024-11-15 | 30              | C-9012  | 94           | Carlos Gómez |
| Delta Inc   | 1200.00        | 2024-12-20 | 60              | D-3456  | 59           | Ana Martínez |
```

---

## 🔗 Integración con Sistemas Externos

### CRMs Comunes

#### Salesforce
**Export recomendado:**
- Objeto: Opportunities (Closed Won)
- Mapeo:
  - `CloseDate` → `fecha`
  - `Amount` → `ventas_usd`
  - `Product_Line__c` → `linea_de_negocio`
  - `Owner.Name` → `vendedor`
  - `Account.Name` → `cliente`

#### HubSpot
**Export recomendado:**
- Objeto: Deals (Closed Won)
- Mapeo:
  - `closedate` → `fecha`
  - `amount` → `ventas_usd`
  - `product_line` → `linea_de_negocio`
  - `hubspot_owner_id.name` → `vendedor`

### ERPs Comunes

#### SAP
**Transacción:** VA05 (List of Sales Orders)
**Mapeo:**
- `VBAK-ERDAT` → `fecha`
- `VBAP-NETWR` → `ventas_usd`
- `VBAP-PRODH` → `linea_de_negocio`
- `VBPA-PERNR` → `vendedor`

#### Oracle NetSuite
**Saved Search:** Transactions
**Mapeo:**
- `Transaction Date` → `fecha`
- `Amount (Foreign Currency)` → `ventas_usd`
- `Item: Product Line` → `linea_de_negocio`
- `Sales Rep` → `vendedor`

---

## 📞 Soporte

Si encuentras errores al cargar archivos:
1. **Revisa el checklist de validación** en la app (desplegable "📋 Validación de Columnas")
2. **Consulta esta guía** para verificar nombres de columnas
3. **Verifica formatos de datos** (fechas, números)
4. **Exporta un archivo de muestra** desde el módulo de exportación de la app

---

**Última actualización:** Febrero 2026  
**Versión:** 2.0  
**Compatibilidad:** Dashboard Fradma v3.0+

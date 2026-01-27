# 📋 Especificación Completa de Inputs Excel - Fradma Dashboard

> **Documento de referencia oficial** para la preparación de archivos Excel que alimentan el dashboard.  
> **Versión:** 1.0 | **Fecha:** Enero 2026

---

## ⚡ REFERENCIA RÁPIDA: Campos por Pestaña

### 📊 ARCHIVO DE VENTAS (CSV o Excel)

#### Campos OBLIGATORIOS:
| Campo | Nombres Aceptados | Formato | Ejemplo |
|-------|-------------------|---------|---------|
| **Fecha** | `fecha` | Date (DD/MM/YYYY) | 15/01/2024 |
| **Importe** | `valor_usd`, `ventas_usd`, `importe`, `ventas_usd_con_iva`, `monto_usd`, `valor`, `venta` | Número | 15000.50 |

#### Campos OPCIONALES (recomendados):
| Campo | Nombres Aceptados | Formato | Ejemplo |
|-------|-------------------|---------|---------|
| Línea de Negocio | `linea_producto`, `linea_de_negocio`, `linea` | Texto | Electrodomésticos |
| Cliente | `cliente`, `razon_social`, `deudor` | Texto | ACME Corp |
| Vendedor | `vendedor`, `agente`, `ejecutivo` | Texto | Juan Pérez |
| Producto | `producto`, `articulo`, `item` | Texto | Refrigerador LG |
| Año | `año`, `anio` | Número | 2024 |
| Mes | `mes` | Número (1-12) | 1 |

---

### 🏦 ARCHIVO DE CXC (Excel con 2 hojas obligatorias)

#### 📑 Hoja 1: `CXC VIGENTES`

**Campos OBLIGATORIOS:**
| Campo | Nombres Aceptados | Formato | Ejemplo |
|-------|-------------------|---------|---------|
| **Cliente** | `cliente`, `razon_social`, `deudor` | Texto | ACME Corporation |
| **Saldo** | `saldo_adeudado` | Número | 50000.00 |

**Campos OPCIONALES (recomendados):**
| Campo | Nombres Aceptados | Formato | Ejemplo |
|-------|-------------------|---------|---------|
| Días de Crédito | `dias_de_credito`, `dias_credito` | Número | 30 |
| Fecha de Pago | `fecha_pago`, `fecha_de_pago` | Date | 20/12/2024 |
| Línea de Negocio | `linea_negocio`, `linea_de_negocio` | Texto | Electrodomésticos |
| Vendedor | `vendedor`, `agente` | Texto | Juan Pérez |
| Estatus | `estatus`, `status` | Texto | Vigente |

---

#### 📑 Hoja 2: `CXC VENCIDAS`

**Campos OBLIGATORIOS:**
| Campo | Nombres Aceptados | Formato | Ejemplo |
|-------|-------------------|---------|---------|
| **Cliente** | `cliente`, `razon_social`, `deudor` | Texto | Old Client Corp |
| **Saldo** | `saldo_adeudado` | Número | 100000.00 |
| **Días Vencidos** | `dias_vencido` | Número | 120 |

**Campos OPCIONALES (recomendados):**
| Campo | Nombres Aceptados | Formato | Ejemplo |
|-------|-------------------|---------|---------|
| Días de Crédito | `dias_de_credito`, `dias_credito` | Número | 30 |
| Fecha de Pago | `fecha_pago`, `fecha_de_pago` | Date | 15/08/2024 |
| Fecha Vencimiento | `fecha_vencimiento` | Date | 14/09/2024 |
| Línea de Negocio | `linea_negocio`, `linea_de_negocio` | Texto | Herramientas |
| Vendedor | `vendedor`, `agente` | Texto | María García |
| Estatus | `estatus`, `status` | Texto | Vencido |

---

### 📝 Notas Importantes:

1. **Nombres de columnas:** El sistema acepta múltiples variantes (con/sin acentos, espacios, mayúsculas)
2. **Nombres de hojas CxC:** Deben ser EXACTAMENTE `CXC VIGENTES` y `CXC VENCIDAS`
3. **Cálculo automático:** Si no existe `dias_vencido`, el sistema lo calcula desde `fecha_pago + dias_credito`
4. **Formato CONTPAQi:** Detectado automáticamente (salta primeras 3 filas)
5. **Hoja X AGENTE:** Si existe, genera automáticamente columnas `año` y `mes` desde `fecha`

---

## 📌 Índice Detallado

1. [Formatos de Archivo Soportados](#formatos-de-archivo-soportados)
2. [Archivo de Ventas](#archivo-de-ventas)
3. [Archivo de Cuentas por Cobrar (CxC)](#archivo-de-cuentas-por-cobrar-cxc)
4. [Detección Automática de Formatos](#detección-automática-de-formatos)
5. [Reglas de Negocio](#reglas-de-negocio)
6. [Validaciones del Sistema](#validaciones-del-sistema)
7. [Ejemplos Completos](#ejemplos-completos)
8. [Checklist de Validación](#checklist-de-validación)

---

## 1. Formatos de Archivo Soportados

### ✅ Archivos Aceptados

| Tipo | Extensiones | Uso |
|------|-------------|-----|
| **CSV** | `.csv` | Ventas únicamente |
| **Excel** | `.xlsx`, `.xls` | Ventas y CxC |

### ⚠️ Consideraciones

- **Codificación CSV:** UTF-8 preferentemente
- **Separadores CSV:** Coma (`,`) o punto y coma (`;`)
- **Tamaño máximo:** No hay límite técnico, pero archivos >50MB pueden ser lentos
- **Formato CONTPAQi:** Detectado y procesado automáticamente

---

## 2. Archivo de Ventas

### 📊 Estructura General

**Nombre sugerido:** `ventas_YYYY-MM.xlsx` o `ventas_YYYY-MM.csv`

**Hojas aceptadas (si es Excel multi-hoja):**
- `X AGENTE` (prioridad alta - procesada primero)
- Cualquier hoja con datos de ventas si no existe `X AGENTE`
- Si tiene múltiples hojas, el usuario selecciona cuál usar

---

### 📑 Columnas Requeridas (OBLIGATORIAS)

#### 1️⃣ **Fecha de Transacción**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `fecha` |
| **Formato esperado** | Fecha Excel (`2024-01-15`, `15/01/2024`, etc.) |
| **Tipo de dato** | DateTime |
| **Validación** | Convertido automáticamente con `pd.to_datetime()` |
| **Comportamiento NaT** | Los registros con fecha inválida se excluyen de análisis temporales |

**Importante:**
- Si la hoja es `X AGENTE` y contiene la columna `fecha`, el sistema genera automáticamente:
  - `año` = Año extraído de fecha
  - `mes` = Mes numérico extraído de fecha

#### 2️⃣ **Importe/Monto de Venta**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna aceptados** | `valor_usd` *(preferido)*, `ventas_usd`, `ventas_usd_con_iva`, `importe`, `valor`, `venta`, `monto_usd`, `total_usd`, `valor_mn` |
| **Formato esperado** | Número decimal positivo |
| **Tipo de dato** | Float/Numeric |
| **Separador decimal** | Punto (`.`) o coma (`,`) |
| **Símbolos aceptados** | `$`, `,` se eliminan automáticamente |
| **Validación** | Convertido con `pd.to_numeric(errors='coerce')` |
| **Valores nulos** | Reemplazados por `0` |

**Orden de prioridad de detección:**
1. `ventas_usd_con_iva`
2. `ventas_usd`
3. `importe`
4. `valor_usd`
5. `monto_usd`
6. `total_usd`
7. `valor`
8. `venta`

---

### 📑 Columnas Opcionales (Mejoran funcionalidad)

#### 3️⃣ **Año y Mes**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `año`, `anio`, `mes` |
| **Formato esperado** | Entero (año: 2024, mes: 1-12) |
| **Generación automática** | Si existen `fecha`, se extraen automáticamente |
| **Validación** | Si no existen ni `fecha`, el módulo comparativo no funcionará |

#### 4️⃣ **Línea de Negocio / Producto**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `linea_producto`, `linea_prodcucto` *(con typo)*, `linea_de_negocio`, `linea producto`, `linea_de_producto`, `linea` |
| **Formato esperado** | Texto |
| **Tipo de dato** | String |
| **Uso** | Heatmap de ventas, segmentación por línea |
| **Validación** | Si no existe, heatmap no se genera |

#### 5️⃣ **Cliente**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `cliente`, `razon_social`, `deudor`, `nombre_cliente` |
| **Formato esperado** | Texto |
| **Tipo de dato** | String |
| **Uso** | Análisis por cliente, reportes detallados |
| **Normalización** | Espacios múltiples eliminados, mayúsculas/minúsculas normalizadas |

#### 6️⃣ **Vendedor / Agente**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `vendedor`, `agente`, `ejecutivo`, `vendedor_asignado` |
| **Formato esperado** | Texto |
| **Tipo de dato** | String |
| **Uso** | Análisis por agente comercial |

#### 7️⃣ **Producto Específico**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `producto`, `articulo`, `item`, `descripcion`, `producto_nombre` |
| **Formato esperado** | Texto |
| **Tipo de dato** | String |
| **Uso** | Heatmap de productos específicos |

---

### ✅ Ejemplo Completo: Estructura de Ventas

```excel
| fecha      | valor_usd | linea_producto      | cliente        | vendedor | producto              |
|------------|-----------|---------------------|----------------|----------|-----------------------|
| 2024-01-15 | 15000.50  | Electrodomésticos   | ACME Corp      | Juan P.  | Refrigerador LG 500L  |
| 2024-01-20 | 8500.00   | Ferretería          | Tech Solutions | María G. | Taladro Industrial    |
| 2024-01-22 | 12300.75  | Línea Blanca        | Constructora X | Juan P.  | Lavadora Samsung 15kg |
| 2024-02-05 | 6700.00   | Herramientas        | ACME Corp      | Carlos R.| Juego Llaves          |
```

**Estructura mínima funcional:**
```excel
| fecha      | valor_usd |
|------------|-----------|
| 2024-01-15 | 15000.50  |
| 2024-01-20 | 8500.00   |
```

---

## 3. Archivo de Cuentas por Cobrar (CxC)

### 🏦 Estructura General

**Nombre sugerido:** `cxc_YYYY-MM.xlsx`

**Formato requerido:** Excel (`.xlsx`) con **DOS HOJAS OBLIGATORIAS**

---

### 📑 Hojas Requeridas (OBLIGATORIO)

#### ✅ Hoja 1: `CXC VIGENTES`
Contiene todas las cuentas por cobrar que aún no han vencido.

#### ✅ Hoja 2: `CXC VENCIDAS`
Contiene todas las cuentas por cobrar que ya vencieron.

**⚠️ IMPORTANTE:**
- Los nombres de las hojas deben ser **EXACTAMENTE** como se especifica (mayúsculas/minúsculas)
- Si falta alguna de las dos hojas, el módulo CxC no funcionará
- El sistema combina automáticamente ambas hojas para el análisis

---

### 📑 Columnas Requeridas (OBLIGATORIAS en ambas hojas)

#### 1️⃣ **Cliente / Deudor**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `cliente` *(prioridad 1)*, `razon_social` *(prioridad 2)*, `deudor`, `nombre_cliente` |
| **Formato esperado** | Texto |
| **Tipo de dato** | String |
| **Comportamiento** | Si existe `cliente`, se renombra a `deudor` internamente. Si existe `razon_social` y no `cliente`, se usa como `deudor` |
| **Validación** | Si no existe ninguna de estas columnas, el módulo muestra error |

**Regla especial:**
- **Columna F (Cliente) tiene prioridad** sobre `razon_social`
- Si coexisten ambas, se usa `cliente` y se elimina `razon_social`

#### 2️⃣ **Saldo Adeudado**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombre de columna** | `saldo_adeudado` (exacto) |
| **Formato esperado** | Número decimal positivo |
| **Tipo de dato** | Float/Numeric |
| **Símbolos aceptados** | `$`, `,` se eliminan automáticamente |
| **Validación** | Convertido con limpieza de caracteres no numéricos |
| **Valores negativos** | Aceptados (pueden indicar saldos a favor) |

---

### 📑 Columnas Opcionales (Alta Prioridad para Cálculos)

#### 3️⃣ **Días de Crédito**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `dias_de_credito`, `dias_credito`, `dias_de_credit`, `dias_credit` |
| **Formato esperado** | Entero positivo (30, 45, 60, 90, etc.) |
| **Tipo de dato** | Integer |
| **Uso** | Cálculo de fecha de vencimiento y días de atraso |
| **Valor por defecto** | Si no existe, algunos cálculos se omiten |

#### 4️⃣ **Fecha de Pago / Fecha Tentativa**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `fecha_de_pago`, `fecha_pago`, `fecha_tentativa_de_pag`, `fecha_tentativa_de_pago` |
| **Formato esperado** | Fecha Excel |
| **Tipo de dato** | DateTime |
| **Uso** | Cálculo de vencimiento: `fecha_pago + dias_credito` |
| **Validación** | Convertido con `pd.to_datetime()` |

#### 5️⃣ **Días Vencidos** (Hoja `CXC VENCIDAS` principalmente)

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombre de columna** | `dias_vencido` |
| **Formato esperado** | Entero (puede ser positivo o negativo) |
| **Tipo de dato** | Integer |
| **Uso** | Clasificación de antigüedad de saldos |
| **Cálculo automático** | Si no existe, el sistema lo calcula desde otras fuentes |

**Fuentes alternativas para calcular días vencidos (en orden de prioridad):**
1. Columna `dias_vencido` directa
2. Columna `dias_restante` (se invierte: `dias_vencido = -dias_restante`)
3. Columna `fecha_vencimiento`: `dias_vencido = (HOY - fecha_vencimiento).days`
4. Columnas `fecha_pago + credito_dias`: `vencimiento = fecha_pago + dias_credito`, luego `dias_vencido = (HOY - vencimiento).days`

#### 6️⃣ **Estatus del Documento**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `estatus`, `status`, `pagado` |
| **Formato esperado** | Texto |
| **Valores reconocidos** | `Pagado`, `Pago`, `Cobrado`, `Liquidado` (mayúsculas/minúsculas ignoradas) |
| **Uso** | Exclusión de registros pagados del análisis |
| **Validación** | Si contiene "pag" (case-insensitive), se marca como pagado |

#### 7️⃣ **Fecha de Vencimiento**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombre de columna** | `fecha_vencimiento` |
| **Formato esperado** | Fecha Excel |
| **Tipo de dato** | DateTime |
| **Uso** | Cálculo directo de días vencidos |

#### 8️⃣ **Línea de Negocio**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `linea_negocio`, `linea_de_negocio`, `linea_producto`, `linea` |
| **Formato esperado** | Texto |
| **Tipo de dato** | String |
| **Uso** | Segmentación de CxC por línea |
| **Normalización** | Se renombra a `linea_negocio` internamente |

#### 9️⃣ **Vendedor**

| Concepto | Valores aceptados |
|----------|-------------------|
| **Nombres de columna** | `vendedor`, `agente`, `ejecutivo` |
| **Formato esperado** | Texto |
| **Tipo de dato** | String |
| **Uso** | Análisis de cobranza por agente |

---

### ✅ Ejemplo Completo: Estructura CxC

**Hoja: `CXC VIGENTES`**
```excel
| cliente        | saldo_adeudado | dias_de_credito | fecha_pago | linea_negocio      | vendedor |
|----------------|----------------|-----------------|------------|--------------------|----------|
| ACME Corp      | 50000.00       | 30              | 2024-02-15 | Electrodomésticos  | Juan P.  |
| Tech Solutions | 25000.50       | 45              | 2024-03-01 | Ferretería         | María G. |
| Constructora X | 18000.00       | 60              | 2024-03-20 | Línea Blanca       | Juan P.  |
```

**Hoja: `CXC VENCIDAS`**
```excel
| cliente       | saldo_adeudado | dias_vencido | dias_de_credito | fecha_pago | linea_negocio |
|---------------|----------------|--------------|-----------------|------------|---------------|
| Old Client    | 100000.00      | 120          | 30              | 2023-10-15 | Herramientas  |
| Late Company  | 35000.00       | 60           | 45              | 2023-11-20 | Ferretería    |
| Slow Payer    | 15000.00       | 15           | 30              | 2023-12-25 | Línea Blanca  |
```

**Estructura mínima funcional:**

**Hoja: `CXC VIGENTES`**
```excel
| cliente     | saldo_adeudado |
|-------------|----------------|
| ACME Corp   | 50000.00       |
| Tech Inc    | 25000.50       |
```

**Hoja: `CXC VENCIDAS`**
```excel
| cliente      | saldo_adeudado | dias_vencido |
|--------------|----------------|--------------|
| Old Client   | 100000.00      | 120          |
| Late Company | 35000.00       | 60           |
```

---

## 4. Detección Automática de Formatos

### 🔍 Formato CONTPAQi

El sistema detecta automáticamente archivos exportados desde CONTPAQi.

**Características detectadas:**
- Primera celda (A1) contiene texto "contpaqi" (case-insensitive)
- Primeras 3 filas son encabezados/metadatos

**Comportamiento:**
```python
if primera_celda.lower().contains("contpaqi"):
    skiprows = 3  # Salta las 3 primeras filas
```

**Resultado visible:**
```
📌 Archivo CONTPAQi detectado. Saltando primeras 3 filas.
```

---

### 📑 Hoja `X AGENTE` (Prioridad Especial)

Si el archivo Excel contiene múltiples hojas y una se llama **`X AGENTE`**:

**Comportamiento especial:**
1. Se procesa automáticamente como hoja principal
2. Si contiene columna `fecha`:
   - Se genera `año = fecha.dt.year`
   - Se genera `mes = fecha.dt.month`
3. Se muestra mensaje de confirmación

**Mensaje visible:**
```
✅ Hoja 'X AGENTE' detectada y seleccionada automáticamente.
✅ Columnas virtuales 'año' y 'mes' generadas correctamente desde 'fecha' en X AGENTE.
```

---

### 🔄 Normalización Automática de Columnas

**Todos** los encabezados de columnas se normalizan automáticamente:

```python
def normalizar_columnas(df):
    nuevas_columnas = []
    for col in df.columns:
        col_str = str(col).lower()          # Minúsculas
        col_str = col_str.strip()           # Sin espacios extremos
        col_str = col_str.replace(" ", "_") # Espacios → guiones bajos
        col_str = unidecode(col_str)        # Elimina acentos (ñ → n, á → a)
        nuevas_columnas.append(col_str)
    df.columns = nuevas_columnas
    return df
```

**Ejemplos de transformación:**

| Original | Normalizado |
|----------|-------------|
| `Fecha de Pago` | `fecha_de_pago` |
| `VALOR USD` | `valor_usd` |
| `Línea de Negocio` | `linea_de_negocio` |
| `Días de Crédito` | `dias_de_credito` |
| `Razón Social` | `razon_social` |
| `  Cliente  ` | `cliente` |

---

## 5. Reglas de Negocio

### 📊 Módulo de Ventas

#### ✅ Cálculo de Totales
```
Total Ventas = SUM(valor_usd WHERE valor_usd > 0)
```

#### ✅ Ticket Promedio
```
Ticket Promedio = Total Ventas / COUNT(registros)
```

#### ✅ Filtrado por Fecha
- Si `fecha` es inválida (NaT), el registro se excluye de análisis temporales
- Rango de fechas configurable vía sidebar

#### ✅ Agrupaciones
- **Mensual:** `fecha.dt.to_period('M')`
- **Trimestral:** `fecha.dt.to_period('Q')`
- **Anual:** `fecha.dt.year`

---

### 🏦 Módulo de CxC

#### ✅ Exclusión de Pagados

**Antes de cualquier cálculo:**
```python
# Se excluyen registros donde estatus contiene "pag" (case-insensitive)
mask_pagado = df['estatus'].str.contains('pag', case=False, na=False)
df_no_pagados = df[~mask_pagado]
```

#### ✅ Cálculo de Días Vencidos

**Algoritmo de prioridad:**
1. Si existe `dias_vencido` → usar directo
2. Si existe `dias_restante` → `dias_vencido = -dias_restante`
3. Si existe `fecha_vencimiento` → `dias_vencido = (HOY - fecha_vencimiento).days`
4. Si existen `fecha_pago + dias_credito`:
   ```python
   fecha_vencimiento = fecha_pago + timedelta(days=dias_credito)
   dias_vencido = (datetime.now() - fecha_vencimiento).days
   ```
5. Si no hay datos → `dias_vencido = 0` (asumido vigente)

#### ✅ Clasificación de Antigüedad de Saldos

```python
BINS_ANTIGUEDAD = [0, 30, 60, 90, 120, 180, float('inf')]
LABELS_ANTIGUEDAD = [
    '0-30 días',
    '31-60 días', 
    '61-90 días',
    '91-120 días',
    '121-180 días',
    '>180 días'
]
```

#### ✅ Score de Salud Financiera

**Fórmula:**
```
Score = (Cartera_Vigente / Cartera_Total) * 0.7 + 
        (1 - Cartera_Critica / Cartera_Total) * 0.3
```

Donde:
- `Cartera_Vigente` = saldos con `dias_vencido <= 0`
- `Cartera_Critica` = saldos con `dias_vencido > 90`

**Clasificación:**
- **80-100:** Excelente (🟢)
- **60-79:** Bueno (🟢)
- **40-59:** Regular (🟡)
- **20-39:** Malo (🟠)
- **0-19:** Crítico (🔴)

#### ✅ Umbrales de Riesgo

```python
CRITICO_MONTO = 50,000 USD
ALTO_RIESGO_MONTO = 100,000 USD
DIAS_ALTO_RIESGO = 90 días
DIAS_DETERIORO_SEVERO = 120 días
DIAS_INCOBRABILIDAD = 180 días
```

#### ✅ Métricas Clave

**DSO (Days Sales Outstanding):**
```
DSO = (Cuentas por Cobrar / Ventas Anuales) * 365
```

**Rotación de CxC:**
```
Rotación = Ventas Anuales / Cuentas por Cobrar Promedio
```

**Índice de Morosidad:**
```
Morosidad = (Cartera Vencida / Cartera Total) * 100
```

---

## 6. Validaciones del Sistema

### ✅ Validaciones en Carga de Archivo

#### Ventas

```python
# 1. Validar extensión
if not archivo.name.endswith(('.csv', '.xlsx')):
    ERROR: "Formato no soportado"

# 2. Validar columna de ventas
columnas_ventas = ["valor_usd", "ventas_usd", "importe", ...]
if none found:
    WARNING: "No se detectó columna de ventas estándar"
    SHOW: Lista de columnas disponibles

# 3. Validar columna fecha
if "fecha" in df.columns:
    df["fecha"] = pd.to_datetime(df["fecha"], errors='coerce')
    if df["fecha"].isna().all():
        WARNING: "Todas las fechas son inválidas"
```

#### CxC

```python
# 1. Validar extensión
if not archivo.name.endswith(('.xls', '.xlsx')):
    ERROR: "Solo se aceptan archivos Excel para el reporte de deudas"

# 2. Validar hojas requeridas
if "CXC VIGENTES" not in hojas or "CXC VENCIDAS" not in hojas:
    ERROR: "No se encontraron las hojas requeridas: 'CXC VIGENTES' y 'CXC VENCIDAS'"

# 3. Validar columna saldo
if 'saldo_adeudado' not in df.columns:
    ERROR: "No existe columna de saldo en los datos"
    SHOW: Columnas disponibles

# 4. Validar columna cliente
if 'deudor' not in df.columns:
    ERROR: "No se encontró columna para identificar deudores"
    INFO: "Se esperaba 'cliente' o 'razon_social' en los encabezados"
```

---

### ⚠️ Errores Comunes y Soluciones

| Error | Causa | Solución |
|-------|-------|----------|
| "No se encontró columna de ventas" | Nombre de columna no reconocido | Renombrar a `valor_usd`, `ventas_usd` o `importe` |
| "No se encontraron hojas CXC" | Nombres de hojas incorrectos | Renombrar exactamente a `CXC VIGENTES` y `CXC VENCIDAS` |
| "No existe columna de saldo" | Columna no se llama `saldo_adeudado` | Renombrar a `saldo_adeudado` |
| "Todas las fechas son inválidas" | Formato de fecha no reconocido | Usar formato Excel estándar (DD/MM/YYYY) |
| "No se detectó formato CONTPAQi" | Archivo tiene filas extra al inicio | Asegurar que celda A1 contenga "contpaqi" |

---

## 7. Ejemplos Completos

### 📊 Ejemplo 1: Archivo de Ventas Básico (CSV)

**Archivo:** `ventas_enero_2024.csv`

```csv
fecha,valor_usd,linea_producto,cliente
2024-01-05,12500.00,Electrodomésticos,ACME Corporation
2024-01-10,8300.50,Ferretería,Tech Solutions SA
2024-01-15,15000.00,Línea Blanca,Constructora del Norte
2024-01-20,9500.00,Herramientas,ACME Corporation
2024-01-25,11200.75,Electrodomésticos,Distribuidora Central
```

**Resultado:** ✅ Funciona perfectamente
- Dashboard principal con KPIs
- Comparativo mensual/anual
- Heatmap por línea de producto

---

### 📊 Ejemplo 2: Archivo de Ventas Completo (Excel)

**Archivo:** `ventas_2024_completo.xlsx`

**Hoja: X AGENTE**

| fecha      | valor_usd | linea_producto      | cliente            | vendedor  | producto                |
|------------|-----------|---------------------|--------------------|-----------|-------------------------|
| 2024-01-05 | 12500.00  | Electrodomésticos   | ACME Corporation   | Juan P.   | Refrigerador Samsung    |
| 2024-01-10 | 8300.50   | Ferretería          | Tech Solutions SA  | María G.  | Taladro Makita          |
| 2024-01-15 | 15000.00  | Línea Blanca        | Constructora Norte | Carlos R. | Lavadora LG 18kg        |
| 2024-02-01 | 9500.00   | Herramientas        | ACME Corporation   | Juan P.   | Set Llaves Craftsman    |
| 2024-02-14 | 11200.75  | Electrodomésticos   | Distribuidora      | María G.  | Microondas Whirlpool    |

**Resultado:** ✅ Funcionalidad completa
- Detección automática de hoja `X AGENTE`
- Generación automática de columnas `año` y `mes`
- Análisis por vendedor
- Heatmap por producto específico

---

### 🏦 Ejemplo 3: Archivo CxC Completo

**Archivo:** `cxc_diciembre_2024.xlsx`

**Hoja 1: CXC VIGENTES**

| cliente            | saldo_adeudado | dias_de_credito | fecha_pago | linea_negocio      | vendedor  |
|--------------------|----------------|-----------------|------------|--------------------|-----------|
| ACME Corporation   | 50000.00       | 30              | 2024-12-20 | Electrodomésticos  | Juan P.   |
| Tech Solutions SA  | 25000.50       | 45              | 2025-01-15 | Ferretería         | María G.  |
| Constructora Norte | 18000.00       | 60              | 2025-02-01 | Línea Blanca       | Carlos R. |
| Distribuidora Mx   | 32000.00       | 30              | 2024-12-25 | Herramientas       | Juan P.   |

**Hoja 2: CXC VENCIDAS**

| cliente              | saldo_adeudado | dias_vencido | dias_de_credito | fecha_pago | linea_negocio |
|----------------------|----------------|--------------|-----------------|------------|---------------|
| Old Client Corp      | 100000.00      | 120          | 30              | 2024-08-15 | Herramientas  |
| Late Payments SA     | 35000.00       | 60           | 45              | 2024-10-01 | Ferretería    |
| Slow Payer Inc       | 15000.00       | 15           | 30              | 2024-11-25 | Línea Blanca  |
| Deudor Antiguo Ltda  | 85000.00       | 180          | 60              | 2024-06-15 | Electrodomésticos |

**Resultado:** ✅ Dashboard CxC completo
- Score de salud: calculado automáticamente
- Tabla de antigüedad de saldos
- Semáforos de riesgo por cliente
- Top 10 clientes con mayor saldo
- Análisis por línea de negocio
- Prioridades de cobranza

---

### 🏦 Ejemplo 4: Archivo CxC Mínimo (Sin días vencidos)

**Archivo:** `cxc_basico.xlsx`

**Hoja 1: CXC VIGENTES**

| cliente         | saldo_adeudado | fecha_pago | dias_de_credito |
|-----------------|----------------|------------|-----------------|
| Cliente A       | 25000.00       | 2024-12-20 | 30              |
| Cliente B       | 15000.00       | 2025-01-15 | 45              |

**Hoja 2: CXC VENCIDAS**

| cliente         | saldo_adeudado | fecha_pago | dias_de_credito |
|-----------------|----------------|------------|-----------------|
| Cliente C       | 50000.00       | 2024-06-15 | 30              |
| Cliente D       | 12000.00       | 2024-09-01 | 45              |

**Resultado:** ✅ Funciona con cálculo automático
- `dias_vencido` se calcula automáticamente:
  - Cliente A: `(HOY - (2024-12-20 + 30 días)).days` = -X días (vigente)
  - Cliente C: `(HOY - (2024-06-15 + 30 días)).days` = ~180 días (vencido)

---

### 🔍 Ejemplo 5: Archivo CONTPAQi

**Archivo:** `reporte_contpaqi_enero.xlsx`

**Estructura:**

```
| Fila 1: CONTPAQI i - Reporte de Ventas
| Fila 2: Empresa: FRADMA SA de CV
| Fila 3: Periodo: Enero 2024
| Fila 4: fecha | valor_usd | linea_producto | cliente
| Fila 5: 2024-01-05 | 12500.00 | Electrodomésticos | ACME Corp
| Fila 6: ...
```

**Resultado:** ✅ Detección automática
- Sistema detecta "contpaqi" en fila 1
- Salta automáticamente las primeras 3 filas
- Procesa desde fila 4 en adelante
- Mensaje: "📌 Archivo CONTPAQi detectado. Saltando primeras 3 filas."

---

## 8. Checklist de Validación

### ✅ Antes de Subir Archivo de Ventas

- [ ] Formato: CSV o Excel (.xlsx)
- [ ] Contiene columna `fecha` con fechas válidas
- [ ] Contiene al menos una columna de ventas (`valor_usd`, `ventas_usd`, `importe`)
- [ ] Valores numéricos en columna de ventas
- [ ] Sin filas completamente vacías al inicio (excepto si es CONTPAQi)
- [ ] Encabezados en primera fila (o fila 4 si es CONTPAQi)
- [ ] (Opcional pero recomendado) Contiene `linea_producto` para heatmap
- [ ] (Opcional) Contiene `cliente` y `vendedor` para análisis detallado

### ✅ Antes de Subir Archivo de CxC

- [ ] Formato: Excel (.xlsx) obligatorio
- [ ] Contiene hoja llamada exactamente `CXC VIGENTES`
- [ ] Contiene hoja llamada exactamente `CXC VENCIDAS`
- [ ] Ambas hojas tienen columna `cliente` o `razon_social`
- [ ] Ambas hojas tienen columna `saldo_adeudado` con valores numéricos
- [ ] (Recomendado) Incluye `dias_de_credito` y `fecha_pago`
- [ ] Hoja `CXC VENCIDAS` incluye `dias_vencido` (o datos para calcularlo)
- [ ] Sin filas vacías al inicio de cada hoja
- [ ] Encabezados en primera fila de cada hoja

### ✅ Post-Carga: Validaciones Visuales

**Después de subir el archivo, verificar:**

1. **Mensaje de éxito:**
   ```
   ✅ Archivo cargado: nombre_archivo.xlsx
   📊 X registros | Y columnas
   ```

2. **Sidebar muestra:**
   - Nombre del archivo
   - Número de registros
   - Número de columnas

3. **Si hay warnings:**
   - Expandir sección "🔍 Ver columnas disponibles"
   - Verificar que columnas clave estén listadas
   - Si falta columna crítica, renombrar en Excel y recargar

4. **Dashboard muestra datos:**
   - Gráficos se generan correctamente
   - Tablas muestran valores numéricos reales (no NaN)
   - Fechas se muestran en formato correcto

---

## 📞 Soporte y Resolución de Problemas

### 🐛 Si el archivo no carga

1. **Verificar extensión:** Solo `.csv`, `.xlsx`, `.xls`
2. **Verificar tamaño:** Archivos muy grandes (>100MB) pueden fallar
3. **Verificar encoding (CSV):** Debe ser UTF-8
4. **Abrir en Excel:** Asegurar que el archivo no está corrupto

### 🐛 Si no se generan gráficos

1. **Verificar columnas:** Expandir "🔍 Ver columnas disponibles"
2. **Verificar tipos de datos:** 
   - Fechas deben ser reconocidas como Date en Excel
   - Números deben estar en formato numérico (no texto)
3. **Verificar contenido:** Al menos 1 registro válido es necesario

### 🐛 Si CxC no funciona

1. **Verificar nombres de hojas:** Deben ser exactos (copiar/pegar recomendado):
   - `CXC VIGENTES`
   - `CXC VENCIDAS`
2. **Verificar columna `saldo_adeudado`:** Debe existir con ese nombre exacto
3. **Verificar columna cliente:** Debe llamarse `cliente` o `razon_social`

### 🐛 Si aparece "Todas las fechas son inválidas"

1. Abrir Excel y verificar formato de columna `fecha`
2. Cambiar formato a "Fecha" (DD/MM/YYYY)
3. Si dice "Texto", copiar columna → Pegar Especial → Valores
4. Guardar y recargar

---

## 📚 Recursos Adicionales

- **Código fuente:** [`utils/constantes.py`](utils/constantes.py) - Lista completa de columnas aceptadas
- **Documentación técnica:** [`ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Tests de integración:** [`tests/integration/test_pipeline_cxc.py`](tests/integration/test_pipeline_cxc.py)
- **Guía de contribución:** [`CONTRIBUTING.md`](CONTRIBUTING.md)

---

## 📝 Historial de Cambios

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0 | Enero 2026 | Documento inicial completo |

---

## 📧 Contacto

Para dudas sobre la estructura de los archivos Excel o problemas con la carga de datos, contactar al propietario del repositorio: **@B10sp4rt4n**

---

**Fin del documento**

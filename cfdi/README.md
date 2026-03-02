# 📄 Módulo CFDI Parser → Neon PostgreSQL

## 🎯 Objetivo

Parsear XMLs de CFDI 4.0 (facturas electrónicas mexicanas) y almacenarlos en base de datos Neon PostgreSQL para:
- Eliminar fricción de setup (upload XML una vez, dashboard para siempre)
- Garantizar precisión fiscal (datos oficiales del SAT)
- Permitir históricos ilimitados (XMLs desde 2014 disponibles)
- Construir benchmarks sectoriales con datos agregados

---

## 📁 Estructura del Módulo

```
cfdi/
├── __init__.py              # Módulo principal
├── parser.py                # Parser de CFDI 4.0 y complementos
├── neon_schema.sql          # Schema de base de datos
├── ingestion.py             # ✅ Lógica de ingesta a Neon
├── enrichment.py            # ✅ Enriquecimiento con IA
└── README.md                # Esta documentación

main/
└── ingesta_cfdi.py          # ✅ UI Streamlit para upload ZIP

examples/
├── test_parser.py           # CLI para parsear un CFDI
└── ingest_cfdi_to_neon.py   # ✅ Ingesta completa XML → Neon
```

---

## 🚀 Quick Start

### 1. Instalar dependencias

```bash
pip install lxml psycopg2-binary python-dotenv
```

### 2. Configurar Neon Database

```bash
# Crear cuenta en https://neon.tech
# Crear proyecto y base de datos

# Ejecutar schema
psql $DATABASE_URL -f cfdi/neon_schema.sql
```

### 3. Parsear un CFDI de ejemplo

```python
from cfdi.parser import CFDIParser

parser = CFDIParser()
datos = parser.parse_cfdi_venta('path/to/factura.xml')

print(f"UUID: {datos['timbre']['uuid']}")
print(f"Cliente: {datos['receptor']['nombre']}")
print(f"Total: ${datos['total']:.2f} {datos['moneda']}")
```

### 4. Ingesta completa a Neon (desde ZIP o carpeta)

```bash
# Opción 1: Desde un ZIP de XMLs
python examples/ingest_cfdi_to_neon.py \
    --xml-zip /ruta/a/facturas_2025.zip \
    --empresa-id 1 \
    --neon-url "postgresql://user:pass@ep-xyz.us-east-2.aws.neon.tech/fradma?sslmode=require"

# Opción 2: Desde una carpeta local
python examples/ingest_cfdi_to_neon.py \
    --xml-folder /ruta/a/cfdi_xmls/ \
    --empresa-id 1 \
    --neon-url "postgresql://user:pass@ep-xyz.us-east-2.aws.neon.tech/fradma?sslmode=require"
```

**Output esperado:**
```
============================================================
📊 RESUMEN DE INGESTA
============================================================
Total XMLs procesados:    1,247
✅ Insertados correctamente: 1,195
⚠️  Duplicados (saltados):    42
❌ Errores:                  10
============================================================

============================================================
📈 ESTADÍSTICAS EMPRESA ID 1
============================================================
Total CFDIs almacenados:  5,234
Total conceptos:          18,923
Total pagos registrados:  3,456

Rango de fechas:
  Primer CFDI: 2020-01-15
  Último CFDI: 2025-02-25

Total facturado por moneda:
  MXN: $45,234,567.00
  USD: $123,456.00
============================================================
```

### 5. Uso programático con Python

```python
from cfdi.parser import CFDIParser, parse_cfdi_batch
from cfdi.ingestion import NeonIngestion

# Configurar conexión a Neon
NEON_URL = "postgresql://user:pass@host/db?sslmode=require"

# Parsear XMLs
parser = CFDIParser()
ventas = []

for xml_file in ['factura1.xml', 'factura2.xml', 'factura3.xml']:
    with open(xml_file, 'r') as f:
        xml_content = f.read()
    venta = parser.parse_cfdi_venta(xml_content)
    ventas.append(venta)

# Insertar en Neon
with NeonIngestion(NEON_URL) as ingestion:
    stats = ingestion.insert_ventas_batch(
        empresa_id=1,
        ventas_list=ventas,
        skip_duplicates=True
    )
    
    print(f"✅ {stats['insertados']} CFDIs insertados")
    print(f"⚠️ {stats['duplicados']} duplicados")
    print(f"❌ {stats['errores']} errores")
    
    # Obtener estadísticas de la empresa
    empresa_stats = ingestion.get_empresa_stats(empresa_id=1)
    print(f"Total acumulado: {empresa_stats['total_cfdis']} CFDIs")
```

---

## 💾 Configuración de Neon PostgreSQL

### 1. Crear proyecto en Neon

1. Ir a https://neon.tech y crear cuenta gratuita
2. Crear nuevo proyecto: `fradma-dashboard`
3. Seleccionar región: `US East (Ohio)` o `AWS us-east-2`
4. Copiar la connection string (formato: `postgresql://user:pass@host/db`)

### 2. Ejecutar schema inicial

```bash
# Conectar a Neon y crear tablas
psql $NEON_URL -f cfdi/neon_schema.sql
```

**Verificar instalación:**
```sql
-- Debe retornar 6 tablas
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public';

-- Output esperado:
-- empresas
-- cfdi_ventas
-- cfdi_conceptos
-- cfdi_pagos
-- clientes_master
-- benchmarks_industria
```

### 3. Crear empresa de prueba

```sql
INSERT INTO empresas (
    nombre_comercial,
    rfc,
    plan,
    industria,
    tamanio
) VALUES (
    'Mi Distribuidora SA de CV',
    'MDI123456ABC',
    'business',
    'distribucion_materiales',
    'mediana'
) RETURNING id;

-- Usar el ID retornado para --empresa-id en el script de ingesta
```

### 4. Variables de entorno (recomendado)

```bash
# .env
NEON_DATABASE_URL="postgresql://user:pass@ep-xyz.us-east-2.aws.neon.tech/fradma?sslmode=require"
EMPRESA_ID=1
```

```python
# En tu código
import os
from dotenv import load_dotenv

load_dotenv()
NEON_URL = os.getenv('NEON_DATABASE_URL')
EMPRESA_ID = int(os.getenv('EMPRESA_ID'))
```

---

## 🔍 Queries Útiles

### Ver últimas facturas insertadas

```sql
SELECT 
    uuid,
    fecha_emision,
    receptor_nombre,
    total,
    moneda
FROM cfdi_ventas
WHERE empresa_id = 1
ORDER BY fecha_emision DESC
LIMIT 10;
```

### Ventas totales por mes

```sql
SELECT 
    DATE_TRUNC('month', fecha_emision) as mes,
    COUNT(*) as num_facturas,
    SUM(total) as total_facturado,
    moneda
FROM cfdi_ventas
WHERE empresa_id = 1
GROUP BY mes, moneda
ORDER BY mes DESC;
```

### Clientes con mayor cartera vencida

```sql
SELECT * FROM v_cartera_clientes
WHERE empresa_id = 1
  AND saldo_pendiente > 0
ORDER BY dias_promedio_cobro DESC
LIMIT 20;
```

### Top productos vendidos

```sql
SELECT 
    descripcion,
    COUNT(*) as veces_vendido,
    SUM(cantidad) as cantidad_total,
    SUM(importe) as importe_total
FROM cfdi_conceptos cc
JOIN cfdi_ventas cv ON cc.cfdi_id = cv.id
WHERE cv.empresa_id = 1
  AND cv.fecha_emision >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY descripcion
ORDER BY importe_total DESC
LIMIT 50;
```

---

## � Conciliación Factura-Complemento

### ⚠️ Concepto Crítico: NO sumar Facturas + Complementos

En el sistema CFDI mexicano:
- **Factura (cfdi_ventas)** = Documento que registra la VENTA (monto a cobrar)
- **Complemento de Pago (cfdi_pagos)** = Documento que registra el PAGO recibido

**❌ ERROR COMÚN**: Sumar `cfdi_ventas.total + cfdi_pagos.monto_pagado` → duplica los montos  
**✅ CORRECTO**: Son eventos distintos que se relacionan vía `cfdi_pagos.cfdi_venta_uuid → cfdi_ventas.uuid_sat`

### Escenarios con Datos Incompletos

Durante la carga inicial o cuando la BD está en construcción, pueden ocurrir:

#### 1. **COMPLEMENTOS HUÉRFANOS** (hay pago pero NO factura)
**Causa**: El complemento de pago llegó primero, pero su factura relacionada aún no se cargó en la BD.

**Detección**:
```sql
-- Complementos que apuntan a facturas inexistentes
SELECT 
    p.uuid_complemento,
    p.cfdi_venta_uuid AS uuid_factura_faltante,
    p.fecha_pago,
    p.monto_pagado
FROM cfdi_pagos p
LEFT JOIN cfdi_ventas v ON p.cfdi_venta_uuid = v.uuid_sat
WHERE v.uuid_sat IS NULL;
```

**Acción**: 
- ❌ **NO incluir estos complementos en análisis de cobranza** (datos no confiables)
- ✅ Usar `INNER JOIN` en consultas de cobranza para excluirlos automáticamente
- 🔧 Cargar las facturas faltantes en la BD

#### 2. **FACTURAS SIN COMPLEMENTO** (hay factura pero NO pago)
**Causa**: 
- **Opción A**: Realmente está pendiente de cobro (legítimo)
- **Opción B**: Ya se pagó pero el complemento no está generado/cargado aún

**Detección**:
```sql
-- Facturas a crédito sin complemento registrado
SELECT 
    v.receptor_nombre AS cliente,
    v.folio,
    v.fecha_emision,
    v.total AS monto_original,
    CURRENT_DATE - v.fecha_emision::date AS dias_transcurridos,
    CASE 
        WHEN p.uuid_complemento IS NULL 
        THEN 'PENDIENTE DE CONCILIAR - Puede estar pagado sin complemento cargado'
        ELSE 'OK'
    END AS estado
FROM cfdi_ventas v
LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid
WHERE v.metodo_pago = 'PPD'  -- Pago en parcialidades/diferido
  AND p.uuid_complemento IS NULL
ORDER BY dias_transcurridos DESC;
```

**Acción**:
- ⚠️ **NO asumir automáticamente que está impago**
- ✅ Marcar como "Pendiente de conciliar" con flag de estado
- 🔍 Revisar manualmente o cargar complementos faltantes

### Reglas de Consultas Seguras

Para evitar errores con datos incompletos:

#### ✅ Para VENTAS TOTALES (solo facturas):
```sql
-- Correcto: Solo cfdi_ventas (fuente de verdad de facturación)
SELECT SUM(total * tipo_cambio) AS total_facturado
FROM cfdi_ventas
WHERE fecha_emision >= '2025-01-01';
```

#### ✅ Para COBRANZA REAL (solo pagos válidos):
```sql
-- Correcto: INNER JOIN para excluir complementos huérfanos
SELECT SUM(p.monto_pagado) AS total_cobrado
FROM cfdi_pagos p
INNER JOIN cfdi_ventas v ON p.cfdi_venta_uuid = v.uuid_sat
WHERE p.fecha_pago >= '2025-01-01';
```

#### ✅ Para CARTERA (facturas con estado de conciliación):
```sql
-- Correcto: LEFT JOIN con flags de conciliación
SELECT 
    v.receptor_nombre AS cliente,
    COUNT(DISTINCT v.uuid_sat) AS num_facturas,
    SUM(v.total * v.tipo_cambio) AS total_facturado,
    COALESCE(SUM(p.monto_pagado), 0) AS total_cobrado,
    SUM(v.total * v.tipo_cambio) - COALESCE(SUM(p.monto_pagado), 0) AS saldo_pendiente,
    
    -- Flags de conciliación
    COUNT(p.uuid_complemento) AS facturas_con_complemento,
    COUNT(DISTINCT v.uuid_sat) - COUNT(p.uuid_complemento) AS facturas_sin_conciliar,
    CASE 
        WHEN COUNT(p.uuid_complemento) = 0 THEN 'Sin complementos'
        WHEN COUNT(p.uuid_complemento) < COUNT(DISTINCT v.uuid_sat) THEN 'Conciliación parcial'
        ELSE 'Conciliado'
    END AS estado_conciliacion
    
FROM cfdi_ventas v
LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid
WHERE v.metodo_pago = 'PPD' 
GROUP BY v.receptor_nombre
HAVING SUM(v.total * v.tipo_cambio) - COALESCE(SUM(p.monto_pagado), 0) > 0
ORDER BY saldo_pendiente DESC;
```

### Vista v_cartera_clientes (ya incluye conciliación)

La vista `v_cartera_clientes` ya está preparada para manejar datos incompletos:

```sql
SELECT * FROM v_cartera_clientes
WHERE empresa_id = 1
ORDER BY saldo_pendiente DESC;

-- Columnas incluidas:
-- - facturas_con_complemento: Número de facturas que tienen pago registrado
-- - facturas_sin_conciliar: Número de facturas sin complemento
-- - estado_conciliacion: 'sin_complementos' | 'conciliacion_parcial' | 'conciliado'
```

### Auditoría de Integridad

Para validar la calidad de los datos cargados:

```sql
-- Resumen de registros sin conciliar
WITH huerfanos_pago AS (
    SELECT 
        COUNT(*) AS complementos_sin_factura,
        COALESCE(SUM(monto_pagado), 0) AS monto_sin_factura
    FROM cfdi_pagos p
    LEFT JOIN cfdi_ventas v ON p.cfdi_venta_uuid = v.uuid_sat
    WHERE v.uuid_sat IS NULL
),
facturas_sin_pago AS (
    SELECT 
        COUNT(*) AS facturas_sin_complemento,
        COALESCE(SUM(total), 0) AS monto_sin_complemento
    FROM cfdi_ventas v
    LEFT JOIN cfdi_pagos p ON v.uuid_sat = p.cfdi_venta_uuid
    WHERE v.metodo_pago = 'PPD' 
      AND p.uuid_complemento IS NULL
)
SELECT 
    hp.complementos_sin_factura,
    ROUND(hp.monto_sin_factura, 2) AS monto_complementos_huerfanos,
    fs.facturas_sin_complemento,
    ROUND(fs.monto_sin_complemento, 2) AS monto_facturas_sin_conciliar
FROM huerfanos_pago hp, facturas_sin_pago fs;
```

---

## �📊 Schema de Base de Datos

### Tablas principales:

| Tabla | Descripción | Registros esperados |
|-------|-------------|-------------------|
| `empresas` | Clientes de Fradma | 100-1000 |
| `cfdi_ventas` | Facturas emitidas | 500K-5M |
| `cfdi_conceptos` | Líneas de productos | 2M-20M |
| `cfdi_pagos` | Complementos de pago | 200K-2M |
| `clientes_master` | Catálogo de end-customers | 10K-100K |
| `benchmarks_industria` | Métricas agregadas | 1K-10K |

### Vistas útiles:

- `v_cartera_clientes` - CxC por cliente con días de crédito
- `v_ventas_linea_mes` - Ventas por línea de negocio y mes

---

## 🔄 Flujo de Ingesta

```mermaid
graph LR
    A[Usuario sube ZIP de XMLs] --> B[Parser extrae datos]
    B --> C[Normalización de moneda]
    C --> D[Deduplicación por UUID]
    D --> E[Enriquecimiento con IA]
    E --> F[Insert a Neon]
    F --> G[Dashboard actualizado]
```

### Detalles técnicos:

1. **Upload:** Usuario sube ZIP con 100-5000 XMLs
2. **Validación:** Verificar estructura CFDI 4.0 válida
3. **Parsing:** Extraer datos con `CFDIParser` y `ComplementoPagoParser`
4. **Normalización:** 
   - Convertir monedas a MXN usando tipo de cambio oficial
   - Estandarizar nombres de clientes (similar strings)
5. **Deduplicación:** Verificar UUID no exista ya
6. **Enriquecimiento:**
   - Clasificar línea de negocio con GPT-4 fine-tuned
   - Detectar patrones de estacionalidad
7. **Insert:** Transacción batch a Neon
8. **Post-procesamiento:** Actualizar métricas agregadas

---

## 🤖 Enriquecimiento con IA

El módulo [cfdi/enrichment.py](cfdi/enrichment.py) ofrece clasificación automática y detección de anomalías usando GPT-4.

### 1. Clasificación de líneas de negocio

**14 categorías predefinidas para México:**
- ferreteria_herramientas
- ferreteria_industrial
- materiales_construccion
- plasticos_industriales
- equipos_hidraulicos
- equipos_electricos
- pinturas_recubrimientos
- quimicos_industriales
- seguridad_industrial
- textiles_industriales
- automotriz_refacciones
- empaque_embalaje
- limpieza_industrial
- otro

**Ejemplo de uso:**
```python
from cfdi.enrichment import CFDIEnrichment

# Inicializar con API key de OpenAI
enricher = CFDIEnrichment(api_key="sk-...", model="gpt-4o-mini")

# Clasificar un producto
linea = enricher.clasificar_concepto("Tornillo hexagonal 1/4 x 2 pulgadas")
print(f"Línea: {linea}")  # Output: "ferreteria_industrial"

# Clasificar batch con límite de GPT calls
conceptos = [
    {'descripcion': 'Tornillo', 'importe': 100},
    {'descripcion': 'Cemento 50kg', 'importe': 150},
    {'descripcion': 'Cable eléctrico', 'importe': 200}
]

enriquecidos = enricher.enriquecer_conceptos_batch(
    conceptos,
    usar_gpt=True,
    max_gpt_calls=100  # Límite para controlar costos
)

# Resultado: cada concepto tiene campo 'linea_negocio'
print(enriquecidos[0])
# {'descripcion': 'Tornillo', 'importe': 100, 'linea_negocio': 'ferreteria_industrial'}
```

**Sistema de caché inteligente:**
- Guarda clasificaciones previas para evitar llamadas duplicadas
- Reduce costos hasta 90% en procesamiento repetido
- Exportable/importable para compartir entre sesiones

```python
# Exportar caché
enricher.export_cache('cache_clasificaciones.json')

# Importar en otra sesión
enricher2 = CFDIEnrichment()
enricher2.import_cache('cache_clasificaciones.json')
```

**Clasificación sin GPT (solo keywords):**
Para ahorrar costos o procesamiento offline:

```python
from cfdi.enrichment import clasificar_rapido

linea = clasificar_rapido("Tornillo hexagonal")  # Usa solo keywords
# Output: "ferreteria_industrial"
```

### 2. Detección de anomalías

El módulo detecta automáticamente:
- ✅ Cantidades anormalmente altas (>10,000 unidades)
- ✅ Precios <= 0 o excesivamente altos
- ✅ Descripciones muy cortas o vacías
- ✅ Precios desviados vs histórico (>50%)

```python
concepto = {
    'descripcion': 'Tornillo',
    'cantidad': 15000,  # Anormal
    'valor_unitario': 1.50
}

anomalias = enricher.detectar_anomalias(concepto)
print(anomalias)
# Output: ['Cantidad inusualmente alta: 15,000 unidades']
```

### 3. Resumen por línea de negocio

```python
resumen = enricher.generar_resumen(conceptos_enriquecidos)

# Resultado:
{
    'ferreteria_industrial': {
        'total_conceptos': 1245,
        'importe_total': 567890.50,
        'conceptos_ejemplo': ['Tornillo 1/4', 'Tuerca hex', 'Clavo 2"']
    },
    'materiales_construccion': {
        'total_conceptos': 856,
        'importe_total': 1234567.00,
        'conceptos_ejemplo': ['Cemento gris 50kg', 'Arena', 'Grava']
    }
}
```

### 4. Uso en UI Streamlit

La página **📦 Ingesta CFDIs (ZIP)** integra todo automáticamente:
1. Upload ZIP de XMLs
2. Parsing automático
3. Clasificación IA opcional (con control de costos)
4. Reportes consolidados por línea
5. Guardado a Neon PostgreSQL

Accesible desde el menú principal → "📦 Ingesta CFDIs (ZIP)"

---

## 📈 Ventajas vs Excel Upload

| Aspecto | Excel Manual | XML CFDI |
|---------|-------------|----------|
| **Setup time** | 5-10 min | 2 min |
| **Precisión** | 90-95% (errores humanos) | 100% (datos SAT) |
| **Histórico** | Lo que exportes | Ilimitado (2014+) |
| **Actualización** | Manual cada vez | 1 vez, luego automático |
| **Validación fiscal** | No | Sí (UUID oficial) |
| **Benchmarks** | No disponible | Sí (con N ≥50 clientes) |

---

## 🔐 Seguridad y Privacidad

### Datos sensibles:
- XMLs contienen datos fiscales reales (RFC, razones sociales, montos)
- **Nunca** compartir XML completo entre clientes
- Anonimizar para benchmarks (solo agregados, sin identificadores)

### Medidas implementadas:
```sql
-- Benchmarks: sin identificadores de empresa
SELECT 
    industria,
    AVG(dias_credito) as dso_promedio,
    COUNT(DISTINCT empresa_id) as n_empresas  -- Mínimo 30
FROM cfdi_ventas
GROUP BY industria
HAVING COUNT(DISTINCT empresa_id) >= 30;  -- K-anonymity
```

---

## 🚧 Roadmap

### Fase 1: MVP (Semanas 1-4) ✅ COMPLETADO
- [x] Parser CFDI 4.0 básico
- [x] Parser Complemento de Pagos 2.0
- [x] Schema Neon PostgreSQL
- [x] Script de ingesta completo
- [x] Tests unitarios (parser + ingestion)
- [x] Documentación completa
- [x] CLI tools (test_parser.py, ingest_cfdi_to_neon.py)

### Fase 2: Automatización (Semanas 5-8)
- [ ] Upload ZIP desde Streamlit UI
- [ ] Progress bar durante ingesta
- [ ] Enriquecimiento con GPT-4
- [ ] Dashboard conectado a Neon

### Fase 3: Integración PAC (Semanas 9-16)
- [ ] API connector Finkok
- [ ] API connector SW Sapien
- [ ] Sync automático diario
- [ ] Webhook para CFDIs nuevos

### Fase 4: Inteligencia (Semanas 17-24)
- [ ] Benchmarks sectoriales (N≥50)
- [ ] Alertas predictivas
- [ ] Fine-tuning GPT-4 en descripciones MX
- [ ] Sugerencias de cobranza basadas en patterns

---

## 📞 Soporte

**Responsable:** @B10sp4rt4n  
**Última actualización:** 26 febrero 2026  
**Versión:** 0.1.0

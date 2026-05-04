# Framework NL2SQL Guiado

## Objetivo

Este framework prepara el Asistente de Datos para operar en modo deterministico:

- Sin texto libre para generar SQL.
- Solo casos predefinidos del catalogo.
- Parametros controlados por UI o CLI.
- Ejecucion con filtros de seguridad existentes (tenant/perfil).

## Componentes

- Catalogo versionado:
  - config/guided_query_catalog.json
  - cfdi/migration_guided_query_catalog.sql
  - cfdi/migration_guided_usage_metrics.sql
  - cfdi/migration_guided_tenant_overrides.sql
  - scripts/sync_guided_catalog.py
- Runtime framework:
  - utils/guided_query_framework.py
- Integracion en Streamlit:
  - main/data_assistant.py (modo "Guiado")
  - Expander de adopcion guiada con selector de alcance (tenant/global) y ventana (7/30/90 dias)
  - Visualizacion diaria de eventos y tasa de exito
- Runner practico CLI:
  - scripts/run_guided_case.py
  - scripts/set_guided_tenant_override.py

## Flujo runtime

1. Cargar catalogo (BD activa o JSON fallback).
2. Construir instancia de GuidedQueryFramework.
3. Seleccionar dominio y caso.
4. Capturar parametros permitidos.
5. Resolver SQL por template.
6. Ejecutar query y renderizar KPI/chart/table/export.

## Modo Guiado en UI

En el Asistente de Datos, ahora hay dos modos activos:

- Chat
- Guiado

En Guiado:

- El usuario elige dominio y analisis.
- El sistema solo muestra filtros permitidos por caso.
- La consulta se ejecuta con plantilla fija.
- El resultado se incorpora al historial del asistente.

## Practica: ejecucion por CLI

### 1) Sincronizar catalogo a BD (opcional)

```bash
python scripts/sync_guided_catalog.py \
  --connection-string "$NEON_DATABASE_URL" \
  --source "manual-sync"
```

### 2) Ejecutar un caso guiado

```bash
python scripts/run_guided_case.py \
  --connection-string "$NEON_DATABASE_URL" \
  --case-id ventas_top_clientes \
  --period-mode ultimos_12_meses \
  --top-n 15 \
  --metodo-pago PUE
```

### 3) Caso con rango personalizado

```bash
python scripts/run_guided_case.py \
  --connection-string "$NEON_DATABASE_URL" \
  --case-id fiscal_impuestos_retenidos_trasladados \
  --period-mode rango_personalizado \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --grouping mensual
```

## Variables utiles

- GUIDED_CATALOG_SOURCE=db
  - Prioriza cargar catalogo activo desde BD en runtime.
- GUIDED_CATALOG_SOURCE=json
  - Fuerza catalogo local JSON.

## Migracion de metricas de uso

Para habilitar analytics persistente por caso:

```bash
python - <<'PY'
import os, psycopg2
from pathlib import Path
url = os.getenv('NEON_DATABASE_URL', '')
sql = Path('cfdi/migration_guided_usage_metrics.sql').read_text(encoding='utf-8')
with psycopg2.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
print('ok')
PY
```

## Rollout por tenant

Migrar tabla de overrides por empresa:

```bash
python - <<'PY'
import os, psycopg2
from pathlib import Path
url = os.getenv('NEON_DATABASE_URL', '')
sql = Path('cfdi/migration_guided_tenant_overrides.sql').read_text(encoding='utf-8')
with psycopg2.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
print('ok')
PY
```

Ejemplos de rollout:

```bash
# Listar overrides de una empresa
python scripts/set_guided_tenant_override.py \
  --connection-string "$NEON_DATABASE_URL" \
  --empresa-id "UUID_EMPRESA" \
  --list

# Deshabilitar dominio completo para una empresa
python scripts/set_guided_tenant_override.py \
  --connection-string "$NEON_DATABASE_URL" \
  --empresa-id "UUID_EMPRESA" \
  --domain-id clientes \
  --case-id '*' \
  --enabled false

# Deshabilitar un caso puntual
python scripts/set_guided_tenant_override.py \
  --connection-string "$NEON_DATABASE_URL" \
  --empresa-id "UUID_EMPRESA" \
  --domain-id ventas \
  --case-id ventas_top_clientes \
  --enabled false
```

## Estado de frameworkizacion

Cubierto en esta fase:

- Contrato unico de ejecucion guiada.
- Registro de templates por ID y separacion por dominio.
- Integracion UI y ejecucion real.
- Runner CLI para operacion y validacion tecnica.
- Metricas de uso por caso en session y BD.
- Tests de regresion SQL para los 20 casos del catalogo.
- Rollout por tenant con overrides de dominio/caso.

Siguiente fase recomendada:

- Implementar estrategia de rollout por tenant.
- Agregar dashboard de adopcion por dominio/caso.

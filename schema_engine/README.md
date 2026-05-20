# CIMA Schema Engine by FixCel

## Definicion

Motor interno de CIMA para declarar esquemas minimos de entrada, validar archivos
Excel/CSV/XML, mapear columnas equivalentes, calcular completitud contextual y
determinar que modulos analiticos pueden activarse segun la data disponible.

## Proposito

Permitir que los usuarios carguen reportes con informacion minima y que CIMA
determine que puede analizar, que esta limitado y que campos faltan para mejorar
el diagnostico.

**Pregunta clave que responde:** "Con la informacion disponible, que puede analizar CIMA?"

## Alcance inicial

- Plantillas descargables CSV para ventas y CxC
- Schemas JSON iniciales declarados formalmente
- Validador de estructura contra esquemas
- Mapeo de alias de columnas hacia nombres canonicos
- Score de completitud contextual (0-100)
- Declaracion de requerimientos por modulo analitico
- Activacion de modulos segun fuentes y campos disponibles
- Declaracion arquitectonica de CrossConnector Layer para conectores futuros

## Fuentes contempladas

| ID | Descripcion |
|----|-------------|
| `ventas_excel` | Archivo Excel o CSV de ventas |
| `cxc_excel` | Archivo Excel de cuentas por cobrar (hojas VIGENTES/VENCIDAS) |
| `cfdi_xml` | Archivos XML o ZIP de facturas CFDI |
| `neon_cfdi` | Datos CFDI persistidos en base de datos Neon |
| `manual_input` | Entradas manuales en herramientas financieras |
| `dataframe_flexible` | DataFrame cargado libremente para Asistente de Datos |
| `external_connector` | Conector programatico externo (SAE, CONTPAQi, ERP, CRM) |

## Estructura del modulo

```
schema_engine/
  __init__.py              Exportaciones publicas
  README.md                Este archivo
  schema_registry.py       Registro central de esquemas disponibles
  schema_validator.py      Validacion de DataFrame contra esquema
  schema_generator.py      Generacion de plantillas CSV/XLSX descargables
  column_mapper.py         Mapeo de columnas hacia nombres canonicos
  context_score.py         Score de completitud contextual 0-100
  module_requirements.py   Requisitos por modulo y activacion dinamica
  connector_registry.py    Registro de conectores declarados
  source_contracts.py      Relacion fuentes <-> contratos canonicos
  sample_data_generator.py Filas de ejemplo por esquema

schemas/
  ventas_minimo.json
  ventas_comercial.json
  cxc_minimo.json
  cxc_aging.json
  cfdi_xml_basico.json
  cfdi_neon_mapa_clientes.json
  manual_financial_tools.json
  data_assistant_flexible.json

templates/
  ventas_minimo.csv
  ventas_comercial.csv
  cxc_minimo.csv
  cxc_aging.csv

connections/
  connectors/
    base_connector.py      Clase abstracta base
    sae_connector.py       Placeholder SAE
    contpaqi_connector.py  Placeholder CONTPAQi
    generic_erp_connector.py
    generic_crm_connector.py
    cfdi_connector.py
  translators/
    canonical_sales_translator.py
    canonical_cxc_translator.py
    canonical_customer_translator.py
    canonical_product_translator.py
  contracts/
    canonical_sales_v1.json
    canonical_cxc_v1.json
    canonical_customer_v1.json
    canonical_product_v1.json
```

## CrossConnector Layer

Capa arquitectonica futura que permitira extraer datos desde sistemas externos
(SAE, CONTPAQi, ERPs, CRMs, PACs, APIs) y traducirlos hacia contratos canonicos
consumibles por CIMA.

**Principio obligatorio:** Los conectores no alimentan directamente los dashboards.
Todo dato extraido pasa por el flujo:

```
Sistema externo
  -> Connector (extraccion cruda)
  -> Raw staging
  -> Canonical Translator
  -> Canonical Contract
  -> Schema Validator
  -> Module Requirements
  -> CIMA dashboards
```

## Que NO hace todavia

- No reemplaza reportes existentes
- No modifica visualizaciones actuales
- No corrige calculos de CxC
- No implementa conexiones reales a SAE, CONTPAQi, ERPs o CRMs
- No maneja credenciales ni variables de entorno de produccion
- No cambia estructura de datos productiva
- No modifica app.py ni navegacion

## Version

`1.0.0` — Declaracion arquitectonica inicial (branch: feature/cima-schema-engine-by-fixcel)

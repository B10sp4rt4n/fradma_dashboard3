"""
schema_registry.py
Registro central de esquemas del CIMA Schema Engine.

Cada esquema declara:
- Fuente de origen (ventas_excel, cxc_excel, cfdi_xml, etc.)
- Campos obligatorios, recomendados y opcionales (nombres canonicos)
- Salidas analiticas disponibles segun la informacion detectada
- Tipo de archivos soportados
- Version del esquema
"""

import json
import os
from typing import Optional

# =====================================================================
# DIRECTORIO DE SCHEMAS JSON
# =====================================================================

_SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), "..", "schemas")


# =====================================================================
# REGISTRO EN MEMORIA
# =====================================================================

SCHEMA_REGISTRY: dict = {

    "ventas_minimo_v1": {
        "schema_id": "ventas_minimo_v1",
        "nombre": "Ventas Minimo",
        "descripcion": "Esquema minimo para analisis de ventas. Solo requiere fecha y monto.",
        "fuente": "ventas_excel",
        "campos_obligatorios": ["fecha", "monto"],
        "campos_recomendados": ["cliente"],
        "campos_opcionales": ["vendedor", "linea_de_negocio", "producto", "region", "canal"],
        "salidas_disponibles": [
            "ventas_totales",
            "tendencia_mensual",
            "clientes_activos",
        ],
        "tipo_archivo_soportado": ["csv", "xlsx"],
        "version": "1.0.0",
        "json_file": "ventas_minimo.json",
    },

    "ventas_comercial_v1": {
        "schema_id": "ventas_comercial_v1",
        "nombre": "Ventas Comercial",
        "descripcion": (
            "Esquema para analisis comercial completo: fecha, monto, cliente, "
            "vendedor, linea de negocio y producto."
        ),
        "fuente": "ventas_excel",
        "campos_obligatorios": ["fecha", "monto"],
        "campos_recomendados": ["cliente", "vendedor", "linea_de_negocio", "producto"],
        "campos_opcionales": ["region", "canal", "moneda", "forma_pago", "sucursal"],
        "salidas_disponibles": [
            "ventas_totales",
            "tendencia_mensual",
            "top_clientes",
            "desempeno_vendedor",
            "ventas_por_linea",
            "ventas_por_producto",
            "heatmap_ventas",
            "comparativo_anual",
            "ytd_lineas",
            "ytd_productos",
        ],
        "tipo_archivo_soportado": ["csv", "xlsx"],
        "version": "1.0.0",
        "json_file": "ventas_comercial.json",
    },

    "cxc_minimo_v1": {
        "schema_id": "cxc_minimo_v1",
        "nombre": "CxC Minimo",
        "descripcion": "Esquema minimo para cartera de cuentas por cobrar.",
        "fuente": "cxc_excel",
        "campos_obligatorios": ["cliente", "saldo_adeudado"],
        "campos_recomendados": ["fecha"],
        "campos_opcionales": ["factura", "vendedor", "estatus"],
        "salidas_disponibles": [
            "total_adeudado",
            "top_deudores",
            "cartera_basica",
        ],
        "tipo_archivo_soportado": ["xlsx"],
        "version": "1.0.0",
        "json_file": "cxc_minimo.json",
    },

    "cxc_aging_v1": {
        "schema_id": "cxc_aging_v1",
        "nombre": "CxC Aging",
        "descripcion": (
            "Esquema completo para analisis de antiguedad de cartera CxC. "
            "Incluye aging, score de salud y plan de cobranza."
        ),
        "fuente": "cxc_excel",
        "campos_obligatorios": ["cliente", "saldo_adeudado"],
        "campos_recomendados": [
            "fecha_emision",
            "fecha_vencimiento",
            "dias_vencido",
            "dias_credito",
            "vendedor",
            "estatus",
        ],
        "campos_opcionales": [
            "factura",
            "linea_negocio",
            "moneda",
            "fecha_pago",
        ],
        "salidas_disponibles": [
            "total_adeudado",
            "cartera_vigente",
            "cartera_vencida",
            "aging_buckets",
            "score_salud_cxc",
            "top_deudores",
            "plan_cobranza",
            "desempeno_cobranza_vendedor",
        ],
        "tipo_archivo_soportado": ["xlsx"],
        "version": "1.0.0",
        "json_file": "cxc_aging.json",
    },

    "cfdi_xml_basico_v1": {
        "schema_id": "cfdi_xml_basico_v1",
        "nombre": "CFDI XML Basico",
        "descripcion": "Esquema para facturas CFDI extraidas de archivos XML.",
        "fuente": "cfdi_xml",
        "campos_obligatorios": ["uuid", "fecha_emision", "total", "receptor_rfc"],
        "campos_recomendados": [
            "subtotal",
            "moneda",
            "tipo_cambio",
            "tipo_comprobante",
            "forma_pago",
            "metodo_pago",
            "receptor_nombre",
            "receptor_domicilio_fiscal",
            "emisor_rfc",
            "emisor_nombre",
        ],
        "campos_opcionales": [
            "descuento",
            "concepto_descripcion",
            "concepto_importe",
            "iva",
        ],
        "salidas_disponibles": [
            "universo_cfdi",
            "desglose_fiscal",
            "ventas_por_cliente",
            "ventas_por_forma_pago",
        ],
        "tipo_archivo_soportado": ["xml", "zip"],
        "version": "1.0.0",
        "json_file": "cfdi_xml_basico.json",
    },

    "cfdi_neon_mapa_clientes_v1": {
        "schema_id": "cfdi_neon_mapa_clientes_v1",
        "nombre": "CFDI Neon Mapa de Clientes",
        "descripcion": "Esquema para distribucion geografica de clientes desde Neon.",
        "fuente": "neon_cfdi",
        "campos_obligatorios": [
            "receptor_domicilio_fiscal",
            "receptor_rfc",
            "total_mxn",
        ],
        "campos_recomendados": ["receptor_nombre", "uuid"],
        "campos_opcionales": [],
        "salidas_disponibles": [
            "mapa_clientes",
            "facturacion_por_cp",
            "clientes_por_zona",
            "monto_facturado_por_zona",
        ],
        "tipo_archivo_soportado": ["neon_db"],
        "version": "1.0.0",
        "json_file": "cfdi_neon_mapa_clientes.json",
    },

    "manual_financial_tools_v1": {
        "schema_id": "manual_financial_tools_v1",
        "nombre": "Herramientas Financieras Manuales",
        "descripcion": (
            "Esquema para herramientas que no dependen de DataFrame. "
            "Todas las entradas son manuales via UI."
        ),
        "fuente": "manual_input",
        "campos_obligatorios": [],
        "campos_recomendados": [],
        "campos_opcionales": [],
        "herramientas": [
            "conversor_monedas",
            "descuento_pronto_pago",
            "dso_manual",
            "interes_moratorio",
            "indicadores_economicos",
        ],
        "salidas_disponibles": [
            "conversion_moneda",
            "analisis_descuento_pp",
            "dso_calculado",
            "interes_mora_calculado",
            "tiie_inflacion",
        ],
        "tipo_archivo_soportado": [],
        "version": "1.0.0",
        "json_file": "manual_financial_tools.json",
    },

    "data_assistant_flexible_v1": {
        "schema_id": "data_assistant_flexible_v1",
        "nombre": "Asistente de Datos Flexible",
        "descripcion": (
            "Esquema flexible para el Asistente de Datos. "
            "Funciona con cualquier DataFrame valido; mejores resultados con columnas "
            "numericas, categoricas y de fecha."
        ),
        "fuente": "dataframe_flexible",
        "campos_obligatorios": [],
        "campos_recomendados": ["fecha", "monto", "cliente"],
        "campos_opcionales": [
            "vendedor",
            "linea_de_negocio",
            "producto",
            "region",
        ],
        "salidas_disponibles": [
            "estadisticas_descriptivas",
            "series_temporales",
            "rankings",
            "analisis_libre_nl",
        ],
        "tipo_archivo_soportado": ["csv", "xlsx", "dataframe"],
        "version": "1.0.0",
        "json_file": "data_assistant_flexible.json",
    },
}


# =====================================================================
# FUNCIONES PUBLICAS
# =====================================================================

def get_schema(schema_id: str) -> dict:
    """
    Retorna la definicion completa de un esquema por su ID.

    Args:
        schema_id: Identificador del esquema (e.g. 'ventas_comercial_v1')

    Returns:
        dict con la definicion del esquema

    Raises:
        KeyError: Si el schema_id no existe en el registro
    """
    if schema_id not in SCHEMA_REGISTRY:
        available = list(SCHEMA_REGISTRY.keys())
        raise KeyError(
            f"Schema '{schema_id}' no encontrado. "
            f"Disponibles: {available}"
        )
    return dict(SCHEMA_REGISTRY[schema_id])


def list_schemas() -> list:
    """
    Retorna lista de todos los schema_ids registrados.

    Returns:
        Lista de strings con los IDs de esquemas disponibles
    """
    return list(SCHEMA_REGISTRY.keys())


def list_schemas_by_source(source_type: str) -> list:
    """
    Retorna esquemas filtrados por tipo de fuente.

    Args:
        source_type: Tipo de fuente (e.g. 'ventas_excel', 'cxc_excel', 'cfdi_xml')

    Returns:
        Lista de dicts con esquemas que pertenecen a esa fuente
    """
    return [
        dict(schema)
        for schema in SCHEMA_REGISTRY.values()
        if schema.get("fuente") == source_type
    ]


def get_required_fields(schema_id: str) -> list:
    """
    Retorna los campos obligatorios de un esquema.

    Args:
        schema_id: Identificador del esquema

    Returns:
        Lista de nombres canonicos de campos obligatorios
    """
    return get_schema(schema_id).get("campos_obligatorios", [])


def get_recommended_fields(schema_id: str) -> list:
    """
    Retorna los campos recomendados de un esquema.

    Args:
        schema_id: Identificador del esquema

    Returns:
        Lista de nombres canonicos de campos recomendados
    """
    return get_schema(schema_id).get("campos_recomendados", [])


def load_schema_from_json(schema_id: str) -> Optional[dict]:
    """
    Carga un esquema desde su archivo JSON en /schemas/.
    Retorna None si el archivo no existe.

    Args:
        schema_id: Identificador del esquema

    Returns:
        dict con contenido JSON o None
    """
    schema = SCHEMA_REGISTRY.get(schema_id)
    if not schema:
        return None
    json_file = schema.get("json_file")
    if not json_file:
        return None
    path = os.path.join(_SCHEMAS_DIR, json_file)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)

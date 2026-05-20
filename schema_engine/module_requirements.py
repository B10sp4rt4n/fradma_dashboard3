"""
module_requirements.py
Declara que fuentes y campos minimos necesita cada modulo de CIMA.
Implementa la funcion get_activable_modules() que determina, segun
las fuentes disponibles y campos detectados, cuales modulos pueden activarse.
"""

from typing import Optional
from .column_mapper import get_detected_canonical_fields


# =====================================================================
# FUENTES DE DATOS RECONOCIDAS
# =====================================================================

DATA_SOURCES = {
    "ventas_excel":       "Archivo Excel/CSV de ventas",
    "cxc_excel":          "Archivo Excel de cuentas por cobrar (hojas VIGENTES/VENCIDAS)",
    "cfdi_xml":           "Archivos XML o ZIP de facturas CFDI",
    "neon_cfdi":          "Datos CFDI persistidos en base de datos Neon",
    "manual_input":       "Entradas manuales del usuario (herramientas financieras)",
    "dataframe_flexible": "DataFrame cargado para analisis libre (Asistente de Datos)",
    "external_connector": "Conector programatico externo (SAE, CONTPAQi, ERP, CRM)",
}


# =====================================================================
# REQUERIMIENTOS POR MODULO
# =====================================================================

MODULE_REQUIREMENTS = {

    "desempeno_comercial": {
        "nombre":              "Desempeno Comercial",
        "menu_label":          "Desempeno Comercial",
        "fuentes_requeridas":  ["ventas_excel"],
        "fuentes_opcionales":  [],
        "schemas_compatibles": ["ventas_minimo_v1", "ventas_comercial_v1"],
        "campos_minimos":      ["fecha", "monto"],
        "campos_recomendados": ["cliente", "vendedor", "linea_de_negocio"],
    },

    "comparativo_anual": {
        "nombre":              "Comparativo Ano vs Ano",
        "menu_label":          "Comparativo Ano vs Ano",
        "fuentes_requeridas":  ["ventas_excel"],
        "fuentes_opcionales":  [],
        "schemas_compatibles": ["ventas_minimo_v1", "ventas_comercial_v1"],
        "campos_minimos":      ["fecha", "monto"],
        "campos_recomendados": [],
    },

    "ytd_lineas": {
        "nombre":              "YTD por Linea de Negocio",
        "menu_label":          "YTD por Linea de Negocio",
        "fuentes_requeridas":  ["ventas_excel"],
        "fuentes_opcionales":  [],
        "schemas_compatibles": ["ventas_comercial_v1"],
        "campos_minimos":      ["fecha", "monto", "linea_de_negocio"],
        "campos_recomendados": ["vendedor", "cliente"],
    },

    "ytd_productos": {
        "nombre":              "YTD por Producto",
        "menu_label":          "YTD por Producto",
        "fuentes_requeridas":  ["ventas_excel"],
        "fuentes_opcionales":  [],
        "schemas_compatibles": ["ventas_comercial_v1"],
        "campos_minimos":      ["fecha", "monto", "producto"],
        "campos_recomendados": ["vendedor", "cliente"],
    },

    "heatmap_ventas": {
        "nombre":              "Heatmap Ventas",
        "menu_label":          "Heatmap Ventas",
        "fuentes_requeridas":  ["ventas_excel"],
        "fuentes_opcionales":  [],
        "schemas_compatibles": ["ventas_comercial_v1"],
        "campos_minimos":      ["fecha", "monto", "linea_de_negocio"],
        "campos_recomendados": ["producto", "cliente", "vendedor", "region", "canal"],
    },

    "reporte_ejecutivo": {
        "nombre":              "Reporte Ejecutivo",
        "menu_label":          "Reporte Ejecutivo",
        "fuentes_requeridas":  ["ventas_excel"],
        "fuentes_opcionales":  ["cxc_excel"],
        "schemas_compatibles": ["ventas_comercial_v1", "cxc_aging_v1"],
        "campos_minimos":      ["fecha", "monto"],
        "campos_recomendados": ["cliente", "saldo_adeudado", "dias_vencido", "fecha_vencimiento"],
    },

    "reporte_consolidado": {
        "nombre":              "Reporte Consolidado",
        "menu_label":          "Reporte Consolidado",
        "fuentes_requeridas":  ["ventas_excel"],
        "fuentes_opcionales":  ["cxc_excel"],
        "schemas_compatibles": ["ventas_comercial_v1", "cxc_aging_v1"],
        "campos_minimos":      ["fecha", "monto"],
        "campos_recomendados": ["cliente", "saldo_adeudado", "vendedor", "linea_de_negocio"],
    },

    "kpi_cartera_cxc": {
        "nombre":              "KPI Cartera CxC",
        "menu_label":          "KPI Cartera CxC",
        "fuentes_requeridas":  ["cxc_excel"],
        "fuentes_opcionales":  [],
        "schemas_compatibles": ["cxc_minimo_v1", "cxc_aging_v1"],
        "campos_minimos":      ["cliente", "saldo_adeudado"],
        "campos_recomendados": ["fecha_vencimiento", "dias_vencido", "vendedor", "estatus"],
    },

    "vendedores_cxc": {
        "nombre":              "Vendedores + CxC",
        "menu_label":          "Vendedores + CxC",
        "fuentes_requeridas":  ["ventas_excel", "cxc_excel"],
        "fuentes_opcionales":  [],
        "schemas_compatibles": ["ventas_comercial_v1", "cxc_aging_v1"],
        "campos_minimos":      ["cliente", "saldo_adeudado", "vendedor", "monto"],
        "campos_recomendados": ["dias_vencido", "estatus", "fecha"],
    },

    "mapa_clientes": {
        "nombre":              "Mapa de Clientes",
        "menu_label":          "Mapa de Clientes",
        "fuentes_requeridas":  ["neon_cfdi"],
        "fuentes_opcionales":  [],
        "schemas_compatibles": ["cfdi_neon_mapa_clientes_v1"],
        "campos_minimos":      ["receptor_domicilio_fiscal", "receptor_rfc", "monto"],
        "campos_recomendados": ["receptor_nombre", "uuid"],
    },

    "herramientas_financieras": {
        "nombre":              "Herramientas Financieras",
        "menu_label":          "Herramientas Financieras",
        "fuentes_requeridas":  ["manual_input"],
        "fuentes_opcionales":  [],
        "schemas_compatibles": ["manual_financial_tools_v1"],
        "campos_minimos":      [],
        "campos_recomendados": [],
    },

    "universo_cfdi": {
        "nombre":              "Universo de CFDIs",
        "menu_label":          "Universo de CFDIs",
        "fuentes_requeridas":  ["neon_cfdi"],
        "fuentes_opcionales":  ["cfdi_xml"],
        "schemas_compatibles": ["cfdi_xml_basico_v1", "cfdi_neon_mapa_clientes_v1"],
        "campos_minimos":      ["uuid", "fecha_emision", "monto", "receptor_rfc"],
        "campos_recomendados": ["tipo_comprobante", "forma_pago", "receptor_nombre"],
    },

    "desglose_fiscal": {
        "nombre":              "Desglose Fiscal",
        "menu_label":          "Desglose Fiscal",
        "fuentes_requeridas":  ["cfdi_xml"],
        "fuentes_opcionales":  ["neon_cfdi"],
        "schemas_compatibles": ["cfdi_xml_basico_v1"],
        "campos_minimos":      ["uuid", "fecha_emision", "monto"],
        "campos_recomendados": ["subtotal", "iva", "tipo_comprobante", "metodo_pago"],
    },

    "asistente_datos": {
        "nombre":              "Asistente de Datos",
        "menu_label":          "Asistente de Datos",
        "fuentes_requeridas":  ["dataframe_flexible"],
        "fuentes_opcionales":  [],
        "schemas_compatibles": ["data_assistant_flexible_v1"],
        "campos_minimos":      [],
        "campos_recomendados": ["fecha", "monto", "cliente"],
    },
}


# =====================================================================
# FUNCION PRINCIPAL
# =====================================================================

def get_activable_modules(
    available_sources: list,
    detected_fields: Optional[list] = None,
    df_columns: Optional[list] = None,
) -> dict:
    """
    Determina que modulos pueden activarse segun las fuentes disponibles
    y los campos canonicos detectados.

    Args:
        available_sources: Lista de source IDs disponibles
                           (e.g. ['ventas_excel', 'cxc_excel'])
        detected_fields:   Lista de nombres canonicos ya detectados.
                           Si se omite, se usa df_columns para detectarlos.
        df_columns:        Lista de nombres de columnas del DataFrame.
                           Ignorado si detected_fields esta presente.

    Returns:
        {
            "modulos_activables":    [str, ...],
            "modulos_parciales":     [str, ...],
            "modulos_no_activables": [str, ...],
            "detalle": {
                "modulo_id": {
                    "status":                     "activable|parcial|no_activable",
                    "fuentes_faltantes":          [...],
                    "campos_faltantes":           [...],
                    "campos_recomendados_faltantes": [...],
                }
            }
        }
    """
    if detected_fields is None:
        detected_fields = get_detected_canonical_fields(df_columns or [])

    detected_set = set(detected_fields)
    sources_set  = set(available_sources)

    activables    = []
    parciales     = []
    no_activables = []
    detalle       = {}

    for mod_id, req in MODULE_REQUIREMENTS.items():
        req_sources  = req.get("fuentes_requeridas", [])
        min_fields   = req.get("campos_minimos", [])
        recom_fields = req.get("campos_recomendados", [])

        # -- Fuentes faltantes --
        fuentes_faltantes = [s for s in req_sources if s not in sources_set]

        # -- Campos minimos faltantes --
        campos_faltantes = [f for f in min_fields if f not in detected_set]

        # -- Campos recomendados faltantes --
        recom_faltantes = [f for f in recom_fields if f not in detected_set]

        # -- Clasificacion --
        if fuentes_faltantes or campos_faltantes:
            status = "no_activable"
            no_activables.append(mod_id)
        elif recom_faltantes:
            status = "parcial"
            parciales.append(mod_id)
        else:
            status = "activable"
            activables.append(mod_id)

        detalle[mod_id] = {
            "nombre":                      req["nombre"],
            "status":                      status,
            "fuentes_faltantes":           fuentes_faltantes,
            "campos_faltantes":            campos_faltantes,
            "campos_recomendados_faltantes": recom_faltantes,
        }

    return {
        "modulos_activables":    activables,
        "modulos_parciales":     parciales,
        "modulos_no_activables": no_activables,
        "detalle":               detalle,
    }

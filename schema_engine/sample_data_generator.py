"""
sample_data_generator.py
Genera filas de ejemplo para cada esquema registrado.
Usado por schema_generator.py para crear plantillas CSV con datos de muestra.
"""

from datetime import date

# =====================================================================
# FILAS DE EJEMPLO POR SCHEMA
# =====================================================================

SAMPLE_ROWS: dict = {

    "ventas_minimo_v1": [
        {"fecha": "2026-01-15", "monto": 12500.00, "cliente": "Empresa ABC"},
        {"fecha": "2026-02-10", "monto": 8750.50,  "cliente": "Empresa XYZ"},
        {"fecha": "2026-03-05", "monto": 21000.00, "cliente": "Industrias MNO"},
    ],

    "ventas_comercial_v1": [
        {
            "fecha": "2026-01-15", "monto": 12500.00,
            "cliente": "Empresa ABC", "vendedor": "Ana Lopez",
            "linea_de_negocio": "Ciberseguridad", "producto": "EDR-Pro",
            "region": "Norte", "canal": "Directo",
        },
        {
            "fecha": "2026-02-10", "monto": 8750.50,
            "cliente": "Empresa XYZ", "vendedor": "Carlos Mendez",
            "linea_de_negocio": "Proteccion Corrosion", "producto": "ZR-100",
            "region": "Centro", "canal": "Canal",
        },
        {
            "fecha": "2026-03-05", "monto": 21000.00,
            "cliente": "Industrias MNO", "vendedor": "Ana Lopez",
            "linea_de_negocio": "Recubrimientos", "producto": "EZK-300",
            "region": "Sur", "canal": "Directo",
        },
    ],

    "cxc_minimo_v1": [
        {"cliente": "Empresa ABC",     "saldo_adeudado": 8500.00,  "fecha": "2026-01-15"},
        {"cliente": "Empresa XYZ",     "saldo_adeudado": 15200.00, "fecha": "2026-02-01"},
        {"cliente": "Industrias MNO",  "saldo_adeudado": 4300.00,  "fecha": "2026-01-28"},
    ],

    "cxc_aging_v1": [
        {
            "cliente": "Empresa ABC", "saldo_adeudado": 8500.00,
            "fecha_emision": "2026-01-01", "fecha_vencimiento": "2026-01-31",
            "dias_credito": 30, "dias_vencido": 15,
            "vendedor": "Ana Lopez", "factura": "F-1001", "estatus": "Vencida",
        },
        {
            "cliente": "Empresa XYZ", "saldo_adeudado": 15200.00,
            "fecha_emision": "2026-02-01", "fecha_vencimiento": "2026-03-02",
            "dias_credito": 30, "dias_vencido": 0,
            "vendedor": "Carlos Mendez", "factura": "F-1002", "estatus": "Vigente",
        },
        {
            "cliente": "Industrias MNO", "saldo_adeudado": 4300.00,
            "fecha_emision": "2025-12-01", "fecha_vencimiento": "2025-12-31",
            "dias_credito": 30, "dias_vencido": 45,
            "vendedor": "Ana Lopez", "factura": "F-0988", "estatus": "Vencida",
        },
    ],

    "cfdi_xml_basico_v1": [
        {
            "uuid": "A1B2C3D4-0000-1111-AAAA-BBBBCCCC0001",
            "fecha_emision": "2026-01-15", "total": 14500.00,
            "subtotal": 12500.00, "iva": 2000.00,
            "moneda": "MXN", "tipo_cambio": 1.0,
            "tipo_comprobante": "I", "forma_pago": "03",
            "metodo_pago": "PUE",
            "receptor_rfc": "EAB860101AAA", "receptor_nombre": "Empresa ABC",
            "receptor_domicilio_fiscal": "06600",
            "emisor_rfc": "XAXX010101000", "emisor_nombre": "Mi Empresa SA",
            "concepto_descripcion": "Servicio de consultoria", "concepto_importe": 12500.00,
        },
    ],

    "cfdi_neon_mapa_clientes_v1": [
        {
            "receptor_domicilio_fiscal": "06600",
            "receptor_rfc": "EAB860101AAA",
            "receptor_nombre": "Empresa ABC",
            "total_mxn": 14500.00,
            "uuid": "A1B2C3D4-0000-1111-AAAA-BBBBCCCC0001",
        },
    ],

    "manual_financial_tools_v1": [],  # Sin filas de ejemplo; es entrada manual

    "data_assistant_flexible_v1": [
        {"fecha": "2026-01-15", "monto": 12500.00, "cliente": "Empresa ABC"},
        {"fecha": "2026-02-10", "monto": 8750.50,  "cliente": "Empresa XYZ"},
    ],
}


# =====================================================================
# FUNCION PUBLICA
# =====================================================================

def get_sample_rows(schema_id: str) -> list:
    """
    Retorna filas de ejemplo para un esquema dado.

    Args:
        schema_id: ID del esquema (e.g. 'ventas_comercial_v1')

    Returns:
        Lista de dicts con filas de ejemplo. Lista vacia si el esquema
        no tiene ejemplos o no existe.
    """
    return list(SAMPLE_ROWS.get(schema_id, []))


def get_sample_headers(schema_id: str) -> list:
    """
    Retorna las columnas de la primera fila de ejemplo de un esquema.

    Args:
        schema_id: ID del esquema

    Returns:
        Lista de nombres de columna o lista vacia
    """
    rows = get_sample_rows(schema_id)
    if not rows:
        return []
    return list(rows[0].keys())

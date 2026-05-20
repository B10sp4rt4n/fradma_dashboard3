"""
column_mapper.py
Mapeo de nombres de columnas reales hacia nombres canonicos del Schema Engine.

Principio: los archivos de clientes usan nombres variados (agente, ejecutivo,
vendedor, rep...). Este modulo resuelve el alias hacia el nombre canonico
(vendedor) para que el motor trabaje de forma consistente.
"""

import unicodedata
import re
from typing import Optional

# =====================================================================
# MAPA DE ALIASES: canonical_name -> [lista de variantes aceptadas]
# =====================================================================

COLUMN_ALIASES: dict = {

    "fecha": [
        "fecha",
        "date",
        "fecha_factura",
        "fecha de factura",
        "fecha_documento",
        "fecha de documento",
        "fecha_emision",
        "fecha de emision",
        "fecha_venta",
        "fecha de venta",
        "f_emision",
        "fecha_transaccion",
        "fecha de transaccion",
        "fecha_operacion",
        "fecha de operacion",
        "transaction_date",
        "invoice_date",
    ],

    "monto": [
        "monto",
        "monto total",
        "valor",
        "importe",
        "total",
        "venta",
        "ventas",
        "ventas_usd",
        "ventas_mxn",
        "valor_mxn",
        "valor_usd",
        "valor usd",
        "importe_mxn",
        "importe_usd",
        "ventas_usd_con_iva",
        "ventas_usd_sin_iva",
        "monto_usd",
        "total_usd",
        "amount",
        "sales_amount",
    ],

    "cliente": [
        "cliente",
        "razon_social",
        "razon social",
        "deudor",
        "nombre_cliente",
        "nombre cliente",
        "nombre del cliente",
        "receptor_nombre",
        "account",
        "cuenta",
        "customer",
        "customer_name",
        "client",
        "company",
    ],

    "vendedor": [
        "vendedor",
        "agente",
        "ejecutivo",
        "seller",
        "rep",
        "representante",
        "owner",
        "asesor",
        "vendedor_asignado",
        "account_owner",
        "sales_rep",
    ],

    "linea_de_negocio": [
        "linea",
        "linea_producto",
        "linea_prodcucto",  # typo comun SAE
        "linea_de_producto",
        "linea_negocio",
        "linea_de_negocio",
        "linea producto",
        "categoria",
        "familia",
        "division",
        "business_line",
        "product_line",
        "segment",
    ],

    "producto": [
        "producto",
        "articulo",
        "item",
        "sku",
        "descripcion",
        "concepto",
        "servicio",
        "product",
        "product_name",
        "item_name",
    ],

    "saldo_adeudado": [
        "saldo",
        "saldo_usd",
        "saldo_mxn",
        "saldo_adeudo",
        "adeudo",
        "saldo_adeudado",
        "open_amount",
        "balance",
        "outstanding_balance",
        "amount_due",
    ],

    "fecha_vencimiento": [
        "fecha_vencimiento",
        "vencimiento",
        "fecha_venc",
        "vencimient",
        "fecha_limite_pago",
        "due_date",
        "maturity_date",
    ],

    "dias_vencido": [
        "dias_vencido",
        "dias_vencidos",
        "dias_mora",
        "dias_de_mora",
        "overdue_days",
        "days_overdue",
        "days_past_due",
    ],

    "dias_credito": [
        "dias_credito",
        "dias_de_credito",
        "dias_de_credit",
        "credit_days",
        "payment_terms",
        "terminos_pago",
    ],

    "estatus": [
        "estatus",
        "status",
        "estado",
        "pagado",
        "situacion",
        "payment_status",
    ],

    "factura": [
        "factura",
        "folio",
        "documento",
        "invoice",
        "invoice_number",
        "numero_factura",
        "num_factura",
        "doc_num",
    ],

    "region": [
        "region",
        "region",
        "zona",
        "estado",
        "territorio",
        "area",
        "geography",
        "territory",
    ],

    "canal": [
        "canal",
        "canal_venta",
        "canal_comercial",
        "canal venta",
        "channel",
        "sales_channel",
    ],

    "moneda": [
        "moneda",
        "currency",
        "divisa",
        "cod_moneda",
    ],

    "forma_pago": [
        "forma_pago",
        "forma de pago",
        "payment_method",
        "metodo_pago",
        "tipo_pago",
    ],

    "fecha_emision": [
        "fecha_emision",
        "fecha emision",
        "f_emision",
        "issue_date",
        "fecha_documento",
    ],

    "fecha_pago": [
        "fecha_pago",
        "fecha_de_pago",
        "fecha_tentativa_de_pago",
        "fecha tentativa de pago",
        "payment_date",
        "fecha_cobro",
    ],

    "uuid": [
        "uuid",
        "folio_fiscal",
        "uuid_cfdi",
        "folio fiscal",
        "timbre",
    ],

    "receptor_rfc": [
        "receptor_rfc",
        "rfc_receptor",
        "rfc_cliente",
        "rfc",
        "customer_rfc",
    ],

    "receptor_domicilio_fiscal": [
        "receptor_domicilio_fiscal",
        "cp",
        "codigo_postal",
        "domicilio_fiscal",
        "postal_code",
        "zip_code",
    ],

    "sucursal": [
        "sucursal",
        "branch",
        "oficina",
        "store",
        "location",
    ],
}


# =====================================================================
# FUNCIONES UTILITARIAS INTERNAS (definidas antes del indice para poder usarlas)
# =====================================================================

def _clean(text: str) -> str:
    """
    Normaliza texto: minusculas, sin acentos, espacios a underscores,
    elimina caracteres especiales.
    """
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower().strip()
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^\w]", "", text)
    return text


# Indice invertido: alias -> canonical (construido una vez)
# Se indexa tanto con lower().strip() como con _clean() para cubrir
# variantes con espacios, guiones y acentos.
_ALIAS_INDEX: dict = {}
for _canonical, _aliases in COLUMN_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_INDEX[_alias.lower().strip()] = _canonical
        _ALIAS_INDEX[_clean(_alias)] = _canonical





# =====================================================================
# FUNCIONES PUBLICAS
# =====================================================================

def normalize_column_name(col_name: str) -> str:
    """
    Normaliza un nombre de columna: minusculas, sin acentos,
    espacios reemplazados por underscores.

    Args:
        col_name: Nombre original de la columna

    Returns:
        Nombre normalizado (str)

    Example:
        normalize_column_name("Fecha Factura") -> "fecha_factura"
        normalize_column_name("Razón Social") -> "razon_social"
    """
    return _clean(col_name)


def get_canonical_field(column_name: str) -> Optional[str]:
    """
    Retorna el nombre canonico para un nombre de columna dado.
    Devuelve None si no tiene mapeo conocido.

    Args:
        column_name: Nombre original o normalizado de la columna

    Returns:
        Nombre canonico (str) o None

    Example:
        get_canonical_field("Razon Social") -> "cliente"
        get_canonical_field("agente")        -> "vendedor"
        get_canonical_field("xyz_custom")    -> None
    """
    normalized = _clean(column_name)
    return _ALIAS_INDEX.get(normalized)


def map_columns(df_columns: list) -> dict:
    """
    Mapea una lista de nombres de columnas hacia sus nombres canonicos.
    Las columnas sin mapeo se incluyen con valor None.

    Args:
        df_columns: Lista de nombres de columnas del DataFrame

    Returns:
        dict { nombre_original: nombre_canonico_o_None }

    Example:
        map_columns(["Fecha Factura", "Importe", "Razon Social", "Agente", "X_Custom"])
        -> {
             "Fecha Factura": "fecha",
             "Importe": "monto",
             "Razon Social": "cliente",
             "Agente": "vendedor",
             "X_Custom": None
           }
    """
    result = {}
    for col in df_columns:
        result[col] = get_canonical_field(col)
    return result


def detect_unmapped_columns(df_columns: list) -> list:
    """
    Retorna las columnas que no tienen mapeo canonico conocido.

    Args:
        df_columns: Lista de nombres de columnas del DataFrame

    Returns:
        Lista de nombres de columnas sin mapeo
    """
    return [col for col in df_columns if get_canonical_field(col) is None]


def get_detected_canonical_fields(df_columns: list) -> list:
    """
    Retorna los nombres canonicos detectados (sin duplicados, sin None).

    Args:
        df_columns: Lista de nombres de columnas del DataFrame

    Returns:
        Lista de nombres canonicos detectados
    """
    seen = set()
    result = []
    for col in df_columns:
        canonical = get_canonical_field(col)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result

"""
canonical_product_translator.py
Traduce registros de productos al contrato canonico de productos.
"""

from datetime import datetime, timezone


def translate_to_canonical_product(
    record: dict,
    source_id: str = "unknown",
) -> dict:
    """
    Traduce un registro de producto al contrato canonico.

    Args:
        record:    Dict con datos del producto de la fuente original.
        source_id: ID de la fuente de origen.

    Returns:
        Dict con campos del contrato canonical_product_v1.
    """
    return {
        "producto":        record.get("producto") or record.get("descripcion") or record.get("nombre"),
        "linea_de_negocio": record.get("linea_de_negocio") or record.get("categoria"),
        "sku":             record.get("sku") or record.get("codigo"),
        "precio_unitario": record.get("precio_unitario") or record.get("precio"),
        "unidad":          record.get("unidad"),
        "fuente_origen":   source_id,
        "extracted_at":    datetime.now(tz=timezone.utc).isoformat(),
    }


def translate_batch(
    records: list,
    source_id: str = "unknown",
) -> list:
    """
    Traduce una lista de registros de productos al contrato canonico.

    Args:
        records:   Lista de dicts de productos.
        source_id: ID de la fuente de origen.

    Returns:
        Lista de dicts canonicos.
    """
    return [translate_to_canonical_product(r, source_id) for r in records]

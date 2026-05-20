"""
canonical_sales_translator.py
Traduce registros de ventas de cualquier fuente al contrato canonico de ventas.

El contrato canonico canonical_sales_v1 define los campos estandar
que CIMA usa internamente, independientemente del sistema de origen.
"""

from datetime import datetime, timezone
from typing import Optional

# Campos del contrato canonico de ventas (ver /connections/contracts/canonical_sales_v1.json)
_CANONICAL_FIELDS = [
    "fecha",
    "monto",
    "cliente",
    "vendedor",
    "linea_de_negocio",
    "producto",
    "region",
    "canal",
    "moneda",
    "fuente_origen",
    "extracted_at",
]


def translate_to_canonical_sales(
    record: dict,
    source_id: str = "unknown",
) -> dict:
    """
    Traduce un registro de ventas de cualquier fuente al contrato canonico.

    Los campos desconocidos se ignoran. Los campos que faltan se dejan como None.

    Args:
        record:    Dict con datos de ventas de la fuente original.
        source_id: ID de la fuente de origen (e.g. 'ventas_excel', 'sae').

    Returns:
        Dict con campos del contrato canonical_sales_v1.
    """
    return {
        "fecha":             record.get("fecha"),
        "monto":             record.get("monto"),
        "cliente":           record.get("cliente"),
        "vendedor":          record.get("vendedor"),
        "linea_de_negocio":  record.get("linea_de_negocio"),
        "producto":          record.get("producto"),
        "region":            record.get("region"),
        "canal":             record.get("canal"),
        "moneda":            record.get("moneda", "MXN"),
        "fuente_origen":     source_id,
        "extracted_at":      datetime.now(tz=timezone.utc).isoformat(),
    }


def translate_batch(
    records: list,
    source_id: str = "unknown",
) -> list:
    """
    Traduce una lista de registros al contrato canonico de ventas.

    Args:
        records:   Lista de dicts de ventas.
        source_id: ID de la fuente de origen.

    Returns:
        Lista de dicts canonicos.
    """
    return [translate_to_canonical_sales(r, source_id) for r in records]

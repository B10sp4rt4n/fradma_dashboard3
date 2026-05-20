"""
canonical_customer_translator.py
Traduce registros de clientes al contrato canonico de clientes.
"""

from datetime import datetime, timezone


def translate_to_canonical_customer(
    record: dict,
    source_id: str = "unknown",
) -> dict:
    """
    Traduce un registro de cliente al contrato canonico.

    Args:
        record:    Dict con datos del cliente de la fuente original.
        source_id: ID de la fuente de origen.

    Returns:
        Dict con campos del contrato canonical_customer_v1.
    """
    return {
        "cliente":                   record.get("cliente") or record.get("receptor_nombre"),
        "rfc":                       record.get("rfc") or record.get("receptor_rfc"),
        "domicilio_fiscal":          record.get("domicilio_fiscal") or record.get("receptor_domicilio_fiscal"),
        "region":                    record.get("region"),
        "vendedor":                  record.get("vendedor"),
        "fuente_origen":             source_id,
        "extracted_at":              datetime.now(tz=timezone.utc).isoformat(),
    }


def translate_batch(
    records: list,
    source_id: str = "unknown",
) -> list:
    """
    Traduce una lista de registros de clientes al contrato canonico.

    Args:
        records:   Lista de dicts de clientes.
        source_id: ID de la fuente de origen.

    Returns:
        Lista de dicts canonicos.
    """
    return [translate_to_canonical_customer(r, source_id) for r in records]

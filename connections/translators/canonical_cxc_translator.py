"""
canonical_cxc_translator.py
Traduce registros de cuentas por cobrar al contrato canonico CxC.
"""

from datetime import datetime, timezone


def translate_to_canonical_cxc(
    record: dict,
    source_id: str = "unknown",
) -> dict:
    """
    Traduce un registro de CxC al contrato canonico.

    Args:
        record:    Dict con datos de CxC de la fuente original.
        source_id: ID de la fuente de origen.

    Returns:
        Dict con campos del contrato canonical_cxc_v1.
    """
    return {
        "cliente":           record.get("cliente"),
        "saldo_adeudado":    record.get("saldo_adeudado"),
        "fecha_emision":     record.get("fecha_emision"),
        "fecha_vencimiento": record.get("fecha_vencimiento"),
        "dias_credito":      record.get("dias_credito"),
        "dias_vencido":      record.get("dias_vencido"),
        "vendedor":          record.get("vendedor"),
        "factura":           record.get("factura"),
        "estatus":           record.get("estatus"),
        "fuente_origen":     source_id,
        "extracted_at":      datetime.now(tz=timezone.utc).isoformat(),
    }


def translate_batch(
    records: list,
    source_id: str = "unknown",
) -> list:
    """
    Traduce una lista de registros CxC al contrato canonico.

    Args:
        records:   Lista de dicts de CxC.
        source_id: ID de la fuente de origen.

    Returns:
        Lista de dicts canonicos.
    """
    return [translate_to_canonical_cxc(r, source_id) for r in records]

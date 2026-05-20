"""
source_contracts.py
Relaciona fuentes de datos con los contratos canonicos que producen.

Un contrato canonico es la estructura estandarizada (ventas, CxC, clientes,
productos) que usa CIMA internamente, independientemente de la fuente de origen.
"""

from typing import Optional

# =====================================================================
# MAPA FUENTE -> CONTRATOS CANONICOS
# =====================================================================

SOURCE_CONTRACTS: dict = {
    "ventas_excel": [
        "canonical_sales_v1",
    ],
    "cxc_excel": [
        "canonical_cxc_v1",
    ],
    "cfdi_xml": [
        "canonical_sales_v1",
        "canonical_customer_v1",
    ],
    "neon_cfdi": [
        "canonical_sales_v1",
        "canonical_customer_v1",
    ],
    "manual_input": [],  # Sin contrato canonico; entradas directas al UI
    "dataframe_flexible": [
        "canonical_sales_v1",  # Si el df es de ventas
    ],
    "sae": [
        "canonical_sales_v1",
        "canonical_cxc_v1",
        "canonical_customer_v1",
        "canonical_product_v1",
    ],
    "contpaqi": [
        "canonical_sales_v1",
        "canonical_cxc_v1",
        "canonical_customer_v1",
    ],
    "generic_crm": [
        "canonical_customer_v1",
    ],
    "generic_erp": [
        "canonical_sales_v1",
        "canonical_cxc_v1",
        "canonical_customer_v1",
        "canonical_product_v1",
    ],
}


# =====================================================================
# FUNCIONES PUBLICAS
# =====================================================================

def get_contracts_for_source(source_id: str) -> list:
    """
    Retorna los contratos canonicos que puede producir una fuente.

    Args:
        source_id: ID de la fuente (e.g. 'ventas_excel', 'sae')

    Returns:
        Lista de contract IDs (puede estar vacia si la fuente no tiene contratos)
    """
    return list(SOURCE_CONTRACTS.get(source_id, []))


def source_supports_contract(source_id: str, contract_id: str) -> bool:
    """
    Verifica si una fuente soporta un contrato canonico especifico.

    Args:
        source_id:   ID de la fuente
        contract_id: ID del contrato (e.g. 'canonical_sales_v1')

    Returns:
        bool
    """
    return contract_id in SOURCE_CONTRACTS.get(source_id, [])


def get_sources_for_contract(contract_id: str) -> list:
    """
    Retorna todas las fuentes que pueden producir un contrato dado.

    Args:
        contract_id: ID del contrato canonico

    Returns:
        Lista de source IDs
    """
    return [
        src for src, contracts in SOURCE_CONTRACTS.items()
        if contract_id in contracts
    ]

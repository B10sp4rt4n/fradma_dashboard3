"""
connector_registry.py
Registro de conectores programaticos del CrossConnector Layer.
Los conectores estan declarados pero NO implementados todavia.
"""

from typing import Optional

# =====================================================================
# REGISTRO DE CONECTORES
# =====================================================================

CONNECTOR_REGISTRY: dict = {

    "sae": {
        "name":        "SAE",
        "description": "Sistema Adminstrativo Empresarial (ASPEL SAE)",
        "type":        "erp_accounting",
        "supports":    ["sales", "cxc", "customers", "products", "inventory"],
        "status":      "planned",
        "version":     None,
        "notes":       "Requiere ODBC o API SAE. No implementado.",
    },

    "contpaqi": {
        "name":        "CONTPAQi",
        "description": "CONTPAQi Contabilidad / Comercial / Nominas",
        "type":        "accounting",
        "supports":    ["sales", "cxc", "customers", "cfdi", "accounting"],
        "status":      "planned",
        "version":     None,
        "notes":       "Requiere SDK CONTPAQi o ODBC. No implementado.",
    },

    "generic_crm": {
        "name":        "Generic CRM",
        "description": "Conector generico para CRM (Salesforce, HubSpot, Zoho, etc.)",
        "type":        "crm",
        "supports":    ["customers", "opportunities", "sales_pipeline", "contacts"],
        "status":      "planned",
        "version":     None,
        "notes":       "Interfaz generica. Requiere adaptador especifico por CRM.",
    },

    "generic_erp": {
        "name":        "Generic ERP",
        "description": "Conector generico para ERP empresarial",
        "type":        "erp",
        "supports":    ["sales", "cxc", "inventory", "products", "customers"],
        "status":      "planned",
        "version":     None,
        "notes":       "Interfaz generica. Requiere adaptador especifico por ERP.",
    },

    "cfdi": {
        "name":        "CFDI Connector",
        "description": "Conector para facturas CFDI via XML o PAC",
        "type":        "fiscal_xml",
        "supports":    ["cfdi", "sales", "customers", "fiscal"],
        "status":      "partial",
        "version":     "1.0",
        "notes":       "Parseo XML implementado en herramientas_financieras.py y ingesta_cfdi.",
    },

    "neon": {
        "name":        "Neon Database",
        "description": "Base de datos Neon PostgreSQL para datos CFDI persistidos",
        "type":        "database",
        "supports":    ["cfdi", "customers", "sales", "fiscal"],
        "status":      "active",
        "version":     "1.0",
        "notes":       "Activo. Usado por mapa_clientes y universo_cfdi.",
    },
}


# =====================================================================
# FUNCIONES PUBLICAS
# =====================================================================

def list_connectors() -> list:
    """
    Retorna lista de IDs de todos los conectores registrados.

    Returns:
        Lista de strings con los IDs de conectores
    """
    return list(CONNECTOR_REGISTRY.keys())


def get_connector_metadata(connector_id: str) -> dict:
    """
    Retorna los metadatos de un conector por su ID.

    Args:
        connector_id: Identificador del conector (e.g. 'sae', 'contpaqi')

    Returns:
        dict con metadatos del conector

    Raises:
        KeyError: Si el connector_id no existe
    """
    if connector_id not in CONNECTOR_REGISTRY:
        available = list(CONNECTOR_REGISTRY.keys())
        raise KeyError(
            f"Conector '{connector_id}' no encontrado. Disponibles: {available}"
        )
    return dict(CONNECTOR_REGISTRY[connector_id])


def list_connectors_by_capability(capability: str) -> list:
    """
    Retorna conectores que soportan una capacidad especifica.

    Args:
        capability: Capacidad buscada (e.g. 'sales', 'cxc', 'cfdi', 'customers')

    Returns:
        Lista de dicts con conectores que incluyen esa capacidad
    """
    return [
        {"id": cid, **dict(meta)}
        for cid, meta in CONNECTOR_REGISTRY.items()
        if capability in meta.get("supports", [])
    ]


def list_active_connectors() -> list:
    """
    Retorna solo los conectores con status 'active' o 'partial'.

    Returns:
        Lista de IDs de conectores activos o parcialmente implementados
    """
    return [
        cid for cid, meta in CONNECTOR_REGISTRY.items()
        if meta.get("status") in ("active", "partial")
    ]

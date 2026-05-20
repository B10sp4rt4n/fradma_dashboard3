"""
generic_crm_connector.py
Conector PLACEHOLDER generico para CRMs (Salesforce, HubSpot, Zoho, etc.).

Estado: planned — NO implementado.
"""

from .base_connector import BaseConnector


class GenericCRMConnector(BaseConnector):
    """
    Conector generico para sistemas CRM.

    PLACEHOLDER — Requiere adaptador especifico por CRM.
    """

    connector_id = "generic_crm"
    status       = "planned"

    def connect(self) -> bool:
        raise NotImplementedError(
            "GenericCRMConnector no implementado. Requiere adaptador especifico."
        )

    def test_connection(self) -> dict:
        raise NotImplementedError(
            "GenericCRMConnector no implementado. Requiere adaptador especifico."
        )

    def get_metadata(self) -> dict:
        raise NotImplementedError(
            "GenericCRMConnector no implementado. Requiere adaptador especifico."
        )

    def fetch_customers(self, **kwargs) -> list:
        raise NotImplementedError("GenericCRMConnector.fetch_customers no implementado.")

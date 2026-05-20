"""
generic_erp_connector.py
Conector PLACEHOLDER generico para ERPs empresariales.

Estado: planned — NO implementado.
Define la interfaz para cualquier ERP (SAP, Oracle, Dynamics, etc.).
"""

from .base_connector import BaseConnector


class GenericERPConnector(BaseConnector):
    """
    Conector generico para sistemas ERP.

    PLACEHOLDER — Requiere adaptador especifico por ERP.
    Todos los metodos lanzan NotImplementedError hasta que se implemente.
    """

    connector_id = "generic_erp"
    status       = "planned"

    def connect(self) -> bool:
        raise NotImplementedError(
            "GenericERPConnector no implementado. Requiere adaptador especifico."
        )

    def test_connection(self) -> dict:
        raise NotImplementedError(
            "GenericERPConnector no implementado. Requiere adaptador especifico."
        )

    def get_metadata(self) -> dict:
        raise NotImplementedError(
            "GenericERPConnector no implementado. Requiere adaptador especifico."
        )

    def fetch_sales(self, **kwargs) -> list:
        raise NotImplementedError("GenericERPConnector.fetch_sales no implementado.")

    def fetch_cxc(self, **kwargs) -> list:
        raise NotImplementedError("GenericERPConnector.fetch_cxc no implementado.")

    def fetch_customers(self, **kwargs) -> list:
        raise NotImplementedError("GenericERPConnector.fetch_customers no implementado.")

    def fetch_products(self, **kwargs) -> list:
        raise NotImplementedError("GenericERPConnector.fetch_products no implementado.")

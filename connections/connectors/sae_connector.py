"""
sae_connector.py
Conector PLACEHOLDER para ASPEL SAE.

Estado: planned — NO implementado.
No realiza conexion real. No importa librerias de SAE.
"""

from .base_connector import BaseConnector


class SAEConnector(BaseConnector):
    """
    Conector para ASPEL SAE.

    PLACEHOLDER — Requiere ODBC o API SAE oficial.
    Todos los metodos lanzan NotImplementedError hasta que se implemente.
    """

    connector_id = "sae"
    status       = "planned"

    def connect(self) -> bool:
        raise NotImplementedError(
            "SAEConnector no implementado. Requiere ODBC o API SAE."
        )

    def test_connection(self) -> dict:
        raise NotImplementedError(
            "SAEConnector no implementado. Requiere ODBC o API SAE."
        )

    def get_metadata(self) -> dict:
        raise NotImplementedError(
            "SAEConnector no implementado. Requiere ODBC o API SAE."
        )

    def fetch_sales(self, **kwargs) -> list:
        raise NotImplementedError("SAEConnector.fetch_sales no implementado.")

    def fetch_cxc(self, **kwargs) -> list:
        raise NotImplementedError("SAEConnector.fetch_cxc no implementado.")

    def fetch_customers(self, **kwargs) -> list:
        raise NotImplementedError("SAEConnector.fetch_customers no implementado.")

    def fetch_products(self, **kwargs) -> list:
        raise NotImplementedError("SAEConnector.fetch_products no implementado.")

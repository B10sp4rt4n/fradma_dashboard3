"""
contpaqi_connector.py
Conector PLACEHOLDER para CONTPAQi.

Estado: planned — NO implementado.
No realiza conexion real. No importa SDK de CONTPAQi.
"""

from .base_connector import BaseConnector


class CONTPAQiConnector(BaseConnector):
    """
    Conector para CONTPAQi (Contabilidad / Comercial).

    PLACEHOLDER — Requiere SDK CONTPAQi o ODBC.
    Todos los metodos lanzan NotImplementedError hasta que se implemente.
    """

    connector_id = "contpaqi"
    status       = "planned"

    def connect(self) -> bool:
        raise NotImplementedError(
            "CONTPAQiConnector no implementado. Requiere SDK CONTPAQi o ODBC."
        )

    def test_connection(self) -> dict:
        raise NotImplementedError(
            "CONTPAQiConnector no implementado. Requiere SDK CONTPAQi o ODBC."
        )

    def get_metadata(self) -> dict:
        raise NotImplementedError(
            "CONTPAQiConnector no implementado. Requiere SDK CONTPAQi o ODBC."
        )

    def fetch_sales(self, **kwargs) -> list:
        raise NotImplementedError("CONTPAQiConnector.fetch_sales no implementado.")

    def fetch_cxc(self, **kwargs) -> list:
        raise NotImplementedError("CONTPAQiConnector.fetch_cxc no implementado.")

    def fetch_customers(self, **kwargs) -> list:
        raise NotImplementedError("CONTPAQiConnector.fetch_customers no implementado.")

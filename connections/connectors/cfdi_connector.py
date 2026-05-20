"""
cfdi_connector.py
Conector para CFDI via XML local o PAC.

Estado: partial — Parseo XML ya implementado en cfdi/parser.py.
Este conector actua como wrapper del modulo cfdi existente.
"""

from .base_connector import BaseConnector


class CFDIConnector(BaseConnector):
    """
    Conector para CFDI.

    Estado partial: el parseo XML ya existe en cfdi/parser.py.
    Este conector envuelve esa funcionalidad con la interfaz estandar.
    La conexion a PACs (Finkok, Tralix, etc.) no esta implementada.
    """

    connector_id = "cfdi"
    status       = "partial"

    def connect(self) -> bool:
        # No requiere conexion de red para parseo XML local
        return True

    def test_connection(self) -> dict:
        return {
            "ok":      True,
            "message": "CFDIConnector listo para parseo XML local.",
            "status":  "partial",
        }

    def get_metadata(self) -> dict:
        return {
            "connector_id": self.connector_id,
            "status":       self.status,
            "source":       "XML local / PAC",
            "version":      "1.0",
            "notes":        "Parseo XML implementado en cfdi/parser.py. PAC no conectado.",
        }

    def fetch_sales(self, xml_paths: list = None, **kwargs) -> list:
        """
        Parsea facturas CFDI desde una lista de rutas de archivos XML.

        Args:
            xml_paths: Lista de rutas absolutas a archivos XML CFDI.

        Returns:
            Lista de dicts con datos de cada CFDI.
        """
        if not xml_paths:
            return []

        try:
            from cfdi.parser import parse_cfdi  # type: ignore
        except ImportError:
            raise ImportError(
                "cfdi.parser no disponible. Verifica que el modulo cfdi/ exista."
            )

        results = []
        for path in xml_paths:
            try:
                record = parse_cfdi(path)
                results.append(record)
            except Exception:
                pass  # Archivo invalido; se omite sin lanzar excepcion
        return results

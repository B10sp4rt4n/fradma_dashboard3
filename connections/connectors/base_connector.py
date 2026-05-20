"""
base_connector.py
Clase abstracta que define la interfaz comun de todos los conectores.
Cada conector especifico (SAE, CONTPAQi, etc.) debe heredar esta clase.
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseConnector(ABC):
    """
    Interfaz base del CrossConnector Layer.

    Todos los conectores deben:
    - Declarar su `connector_id` (string unico)
    - Implementar `connect()` y `test_connection()`
    - Implementar los fetch_* que correspondan a su sistema
    - Levantar NotImplementedError en los fetch_* no soportados

    NOTA DE SEGURIDAD:
    - Las credenciales NUNCA se almacenan en atributos publicos
    - Los conectores NO hardcodean strings de conexion
    - Las credenciales se pasan por constructor o variables de entorno
    """

    connector_id: str = "base"
    status:       str = "abstract"

    # -----------------------------------------------------------------
    # Ciclo de vida
    # -----------------------------------------------------------------

    @abstractmethod
    def connect(self) -> bool:
        """
        Establece la conexion al sistema externo.

        Returns:
            True si la conexion fue exitosa, False en caso contrario.
        """
        ...

    @abstractmethod
    def test_connection(self) -> dict:
        """
        Verifica que la conexion este activa y retorna metadatos basicos.

        Returns:
            dict con al menos: {ok: bool, message: str, ...}
        """
        ...

    @abstractmethod
    def get_metadata(self) -> dict:
        """
        Retorna metadatos del sistema conectado (version, empresa, etc.).

        Returns:
            dict con informacion del sistema externo.
        """
        ...

    # -----------------------------------------------------------------
    # Fetch de datos
    # -----------------------------------------------------------------

    def fetch_sales(self, **kwargs) -> list:
        """
        Obtiene registros de ventas del sistema externo.

        Returns:
            Lista de dicts con registros de ventas.
        """
        raise NotImplementedError(
            f"fetch_sales no implementado para el conector '{self.connector_id}'"
        )

    def fetch_cxc(self, **kwargs) -> list:
        """
        Obtiene registros de cuentas por cobrar del sistema externo.

        Returns:
            Lista de dicts con registros de CxC.
        """
        raise NotImplementedError(
            f"fetch_cxc no implementado para el conector '{self.connector_id}'"
        )

    def fetch_customers(self, **kwargs) -> list:
        """
        Obtiene catalogo de clientes del sistema externo.

        Returns:
            Lista de dicts con registros de clientes.
        """
        raise NotImplementedError(
            f"fetch_customers no implementado para el conector '{self.connector_id}'"
        )

    def fetch_products(self, **kwargs) -> list:
        """
        Obtiene catalogo de productos del sistema externo.

        Returns:
            Lista de dicts con registros de productos.
        """
        raise NotImplementedError(
            f"fetch_products no implementado para el conector '{self.connector_id}'"
        )

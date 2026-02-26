"""
Tests unitarios para el módulo de ingesta CFDI → Neon.

Usa mocks para simular la conexión a PostgreSQL sin necesitar
una base de datos real durante los tests.

Autor: Fradma Dashboard Team
Fecha: Febrero 2026
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from decimal import Decimal
from datetime import datetime

from cfdi.ingestion import NeonIngestion, verify_connection


@pytest.fixture
def mock_connection():
    """Mock de conexión psycopg2."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


@pytest.fixture
def sample_venta_data():
    """Datos de ejemplo de una factura parseada."""
    return {
        'uuid': '12345678-1234-1234-1234-123456789012',
        'fecha_emision': datetime(2025, 1, 15, 10, 30, 0),
        'fecha_timbrado': datetime(2025, 1, 15, 10, 35, 0),
        'subtotal': Decimal('10000.00'),
        'iva': Decimal('1600.00'),
        'total': Decimal('11600.00'),
        'moneda': 'MXN',
        'tipo_cambio': Decimal('1.0'),
        'emisor_rfc': 'XAXX010101000',
        'emisor_nombre': 'Empresa Test SA de CV',
        'receptor_rfc': 'XEXX010101000',
        'receptor_nombre': 'Cliente Test SA de CV',
        'forma_pago': '99',
        'metodo_pago': 'PPD',
        'uso_cfdi': 'G03',
        'lugar_expedicion': '01000',
        'serie': 'A',
        'folio': '12345',
        'tipo_comprobante': 'I',
        'xml_original': '<xml>...</xml>',
        'conceptos': [
            {
                'clave_prod_serv': '01010101',
                'clave_unidad': 'H87',
                'cantidad': Decimal('100'),
                'unidad': 'Pieza',
                'descripcion': 'Producto de prueba',
                'valor_unitario': Decimal('100.00'),
                'importe': Decimal('10000.00')
            }
        ]
    }


@pytest.fixture
def sample_pago_data():
    """Datos de ejemplo de un complemento de pago."""
    return {
        'uuid_pago': '98765432-9876-9876-9876-987654321098',
        'fecha_pago': datetime(2025, 2, 15, 14, 0, 0),
        'cfdi_relacionados': [
            {
                'uuid_venta': '12345678-1234-1234-1234-123456789012',
                'forma_pago': '03',
                'moneda': 'MXN',
                'tipo_cambio': Decimal('1.0'),
                'monto_pagado': Decimal('11600.00'),
                'monto_pagado_mxn': Decimal('11600.00'),
                'saldo_anterior': Decimal('11600.00'),
                'saldo_insoluto': Decimal('0.00'),
                'num_parcialidad': 1
            }
        ]
    }


class TestNeonIngestionInit:
    """Tests de inicialización de NeonIngestion."""
    
    def test_init_guarda_connection_string(self):
        """Verifica que se guarde el connection string."""
        conn_str = "postgresql://user:pass@host:5432/db"
        ingestion = NeonIngestion(conn_str)
        
        assert ingestion.connection_string == conn_str
        assert ingestion.conn is None
        
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_connect_establece_conexion(self, mock_connect):
        """Verifica que connect() establezca la conexión."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        ingestion = NeonIngestion("postgresql://test")
        ingestion.connect()
        
        assert ingestion.conn == mock_conn
        mock_connect.assert_called_once_with("postgresql://test")
        
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_context_manager(self, mock_connect):
        """Verifica que funcione como context manager."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        with NeonIngestion("postgresql://test") as ingestion:
            assert ingestion.conn == mock_conn
            
        mock_conn.close.assert_called_once()


class TestInsertVenta:
    """Tests de inserción de facturas."""
    
    @patch('cfdi.ingestion.extras.execute_values')
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_insert_venta_exitosa(self, mock_connect, mock_execute_values, sample_venta_data):
        """Verifica inserción exitosa de una factura con conceptos."""
        mock_conn, mock_cursor = self._setup_mock_connection(mock_connect)
        
        # Mock de fetchone para simular RETURNING id
        mock_cursor.fetchone.side_effect = [
            None,  # Primera llamada: _uuid_exists (no existe)
            (123,),  # Segunda llamada: RETURNING id del INSERT
        ]
        
        ingestion = NeonIngestion("postgresql://test")
        ingestion.connect()
        
        success, msg = ingestion.insert_venta(
            empresa_id=1,
            venta_data=sample_venta_data
        )
        
        assert success is True
        assert 'insertado correctamente' in msg
        mock_conn.commit.assert_called_once()
        
        # Verificar que se llamó execute para INSERT ventas
        assert mock_cursor.execute.call_count >= 1
        # Y execute_values para conceptos
        mock_execute_values.assert_called_once()
        
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_insert_venta_duplicada_se_salta(self, mock_connect, sample_venta_data):
        """Verifica que un UUID duplicado se salte sin error."""
        mock_conn, mock_cursor = self._setup_mock_connection(mock_connect)
        
        # Simular que el UUID ya existe
        mock_cursor.fetchone.return_value = (1,)
        
        ingestion = NeonIngestion("postgresql://test")
        ingestion.connect()
        
        success, msg = ingestion.insert_venta(
            empresa_id=1,
            venta_data=sample_venta_data,
            skip_duplicates=True
        )
        
        assert success is True
        assert 'duplicado' in msg.lower()
        mock_conn.commit.assert_not_called()
        
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_insert_venta_sin_uuid_falla(self, mock_connect):
        """Verifica que fallar si no hay UUID."""
        mock_conn, mock_cursor = self._setup_mock_connection(mock_connect)
        
        ingestion = NeonIngestion("postgresql://test")
        ingestion.connect()
        
        venta_sin_uuid = {'subtotal': Decimal('100')}
        
        success, msg = ingestion.insert_venta(
            empresa_id=1,
            venta_data=venta_sin_uuid
        )
        
        assert success is False
        assert 'UUID faltante' in msg
        
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_insert_venta_rollback_en_error(self, mock_connect, sample_venta_data):
        """Verifica que se haga rollback en caso de error."""
        mock_conn, mock_cursor = self._setup_mock_connection(mock_connect)
        
        # Simular error en execute
        mock_cursor.execute.side_effect = Exception("Error de prueba")
        
        ingestion = NeonIngestion("postgresql://test")
        ingestion.connect()
        
        success, msg = ingestion.insert_venta(
            empresa_id=1,
            venta_data=sample_venta_data
        )
        
        assert success is False
        assert 'Error de prueba' in msg
        mock_conn.rollback.assert_called_once()
        
    def _setup_mock_connection(self, mock_connect):
        """Helper para configurar mock de conexión."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        return mock_conn, mock_cursor


class TestInsertVentasBatch:
    """Tests de inserción batch de facturas."""
    
    @patch('cfdi.ingestion.extras.execute_values')
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_batch_procesa_multiples_ventas(self, mock_connect, mock_execute_values, sample_venta_data):
        """Verifica procesamiento batch de múltiples facturas."""
        mock_conn, mock_cursor = self._setup_mock_connection(mock_connect)
        
        # Simular 3 ventas: 2 nuevas, 1 duplicada
        mock_cursor.fetchone.side_effect = [
            None, (1,),  # Primera venta: no existe, insertar con ID 1
            None, (2,),  # Segunda venta: no existe, insertar con ID 2
            (1,),  # Tercera venta: ya existe (duplicada)
        ]
        
        # Crear 3 ventas con UUIDs diferentes
        ventas = [
            {**sample_venta_data, 'uuid': f'uuid-{i}'}
            for i in range(1, 4)
        ]
        
        ingestion = NeonIngestion("postgresql://test")
        ingestion.connect()
        
        stats = ingestion.insert_ventas_batch(
            empresa_id=1,
            ventas_list=ventas
        )
        
        assert stats['total'] == 3
        assert stats['insertados'] == 2
        assert stats['duplicados'] == 1
        assert stats['errores'] == 0
        
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_batch_captura_errores(self, mock_connect, sample_venta_data):
        """Verifica que el batch capture errores individuales sin fallar."""
        mock_conn, mock_cursor = self._setup_mock_connection(mock_connect)
        
        # Primera venta OK, segunda con error, tercera OK
        mock_cursor.fetchone.side_effect = [
            None, (1,),  # Primera OK
            None, Exception("Error en segunda"),  # Segunda falla
            None, (3,),  # Tercera OK
        ]
        
        ventas = [
            {**sample_venta_data, 'uuid': f'uuid-{i}'}
            for i in range(1, 4)
        ]
        
        # Forzar error en insert_venta para la segunda
        def side_effect_execute(*args):
            if 'uuid-2' in str(args):
                raise Exception("Error simulado")
        
        mock_cursor.execute.side_effect = side_effect_execute
        
        ingestion = NeonIngestion("postgresql://test")
        ingestion.connect()
        
        stats = ingestion.insert_ventas_batch(
            empresa_id=1,
            ventas_list=ventas
        )
        
        assert stats['total'] == 3
        assert stats['errores'] >= 1
        assert len(stats['detalles_errores']) >= 1
        
    def _setup_mock_connection(self, mock_connect):
        """Helper para configurar mock de conexión."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        return mock_conn, mock_cursor


class TestInsertPago:
    """Tests de inserción de complementos de pago."""
    
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_insert_pago_exitoso(self, mock_connect, sample_pago_data):
        """Verifica inserción exitosa de un complemento de pago."""
        mock_conn, mock_cursor = self._setup_mock_connection(mock_connect)
        
        # Mock fetchone: check duplicado (no existe), luego buscar cfdi_id
        mock_cursor.fetchone.side_effect = [
            None,  # No existe pago duplicado
            (999,),  # cfdi_id encontrado para el UUID de venta
        ]
        
        ingestion = NeonIngestion("postgresql://test")
        ingestion.connect()
        
        success, msg = ingestion.insert_pago(
            empresa_id=1,
            pago_data=sample_pago_data
        )
        
        assert success is True
        assert 'insertado' in msg.lower()
        mock_conn.commit.assert_called_once()
        
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_insert_pago_sin_cfdi_relacionado(self, mock_connect, sample_pago_data):
        """Verifica manejo cuando el CFDI relacionado no existe."""
        mock_conn, mock_cursor = self._setup_mock_connection(mock_connect)
        
        # Mock: pago no duplicado, pero cfdi_id no encontrado
        mock_cursor.fetchone.side_effect = [
            None,  # No existe pago duplicado
            None,  # cfdi_id NO encontrado
        ]
        
        ingestion = NeonIngestion("postgresql://test")
        ingestion.connect()
        
        success, msg = ingestion.insert_pago(
            empresa_id=1,
            pago_data=sample_pago_data
        )
        
        # El insert debe "funcionar" pero sin insertar nada (0 relaciones)
        assert success is True
        assert '0 relaciones' in msg
        
    def _setup_mock_connection(self, mock_connect):
        """Helper para configurar mock de conexión."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        return mock_conn, mock_cursor


class TestGetEmpresaStats:
    """Tests de estadísticas de empresa."""
    
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_get_stats_retorna_datos_correctos(self, mock_connect):
        """Verifica que get_empresa_stats retorne estructura correcta."""
        mock_conn, mock_cursor = self._setup_mock_connection(mock_connect)
        
        # Mock de respuestas para cada query
        mock_cursor.fetchone.side_effect = [
            (150,),  # total_cfdis
            (450,),  # total_conceptos
            (75,),   # total_pagos
            (datetime(2024, 1, 1), datetime(2025, 12, 31)),  # rango fechas
        ]
        
        mock_cursor.fetchall.return_value = [
            (Decimal('1500000.00'), 'MXN'),
            (Decimal('50000.00'), 'USD'),
        ]
        
        ingestion = NeonIngestion("postgresql://test")
        ingestion.connect()
        
        stats = ingestion.get_empresa_stats(empresa_id=1)
        
        assert stats['total_cfdis'] == 150
        assert stats['total_conceptos'] == 450
        assert stats['total_pagos'] == 75
        assert 'fecha_primer_cfdi' in stats
        assert 'totales_por_moneda' in stats
        assert stats['totales_por_moneda']['MXN'] == 1500000.00
        assert stats['totales_por_moneda']['USD'] == 50000.00
        
    def _setup_mock_connection(self, mock_connect):
        """Helper para configurar mock de conexión."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        return mock_conn, mock_cursor


class TestConnectionHelpers:
    """Tests de funciones auxiliares de conexión."""
    
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_verify_connection_exitosa(self, mock_connect):
        """Verifica que verify_connection retorne True en conexión exitosa."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ('PostgreSQL 14.5',)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        result = verify_connection("postgresql://test")
        
        assert result is True
        mock_connect.assert_called_once_with("postgresql://test")
        mock_conn.close.assert_called_once()
        
    @patch('cfdi.ingestion.psycopg2.connect')
    def test_verify_connection_falla(self, mock_connect):
        """Verifica que verify_connection retorne False en error."""
        mock_connect.side_effect = Exception("Connection refused")
        
        result = verify_connection("postgresql://invalid")
        
        assert result is False

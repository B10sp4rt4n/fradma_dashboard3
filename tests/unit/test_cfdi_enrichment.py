"""
Tests unitarios para el módulo de enriquecimiento CFDI.

Autor: Fradma Dashboard Team
Fecha: Febrero 2026
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from cfdi.enrichment import (
    CFDIEnrichment,
    clasificar_rapido,
    LINEAS_NEGOCIO,
    ALIASES_DIRECTOS
)


@pytest.fixture
def enricher_sin_gpt():
    """Enricher sin cliente GPT (solo keywords)."""
    return CFDIEnrichment()


@pytest.fixture
def enricher_con_gpt_mock():
    """Enricher con cliente GPT mockeado."""
    with patch('cfdi.enrichment.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        enricher = CFDIEnrichment(api_key="test-key")
        enricher.client = mock_client
        
        yield enricher


@pytest.fixture
def conceptos_ejemplo():
    """Conceptos de ejemplo para tests."""
    return [
        {
            'descripcion': 'Tornillo hexagonal 1/4 x 2 pulgadas',
            'cantidad': Decimal('1000'),
            'valor_unitario': Decimal('1.50'),
            'importe': Decimal('1500.00')
        },
        {
            'descripcion': 'Cemento gris Portland 50kg',
            'cantidad': Decimal('100'),
            'valor_unitario': Decimal('150.00'),
            'importe': Decimal('15000.00')
        },
        {
            'descripcion': 'Cable eléctrico calibre 12 AWG',
            'cantidad': Decimal('500'),
            'valor_unitario': Decimal('12.50'),
            'importe': Decimal('6250.00')
        }
    ]


class TestCFDIEnrichmentInit:
    """Tests de inicialización."""
    
    def test_init_sin_api_key(self):
        """Verifica inicialización sin API key."""
        enricher = CFDIEnrichment()
        assert enricher.model == "gpt-4o-mini"
        assert enricher.use_cache is True
        assert enricher.cache == {}
    
    def test_init_con_parametros(self):
        """Verifica inicialización con parámetros custom."""
        enricher = CFDIEnrichment(
            api_key="test",
            model="gpt-4",
            use_cache=False
        )
        assert enricher.model == "gpt-4"
        assert enricher.use_cache is False


class TestClasificacionBasica:
    """Tests de clasificación por keywords."""
    
    def test_clasificar_tornillo(self, enricher_sin_gpt):
        """Verifica clasificación de tornillo."""
        resultado = enricher_sin_gpt._clasificar_por_keywords(
            "Tornillo hexagonal 1/4 x 2 pulgadas"
        )
        assert resultado == "ferreteria_industrial"
    
    def test_clasificar_cemento(self, enricher_sin_gpt):
        """Verifica clasificación de cemento."""
        resultado = enricher_sin_gpt._clasificar_por_keywords(
            "Cemento gris Portland 50kg"
        )
        assert resultado == "materiales_construccion"
    
    def test_clasificar_cable(self, enricher_sin_gpt):
        """Verifica clasificación de cable eléctrico."""
        resultado = enricher_sin_gpt._clasificar_por_keywords(
            "Cable eléctrico calibre 12"
        )
        assert resultado == "equipos_electricos"
    
    def test_sin_match_retorna_otro(self, enricher_sin_gpt):
        """Verifica que sin match retorna 'otro'."""
        resultado = enricher_sin_gpt._clasificar_por_keywords(
            "Producto genérico sin keywords"
        )
        assert resultado == "otro"
    
    def test_case_insensitive(self, enricher_sin_gpt):
        """Verifica que la clasificación es case-insensitive."""
        resultado1 = enricher_sin_gpt._clasificar_por_keywords("TORNILLO")
        resultado2 = enricher_sin_gpt._clasificar_por_keywords("tornillo")
        assert resultado1 == resultado2 == "ferreteria_industrial"


class TestClasificarConcepto:
    """Tests de clasificación completa de conceptos."""
    
    def test_clasificar_con_cache(self, enricher_sin_gpt):
        """Verifica que el caché funciona."""
        desc = "Tornillo especial"
        
        # Primera clasificación
        resultado1 = enricher_sin_gpt.clasificar_concepto(desc, usar_gpt=False)
        
        # Verificar que está en caché
        cache_key = enricher_sin_gpt._get_cache_key(desc)
        assert cache_key in enricher_sin_gpt.cache
        
        # Segunda clasificación debe usar caché
        resultado2 = enricher_sin_gpt.clasificar_concepto(desc, usar_gpt=False)
        assert resultado1 == resultado2
    
    def test_clasificar_sin_cache(self):
        """Verifica clasificación sin caché."""
        enricher = CFDIEnrichment(use_cache=False)
        desc = "Tornillo especial"
        
        resultado = enricher.clasificar_concepto(desc, usar_gpt=False)
        
        # Caché debe estar vacío
        assert len(enricher.cache) == 0
        assert resultado == "ferreteria_industrial"
    
    @patch('cfdi.enrichment.CFDIEnrichment._clasificar_con_gpt')
    def test_clasificar_usa_gpt_cuando_no_hay_match(
        self,
        mock_gpt,
        enricher_sin_gpt
    ):
        """Verifica que usa GPT cuando no hay match de keywords."""
        # Configurar mock GPT
        mock_gpt.return_value = "plasticos_industriales"
        enricher_sin_gpt.client = MagicMock()  # Simular que hay cliente
        
        resultado = enricher_sin_gpt.clasificar_concepto(
            "Producto desconocido XYZ-123",
            usar_gpt=True
        )
        
        # Debe haber llamado a GPT
        mock_gpt.assert_called_once()
        assert resultado == "plasticos_industriales"
    
    def test_clasificar_sin_descripcion(self, enricher_sin_gpt):
        """Verifica manejo de descripción vacía."""
        resultado = enricher_sin_gpt.clasificar_concepto("", usar_gpt=False)
        assert resultado == "otro"


class TestEnriquecimientoBatch:
    """Tests de enriquecimiento batch."""
    
    def test_enriquecer_batch_basico(self, enricher_sin_gpt, conceptos_ejemplo):
        """Verifica enriquecimiento batch sin GPT."""
        enriquecidos = enricher_sin_gpt.enriquecer_conceptos_batch(
            conceptos_ejemplo,
            usar_gpt=False
        )
        
        assert len(enriquecidos) == 3
        assert all('linea_negocio' in c for c in enriquecidos)
        
        # Verificar clasificaciones esperadas
        assert enriquecidos[0]['linea_negocio'] == 'ferreteria_industrial'
        assert enriquecidos[1]['linea_negocio'] == 'materiales_construccion'
        assert enriquecidos[2]['linea_negocio'] == 'equipos_electricos'
    
    def test_enriquecer_batch_con_max_gpt_calls(self, enricher_sin_gpt):
        """Verifica límite de llamadas GPT."""
        # Usar caché deshabilitado para este test
        enricher_sin_gpt.use_cache = False
        
        conceptos = [
            {'descripcion': f'Producto desconocido XYZABC{i}'}
            for i in range(10)
        ]
        
        # Mock cliente GPT
        enricher_sin_gpt.client = MagicMock()
        
        with patch.object(
            enricher_sin_gpt,
            '_clasificar_con_gpt',
            return_value='plasticos_industriales'
        ) as mock_gpt:
            enriquecidos = enricher_sin_gpt.enriquecer_conceptos_batch(
                conceptos,
                usar_gpt=True,
                max_gpt_calls=5
            )
            
            # Solo debe haber llamado GPT máximo 5 veces
            assert mock_gpt.call_count == 5
            assert len(enriquecidos) == 10
            
            # Los primeros 5 deben tener clasificación de GPT
            assert all(
                e['linea_negocio'] == 'plasticos_industriales'
                for e in enriquecidos[:5]
            )
            # Los últimos 5 deben tener "otro" (sin GPT)
            assert all(
                e['linea_negocio'] == 'otro'
                for e in enriquecidos[5:]
            )
    
    def test_enriquecer_batch_sin_descripcion(self, enricher_sin_gpt):
        """Verifica manejo de conceptos sin descripción."""
        conceptos = [
            {'importe': 100},  # Sin descripción
            {'descripcion': '', 'importe': 200},  # Descripción vacía
        ]
        
        enriquecidos = enricher_sin_gpt.enriquecer_conceptos_batch(
            conceptos,
            usar_gpt=False
        )
        
        assert all(c['linea_negocio'] == 'otro' for c in enriquecidos)


class TestDeteccionAnomalias:
    """Tests de detección de anomalías."""
    
    def test_detectar_cantidad_alta(self, enricher_sin_gpt):
        """Verifica detección de cantidad anormalmente alta."""
        concepto = {
            'descripcion': 'Tornillo',
            'cantidad': 15000,
            'valor_unitario': 1.50
        }
        
        anomalias = enricher_sin_gpt.detectar_anomalias(concepto)
        
        assert len(anomalias) > 0
        assert any('alta' in a.lower() for a in anomalias)
    
    def test_detectar_precio_cero(self, enricher_sin_gpt):
        """Verifica detección de precio <= 0."""
        concepto = {
            'descripcion': 'Producto',
            'cantidad': 10,
            'valor_unitario': 0
        }
        
        anomalias = enricher_sin_gpt.detectar_anomalias(concepto)
        
        assert len(anomalias) > 0
        assert any('precio' in a.lower() for a in anomalias)
    
    def test_detectar_descripcion_corta(self, enricher_sin_gpt):
        """Verifica detección de descripción muy corta."""
        concepto = {
            'descripcion': 'ABC',
            'cantidad': 10,
            'valor_unitario': 100
        }
        
        anomalias = enricher_sin_gpt.detectar_anomalias(concepto)
        
        assert len(anomalias) > 0
        assert any('descripción' in a.lower() for a in anomalias)
    
    def test_detectar_precio_desviado_historico(self, enricher_sin_gpt):
        """Verifica detección de precio desviado vs histórico."""
        concepto = {
            'descripcion': 'Tornillo',
            'cantidad': 1000,
            'valor_unitario': 150.00  # Muy alto vs histórico
        }
        
        historico = [
            {'valor_unitario': 10.00},
            {'valor_unitario': 12.00},
            {'valor_unitario': 11.00},
        ]
        
        anomalias = enricher_sin_gpt.detectar_anomalias(concepto, historico)
        
        assert len(anomalias) > 0
        assert any('histórico' in a.lower() for a in anomalias)
    
    def test_sin_anomalias(self, enricher_sin_gpt):
        """Verifica que concepto normal no genera alertas."""
        concepto = {
            'descripcion': 'Tornillo hexagonal estándar',
            'cantidad': 100,
            'valor_unitario': 1.50
        }
        
        anomalias = enricher_sin_gpt.detectar_anomalias(concepto)
        
        assert len(anomalias) == 0


class TestGenerarResumen:
    """Tests de generación de resúmenes."""
    
    def test_generar_resumen_basico(self, enricher_sin_gpt):
        """Verifica generación de resumen por línea de negocio."""
        conceptos = [
            {
                'descripcion': 'Tornillo 1',
                'linea_negocio': 'ferreteria_industrial',
                'importe': 100
            },
            {
                'descripcion': 'Tornillo 2',
                'linea_negocio': 'ferreteria_industrial',
                'importe': 200
            },
            {
                'descripcion': 'Cemento',
                'linea_negocio': 'materiales_construccion',
                'importe': 500
            }
        ]
        
        resumen = enricher_sin_gpt.generar_resumen(conceptos)
        
        assert 'ferreteria_industrial' in resumen
        assert resumen['ferreteria_industrial']['total_conceptos'] == 2
        assert resumen['ferreteria_industrial']['importe_total'] == 300.0
        
        assert 'materiales_construccion' in resumen
        assert resumen['materiales_construccion']['total_conceptos'] == 1
        assert resumen['materiales_construccion']['importe_total'] == 500.0
    
    def test_resumen_ejemplos_limitados(self, enricher_sin_gpt):
        """Verifica que solo guarda máximo 3 ejemplos."""
        conceptos = [
            {
                'descripcion': f'Tornillo {i}',
                'linea_negocio': 'ferreteria_industrial',
                'importe': 100
            }
            for i in range(10)
        ]
        
        resumen = enricher_sin_gpt.generar_resumen(conceptos)
        
        ejemplos = resumen['ferreteria_industrial']['conceptos_ejemplo']
        assert len(ejemplos) <= 3


class TestCacheManagement:
    """Tests de manejo de caché."""
    
    def test_export_import_cache(self, enricher_sin_gpt, tmp_path):
        """Verifica exportación e importación de caché."""
        # Agregar datos al caché
        enricher_sin_gpt.clasificar_concepto("Tornillo", usar_gpt=False)
        enricher_sin_gpt.clasificar_concepto("Cemento", usar_gpt=False)
        
        cache_file = tmp_path / "cache.json"
        
        # Exportar
        enricher_sin_gpt.export_cache(str(cache_file))
        assert cache_file.exists()
        
        # Crear nuevo enricher e importar
        enricher2 = CFDIEnrichment()
        enricher2.import_cache(str(cache_file))
        
        assert len(enricher2.cache) == len(enricher_sin_gpt.cache)
    
    def test_import_cache_no_existente(self, enricher_sin_gpt):
        """Verifica manejo de caché inexistente."""
        # No debe lanzar excepción
        enricher_sin_gpt.import_cache("/ruta/inexistente/cache.json")
        assert len(enricher_sin_gpt.cache) == 0


class TestHelperFunctions:
    """Tests de funciones helper."""
    
    def test_clasificar_rapido(self):
        """Verifica función helper clasificar_rapido."""
        resultado = clasificar_rapido("Tornillo hexagonal")
        assert resultado == "ferreteria_industrial"
    
    def test_lineas_negocio_definidas(self):
        """Verifica que las líneas de negocio están definidas."""
        assert len(LINEAS_NEGOCIO) > 0
        assert "ferreteria_industrial" in LINEAS_NEGOCIO
        assert "otro" in LINEAS_NEGOCIO
    
    def test_aliases_directos_definidos(self):
        """Verifica que los aliases están definidos."""
        assert len(ALIASES_DIRECTOS) > 0
        assert "tornillo" in ALIASES_DIRECTOS
        assert ALIASES_DIRECTOS["tornillo"] == "ferreteria_industrial"


class TestIntegracion:
    """Tests de integración completos."""
    
    def test_flujo_completo_sin_gpt(self, enricher_sin_gpt, conceptos_ejemplo):
        """Verifica flujo completo de enriquecimiento sin GPT."""
        # 1. Enriquecer conceptos
        enriquecidos = enricher_sin_gpt.enriquecer_conceptos_batch(
            conceptos_ejemplo,
            usar_gpt=False
        )
        
        # 2. Generar resumen
        resumen = enricher_sin_gpt.generar_resumen(enriquecidos)
        
        # 3. Detectar anomalías
        anomalias_por_concepto = [
            enricher_sin_gpt.detectar_anomalias(c)
            for c in enriquecidos
        ]
        
        # Verificaciones
        assert len(enriquecidos) == 3
        assert len(resumen) >= 2  # Al menos 2 líneas diferentes
        assert all(isinstance(a, list) for a in anomalias_por_concepto)

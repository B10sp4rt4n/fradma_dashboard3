"""
Tests unitarios para AI Helper Premium (GPT-4o-mini integration).
Valida generación de insights, manejo de API y parseo de respuestas.

Coverage objetivo: 80%+ en utils/ai_helper_premium.py
"""

import pytest
import json
from unittest.mock import patch, Mock, MagicMock


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_openai_response_vendedores():
    """Mock de respuesta de OpenAI para insights de vendedores."""
    mock = Mock()
    mock.choices = [Mock()]
    mock.choices[0].message.content = json.dumps({
        "insight_clave": "Alta concentración de riesgo: 3 vendedores representan 65% de ventas",
        "recomendaciones_equipos": [
            "Implementar programa de capacitación para vendedores bottom 20%",
            "Redistribuir cartera del top performer para reducir concentración"
        ],
        "alertas_estrategicas": [
            "Riesgo de dependencia de vendedor top",
            "5 vendedores por debajo del ticket promedio"
        ],
        "oportunidades_mejora": [
            "Replicar estrategia de vendedor top en equipo medio",
            "Programa de mentoring cruzado"
        ]
    })
    return mock


@pytest.fixture
def mock_openai_response_ejecutivo():
    """Mock de respuesta de OpenAI para insights ejecutivos."""
    mock = Mock()
    mock.choices = [Mock()]
    mock.choices[0].message.content = json.dumps({
        "diagnostico_integral": "Crecimiento de ventas sólido pero cartera en riesgo moderado",
        "riesgos_ocultos": [
            "Línea top en ventas coincide con línea crítica en CxC",
            "Morosidad tendencial creciente"
        ],
        "decisiones_criticas": [
            "Revisar políticas de crédito para línea top",
            "Activar plan de cobranza proactiva para casos urgentes"
        ],
        "escenario_proyectado": "Sin corrección, morosidad aumentará 5-8% en 60 días"
    })
    return mock


@pytest.fixture
def fake_api_key():
    """API key ficticia para tests."""
    return "sk-test-fake-key-1234567890"


# ═══════════════════════════════════════════════════════════════════════
# TESTS: generar_insights_kpi_vendedores
# ═══════════════════════════════════════════════════════════════════════

@patch('utils.ai_helper_premium.OpenAI')
def test_insights_vendedores_exitoso(mock_openai_class, mock_openai_response_vendedores, fake_api_key):
    """Test: generar_insights_kpi_vendedores() retorna insights correctos."""
    from utils.ai_helper_premium import generar_insights_kpi_vendedores
    
    # Configurar mock
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_openai_response_vendedores
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_insights_kpi_vendedores(
        num_vendedores=15,
        ticket_promedio_general=12500,
        eficiencia_general=78.5,
        vendedor_top="Juan Pérez",
        ventas_vendedor_top=350000,
        vendedor_bottom="Pedro López",
        ventas_vendedor_bottom=45000,
        concentracion_top3_pct=65.0,
        api_key=fake_api_key
    )
    
    # Validar estructura de respuesta
    assert isinstance(resultado, dict)
    assert 'insight_clave' in resultado
    assert 'recomendaciones_equipos' in resultado
    assert 'alertas_estrategicas' in resultado
    
    # Validar contenido
    assert len(resultado['recomendaciones_equipos']) >= 2
    assert isinstance(resultado['alertas_estrategicas'], list)


@patch('utils.ai_helper_premium.OpenAI')
def test_insights_vendedores_con_datos_detallados(mock_openai_class, mock_openai_response_vendedores, fake_api_key):
    """Test: Incluye datos detallados de vendedores en el prompt."""
    from utils.ai_helper_premium import generar_insights_kpi_vendedores
    
    # Configurar mock
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_openai_response_vendedores
    mock_openai_class.return_value = mock_client
    
    datos_vendedores = [
        {'nombre': 'Juan Pérez', 'ventas': 350000, 'ticket_avg': 15000},
        {'nombre': 'María García', 'ventas': 280000, 'ticket_avg': 13000},
        {'nombre': 'Carlos Ruiz', 'ventas': 210000, 'ticket_avg': 11000}
    ]
    
    # Ejecutar
    resultado = generar_insights_kpi_vendedores(
        num_vendedores=15,
        ticket_promedio_general=12500,
        eficiencia_general=78.5,
        vendedor_top="Juan Pérez",
        ventas_vendedor_top=350000,
        vendedor_bottom="Pedro López",
        ventas_vendedor_bottom=45000,
        concentracion_top3_pct=65.0,
        api_key=fake_api_key,
        datos_vendedores=datos_vendedores
    )
    
    # Validar que se llamó a la API con datos detallados
    mock_client.chat.completions.create.assert_called_once()
    call_args = mock_client.chat.completions.create.call_args
    mensaje_contexto = call_args.kwargs['messages'][1]['content']
    
    # Validar que el contexto incluye nombres de vendedores
    assert 'Juan Pérez' in mensaje_contexto
    assert '350000' in mensaje_contexto or '350,000' in mensaje_contexto


@patch('utils.ai_helper_premium.OpenAI')
def test_insights_vendedores_maneja_error_api(mock_openai_class, fake_api_key):
    """Test: Maneja correctamente errores de API OpenAI."""
    from utils.ai_helper_premium import generar_insights_kpi_vendedores
    
    # Configurar mock para lanzar excepción
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = Exception("API Rate Limit")
    mock_openai_class.return_value = mock_client
    
    # Ejecutar (no debe lanzar excepción)
    resultado = generar_insights_kpi_vendedores(
        num_vendedores=15,
        ticket_promedio_general=12500,
        eficiencia_general=78.5,
        vendedor_top="Juan Pérez",
        ventas_vendedor_top=350000,
        vendedor_bottom="Pedro López",
        ventas_vendedor_bottom=45000,
        concentracion_top3_pct=65.0,
        api_key=fake_api_key
    )
    
    # Validar respuesta de error estructurada
    assert isinstance(resultado, dict)
    assert 'error' in str(resultado).lower() or 'insight_clave' in resultado


@patch('utils.ai_helper_premium.OpenAI')
def test_insights_vendedores_parsea_json_invalido(mock_openai_class, fake_api_key):
    """Test: Maneja respuestas JSON inválidas de OpenAI."""
    from utils.ai_helper_premium import generar_insights_kpi_vendedores
    
    # Configurar mock con JSON inválido
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Este no es un JSON válido"
    
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_insights_kpi_vendedores(
        num_vendedores=15,
        ticket_promedio_general=12500,
        eficiencia_general=78.5,
        vendedor_top="Juan Pérez",
        ventas_vendedor_top=350000,
        vendedor_bottom="Pedro López",
        ventas_vendedor_bottom=45000,
        concentracion_top3_pct=65.0,
        api_key=fake_api_key
    )
    
    # Debe retornar estructura fallback
    assert isinstance(resultado, dict)
    assert 'insight_clave' in resultado or 'error' in str(resultado)


# ═══════════════════════════════════════════════════════════════════════
# TESTS: generar_insights_ejecutivo_consolidado
# ═══════════════════════════════════════════════════════════════════════

@patch('utils.ai_helper_premium.OpenAI')
def test_insights_ejecutivo_exitoso(mock_openai_class, mock_openai_response_ejecutivo, fake_api_key):
    """Test: generar_insights_ejecutivo_consolidado() retorna análisis correcto."""
    from utils.ai_helper_premium import generar_insights_ejecutivo_consolidado
    
    # Configurar mock
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_openai_response_ejecutivo
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_insights_ejecutivo_consolidado(
        total_ventas_periodo=2500000,
        crecimiento_ventas_pct=8.5,
        score_salud_cxc=72,
        pct_morosidad=18.5,
        top_linea_ventas="Producto A",
        top_linea_cxc_critica="Producto A",
        casos_urgentes_cxc=12,
        api_key=fake_api_key
    )
    
    # Validar estructura
    assert isinstance(resultado, dict)
    assert 'diagnostico_integral' in resultado
    assert 'riesgos_ocultos' in resultado
    assert 'decisiones_criticas' in resultado
    assert 'escenario_proyectado' in resultado
    
    # Validar contenido
    assert len(resultado['riesgos_ocultos']) >= 1
    assert len(resultado['decisiones_criticas']) >= 1


@patch('utils.ai_helper_premium.OpenAI')
def test_insights_ejecutivo_incluye_contexto_correcto(mock_openai_class, mock_openai_response_ejecutivo, fake_api_key):
    """Test: El prompt incluye contexto correcto de comparación de períodos."""
    from utils.ai_helper_premium import generar_insights_ejecutivo_consolidado
    
    # Configurar mock
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_openai_response_ejecutivo
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_insights_ejecutivo_consolidado(
        total_ventas_periodo=2500000,
        crecimiento_ventas_pct=8.5,
        score_salud_cxc=72,
        pct_morosidad=18.5,
        top_linea_ventas="Producto A",
        top_linea_cxc_critica="Producto A",
        casos_urgentes_cxc=12,
        api_key=fake_api_key
    )
    
    # Validar que se llamó a la API
    mock_client.chat.completions.create.assert_called_once()
    call_args = mock_client.chat.completions.create.call_args
    mensaje_contexto = call_args.kwargs['messages'][1]['content']
    
    # Validar que incluye advertencia sobre comparación de períodos
    assert 'PERIODOS EQUIVALENTES' in mensaje_contexto or 'período' in mensaje_contexto.lower()
    assert '2500000' in mensaje_contexto or '2,500,000' in mensaje_contexto
    assert 'Producto A' in mensaje_contexto


@patch('utils.ai_helper_premium.OpenAI')
def test_insights_ejecutivo_maneja_error_api(mock_openai_class, fake_api_key):
    """Test: Maneja errores de API y retorna fallback estructurado."""
    from utils.ai_helper_premium import generar_insights_ejecutivo_consolidado
    
    # Configurar mock para lanzar excepción
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = Exception("Network error")
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_insights_ejecutivo_consolidado(
        total_ventas_periodo=2500000,
        crecimiento_ventas_pct=8.5,
        score_salud_cxc=72,
        pct_morosidad=18.5,
        top_linea_ventas="Producto A",
        top_linea_cxc_critica="Producto A",
        casos_urgentes_cxc=12,
        api_key=fake_api_key
    )
    
    # Debe retornar estructura fallback
    assert isinstance(resultado, dict)
    assert 'diagnostico_integral' in resultado
    assert 'error' in resultado['diagnostico_integral'].lower() or 'No disponible' in resultado['escenario_proyectado']


@patch('utils.ai_helper_premium.OpenAI')
def test_insights_ejecutivo_parsea_json_invalido(mock_openai_class, fake_api_key):
    """Test: Maneja JSON inválido y retorna fallback."""
    from utils.ai_helper_premium import generar_insights_ejecutivo_consolidado
    
    # Configurar mock con respuesta no-JSON
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Texto plano sin formato JSON"
    
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_insights_ejecutivo_consolidado(
        total_ventas_periodo=2500000,
        crecimiento_ventas_pct=8.5,
        score_salud_cxc=72,
        pct_morosidad=18.5,
        top_linea_ventas="Producto A",
        top_linea_cxc_critica="Producto A",
        casos_urgentes_cxc=12,
        api_key=fake_api_key
    )
    
    # Debe retornar fallback con estructura correcta
    assert isinstance(resultado, dict)
    assert 'diagnostico_integral' in resultado
    assert resultado['riesgos_ocultos'] == []
    assert resultado['decisiones_criticas'] == []


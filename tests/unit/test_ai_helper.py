"""
Tests unitarios para utils/ai_helper.py
Valida integración con OpenAI GPT-4o-mini para análisis ejecutivos.

Coverage objetivo: 80%+ en utils/ai_helper.py
"""

import pytest
import json
from unittest.mock import patch, Mock, MagicMock


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def fake_api_key():
    """API key ficticia para tests."""
    return "sk-test-fake-openai-key-abc123"


@pytest.fixture
def mock_openai_ytd_response():
    """Mock de respuesta de OpenAI para análisis YTD."""
    mock = Mock()
    mock.choices = [Mock()]
    mock.choices[0].message.content = json.dumps({
        "diagnostico_general": "Crecimiento sólido del 15% YTD vs mismo período año anterior",
        "fortalezas": [
            "Línea Producto A superó expectativas (+25%)",
            "Ritmo de crecimiento sostenido en 40 días"
        ],
        "areas_atencion": [
            "Línea Producto C mostró declive de 5%",
            "Necesario ajustar estrategia de pricing"
        ],
        "recomendaciones_estrategicas": [
            "Reforzar inversión en Producto A",
            "Revisar portafolio de Producto C"
        ]
    })
    return mock


@pytest.fixture
def mock_openai_cxc_response():
    """Mock de respuesta de OpenAI para análisis CxC."""
    mock = Mock()
    mock.choices = [Mock()]
    mock.choices[0].message.content = json.dumps({
        "salud_cartera": "Moderadamente saludable con 72/100 de score",
        "riesgos_criticos": [
            "18.5% de morosidad superior al objetivo 10%",
            "12 casos urgentes requieren atención inmediata"
        ],
        "acciones_prioritarias": [
            "Activar protocolo de cobranza proactiva",
            "Revisar política de crédito para clientes críticos"
        ]
    })
    return mock


# ═══════════════════════════════════════════════════════════════════════
# TESTS: validar_api_key
# ═══════════════════════════════════════════════════════════════════════

@patch('utils.ai_helper.OpenAI')
def test_validar_api_key_exitoso(mock_openai_class, fake_api_key):
    """Test: validar_api_key() retorna True con API key válida."""
    from utils.ai_helper import validar_api_key
    
    # Configurar mock para simular respuesta exitosa
    mock_client = Mock()
    mock_client.models.list.return_value = []  # Respuesta vacía válida
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = validar_api_key(fake_api_key)
    
    # Validar
    assert resultado is True
    mock_openai_class.assert_called_once_with(api_key=fake_api_key)
    mock_client.models.list.assert_called_once()


@patch('utils.ai_helper.OpenAI')
def test_validar_api_key_invalida(mock_openai_class):
    """Test: validar_api_key() retorna False con API key inválida."""
    from utils.ai_helper import validar_api_key
    
    # Configurar mock para lanzar excepción (API key inválida)
    mock_client = Mock()
    mock_client.models.list.side_effect = Exception("Invalid API key")
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = validar_api_key("sk-invalid-key")
    
    # Validar
    assert resultado is False


# ═══════════════════════════════════════════════════════════════════════
# TESTS: generar_resumen_ejecutivo_ytd
# ═══════════════════════════════════════════════════════════════════════

@patch('utils.ai_helper.OpenAI')
def test_generar_resumen_ytd_exitoso(mock_openai_class, mock_openai_ytd_response, fake_api_key):
    """Test: generar_resumen_ejecutivo_ytd() retorna análisis correcto."""
    from utils.ai_helper import generar_resumen_ejecutivo_ytd
    
    # Configurar mock
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_openai_ytd_response
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_resumen_ejecutivo_ytd(
        ventas_ytd_actual=2500000,
        ventas_ytd_anterior=2200000,
        crecimiento_pct=13.6,
        dias_transcurridos=45,
        proyeccion_anual=20000000,
        linea_top="Producto A",
        ventas_linea_top=1200000,
        api_key=fake_api_key
    )
    
    # Validar estructura
    assert isinstance(resultado, dict)
    assert 'diagnostico_general' in resultado
    assert 'fortalezas' in resultado
    assert 'areas_atencion' in resultado
    assert 'recomendaciones_estrategicas' in resultado
    
    # Validar contenido
    assert "Crecimiento sólido" in resultado['diagnostico_general']
    assert isinstance(resultado['fortalezas'], list)
    assert len(resultado['fortalezas']) >= 2


@patch('utils.ai_helper.OpenAI')
def test_generar_resumen_ytd_con_datos_lineas(mock_openai_class, mock_openai_ytd_response, fake_api_key):
    """Test: Incluye datos detallados de líneas en el prompt."""
    from utils.ai_helper import generar_resumen_ejecutivo_ytd
    
    # Configurar mock
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_openai_ytd_response
    mock_openai_class.return_value = mock_client
    
    datos_lineas = {
        'Producto A': {'ventas': 1200000, 'crecimiento': 25.0},
        'Producto B': {'ventas': 800000, 'crecimiento': 10.0},
        'Producto C': {'ventas': 500000, 'crecimiento': -5.0}
    }
    
    # Ejecutar
    resultado = generar_resumen_ejecutivo_ytd(
        ventas_ytd_actual=2500000,
        ventas_ytd_anterior=2200000,
        crecimiento_pct=13.6,
        dias_transcurridos=45,
        proyeccion_anual=20000000,
        linea_top="Producto A",
        ventas_linea_top=1200000,
        api_key=fake_api_key,
        datos_lineas=datos_lineas
    )
    
    # Validar que se llamó a la API
    mock_client.chat.completions.create.assert_called_once()
    
    # Validar que el contexto incluye datos de líneas
    call_args = mock_client.chat.completions.create.call_args
    mensaje_contexto = call_args.kwargs['messages'][1]['content']
    assert 'Producto A' in mensaje_contexto
    assert '1200000' in mensaje_contexto or '1,200,000' in mensaje_contexto


@patch('utils.ai_helper.OpenAI')
def test_generar_resumen_ytd_maneja_error_api(mock_openai_class, fake_api_key):
    """Test: Maneja errores de API y retorna estructura de error."""
    from utils.ai_helper import generar_resumen_ejecutivo_ytd
    
    # Configurar mock para lanzar excepción
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = Exception("API timeout")
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_resumen_ejecutivo_ytd(
        ventas_ytd_actual=2500000,
        ventas_ytd_anterior=2200000,
        crecimiento_pct=13.6,
        dias_transcurridos=45,
        proyeccion_anual=20000000,
        linea_top="Producto A",
        ventas_linea_top=1200000,
        api_key=fake_api_key
    )
    
    # Debe retornar estructura de error
    assert isinstance(resultado, dict)
    assert 'resumen_ejecutivo' in resultado
    assert 'error' in resultado['resumen_ejecutivo'].lower() or 'Error' in resultado['resumen_ejecutivo']


@patch('utils.ai_helper.OpenAI')
def test_generar_resumen_ytd_parsea_json_invalido(mock_openai_class, fake_api_key):
    """Test: Maneja JSON inválido de OpenAI."""
    from utils.ai_helper import generar_resumen_ejecutivo_ytd
    
    # Configurar mock con respuesta no-JSON
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Texto plano sin estructura JSON"
    
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_resumen_ejecutivo_ytd(
        ventas_ytd_actual=2500000,
        ventas_ytd_anterior=2200000,
        crecimiento_pct=13.6,
        dias_transcurridos=45,
        proyeccion_anual=20000000,
        linea_top="Producto A",
        ventas_linea_top=1200000,
        api_key=fake_api_key
    )
    
    # Debe retornar fallback estructurado
    assert isinstance(resultado, dict)
    assert 'resumen_ejecutivo' in resultado


# ═══════════════════════════════════════════════════════════════════════
# TESTS: generar_resumen_ejecutivo_cxc
# ═══════════════════════════════════════════════════════════════════════

@patch('utils.ai_helper.OpenAI')
def test_generar_resumen_cxc_exitoso(mock_openai_class, mock_openai_cxc_response, fake_api_key):
    """Test: generar_resumen_ejecutivo_cxc() retorna análisis correcto."""
    from utils.ai_helper import generar_resumen_ejecutivo_cxc
    
    # Configurar mock
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_openai_cxc_response
    mock_openai_class.return_value = mock_client
    
    # Ejecutar (parámetros completos según firma real)
    resultado = generar_resumen_ejecutivo_cxc(
        total_adeudado=5000000,
        vigente=3250000,
        vencida=1750000,
        critica=925000,
        pct_vigente=65.0,
        pct_critica=18.5,
        score_salud=72,
        score_status="Bueno",
        top_deudor="ABC Corp",
        monto_top_deudor=500000,
        indice_morosidad=18.5,
        casos_urgentes=12,
        alertas_count=5,
        api_key=fake_api_key
    )
    
    # Validar estructura
    assert isinstance(resultado, dict)
    assert 'salud_cartera' in resultado
    assert 'riesgos_criticos' in resultado
    assert 'acciones_prioritarias' in resultado
    
    # Validar contenido
    assert "72" in resultado['salud_cartera'] or "score" in resultado['salud_cartera'].lower()
    assert isinstance(resultado['riesgos_criticos'], list)
    assert len(resultado['acciones_prioritarias']) >= 1


@patch('utils.ai_helper.OpenAI')
def test_generar_resumen_cxc_maneja_error_api(mock_openai_class, fake_api_key):
    """Test: Maneja errores de API en análisis CxC."""
    from utils.ai_helper import generar_resumen_ejecutivo_cxc
    
    # Configurar mock para lanzar excepción
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = Exception("Rate limit exceeded")
    mock_openai_class.return_value = mock_client
    
    # Ejecutar (parámetros completos)
    resultado = generar_resumen_ejecutivo_cxc(
        total_adeudado=5000000,
        vigente=3250000,
        vencida=1750000,
        critica=925000,
        pct_vigente=65.0,
        pct_critica=18.5,
        score_salud=72,
        score_status="Bueno",
        top_deudor="ABC Corp",
        monto_top_deudor=500000,
        indice_morosidad=18.5,
        casos_urgentes=12,
        alertas_count=5,
        api_key=fake_api_key
    )
    
    # Debe retornar estructura de error (usa estructura general de fallback)
    assert isinstance(resultado, dict)
    assert 'resumen_ejecutivo' in resultado
    assert 'error' in resultado['resumen_ejecutivo'].lower() or 'Error' in resultado['resumen_ejecutivo']


@patch('utils.ai_helper.OpenAI')
def test_generar_resumen_cxc_con_top_deudores(mock_openai_class, mock_openai_cxc_response, fake_api_key):
    """Test: Incluye datos de top deudores en el contexto (líneas 342-347)."""
    from utils.ai_helper import generar_resumen_ejecutivo_cxc
    
    # Configurar mock
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_openai_cxc_response
    mock_openai_class.return_value = mock_client
    
    # Datos de top deudores
    datos_top_deudores = [
        {'nombre': 'ABC Corp', 'monto': 500000, 'porcentaje': 10.0},
        {'nombre': 'XYZ Ltd', 'monto': 300000, 'porcentaje': 6.0},
        {'nombre': 'DEF Inc', 'monto': 250000, 'porcentaje': 5.0}
    ]
    
    # Ejecutar con datos_top_deudores
    resultado = generar_resumen_ejecutivo_cxc(
        total_adeudado=5000000,
        vigente=3250000,
        vencida=1750000,
        critica=925000,
        pct_vigente=65.0,
        pct_critica=18.5,
        score_salud=72,
        score_status="Bueno",
        top_deudor="ABC Corp",
        monto_top_deudor=500000,
        indice_morosidad=18.5,
        casos_urgentes=12,
        alertas_count=5,
        api_key=fake_api_key,
        datos_top_deudores=datos_top_deudores
    )
    
    # Validar que se llamó a la API
    mock_client.chat.completions.create.assert_called_once()
    
    # Validar que el contexto incluye TOP 5 DEUDORES
    call_args = mock_client.chat.completions.create.call_args
    mensaje_contexto = call_args.kwargs['messages'][1]['content']
    assert 'TOP 5 DEUDORES' in mensaje_contexto
    assert 'ABC Corp' in mensaje_contexto
    assert 'XYZ Ltd' in mensaje_contexto


@patch('utils.ai_helper.OpenAI')
def test_generar_resumen_cxc_parsea_json_invalido(mock_openai_class, fake_api_key):
    """Test: Maneja JSON inválido en respuesta CxC (líneas 393-396)."""
    from utils.ai_helper import generar_resumen_ejecutivo_cxc
    
    # Configurar mock con respuesta no-JSON
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Texto plano sin formato JSON válido"
    
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_resumen_ejecutivo_cxc(
        total_adeudado=5000000,
        vigente=3250000,
        vencida=1750000,
        critica=925000,
        pct_vigente=65.0,
        pct_critica=18.5,
        score_salud=72,
        score_status="Bueno",
        top_deudor="ABC Corp",
        monto_top_deudor=500000,
        indice_morosidad=18.5,
        casos_urgentes=12,
        alertas_count=5,
        api_key=fake_api_key
    )
    
    # Debe retornar fallback estructurado (mismo que estructura esperada)
    assert isinstance(resultado, dict)
    assert 'resumen_ejecutivo' in resultado
    assert 'highlights_clave' in resultado
    assert 'areas_atencion' in resultado


# ═══════════════════════════════════════════════════════════════════════
# TESTS: generar_analisis_consolidado_ia
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_openai_consolidado_response():
    """Mock de respuesta de OpenAI para análisis consolidado."""
    mock = Mock()
    mock.choices = [Mock()]
    mock.choices[0].message.content = json.dumps({
        "resumen_ejecutivo": "Crecimiento del 15% con deterioro moderado en cobros (score 72/100)",
        "highlights_clave": [
            "Ventas crecieron $300K vs período anterior",
            "Cartera vigente se mantiene en 65%"
        ],
        "areas_atencion": [
            "Cartera crítica alcanza 18.5%, por encima del objetivo",
            "Riesgo de liquidez si no mejora cobranza"
        ],
        "insights_principales": [
            "Crecimiento en ventas no se traduce en mejora de cobros",
            "Necesario reforzar política crediticia"
        ],
        "recomendaciones_ejecutivas": [
            "Activar protocolo de cobranza intensiva",
            "Revisar límites de crédito para top deudores"
        ]
    })
    return mock


@patch('utils.ai_helper.OpenAI')
def test_generar_analisis_consolidado_exitoso(mock_openai_class, mock_openai_consolidado_response, fake_api_key):
    """Test: generar_analisis_consolidado_ia() retorna análisis integrado correcto."""
    from utils.ai_helper import generar_analisis_consolidado_ia
    
    # Configurar mock
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_openai_consolidado_response
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_analisis_consolidado_ia(
        periodo_analisis="Enero 2026",
        total_ventas=2500000,
        crecimiento_ventas_pct=15.0,
        total_cxc=5000000,
        pct_vigente_cxc=65.0,
        pct_critica_cxc=18.5,
        score_salud_cxc=72,
        api_key=fake_api_key
    )
    
    # Validar estructura
    assert isinstance(resultado, dict)
    assert 'resumen_ejecutivo' in resultado
    assert 'highlights_clave' in resultado
    assert 'areas_atencion' in resultado
    assert 'insights_principales' in resultado
    assert 'recomendaciones_ejecutivas' in resultado
    
    # Validar contenido
    assert "Crecimiento" in resultado['resumen_ejecutivo']
    assert isinstance(resultado['highlights_clave'], list)
    assert len(resultado['highlights_clave']) >= 2


@patch('utils.ai_helper.OpenAI')
def test_generar_analisis_consolidado_con_markdown_wrapper(mock_openai_class, fake_api_key):
    """Test: Maneja respuesta JSON envuelta en markdown (```json ... ```)."""
    from utils.ai_helper import generar_analisis_consolidado_ia
    
    # Configurar mock con JSON envuelto en markdown
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = """```json
{
    "resumen_ejecutivo": "Análisis ejecutivo integrado",
    "highlights_clave": ["Punto 1", "Punto 2"],
    "areas_atencion": ["Área 1"],
    "insights_principales": ["Insight 1"],
    "recomendaciones_ejecutivas": ["Reco 1"]
}
```"""
    
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_analisis_consolidado_ia(
        periodo_analisis="Enero 2026",
        total_ventas=2500000,
        crecimiento_ventas_pct=15.0,
        total_cxc=5000000,
        pct_vigente_cxc=65.0,
        pct_critica_cxc=18.5,
        score_salud_cxc=72,
        api_key=fake_api_key
    )
    
    # Debe parsear correctamente el JSON limpiado
    assert isinstance(resultado, dict)
    assert resultado['resumen_ejecutivo'] == "Análisis ejecutivo integrado"
    assert len(resultado['highlights_clave']) == 2


@patch('utils.ai_helper.OpenAI')
def test_generar_analisis_consolidado_con_backticks_simples(mock_openai_class, fake_api_key):
    """Test: Maneja respuesta con backticks simples (cubre línea 242)."""
    from utils.ai_helper import generar_analisis_consolidado_ia
    
    # Configurar mock con JSON envuelto en ``` (sin json prefijo)
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = """{
    "resumen_ejecutivo": "Test línea 242",
    "highlights_clave": [],
    "areas_atencion": [],
    "insights_principales": [],
    "recomendaciones_ejecutivas": []
}```"""
    
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_analisis_consolidado_ia(
        periodo_analisis="Enero 2026",
        total_ventas=2500000,
        crecimiento_ventas_pct=15.0,
        total_cxc=5000000,
        pct_vigente_cxc=65.0,
        pct_critica_cxc=18.5,
        score_salud_cxc=72,
        api_key=fake_api_key
    )
    
    # Debe limpiar correctamente los backticks del final
    assert isinstance(resultado, dict)
    assert resultado['resumen_ejecutivo'] == "Test línea 242"


@patch('utils.ai_helper.OpenAI')
def test_generar_analisis_consolidado_parsea_json_invalido(mock_openai_class, fake_api_key):
    """Test: Maneja JSON inválido en análisis consolidado (líneas 258-266)."""
    from utils.ai_helper import generar_analisis_consolidado_ia
    
    # Configurar mock con respuesta no-JSON
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Texto sin estructura JSON válida { malformed"
    
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_analisis_consolidado_ia(
        periodo_analisis="Enero 2026",
        total_ventas=2500000,
        crecimiento_ventas_pct=15.0,
        total_cxc=5000000,
        pct_vigente_cxc=65.0,
        pct_critica_cxc=18.5,
        score_salud_cxc=72,
        api_key=fake_api_key
    )
    
    # Debe retornar fallback estructurado
    assert isinstance(resultado, dict)
    assert 'resumen_ejecutivo' in resultado
    assert 'Error al procesar' in resultado['resumen_ejecutivo']
    assert resultado['highlights_clave'] == []
    assert resultado['areas_atencion'] == []


@patch('utils.ai_helper.OpenAI')
def test_generar_analisis_consolidado_maneja_exception_general(mock_openai_class, fake_api_key):
    """Test: Maneja excepciones generales en análisis consolidado."""
    from utils.ai_helper import generar_analisis_consolidado_ia
    
    # Configurar mock para lanzar excepción
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = Exception("Network timeout")
    mock_openai_class.return_value = mock_client
    
    # Ejecutar
    resultado = generar_analisis_consolidado_ia(
        periodo_analisis="Enero 2026",
        total_ventas=2500000,
        crecimiento_ventas_pct=15.0,
        total_cxc=5000000,
        pct_vigente_cxc=65.0,
        pct_critica_cxc=18.5,
        score_salud_cxc=72,
        api_key=fake_api_key
    )
    
    # Debe retornar estructura de error
    assert isinstance(resultado, dict)
    assert 'resumen_ejecutivo' in resultado
    assert 'Error al generar' in resultado['resumen_ejecutivo']
    assert resultado['highlights_clave'] == []

"""
Tests unitarios para utils/cxc_metricas_cliente.py
Valida cálculo de métricas avanzadas por cliente.

Coverage objetivo: 85%+ en utils/cxc_metricas_cliente.py
"""

import pytest
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def df_cxc_multiples_clientes():
    """DataFrame con múltiples clientes y facturas."""
    return pd.DataFrame({
        'deudor': ['Cliente A', 'Cliente A', 'Cliente A', 'Cliente B', 'Cliente B', 'Cliente C'],
        'saldo_adeudado': [10000, 5000, 3000, 50000, 25000, 15000],
        'dias_overdue': [10, 30, 45, 0, 5, 120],
        'factura': ['F001', 'F002', 'F003', 'F004', 'F005', 'F006']
    })


@pytest.fixture
def df_metricas_calculadas():
    """DataFrame con métricas ya calculadas (output de calcular_metricas_por_cliente)."""
    return pd.DataFrame({
        'deudor': ['Cliente B', 'Cliente C', 'Cliente A'],
        'saldo_total': [75000, 15000, 18000],
        'num_facturas': [2, 1, 3],
        'dias_promedio_ponderado': [2.5, 120.0, 22.8],
        'dias_factura_mas_antigua': [5, 120, 45],
        'dias_factura_mas_reciente': [0, 120, 10],
        'rango_antiguedad': ['Vigente', '>90 días', '0-30 días']
    })


# ═══════════════════════════════════════════════════════════════════════
# TESTS: calcular_metricas_por_cliente
# ═══════════════════════════════════════════════════════════════════════

def test_calcular_metricas_por_cliente_basico(df_cxc_multiples_clientes):
    """Test: Calcula métricas correctamente con datos válidos."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    resultado = calcular_metricas_por_cliente(df_cxc_multiples_clientes)
    
    # Validar estructura
    assert len(resultado) == 3, "Debe haber 3 clientes únicos"
    assert 'deudor' in resultado.columns
    assert 'saldo_total' in resultado.columns
    assert 'num_facturas' in resultado.columns
    assert 'dias_promedio_ponderado' in resultado.columns
    assert 'rango_antiguedad' in resultado.columns


def test_metricas_cliente_saldo_total_correcto(df_cxc_multiples_clientes):
    """Test: Suma correcta de saldos por cliente."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    resultado = calcular_metricas_por_cliente(df_cxc_multiples_clientes)
    
    # Cliente A: 10000 + 5000 + 3000 = 18000
    cliente_a = resultado[resultado['deudor'] == 'Cliente A'].iloc[0]
    assert cliente_a['saldo_total'] == 18000
    assert cliente_a['num_facturas'] == 3
    
    # Cliente B: 50000 + 25000 = 75000
    cliente_b = resultado[resultado['deudor'] == 'Cliente B'].iloc[0]
    assert cliente_b['saldo_total'] == 75000


def test_metricas_dias_promedio_ponderado(df_cxc_multiples_clientes):
    """Test: Cálculo correcto del promedio ponderado por monto."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    resultado = calcular_metricas_por_cliente(df_cxc_multiples_clientes)
    
    # Cliente A:
    # (10*10000 + 30*5000 + 45*3000) / 18000 = (100000 + 150000 + 135000) / 18000 = 385000 / 18000 = 21.4
    cliente_a = resultado[resultado['deudor'] == 'Cliente A'].iloc[0]
    assert 21.0 <= cliente_a['dias_promedio_ponderado'] <= 22.0
    
    # Cliente B:
    # (0*50000 + 5*25000) / 75000 = 125000 / 75000 = 1.67
    cliente_b = resultado[resultado['deudor'] == 'Cliente B'].iloc[0]
    assert 1.5 <= cliente_b['dias_promedio_ponderado'] <= 2.0


def test_metricas_dias_factura_mas_antigua():
    """Test: Identifica correctamente la factura más antigua (max días)."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    df_test = pd.DataFrame({
        'deudor': ['Cliente X', 'Cliente X', 'Cliente X'],
        'saldo_adeudado': [10000, 5000, 3000],
        'dias_overdue': [10, 60, 30]  # La más antigua es 60 días
    })
    
    resultado = calcular_metricas_por_cliente(df_test)
    
    assert resultado.iloc[0]['dias_factura_mas_antigua'] == 60


def test_metricas_dias_factura_mas_reciente():
    """Test: Identifica correctamente la factura más reciente (min días)."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    df_test = pd.DataFrame({
        'deudor': ['Cliente Y', 'Cliente Y', 'Cliente Y'],
        'saldo_adeudado': [10000, 5000, 3000],
        'dias_overdue': [10, 60, 5]  # La más reciente es 5 días
    })
    
    resultado = calcular_metricas_por_cliente(df_test)
    
    assert resultado.iloc[0]['dias_factura_mas_reciente'] == 5


def test_clasificacion_rango_antiguedad_vigente():
    """Test: Clasifica correctamente como 'Vigente' (<=0 días)."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    df_test = pd.DataFrame({
        'deudor': ['Cliente VIGENTE'],
        'saldo_adeudado': [10000],
        'dias_overdue': [0]
    })
    
    resultado = calcular_metricas_por_cliente(df_test)
    
    assert resultado.iloc[0]['rango_antiguedad'] == 'Vigente'


def test_clasificacion_rango_antiguedad_0_30():
    """Test: Clasifica correctamente como '0-30 días'."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    df_test = pd.DataFrame({
        'deudor': ['Cliente 0-30'],
        'saldo_adeudado': [10000],
        'dias_overdue': [20]
    })
    
    resultado = calcular_metricas_por_cliente(df_test)
    
    assert resultado.iloc[0]['rango_antiguedad'] == '0-30 días'


def test_clasificacion_rango_antiguedad_31_60():
    """Test: Clasifica correctamente como '31-60 días'."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    df_test = pd.DataFrame({
        'deudor': ['Cliente 31-60'],
        'saldo_adeudado': [10000],
        'dias_overdue': [45]
    })
    
    resultado = calcular_metricas_por_cliente(df_test)
    
    assert resultado.iloc[0]['rango_antiguedad'] == '31-60 días'


def test_clasificacion_rango_antiguedad_mayor_90():
    """Test: Clasifica correctamente como '>90 días'."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    df_test = pd.DataFrame({
        'deudor': ['Cliente >90'],
        'saldo_adeudado': [10000],
        'dias_overdue': [120]
    })
    
    resultado = calcular_metricas_por_cliente(df_test)
    
    assert resultado.iloc[0]['rango_antiguedad'] == '>90 días'


def test_metricas_ordenamiento_por_saldo_desc(df_cxc_multiples_clientes):
    """Test: Resultado ordenado por saldo_total descendente."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    resultado = calcular_metricas_por_cliente(df_cxc_multiples_clientes)
    
    # Cliente B debe ser primero (saldo 75000)
    assert resultado.iloc[0]['deudor'] == 'Cliente B'
    assert resultado.iloc[0]['saldo_total'] == 75000


def test_metricas_dataframe_vacio():
    """Test: Retorna DataFrame vacío si input está vacío."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    df_vacio = pd.DataFrame()
    resultado = calcular_metricas_por_cliente(df_vacio)
    
    assert resultado.empty


def test_metricas_columnas_faltantes():
    """Test: Retorna DataFrame vacío si faltan columnas requeridas."""
    from utils.cxc_metricas_cliente import calcular_metricas_por_cliente
    
    df_sin_columnas = pd.DataFrame({
        'deudor': ['Cliente A'],
        'saldo': [10000]  # Falta 'saldo_adeudado' y 'dias_overdue'
    })
    
    resultado = calcular_metricas_por_cliente(df_sin_columnas)
    
    assert resultado.empty


# ═══════════════════════════════════════════════════════════════════════
# TESTS: obtener_top_n_clientes
# ═══════════════════════════════════════════════════════════════════════

def test_obtener_top_n_clientes_default(df_metricas_calculadas):
    """Test: Retorna top 10 clientes por defecto."""
    from utils.cxc_metricas_cliente import obtener_top_n_clientes
    
    resultado = obtener_top_n_clientes(df_metricas_calculadas)
    
    # Solo hay 3 clientes, debe retornar los 3
    assert len(resultado) <= 10
    assert len(resultado) == 3


def test_obtener_top_n_clientes_n_personalizado(df_metricas_calculadas):
    """Test: Retorna exactamente N clientes."""
    from utils.cxc_metricas_cliente import obtener_top_n_clientes
    
    resultado = obtener_top_n_clientes(df_metricas_calculadas, n=2)
    
    assert len(resultado) == 2
    # Debe retornar Cliente B y Cliente C (mayores saldos)
    assert 'Cliente B' in resultado['deudor'].values
    assert 'Cliente C' in resultado['deudor'].values


# ═══════════════════════════════════════════════════════════════════════
# TESTS: obtener_clientes_por_rango
# ═══════════════════════════════════════════════════════════════════════

def test_obtener_clientes_por_rango_vigente(df_metricas_calculadas):
    """Test: Filtra clientes por rango 'Vigente'."""
    from utils.cxc_metricas_cliente import obtener_clientes_por_rango
    
    resultado = obtener_clientes_por_rango(df_metricas_calculadas, 'Vigente')
    
    assert len(resultado) == 1
    assert resultado.iloc[0]['deudor'] == 'Cliente B'


def test_obtener_clientes_por_rango_mayor_90(df_metricas_calculadas):
    """Test: Filtra clientes por rango '>90 días'."""
    from utils.cxc_metricas_cliente import obtener_clientes_por_rango
    
    resultado = obtener_clientes_por_rango(df_metricas_calculadas, '>90 días')
    
    assert len(resultado) == 1
    assert resultado.iloc[0]['deudor'] == 'Cliente C'


# ═══════════════════════════════════════════════════════════════════════
# TESTS: obtener_facturas_cliente
# ═══════════════════════════════════════════════════════════════════════

def test_obtener_facturas_cliente_exitoso(df_cxc_multiples_clientes):
    """Test: Retorna todas las facturas de un cliente específico."""
    from utils.cxc_metricas_cliente import obtener_facturas_cliente
    
    resultado = obtener_facturas_cliente(df_cxc_multiples_clientes, 'Cliente A')
    
    assert len(resultado) == 3
    # La función retorna solo saldo_adeudado, dias_overdue, rango (sin deudor)
    assert 'saldo_adeudado' in resultado.columns
    assert 'dias_overdue' in resultado.columns


def test_obtener_facturas_cliente_no_existe(df_cxc_multiples_clientes):
    """Test: Retorna DataFrame vacío si cliente no existe."""
    from utils.cxc_metricas_cliente import obtener_facturas_cliente
    
    resultado = obtener_facturas_cliente(df_cxc_multiples_clientes, 'Cliente Inexistente')
    
    assert resultado.empty


def test_obtener_facturas_cliente_filtra_correctamente():
    """Test: Filtra correctamente por nombre de cliente."""
    df_test = pd.DataFrame({
        'deudor': ['Cliente A', 'Cliente B', 'Cliente A'],
        'saldo_adeudado': [10000, 5000, 3000],
        'dias_overdue': [10, 20, 30]
    })
    
    from utils.cxc_metricas_cliente import obtener_facturas_cliente
    
    # Buscar 'Cliente A' debe retornar 2 facturas
    resultado = obtener_facturas_cliente(df_test, 'Cliente A')
    assert len(resultado) == 2

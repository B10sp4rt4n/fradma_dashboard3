"""
Tests unitarios para main/vendedores_cxc.py
Valida detección de columnas y cálculo de scores de calidad de cartera.

Coverage objetivo: 15%+ en main/vendedores_cxc.py (funciones helper)
"""

import pytest
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════
# TESTS: _detectar_col_vendedor
# ═══════════════════════════════════════════════════════════════════════

def test_detectar_col_vendedor_encontrado():
    """Test: Detecta columna 'vendedor' correctamente."""
    from main.vendedores_cxc import _detectar_col_vendedor
    
    df = pd.DataFrame({
        'vendedor': ['Juan', 'María'],
        'cliente': ['Cliente A', 'Cliente B'],
        'monto': [1000, 2000]
    })
    
    resultado = _detectar_col_vendedor(df)
    
    assert resultado == 'vendedor'


def test_detectar_col_vendedor_variantes():
    """Test: Detecta variantes de columna vendedor (agente, ejecutivo, etc)."""
    from main.vendedores_cxc import _detectar_col_vendedor
    
    # Probar con 'agente'
    df_agente = pd.DataFrame({'agente': ['Pedro'], 'monto': [500]})
    assert _detectar_col_vendedor(df_agente) == 'agente'
    
    # Probar con 'ejecutivo'
    df_ejecutivo = pd.DataFrame({'ejecutivo': ['Ana'], 'monto': [300]})
    assert _detectar_col_vendedor(df_ejecutivo) == 'ejecutivo'
    
    # Probar con 'seller'
    df_seller = pd.DataFrame({'seller': ['Tom'], 'monto': [700]})
    assert _detectar_col_vendedor(df_seller) == 'seller'
    
    # Probar con 'rep'
    df_rep = pd.DataFrame({'rep': ['Lisa'], 'monto': [900]})
    assert _detectar_col_vendedor(df_rep) == 'rep'


def test_detectar_col_vendedor_case_insensitive():
    """Test: Detección es case-insensitive."""
    from main.vendedores_cxc import _detectar_col_vendedor
    
    df = pd.DataFrame({
        'VENDEDOR': ['Carlos'],
        'Agente': ['Luis'],
        'monto': [1000]
    })
    
    # Debe detectar 'VENDEDOR' (primera columna que coincida)
    resultado = _detectar_col_vendedor(df)
    assert resultado in ('VENDEDOR', 'Agente')  # Depende del orden


def test_detectar_col_vendedor_no_encontrado():
    """Test: Retorna None si no encuentra columna de vendedor."""
    from main.vendedores_cxc import _detectar_col_vendedor
    
    df = pd.DataFrame({
        'cliente': ['Cliente A'],
        'monto': [1000]
    })
    
    resultado = _detectar_col_vendedor(df)
    
    assert resultado is None


# ═══════════════════════════════════════════════════════════════════════
# TESTS: _detectar_col_ventas
# ═══════════════════════════════════════════════════════════════════════

def test_detectar_col_ventas_encontrado():
    """Test: Detecta columna 'ventas_usd' correctamente."""
    from main.vendedores_cxc import _detectar_col_ventas
    
    df = pd.DataFrame({
        'cliente': ['Cliente A'],
        'ventas_usd': [5000]
    })
    
    resultado = _detectar_col_ventas(df)
    
    assert resultado == 'ventas_usd'


def test_detectar_col_ventas_variantes():
    """Test: Detecta variantes de columna ventas."""
    from main.vendedores_cxc import _detectar_col_ventas
    
    # Probar con 'valor_usd'
    df_valor = pd.DataFrame({'valor_usd': [1000]})
    assert _detectar_col_ventas(df_valor) == 'valor_usd'
    
    # Probar con 'importe'
    df_importe = pd.DataFrame({'importe': [2000]})
    assert _detectar_col_ventas(df_importe) == 'importe'
    
    # Probar con 'monto_usd'
    df_monto = pd.DataFrame({'monto_usd': [3000]})
    assert _detectar_col_ventas(df_monto) == 'monto_usd'


def test_detectar_col_ventas_no_encontrado():
    """Test: Retorna None si no encuentra columna de ventas."""
    from main.vendedores_cxc import _detectar_col_ventas
    
    df = pd.DataFrame({
        'cliente': ['Cliente A'],
        'otro_campo': [1000]
    })
    
    resultado = _detectar_col_ventas(df)
    
    assert resultado is None


# ═══════════════════════════════════════════════════════════════════════
# TESTS: _detectar_col_cliente
# ═══════════════════════════════════════════════════════════════════════

def test_detectar_col_cliente_encontrado():
    """Test: Detecta columna 'cliente' correctamente."""
    from main.vendedores_cxc import _detectar_col_cliente
    
    df = pd.DataFrame({
        'cliente': ['Cliente A', 'Cliente B'],
        'monto': [1000, 2000]
    })
    
    resultado = _detectar_col_cliente(df)
    
    assert resultado == 'cliente'


def test_detectar_col_cliente_variantes():
    """Test: Detecta variantes de columna cliente."""
    from main.vendedores_cxc import _detectar_col_cliente
    
    # Probar con 'deudor'
    df_deudor = pd.DataFrame({'deudor': ['ABC Corp']})
    assert _detectar_col_cliente(df_deudor) == 'deudor'
    
    # Probar con 'razon_social'
    df_razon = pd.DataFrame({'razon_social': ['XYZ Ltd']})
    assert _detectar_col_cliente(df_razon) == 'razon_social'
    
    # Probar con 'nombre_cliente'
    df_nombre = pd.DataFrame({'nombre_cliente': ['DEF Inc']})
    assert _detectar_col_cliente(df_nombre) == 'nombre_cliente'


def test_detectar_col_cliente_no_encontrado():
    """Test: Retorna None si no encuentra columna de cliente."""
    from main.vendedores_cxc import _detectar_col_cliente
    
    df = pd.DataFrame({
        'vendedor': ['Juan'],
        'monto': [1000]
    })
    
    resultado = _detectar_col_cliente(df)
    
    assert resultado is None


# ═══════════════════════════════════════════════════════════════════════
# TESTS: _score_calidad
# ═══════════════════════════════════════════════════════════════════════

def test_score_calidad_excelente():
    """Test: Score 🟢 Excelente para cartera con pct_vencida < 15%."""
    from main.vendedores_cxc import _score_calidad
    
    score, status = _score_calidad(5.0)  # 5% vencida = 95 score
    
    assert score == 95.0
    assert "Excelente" in status
    assert "🟢" in status


def test_score_calidad_aceptable():
    """Test: Score 🟡 Aceptable para cartera con pct_vencida 35%."""
    from main.vendedores_cxc import _score_calidad
    
    score, status = _score_calidad(35.0)  # 35% vencida = 65 score
    
    assert score == 65.0
    assert "Aceptable" in status
    assert "🟡" in status


def test_score_calidad_riesgo():
    """Test: Score 🟠 Riesgo para cartera con pct_vencida 50%."""
    from main.vendedores_cxc import _score_calidad
    
    score, status = _score_calidad(50.0)  # 50% vencida = 50 score
    
    assert score == 50.0
    assert "Riesgo" in status
    assert "🟠" in status


def test_score_calidad_critico():
    """Test: Score 🔴 Crítico para cartera con pct_vencida > 60%."""
    from main.vendedores_cxc import _score_calidad
    
    score, status = _score_calidad(80.0)  # 80% vencida = 20 score
    
    assert score == 20.0
    assert "Crítico" in status
    assert "🔴" in status


def test_score_calidad_minimo():
    """Test: Score no puede ser menor a 0."""
    from main.vendedores_cxc import _score_calidad
    
    score, status = _score_calidad(150.0)  # 150% vencida (edge case)
    
    # Score debe ser 0 (no negativo)
    assert score == 0.0
    assert "Crítico" in status


def test_score_calidad_perfecto():
    """Test: Score perfecto 100 con 0% vencida."""
    from main.vendedores_cxc import _score_calidad
    
    score, status = _score_calidad(0.0)  # 0% vencida = 100 score
    
    assert score == 100.0
    assert "Excelente" in status


def test_score_calidad_umbrales():
    """Test: Valida umbrales exactos de clasificación."""
    from main.vendedores_cxc import _score_calidad
    
    # Umbral 85: Exacto debe ser Excelente
    score_85, status_85 = _score_calidad(15.0)  # score = 85
    assert score_85 == 85.0
    assert "Excelente" in status_85
    
    # Umbral 65: Exacto debe ser Aceptable
    score_65, status_65 = _score_calidad(35.0)  # score = 65
    assert score_65 == 65.0
    assert "Aceptable" in status_65
    
    # Umbral 40: Exacto debe ser Riesgo
    score_40, status_40 = _score_calidad(60.0)  # score = 40
    assert score_40 == 40.0
    assert "Riesgo" in status_40

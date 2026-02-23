"""
Tests extendidos para utils/data_normalizer.py
Cubre funciones adicionales: normalizar_columna_saldo, normalizar_columna_valor,
limpiar_valores_monetarios, detectar_columnas_cxc, excluir_pagados, normalizar_columna_fecha

Objetivo: Aumentar coverage de 25.93% a 80%+
"""

import pytest
import pandas as pd
from utils.data_normalizer import (
    normalizar_columna_saldo,
    normalizar_columna_valor,
    limpiar_valores_monetarios,
    detectar_columnas_cxc,
    excluir_pagados,
    normalizar_columna_fecha
)


# ═══════════════════════════════════════════════════════════════════════
# TESTS ADICIONALES PARA CUBRIR FUNCIONES NO TESTEADAS
# ═══════════════════════════════════════════════════════════════════════


class TestNormalizarColumnaSaldo:
    """Tests para normalizar_columna_saldo()"""
    
    def test_normaliza_saldo_adeudado_existente(self):
        """Test: Si ya existe saldo_adeudado, solo limpia valores."""
        df = pd.DataFrame({
            'saldo_adeudado': ['$10,000', '$25,000.50']
        })
        
        df_norm = normalizar_columna_saldo(df)
        
        assert 'saldo_adeudado' in df_norm.columns
        assert df_norm['saldo_adeudado'].dtype in [float, 'float64']
        assert df_norm['saldo_adeudado'].iloc[0] == 10000.0
    
    def test_renombra_columna_candidata(self):
        """Test: Renombra columna candidata a saldo_adeudado."""
        df = pd.DataFrame({
            'saldo': [10000, 25000],
            'cliente': ['A', 'B']
        })
        
        df_norm = normalizar_columna_saldo(df)
        
        assert 'saldo_adeudado' in df_norm.columns
        assert 'saldo' not in df_norm.columns
    
    def test_crea_columna_con_cero_si_no_existe(self):
        """Test: Crea saldo_adeudado=0 si no encuentra columna."""
        df = pd.DataFrame({
            'cliente': ['A', 'B']
        })
        
        df_norm = normalizar_columna_saldo(df)
        
        assert 'saldo_adeudado' in df_norm.columns
        assert (df_norm['saldo_adeudado'] == 0).all()


class TestNormalizarColumnaValor:
    """Tests para normalizar_columna_valor()"""
    
    def test_normaliza_valor_usd_existente(self):
        """Test: Si ya existe valor_usd, solo limpia valores."""
        df = pd.DataFrame({
            'valor_usd': ['$5,000', '$12,500.75']
        })
        
        from utils.data_normalizer import normalizar_columna_valor
        df_norm = normalizar_columna_valor(df)
        
        assert 'valor_usd' in df_norm.columns
        assert df_norm['valor_usd'].dtype in [float, 'float64']
    
    def test_renombra_ventas_usd_candidata(self):
        """Test: Renombra ventas_usd a valor_usd."""
        df = pd.DataFrame({
            'ventas_usd': [5000, 12500],
            'cliente': ['A', 'B']
        })
        
        from utils.data_normalizer import normalizar_columna_valor
        df_norm = normalizar_columna_valor(df)
        
        assert 'valor_usd' in df_norm.columns
        assert 'ventas_usd' not in df_norm.columns


class TestLimpiarValoresMonetarios:
    """Tests para limpiar_valores_monetarios()"""
    
    def test_limpia_comas_y_signos_dolar(self):
        """Test: Elimina $, comas y convierte a float."""
        serie = pd.Series(['$10,000', '$25,000.50', '$1,234.56'])
        
        serie_limpia = limpiar_valores_monetarios(serie)
        
        assert serie_limpia.iloc[0] == 10000.0
        assert serie_limpia.iloc[1] == 25000.5
        assert serie_limpia.iloc[2] == 1234.56
    
    def test_maneja_valores_nulos(self):
        """Test: NaN se convierte a 0."""
        serie = pd.Series(['$10,000', None, '$5,000'])
        
        serie_limpia = limpiar_valores_monetarios(serie)
        
        assert serie_limpia.iloc[0] == 10000.0
        assert serie_limpia.iloc[1] == 0.0  # NaN → 0
        assert serie_limpia.iloc[2] == 5000.0
    
    def test_maneja_valores_ya_numericos(self):
        """Test: Valores numéricos se preservan."""
        serie = pd.Series([10000, 25000.5, 1234])
        
        serie_limpia = limpiar_valores_monetarios(serie)
        
        assert serie_limpia.iloc[0] == 10000.0
        assert serie_limpia.iloc[1] == 25000.5
        assert serie_limpia.iloc[2] == 1234.0


class TestDetectarColumnasCxC:
    """Tests para detectar_columnas_cxc()"""
    
    def test_detecta_dataframe_cxc(self):
        """Test: Detecta DataFrame con columnas de CxC."""
        df_cxc = pd.DataFrame({
            'cliente': ['A', 'B'],
            'saldo_adeudado': [10000, 25000],
            'dias_vencido': [10, 30],
            'estatus': ['VIGENTE', 'VENCIDA']
        })
        
        es_cxc = detectar_columnas_cxc(df_cxc)
        
        assert es_cxc is True
    
    def test_no_detecta_dataframe_ventas(self):
        """Test: No detecta DataFrame de ventas como CxC."""
        df_ventas = pd.DataFrame({
            'fecha': ['2024-01-01', '2024-01-02'],
            'cliente': ['A', 'B'],
            'ventas_usd': [5000, 12000],
            'vendedor': ['Juan', 'María']
        })
        
        es_cxc = detectar_columnas_cxc(df_ventas)
        
        assert es_cxc is False


class TestExcluirPagados:
    """Tests para excluir_pagados() del módulo data_normalizer"""
    
    def test_excluye_registros_pagados(self):
        """Test: Excluye registros con estatus PAGADO."""
        df = pd.DataFrame({
            'cliente': ['A', 'B', 'C'],
            'saldo': [10000, 0, 5000],
            'estatus': ['VIGENTE', 'PAGADO', 'VENCIDA']
        })
        
        df_filtrado = excluir_pagados(df)
        
        assert len(df_filtrado) == 2
        assert 'PAGADO' not in df_filtrado['estatus'].values
    
    def test_mantiene_todos_si_no_hay_pagados(self):
        """Test: Mantiene todos los registros si no hay PAGADO."""
        df = pd.DataFrame({
            'cliente': ['A', 'B'],
            'saldo': [10000, 5000],
            'estatus': ['VIGENTE', 'VENCIDA']
        })
        
        df_filtrado = excluir_pagados(df)
        
        assert len(df_filtrado) == 2


class TestNormalizarColumnaFecha:
    """Tests para normalizar_columna_fecha()"""
    
    def test_convierte_fechas_string_a_datetime(self):
        """Test: Convierte strings de fecha a datetime."""
        df = pd.DataFrame({
            'fecha': ['2024-01-01', '2024-01-15', '2024-02-01']
        })
        
        df_norm = normalizar_columna_fecha(df)
        
        assert pd.api.types.is_datetime64_any_dtype(df_norm['fecha'])
        assert df_norm['fecha'].iloc[0].year == 2024
        assert df_norm['fecha'].iloc[0].month == 1
    
    def test_maneja_fechas_invalidas(self):
        """Test: Fechas inválidas se convierten a NaT."""
        df = pd.DataFrame({
            'fecha': ['2024-01-01', 'INVALID', '2024-02-01']
        })
        
        df_norm = normalizar_columna_fecha(df)
        
        assert pd.isna(df_norm['fecha'].iloc[1])  # 'INVALID' → NaT
        assert not pd.isna(df_norm['fecha'].iloc[0])
    
    def test_preserva_fechas_ya_datetime(self):
        """Test: Fechas ya datetime se preservan."""
        df = pd.DataFrame({
            'fecha': pd.to_datetime(['2024-01-01', '2024-02-01'])
        })
        
        df_norm = normalizar_columna_fecha(df)
        
        assert pd.api.types.is_datetime64_any_dtype(df_norm['fecha'])
        assert len(df_norm) == 2

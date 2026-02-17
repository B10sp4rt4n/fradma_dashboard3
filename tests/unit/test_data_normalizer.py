"""
Tests unitarios para utils/data_normalizer.py
Enfocado en normalizar_columnas() (función crítica usada en todo el sistema)
"""

import pytest
import pandas as pd
from utils.data_normalizer import normalizar_columnas


class TestNormalizarColumnas:
    """Tests para la función normalizar_columnas"""
    
    def test_normalizar_columnas_basico(self):
        """Test básico: lowercase, espacios a guiones bajos"""
        df = pd.DataFrame({
            'Cliente': [1, 2],
            'Saldo Adeudado': [100, 200],
            'FECHA': ['2024-01-01', '2024-01-02']
        })
        
        df_norm = normalizar_columnas(df)
        
        assert 'cliente' in df_norm.columns
        assert 'saldo_adeudado' in df_norm.columns
        assert 'fecha' in df_norm.columns
        assert 'Cliente' not in df_norm.columns  # Eliminado original
        
    def test_normalizar_columnas_con_acentos(self):
        """Test: elimina acentos correctamente"""
        df = pd.DataFrame({
            'Razón Social': [1],
            'Antigüedad': [30],
            'Días de Crédito': [45]
        })
        
        df_norm = normalizar_columnas(df)
        
        assert 'razon_social' in df_norm.columns
        assert 'antiguedad' in df_norm.columns  # ü → u
        assert 'dias_de_credito' in df_norm.columns  # é → e
        
    def test_normalizar_columnas_con_duplicados(self):
        """Test CRÍTICO: maneja columnas duplicadas con sufijos numéricos"""
        df = pd.DataFrame({
            'Cliente': [1],
            'cliente': [2],
            'CLIENTE': [3]
        })
        
        df_norm = normalizar_columnas(df)
        
        # Primera ocurrencia sin sufijo, siguientes con _2, _3
        assert 'cliente' in df_norm.columns
        assert 'cliente_2' in df_norm.columns
        assert 'cliente_3' in df_norm.columns
        assert len(df_norm.columns) == 3  # No perdió columnas
        
    def test_normalizar_columnas_con_espacios_multiples(self):
        """Test: múltiples espacios se convierten a un solo guion bajo"""
        df = pd.DataFrame({
            'Saldo   Adeudado': [100],  # 3 espacios
            'Fecha  de   Pago': ['2024-01-01']  # Espacios variados
        })
        
        df_norm = normalizar_columnas(df)
        
        # Note: replace(" ", "_") convierte cada espacio a _, no colapsa múltiples
        assert 'saldo___adeudado' in df_norm.columns  # 3 guiones bajos
        assert 'fecha__de___pago' in df_norm.columns  # Respeta espacios múltiples
        
    def test_normalizar_columnas_preserva_datos(self):
        """Test: normalización solo afecta nombres, no datos"""
        df = pd.DataFrame({
            'Cliente': ['ABC Corp', 'XYZ Inc'],
            'Saldo': [1000, 2000]
        })
        
        df_norm = normalizar_columnas(df)
        
        # Datos intactos
        assert df_norm['cliente'].tolist() == ['ABC Corp', 'XYZ Inc']
        assert df_norm['saldo'].tolist() == [1000, 2000]
        
    def test_normalizar_columnas_vacio(self):
        """Test: DataFrame vacío no rompe"""
        df = pd.DataFrame()
        df_norm = normalizar_columnas(df)
        
        assert len(df_norm.columns) == 0
        assert isinstance(df_norm, pd.DataFrame)
        
    def test_normalizar_columnas_con_numeros(self):
        """Test: columnas numéricas se convierten a string"""
        df = pd.DataFrame({
            123: [1, 2],
            'Columna 456': [3, 4]
        })
        
        df_norm = normalizar_columnas(df)
        
        assert '123' in df_norm.columns
        assert 'columna_456' in df_norm.columns
        
    def test_normalizar_columnas_con_caracteres_especiales(self):
        """Test: caracteres especiales se preservan en unidecode"""
        df = pd.DataFrame({
            'Cliente & Proveedor': [1],
            'Saldo (USD)': [100],
            'Fecha/Hora': ['2024-01-01']
        })
        
        df_norm = normalizar_columnas(df)
        
        # unidecode preserva &, (), /
        assert 'cliente_&_proveedor' in df_norm.columns
        assert 'saldo_(usd)' in df_norm.columns
        assert 'fecha/hora' in df_norm.columns
        
    def test_normalizar_columnas_no_modifica_original(self):
        """Test: función no muta el DataFrame original"""
        df_original = pd.DataFrame({
            'Cliente': [1, 2],
            'Saldo': [100, 200]
        })
        columnas_originales = df_original.columns.tolist()
        
        df_norm = normalizar_columnas(df_original)
        
        # Original intacto
        assert df_original.columns.tolist() == columnas_originales
        assert 'Cliente' in df_original.columns
        assert 'cliente' not in df_original.columns
        
        # Normalizado tiene nuevas columnas
        assert 'cliente' in df_norm.columns
        assert 'Cliente' not in df_norm.columns
        
    def test_normalizar_columnas_case_insensitive_duplicados(self):
        """Test: detecta duplicados sin importar mayúsculas/minúsculas"""
        df = pd.DataFrame({
            'CLIENTE': [1],
            'Cliente': [2],
            'cliente': [3],
            'cLiEnTe': [4]
        })
        
        df_norm = normalizar_columnas(df)
        
        # Todas normalizadas a 'cliente' con sufijos
        assert 'cliente' in df_norm.columns
        assert 'cliente_2' in df_norm.columns
        assert 'cliente_3' in df_norm.columns
        assert 'cliente_4' in df_norm.columns
        assert len(df_norm.columns) == 4
        
    def test_normalizar_columnas_con_espacios_inicio_fin(self):
        """Test: strip elimina espacios al inicio/fin"""
        df = pd.DataFrame({
            '  Cliente  ': [1],
            ' Saldo': [100],
            'Fecha ': ['2024-01-01']
        })
        
        df_norm = normalizar_columnas(df)
        
        assert 'cliente' in df_norm.columns
        assert 'saldo' in df_norm.columns
        assert 'fecha' in df_norm.columns
        # No debe haber espacios en nombres
        assert not any(' ' in col for col in df_norm.columns if col.strip() != col)


class TestNormalizarColumnasIntegracion:
    """Tests de integración con casos reales del sistema"""
    
    def test_normalizar_columnas_cxc_vigentes(self):
        """Test: caso real de hoja CXC VIGENTES"""
        df = pd.DataFrame({
            'CLIENTE': ['ABC Corp'],
            'Saldo Adeudado': [10000],
            'Días de Crédito': [30],
            'Fecha de Pago': ['2024-01-15'],
            'ESTATUS': ['VIGENTE']
        })
        
        df_norm = normalizar_columnas(df)
        
        # Columnas esperadas por el sistema
        assert 'cliente' in df_norm.columns
        assert 'saldo_adeudado' in df_norm.columns
        assert 'dias_de_credito' in df_norm.columns
        assert 'fecha_de_pago' in df_norm.columns
        assert 'estatus' in df_norm.columns
        
    def test_normalizar_columnas_ventas(self):
        """Test: caso real de hoja de ventas"""
        df = pd.DataFrame({
            'Fecha': ['2024-01-01'],
            'Cliente': ['XYZ Inc'],
            'Línea de Negocio': ['Producto A'],
            'Vendedor': ['Juan Pérez'],
            'Ventas USD': [5000]
        })
        
        df_norm = normalizar_columnas(df)
        
        assert 'fecha' in df_norm.columns
        assert 'cliente' in df_norm.columns
        assert 'linea_de_negocio' in df_norm.columns
        assert 'vendedor' in df_norm.columns
        assert 'ventas_usd' in df_norm.columns
        
    def test_normalizar_columnas_columna_f_cliente(self):
        """Test: prioridad de columna F (CLIENTE) en archivos reales"""
        # Simula Excel con primera columna siendo índice
        df = pd.DataFrame({
            'Unnamed: 0': [1, 2],  # Común en exports Excel
            'RAZON_SOCIAL': ['Corp A', 'Corp B'],
            'CLIENTE': ['Cliente A', 'Cliente B'],  # Columna F real
            'Saldo': [100, 200]
        })
        
        df_norm = normalizar_columnas(df)
        
        # Sistema debe detectar ambas columnas normalizadas
        assert 'unnamed:_0' in df_norm.columns or 'unnamed_0' in df_norm.columns
        assert 'razon_social' in df_norm.columns
        assert 'cliente' in df_norm.columns
        assert 'saldo' in df_norm.columns

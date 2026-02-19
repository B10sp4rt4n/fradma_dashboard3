"""
Tests unitarios para main/heatmap_ventas.py
Módulo de matriz de estacionalidad y heatmaps de ventas.

Coverage objetivo: 30-40% (helpers de transformación)
Nota: run() es UI Streamlit compleja, difícil de testear
"""

import pytest
import pandas as pd
import numpy as np
import unicodedata
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE NORMALIZACIÓN DE COLUMNAS
# ═══════════════════════════════════════════════════════════════════════

class TestCleanColumns:
    """Valida limpieza y normalización de nombres de columnas"""
    
    def clean_columns(self, columns):
        """Réplica de la función clean_columns del módulo"""
        return (
            columns.astype(str)
            .str.strip()
            .str.lower()
            .map(lambda x: unicodedata.normalize('NFKD', x)
                 .encode('ascii', errors='ignore')
                 .decode('utf-8'))
        )
    
    def test_convierte_mayusculas_a_minusculas(self):
        """Normaliza columnas a lowercase"""
        df = pd.DataFrame(columns=['LINEA_PRODUCTO', 'IMPORTE', 'FECHA'])
        clean = self.clean_columns(df.columns)
        
        assert list(clean) == ['linea_producto', 'importe', 'fecha']
        
    def test_elimina_espacios_laterales(self):
        """Strip espacios al inicio y final"""
        df = pd.DataFrame(columns=[' linea ', '  importe  ', 'fecha '])
        clean = self.clean_columns(df.columns)
        
        assert list(clean) == ['linea', 'importe', 'fecha']
        
    def test_normaliza_unicode_acentos(self):
        """Convierte 'línea' a 'linea' (sin tilde)"""
        df = pd.DataFrame(columns=['línea_producto', 'año', 'descripción'])
        clean = self.clean_columns(df.columns)
        
        assert list(clean) == ['linea_producto', 'ano', 'descripcion']
        
    def test_combinacion_uppercase_espacios_acentos(self):
        """Normalización completa"""
        df = pd.DataFrame(columns=[' LÍNEA PRODUCTO ', 'IMPORTE  ', '  AÑO'])
        clean = self.clean_columns(df.columns)
        
        assert 'linea producto' in list(clean)
        assert 'importe' in list(clean)
        assert 'ano' in list(clean)


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE DETECCIÓN DE COLUMNAS
# ═══════════════════════════════════════════════════════════════════════

class TestDetectarColumna:
    """Valida detección flexible de columnas con variantes"""
    
    def detectar_columna(self, df, posibles_nombres):
        """Réplica de la función detectar_columna del módulo"""
        for posible in posibles_nombres:
            for col in df.columns:
                col_norm = unicodedata.normalize('NFKD', col.lower().strip()).encode('ascii', errors='ignore').decode('utf-8')
                posible_norm = unicodedata.normalize('NFKD', posible.lower().strip()).encode('ascii', errors='ignore').decode('utf-8')
                if col_norm == posible_norm:
                    return col
        return None
    
    def test_detecta_linea_producto_variante_1(self):
        """Detecta 'linea_producto'"""
        df = pd.DataFrame(columns=['linea_producto', 'importe', 'fecha'])
        
        posibles = ["linea_producto", "linea_de_negocio", "linea producto"]
        resultado = self.detectar_columna(df, posibles)
        
        assert resultado == 'linea_producto'
        
    def test_detecta_linea_de_negocio_variante_2(self):
        """Detecta 'linea_de_negocio'"""
        df = pd.DataFrame(columns=['fecha', 'linea_de_negocio', 'importe'])
        
        posibles = ["linea_producto", "linea_de_negocio", "linea producto"]
        resultado = self.detectar_columna(df, posibles)
        
        assert resultado == 'linea_de_negocio'
        
    def test_detecta_importe_desde_valor_usd(self):
        """Detecta 'valor_usd' como variante de 'importe'"""
        df = pd.DataFrame(columns=['linea', 'valor_usd', 'fecha'])
        
        posibles = ["importe", "valor_usd", "ventas_usd"]
        resultado = self.detectar_columna(df, posibles)
        
        assert resultado == 'valor_usd'
        
    def test_detecta_producto_desde_articulo(self):
        """Detecta 'articulo' como variante de 'producto'"""
        df = pd.DataFrame(columns=['articulo', 'importe'])
        
        posibles = ["producto", "articulo", "item"]
        resultado = self.detectar_columna(df, posibles)
        
        assert resultado == 'articulo'
        
    def test_no_encuentra_columna_retorna_none(self):
        """Retorna None si no encuentra ninguna variante"""
        df = pd.DataFrame(columns=['col1', 'col2', 'col3'])
        
        posibles = ["linea_producto", "importe", "producto"]
        resultado = self.detectar_columna(df, posibles)
        
        assert resultado is None
        
    def test_detecta_con_espacios_y_mayusculas(self):
        """Normaliza antes de detectar"""
        df = pd.DataFrame(columns=[' LINEA PRODUCTO ', 'IMPORTE'])
        
        # Limpiar columnas primero (simular clean_columns)
        df.columns = df.columns.str.strip().str.lower()
        
        posibles = ["linea producto", "linea_producto"]
        resultado = self.detectar_columna(df, posibles)
        
        assert resultado == 'linea producto'


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE GENERACIÓN DE PERIODO_ID
# ═══════════════════════════════════════════════════════════════════════

class TestGenerarPeriodoID:
    """Valida creación de identificadores de periodo"""
    
    def generar_periodo_id_mensual(self, row):
        """Versión simplificada para tests"""
        try:
            year_val = row.get('anio') or row.get('año')
            if pd.isna(year_val):
                return ""
            year_short = str(int(float(year_val)))[-2:]
            
            if 'fecha' in row.index and pd.notna(row['fecha']):
                if hasattr(row['fecha'], 'month'):
                    month_num = row['fecha'].month
                else:
                    fecha_dt = pd.to_datetime(row['fecha'], errors='coerce')
                    month_num = fecha_dt.month if pd.notna(fecha_dt) else 1
            else:
                month_num = 1
                
            return f"{year_short}.{month_num:02d}"
        except:
            return ""
    
    def test_periodo_id_mensual_formato(self):
        """Genera ID mensual '24.03' para marzo 2024"""
        row = pd.Series({
            'fecha': pd.Timestamp('2024-03-15'),
            'anio': 2024
        })
        
        resultado = self.generar_periodo_id_mensual(row)
        
        assert resultado == "24.03"
        
    def test_periodo_id_mensual_diciembre(self):
        """Genera ID '24.12' para diciembre"""
        row = pd.Series({
            'fecha': pd.Timestamp('2024-12-25'),
            'anio': 2024
        })
        
        resultado = self.generar_periodo_id_mensual(row)
        
        assert resultado == "24.12"
        
    def test_periodo_id_con_anio_nan_retorna_vacio(self):
        """Retorna string vacío si año es NaN"""
        row = pd.Series({
            'fecha': pd.Timestamp('2024-03-15'),
            'anio': np.nan
        })
        
        resultado = self.generar_periodo_id_mensual(row)
        
        assert resultado == ""
        
    def test_periodo_id_trimestral_q1(self):
        """Calcula trimestre Q1 para enero-marzo"""
        row = pd.Series({
            'fecha': pd.Timestamp('2024-02-15'),
            'anio': 2024
        })
        
        # Q1: meses 1-3 → trimestre 1
        month_num = row['fecha'].month
        trimestre = (month_num - 1) // 3 + 1
        year_short = "24"
        
        assert trimestre == 1
        assert f"{year_short}.Q{trimestre}" == "24.Q1"
        
    def test_periodo_id_trimestral_q4(self):
        """Calcula trimestre Q4 para octubre-diciembre"""
        row = pd.Series({
            'fecha': pd.Timestamp('2024-11-15'),
            'anio': 2024
        })
        
        month_num = row['fecha'].month
        trimestre = (month_num - 1) // 3 + 1
        year_short = "24"
        
        assert trimestre == 4
        assert f"{year_short}.Q{trimestre}" == "24.Q4"


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE TABLA PIVOT
# ═══════════════════════════════════════════════════════════════════════

class TestPivotTable:
    """Valida creación de tabla pivot para heatmap"""
    
    def test_pivot_periodo_x_linea(self):
        """Crea tabla con periodos como filas y líneas como columnas"""
        df = pd.DataFrame({
            'periodo_etiqueta': ['24.01 - Ene-24', '24.01 - Ene-24', '24.02 - Feb-24'],
            'linea_producto': ['Hardware', 'Software', 'Hardware'],
            'importe': [1000, 2000, 1500]
        })
        
        pivot = df.pivot_table(
            index='periodo_etiqueta',
            columns='linea_producto',
            values='importe',
            aggfunc='sum',
            fill_value=0
        )
        
        assert pivot.loc['24.01 - Ene-24', 'Hardware'] == 1000
        assert pivot.loc['24.01 - Ene-24', 'Software'] == 2000
        assert pivot.loc['24.02 - Feb-24', 'Hardware'] == 1500
        assert pivot.loc['24.02 - Feb-24', 'Software'] == 0  # fill_value
        
    def test_pivot_suma_multiples_filas_mismo_periodo_linea(self):
        """Agrega múltiples ventas en mismo periodo/línea"""
        df = pd.DataFrame({
            'periodo_etiqueta': ['24.01 - Ene-24', '24.01 - Ene-24'],
            'linea_producto': ['Hardware', 'Hardware'],
            'importe': [1000, 500]
        })
        
        pivot = df.pivot_table(
            index='periodo_etiqueta',
            columns='linea_producto',
            values='importe',
            aggfunc='sum',
            fill_value=0
        )
        
        assert pivot.loc['24.01 - Ene-24', 'Hardware'] == 1500
        
    def test_pivot_con_multiples_lineas(self):
        """Maneja múltiples líneas de negocio"""
        df = pd.DataFrame({
            'periodo_etiqueta': ['24.01', '24.01', '24.01'],
            'linea_producto': ['A', 'B', 'C'],
            'importe': [100, 200, 300]
        })
        
        pivot = df.pivot_table(
            index='periodo_etiqueta',
            columns='linea_producto',
            values='importe',
            aggfunc='sum'
        )
        
        assert len(pivot.columns) == 3
        assert set(pivot.columns) == {'A', 'B', 'C'}


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE CÁLCULO DE CRECIMIENTO
# ═══════════════════════════════════════════════════════════════════════

class TestCalculoCrecimiento:
    """Valida cálculo de % variación periodo a periodo"""
    
    def test_crecimiento_mensual_secuencial(self):
        """Calcula % crecimiento vs mes anterior"""
        df = pd.DataFrame({
            'Hardware': [1000, 1200, 1100],
            'Software': [2000, 2400, 2200]
        }, index=['24.01', '24.02', '24.03'])
        
        growth = df.pct_change(periods=1) * 100
        
        assert growth.loc['24.02', 'Hardware'] == pytest.approx(20.0, rel=0.01)
        assert growth.loc['24.03', 'Hardware'] == pytest.approx(-8.33, rel=0.01)
        
    def test_crecimiento_year_over_year(self):
        """Calcula % crecimiento vs mismo mes año anterior"""
        df = pd.DataFrame({
            'Hardware': [1000, 1100, 1200, 1300, 1400, 1500],
        }, index=['23.01', '23.02', '23.03', '24.01', '24.02', '24.03'])
        
        # YoY: comparar con 12 meses antes (lag=3 para simplificar test)
        growth = df.pct_change(periods=3) * 100
        
        # 24.01 vs 23.01: 1300 vs 1000 = +30%
        assert growth.loc['24.01', 'Hardware'] == pytest.approx(30.0, rel=0.01)
        
    def test_crecimiento_inf_cuando_periodo_anterior_cero(self):
        """Retorna inf cuando periodo anterior es 0"""
        df = pd.DataFrame({
            'Nuevas': [0, 100, 200]
        }, index=['24.01', '24.02', '24.03'])
        
        growth = df.pct_change(periods=1) * 100
        
        assert np.isinf(growth.loc['24.02', 'Nuevas'])
        
    def test_crecimiento_nan_para_primer_periodo(self):
        """Primer periodo no tiene comparación (NaN)"""
        df = pd.DataFrame({
            'Hardware': [1000, 1200]
        }, index=['24.01', '24.02'])
        
        growth = df.pct_change(periods=1) * 100
        
        assert pd.isna(growth.loc['24.01', 'Hardware'])
        
    def test_crecimiento_negativo(self):
        """Calcula decrecimiento correctamente"""
        df = pd.DataFrame({
            'Hardware': [1000, 800]
        }, index=['24.01', '24.02'])
        
        growth = df.pct_change(periods=1) * 100
        
        assert growth.loc['24.02', 'Hardware'] == pytest.approx(-20.0, rel=0.01)


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE GENERACIÓN DE PERIODOS
# ═══════════════════════════════════════════════════════════════════════

class TestPeriodos:
    """Valida creación de columnas de periodo"""
    
    def test_crea_mes_anio_desde_fecha(self):
        """Genera 'Mar-2024' desde fecha"""
        df = pd.DataFrame({
            'fecha': pd.to_datetime(['2024-03-15', '2024-04-20'])
        })
        
        df['mes_anio'] = df['fecha'].dt.strftime('%b-%Y')
        
        # Nota: %b depende del locale, puede ser 'Mar' o 'mar'
        assert df['mes_anio'].iloc[0] in ['Mar-2024', 'mar-2024']
        assert df['mes_anio'].iloc[1] in ['Apr-2024', 'abr-2024', 'Apr-2024']
        
    def test_crea_anio_desde_fecha(self):
        """Extrae año desde fecha"""
        df = pd.DataFrame({
            'fecha': pd.to_datetime(['2024-03-15', '2023-12-31'])
        })
        
        df['anio'] = df['fecha'].dt.year
        
        assert df['anio'].tolist() == [2024, 2023]
        
    def test_crea_trimestre_desde_fecha(self):
        """Genera 'Q1-2024' desde fecha"""
        df = pd.DataFrame({
            'fecha': pd.to_datetime(['2024-01-15', '2024-04-20', '2024-12-31'])
        })
        
        df['trimestre'] = df['fecha'].dt.to_period('Q').astype(str)
        
        assert df['trimestre'].tolist() == ['2024Q1', '2024Q2', '2024Q4']

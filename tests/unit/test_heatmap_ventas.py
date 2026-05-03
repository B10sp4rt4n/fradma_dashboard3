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
        """Detecta 'valor_mxn' como variante de 'importe'"""
        df = pd.DataFrame(columns=['linea', 'valor_mxn', 'fecha'])
        
        posibles = ["importe", "valor_mxn", "ventas_usd"]
        resultado = self.detectar_columna(df, posibles)
        
        assert resultado == 'valor_mxn'
        
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


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE HELPERS REALES DEL MÓDULO
# ═══════════════════════════════════════════════════════════════════════

class TestHeatmapHelpersReales:
    """Valida helpers reales agregados al módulo de heatmap."""

    def test_preparar_dataframe_base_normaliza_y_crea_periodos(self):
        """Test: prepara columnas fecha, mes, año y trimestre con nombres sucios."""
        from main.heatmap_ventas import preparar_dataframe_base

        df = pd.DataFrame({
            ' FECHA ': ['2024-01-15', '2024-04-20'],
            'IMPORTE': [100, 200],
        })

        preparado, error = preparar_dataframe_base(df)

        assert error is None
        assert 'fecha' in preparado.columns
        assert 'mes_anio' in preparado.columns
        assert 'anio' in preparado.columns
        assert 'trimestre' in preparado.columns
        assert preparado['anio'].tolist() == [2024, 2024]
        assert preparado['trimestre'].tolist() == ['2024Q1', '2024Q2']

    def test_preparar_dataframe_base_rechaza_fecha_inexistente(self):
        """Test: retorna error cuando no existe columna fecha."""
        from main.heatmap_ventas import preparar_dataframe_base

        df = pd.DataFrame({'importe': [100, 200]})

        preparado, error = preparar_dataframe_base(df)

        assert preparado is None
        assert "No se encontró la columna 'fecha'" in error

    def test_calcular_metricas_concentracion_retorna_top_1_top_3_y_relevantes(self):
        """Test: resume concentración visible con umbral comercial."""
        from main.heatmap_ventas import calcular_metricas_concentracion

        ventas_linea = pd.Series(
            [50, 30, 15, 5],
            index=['A', 'B', 'C', 'D'],
            dtype=float,
        )

        top_1_share, top_3_share, lineas_relevantes = calcular_metricas_concentracion(ventas_linea)

        assert top_1_share == pytest.approx(50.0, rel=0.01)
        assert top_3_share == pytest.approx(95.0, rel=0.01)
        assert lineas_relevantes == 3

    def test_construir_pareto_dataframe_calcula_participacion_y_acumulado(self):
        """Test: genera dataframe Pareto con porcentajes acumulados."""
        from main.heatmap_ventas import construir_pareto_dataframe

        ventas_linea = pd.Series([60, 25, 15], index=['A', 'B', 'C'], dtype=float)

        pareto_df = construir_pareto_dataframe(ventas_linea)

        assert pareto_df['linea'].tolist() == ['A', 'B', 'C']
        assert pareto_df['participacion_pct'].tolist() == pytest.approx([60.0, 25.0, 15.0], rel=0.01)
        assert pareto_df['acumulado_pct'].tolist() == pytest.approx([60.0, 85.0, 100.0], rel=0.01)

    def test_resumir_pareto_detecta_minimo_numero_de_lineas_hasta_objetivo(self):
        """Test: identifica cuántas líneas explican al menos 80% de ventas."""
        from main.heatmap_ventas import resumir_pareto

        pareto_df = pd.DataFrame({
            'linea': ['A', 'B', 'C'],
            'ventas': [60, 25, 15],
            'participacion_pct': [60.0, 25.0, 15.0],
            'acumulado_pct': [60.0, 85.0, 100.0],
        })

        lineas_objetivo, cobertura_objetivo = resumir_pareto(pareto_df)

        assert lineas_objetivo == 2
        assert cobertura_objetivo == pytest.approx(85.0, rel=0.01)

    def test_resolver_columnas_clave_detecta_segmentacion_comercial_completa(self):
        """Test: detecta columnas opcionales comerciales además de las obligatorias."""
        from main.heatmap_ventas import resolver_columnas_clave

        df = pd.DataFrame(columns=['linea_de_negocio', 'importe', 'producto', 'cliente', 'agente', 'canal', 'zona'])

        (
            columna_linea,
            columna_importe,
            columna_producto,
            columna_cliente,
            columna_vendedor,
            columna_canal,
            columna_region,
        ) = resolver_columnas_clave(df)

        assert columna_linea == 'linea_de_negocio'
        assert columna_importe == 'importe'
        assert columna_producto == 'producto'
        assert columna_cliente == 'cliente'
        assert columna_vendedor == 'agente'
        assert columna_canal == 'canal'
        assert columna_region == 'zona'

    def test_aplicar_filtros_comerciales_sin_columnas_opcionales_retorna_mismo_df(self):
        """Test: si no hay columnas opcionales, no modifica el dataframe."""
        from main.heatmap_ventas import aplicar_filtros_comerciales

        df = pd.DataFrame({
            'fecha': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'importe': [100, 200],
        })

        resultado = aplicar_filtros_comerciales(df, columna_cliente=None, columna_vendedor=None)

        pd.testing.assert_frame_equal(resultado, df)


class TestCalcularTablaCrecimientoReal:
    """Valida edge cases del cálculo comparable real del heatmap."""

    def test_retorna_sin_comparable_cuando_falta_periodo_base(self):
        """Test: si no existe el período base exacto, marca sin comparable."""
        from main.heatmap_ventas import calcular_tabla_crecimiento

        df_filtered = pd.DataFrame(
            {'Linea A': [100, 150]},
            index=['24.01 - Ene', '24.03 - Mar'],
        )
        df_period_order = pd.Series(
            pd.to_datetime(['2024-01-01', '2024-03-01']),
            index=df_filtered.index,
        )

        growth_table, status_table, comparacion_label = calcular_tabla_crecimiento(
            df_filtered,
            df_period_order,
            'Mensual',
            'Período anterior'
        )

        assert comparacion_label == 'vs período anterior'
        assert status_table.loc['24.03 - Mar', 'Linea A'] == 'sin_comparable'
        assert pd.isna(growth_table.loc['24.03 - Mar', 'Linea A'])

    def test_marca_nuevo_cuando_base_es_cero_y_actual_es_positivo(self):
        """Test: marca nuevo e inf cuando la base es cero y el actual tiene ventas."""
        from main.heatmap_ventas import calcular_tabla_crecimiento

        df_filtered = pd.DataFrame(
            {'Linea A': [0, 200]},
            index=['24.01 - Ene', '24.02 - Feb'],
        )
        df_period_order = pd.Series(
            pd.to_datetime(['2024-01-01', '2024-02-01']),
            index=df_filtered.index,
        )

        growth_table, status_table, _ = calcular_tabla_crecimiento(
            df_filtered,
            df_period_order,
            'Mensual',
            'Período anterior'
        )

        assert status_table.loc['24.02 - Feb', 'Linea A'] == 'nuevo'
        assert np.isinf(growth_table.loc['24.02 - Feb', 'Linea A'])

    def test_marca_sin_actividad_cuando_base_y_actual_son_cero(self):
        """Test: marca sin actividad cuando ambos períodos son cero."""
        from main.heatmap_ventas import calcular_tabla_crecimiento

        df_filtered = pd.DataFrame(
            {'Linea A': [0, 0]},
            index=['24.01 - Ene', '24.02 - Feb'],
        )
        df_period_order = pd.Series(
            pd.to_datetime(['2024-01-01', '2024-02-01']),
            index=df_filtered.index,
        )

        growth_table, status_table, _ = calcular_tabla_crecimiento(
            df_filtered,
            df_period_order,
            'Mensual',
            'Período anterior'
        )

        assert status_table.loc['24.02 - Feb', 'Linea A'] == 'sin_actividad'
        assert pd.isna(growth_table.loc['24.02 - Feb', 'Linea A'])

    def test_calcula_crecimiento_comparable_normal(self):
        """Test: calcula porcentaje cuando existe base comparable válida."""
        from main.heatmap_ventas import calcular_tabla_crecimiento

        df_filtered = pd.DataFrame(
            {'Linea A': [100, 125]},
            index=['24.01 - Ene', '24.02 - Feb'],
        )
        df_period_order = pd.Series(
            pd.to_datetime(['2024-01-01', '2024-02-01']),
            index=df_filtered.index,
        )

        growth_table, status_table, _ = calcular_tabla_crecimiento(
            df_filtered,
            df_period_order,
            'Mensual',
            'Período anterior'
        )

        assert status_table.loc['24.02 - Feb', 'Linea A'] == 'comparable'
        assert growth_table.loc['24.02 - Feb', 'Linea A'] == pytest.approx(25.0, rel=0.01)


class TestInsightsHeatmap:
    """Valida la síntesis automática de insights del heatmap."""

    def test_construir_insights_heatmap_resume_corte_concentracion_y_pareto(self):
        """Test: genera hasta 3 insights con corte, concentración y Pareto."""
        from main.heatmap_ventas import construir_insights_heatmap

        df_contexto = pd.DataFrame({
            'vendedor': ['Ana', 'Luis', 'Ana'],
            'cliente': ['C1', 'C2', 'C3'],
            'canal': ['Directo', 'Distribuidor', 'Directo'],
            'region': ['Norte', 'Norte', 'Centro'],
        })
        ventas_linea = pd.Series([60, 25, 15], index=['Linea A', 'Linea B', 'Linea C'], dtype=float)
        resumen = {
            'mejor_linea': 'Linea B',
            'mejor_crecimiento': 18.5,
            'linea_lider': 'Linea A',
            'ventas_linea_lider': 60.0,
        }
        pareto_df = pd.DataFrame({
            'linea': ['Linea A', 'Linea B', 'Linea C'],
            'ventas': [60, 25, 15],
            'participacion_pct': [60.0, 25.0, 15.0],
            'acumulado_pct': [60.0, 85.0, 100.0],
        })

        insights = construir_insights_heatmap(
            df_contexto=df_contexto,
            ventas_linea=ventas_linea,
            resumen=resumen,
            pareto_df=pareto_df,
            columnas_segmentacion={
                'vendedores': 'vendedor',
                'clientes': 'cliente',
                'canales': 'canal',
                'regiones': 'region',
            },
        )

        assert len(insights) == 3
        assert insights[0].startswith('Corte activo:')
        assert 'Alta concentración' in insights[1]
        assert 'Momentum:' in insights[2]

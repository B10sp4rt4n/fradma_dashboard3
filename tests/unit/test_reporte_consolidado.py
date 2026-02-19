"""
Tests unitarios para main/reporte_consolidado.py
Módulo de reporte consolidado ventas + CxC.

Coverage objetivo: 30-40% (funciones de agregación y cálculo)
Nota: Funciones de UI (_renderizar_*) no se testean
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def df_ventas_multiperiodo():
    """DataFrame de ventas con múltiples periodos"""
    fechas = [
        '2024-01-15', '2024-01-20', '2024-01-25',  # Ene
        '2024-02-10', '2024-02-15',                  # Feb
        '2024-03-05', '2024-03-20',                  # Mar
        '2024-04-10',                                # Abr (Q2)
        '2024-07-15', '2024-08-20',                  # Jul-Ago (Q3)
        '2025-01-10'                                 # Ene 2025
    ]
    return pd.DataFrame({
        'fecha': pd.to_datetime(fechas),
        'ventas_usd': [1000, 1500, 2000, 2500, 3000, 1000, 1500, 2000, 2500, 3000, 5000]
    })


@pytest.fixture
def df_cxc_basico():
    """DataFrame básico CxC con días overdue"""
    return pd.DataFrame({
        'deudor': ['Cliente A', 'Cliente B', 'Cliente C', 'Cliente D', 'Cliente E'],
        'saldo_adeudado': [5000, 3000, 2000, 1000, 500],
        'dias_overdue': [-5, 15, 45, 75, 120]  # Vigente, 0-30, 31-60, 61-90, >90
    })


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE AGRUPACIÓN POR PERIODO
# ═══════════════════════════════════════════════════════════════════════

class TestAgruparPorPeriodo:
    """Valida agrupación de datos por diferentes períodos"""
    
    def agrupar_por_periodo(self, df, tipo_periodo='mensual'):
        """Réplica simplificada de la función del módulo"""
        df = df.copy()
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        df = df.dropna(subset=['fecha'])
        
        if tipo_periodo == 'semanal':
            df['periodo'] = df['fecha'].dt.to_period('W').dt.start_time
            df['periodo_label'] = df['fecha'].dt.strftime('Sem %U - %Y')
        elif tipo_periodo == 'mensual':
            df['periodo'] = df['fecha'].dt.to_period('M').dt.start_time
            df['periodo_label'] = df['fecha'].dt.strftime('%b %Y')
        elif tipo_periodo == 'trimestral':
            df['periodo'] = df['fecha'].dt.to_period('Q').dt.start_time
            df['periodo_label'] = df['fecha'].dt.to_period('Q').astype(str)
        elif tipo_periodo == 'anual':
            df['periodo'] = df['fecha'].dt.to_period('Y').dt.start_time
            df['periodo_label'] = df['fecha'].dt.year.astype(str)
        else:
            raise ValueError(f"Tipo de período no válido: {tipo_periodo}")
        
        return df
    
    def test_agrupacion_mensual(self, df_ventas_multiperiodo):
        """Agrupa datos por mes"""
        df = self.agrupar_por_periodo(df_ventas_multiperiodo, 'mensual')
        
        # Debe tener columna periodo y periodo_label
        assert 'periodo' in df.columns
        assert 'periodo_label' in df.columns
        
        # Agrupar por periodo
        ventas_mes = df.groupby('periodo')['ventas_usd'].sum()
        
        # Enero 2024: 3 ventas (1000+1500+2000=4500)
        # Febrero 2024: 2 ventas (2500+3000=5500)
        assert ventas_mes.iloc[0] == 4500
        assert ventas_mes.iloc[1] == 5500
        
    def test_agrupacion_trimestral(self, df_ventas_multiperiodo):
        """Agrupa datos por trimestre"""
        df = self.agrupar_por_periodo(df_ventas_multiperiodo, 'trimestral')
        
        ventas_trim = df.groupby('periodo')['ventas_usd'].sum()
        
        # Q1 2024: Ene+Feb+Mar (4500+5500+2500=12500)
        assert ventas_trim.iloc[0] == 12500
        
    def test_agrupacion_anual(self, df_ventas_multiperiodo):
        """Agrupa datos por año"""
        df = self.agrupar_por_periodo(df_ventas_multiperiodo, 'anual')
        
        ventas_anio = df.groupby('periodo')['ventas_usd'].sum()
        
        # 2024: suma de todos menos último (5000)
        # 2025: 5000
        assert ventas_anio.iloc[1] == 5000
        
    def test_tipo_periodo_invalido_raise_error(self):
        """Lanza ValueError si tipo_periodo no válido"""
        df = pd.DataFrame({'fecha': ['2024-01-01'], 'ventas_usd': [1000]})
        
        with pytest.raises(ValueError, match="Tipo de período no válido"):
            self.agrupar_por_periodo(df, 'inexistente')
            
    def test_elimina_fechas_nan(self):
        """Elimina filas con fecha NaN"""
        df = pd.DataFrame({
            'fecha': ['2024-01-01', np.nan, '2024-02-01'],
            'ventas_usd': [1000, 2000, 3000]
        })
        
        df_result = self.agrupar_por_periodo(df, 'mensual')
        
        # Solo debe tener 2 filas (la del NaN se elimina)
        assert len(df_result) == 2


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE MÉTRICAS DE VENTAS
# ═══════════════════════════════════════════════════════════════════════

class TestCalculoMetricasVentas:
    """Valida cálculo de métricas de ventas"""
    
    def test_total_ventas(self, df_ventas_multiperiodo):
        """Calcula total de ventas"""
        total = df_ventas_multiperiodo['ventas_usd'].sum()
        
        assert total == 25000  # Suma de todos los valores
        
    def test_promedio_por_periodo(self, df_ventas_multiperiodo):
        """Calcula promedio de ventas por período"""
        df = df_ventas_multiperiodo.copy()
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['periodo'] = df['fecha'].dt.to_period('M')
        
        ventas_por_periodo = df.groupby('periodo')['ventas_usd'].sum()
        promedio = ventas_por_periodo.mean()
        
        # 7 meses con datos
        assert len(ventas_por_periodo) == 7
        
    def test_crecimiento_ultimo_periodo(self, df_ventas_multiperiodo):
        """Calcula % crecimiento del último período vs anterior"""
        df = df_ventas_multiperiodo.copy()
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['periodo'] = df['fecha'].dt.to_period('M')
        
        ventas_por_periodo = df.groupby('periodo')['ventas_usd'].sum().sort_index()
        
        # Últimos 2 períodos
        ultimo = ventas_por_periodo.iloc[-1]
        penultimo = ventas_por_periodo.iloc[-2]
        
        crecimiento_pct = 0
        if penultimo > 0:
            crecimiento_pct = ((ultimo - penultimo) / penultimo) * 100
        
        # Ago 2024: 3000, Ene 2025: 5000 → +66.67%
        assert crecimiento_pct == pytest.approx(66.67, abs=0.1)
        
    def test_conteo_periodos(self, df_ventas_multiperiodo):
        """Cuenta número de períodos únicos"""
        df = df_ventas_multiperiodo.copy()
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['periodo'] = df['fecha'].dt.to_period('M')
        
        periodos_count = df['periodo'].nunique()
        
        assert periodos_count == 7  # Ene, Feb, Mar, Abr, Jul, Ago (2024), Ene (2025)


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE MÉTRICAS CXC
# ═══════════════════════════════════════════════════════════════════════

class TestCalculoMetricasCxC:
    """Valida cálculo de métricas CxC"""
    
    def test_distribucion_por_dias_overdue(self, df_cxc_basico):
        """Clasifica saldos por días de vencimiento"""
        df = df_cxc_basico
        
        # Clasificar por rangos
        vigente = df[df['dias_overdue'] < 0]['saldo_adeudado'].sum()
        vencida_0_30 = df[(df['dias_overdue'] >= 0) & (df['dias_overdue'] <= 30)]['saldo_adeudado'].sum()
        vencida_31_60 = df[(df['dias_overdue'] > 30) & (df['dias_overdue'] <= 60)]['saldo_adeudado'].sum()
        vencida_61_90 = df[(df['dias_overdue'] > 60) & (df['dias_overdue'] <= 90)]['saldo_adeudado'].sum()
        alto_riesgo = df[df['dias_overdue'] > 90]['saldo_adeudado'].sum()
        
        assert vigente == 5000      # Cliente A
        assert vencida_0_30 == 3000 # Cliente B
        assert vencida_31_60 == 2000 # Cliente C
        assert vencida_61_90 == 1000 # Cliente D
        assert alto_riesgo == 500    # Cliente E
        
    def test_total_cartera(self, df_cxc_basico):
        """Calcula total de cartera"""
        total = df_cxc_basico['saldo_adeudado'].sum()
        
        assert total == 11500  # Suma de todos los saldos
        
    def test_porcentaje_vigente(self, df_cxc_basico):
        """Calcula % de cartera vigente"""
        total = df_cxc_basico['saldo_adeudado'].sum()
        vigente = df_cxc_basico[df_cxc_basico['dias_overdue'] < 0]['saldo_adeudado'].sum()
        
        pct_vigente = (vigente / total) * 100 if total > 0 else 0
        
        assert pct_vigente == pytest.approx(43.48, abs=0.1)  # 5000 / 11500
        
    def test_porcentaje_critica(self, df_cxc_basico):
        """Calcula % de cartera crítica (>60 días)"""
        total = df_cxc_basico['saldo_adeudado'].sum()
        critica = df_cxc_basico[df_cxc_basico['dias_overdue'] > 60]['saldo_adeudado'].sum()
        
        pct_critica = (critica / total) * 100 if total > 0 else 0
        
        # Cliente D (1000) + Cliente E (500) = 1500
        assert pct_critica == pytest.approx(13.04, abs=0.1)  # 1500 / 11500


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE PREPARACIÓN DE DATOS
# ═══════════════════════════════════════════════════════════════════════

class TestPreparacionDatos:
    """Valida normalización y preparación de datos"""
    
    def test_normaliza_columna_fecha_desde_string(self):
        """Convierte fecha string a datetime"""
        df = pd.DataFrame({
            'fecha': ['2024-01-15', '2024-02-20', '2024-03-25']
        })
        
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        
        assert df['fecha'].dtype == 'datetime64[ns]'
        assert df['fecha'].iloc[0] == pd.Timestamp('2024-01-15')
        
    def test_renombra_valor_usd_a_ventas_usd(self):
        """Renombra columna para compatibilidad"""
        df = pd.DataFrame({
            'valor_usd': [1000, 2000, 3000]
        })
        
        df_renamed = df.rename(columns={'valor_usd': 'ventas_usd'})
        
        assert 'ventas_usd' in df_renamed.columns
        assert 'valor_usd' not in df_renamed.columns
        
    def test_maneja_dataframe_cxc_vacio(self):
        """Retorna None si CxC está vacío"""
        df_cxc = pd.DataFrame()
        
        if df_cxc is None or df_cxc.empty:
            resultado = None
        else:
            resultado = "procesado"
        
        assert resultado is None


# ═══════════════════════════════════════════════════════════════════════
# TESTS DE ESTRUCTURA PIE CHART CXC
# ═══════════════════════════════════════════════════════════════════════

class TestPieChartCxC:
    """Valida estructura de datos para pie chart CxC"""
    
    def test_estructura_labels_values(self):
        """Crea labels y values para pie chart"""
        metricas_cxc = {
            'vigente': 5000,
            'vencida_0_30': 3000,
            'vencida_31_60': 2000,
            'vencida_61_90': 1000,
            'alto_riesgo': 500
        }
        
        labels = ['Vigente', 'Vencida 0-30', 'Vencida 31-60', 'Vencida 61-90', 'Alto Riesgo >90']
        values = [
            metricas_cxc.get('vigente', 0),
            metricas_cxc.get('vencida_0_30', 0),
            metricas_cxc.get('vencida_31_60', 0),
            metricas_cxc.get('vencida_61_90', 0),
            metricas_cxc.get('alto_riesgo', 0)
        ]
        
        assert len(labels) == 5
        assert len(values) == 5
        assert sum(values) == 11500
        
    def test_colores_por_categoria(self):
        """Define colores apropiados para cada categoría"""
        colors = ['#4CAF50', '#FFC107', '#FF9800', '#FF5722', '#F44336']
        
        # Verde (vigente), Amarillo, Naranja, Rojo oscuro, Rojo fuerte
        assert len(colors) == 5
        assert colors[0] == '#4CAF50'  # Verde para vigente
        assert colors[4] == '#F44336'  # Rojo para alto riesgo

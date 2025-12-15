"""
Tests de integración para el módulo de formateo.
Valida que todas las funciones de formato funcionen juntas correctamente.
"""

import pytest
import pandas as pd
from utils.formatos import (
    formato_moneda,
    formato_numero,
    formato_porcentaje,
    formato_compacto,
    formato_dias,
    formato_delta_moneda
)


class TestIntegracionFormatos:
    """Tests de integración para el flujo completo de formateo."""
    
    def test_formateo_completo_de_metricas(self):
        """
        Test integración: formatear un conjunto completo de métricas CxC.
        Simula el formateo que se hace en el dashboard.
        """
        # Métricas brutas
        metricas = {
            'total_adeudado': 1234567.89,
            'vigente': 543210.50,
            'vencida': 691357.39,
            'pct_vigente': 44.0,
            'pct_vencida': 56.0,
            'dias_promedio': 45,
            'delta_mes': 123456.78
        }
        
        # Formatear todas las métricas
        metricas_formateadas = {
            'total_adeudado': formato_moneda(metricas['total_adeudado']),
            'vigente': formato_moneda(metricas['vigente']),
            'vencida': formato_moneda(metricas['vencida']),
            'pct_vigente': formato_porcentaje(metricas['pct_vigente']),
            'pct_vencida': formato_porcentaje(metricas['pct_vencida']),
            'dias_promedio': formato_dias(metricas['dias_promedio']),
            'delta_mes': formato_delta_moneda(metricas['delta_mes']),
            'total_compacto': formato_compacto(metricas['total_adeudado'])
        }
        
        # Validar todos los formatos
        assert metricas_formateadas['total_adeudado'] == "$1,234,567.89"
        assert metricas_formateadas['vigente'] == "$543,210.50"
        assert metricas_formateadas['vencida'] == "$691,357.39"
        assert metricas_formateadas['pct_vigente'] == "44.0%"
        assert metricas_formateadas['pct_vencida'] == "56.0%"
        assert metricas_formateadas['dias_promedio'] == "45 días"
        assert metricas_formateadas['delta_mes'] == "$123,456.78"
        assert metricas_formateadas['total_compacto'] == "1.2M"
    
    def test_formateo_de_dataframe_completo(self):
        """
        Test integración: formatear todas las columnas de un DataFrame.
        Simula el formateo de tablas en el dashboard.
        """
        # DataFrame con datos brutos
        df = pd.DataFrame({
            'cliente': ['Cliente A', 'Cliente B', 'Cliente C'],
            'saldo': [150000.50, 75000.25, 230000.00],
            'dias_mora': [30, 45, 90],
            'porcentaje': [35.5, 22.3, 42.2]
        })
        
        # Formatear columnas
        df_formateado = df.copy()
        df_formateado['saldo_fmt'] = df['saldo'].apply(formato_moneda)
        df_formateado['dias_fmt'] = df['dias_mora'].apply(formato_dias)
        df_formateado['pct_fmt'] = df['porcentaje'].apply(formato_porcentaje)
        df_formateado['saldo_compacto'] = df['saldo'].apply(formato_compacto)
        
        # Validar formatos
        assert df_formateado['saldo_fmt'].iloc[0] == "$150,000.50"
        assert df_formateado['dias_fmt'].iloc[1] == "45 días"
        assert df_formateado['pct_fmt'].iloc[2] == "42.2%"
        assert df_formateado['saldo_compacto'].iloc[2] == "230.0K"
    
    def test_formateo_con_valores_edge_case(self):
        """
        Test integración: formateo maneja correctamente valores especiales.
        """
        valores_especiales = {
            'cero': 0,
            'negativo': -50000,
            'muy_grande': 5000000000,
            'decimal': 0.75,
            'nulo': None
        }
        
        # Formatear todos
        resultados = {
            'cero_moneda': formato_moneda(valores_especiales['cero']),
            'negativo_moneda': formato_moneda(valores_especiales['negativo']),
            'grande_compacto': formato_compacto(valores_especiales['muy_grande']),
            'decimal_pct': formato_porcentaje(valores_especiales['decimal']),
            'nulo_moneda': formato_moneda(valores_especiales['nulo']),
            'delta_negativo': formato_delta_moneda(valores_especiales['negativo'])
        }
        
        # Validar manejo de casos especiales
        assert resultados['cero_moneda'] == "$0.00"
        assert resultados['negativo_moneda'] == "$-50,000.00"
        assert resultados['grande_compacto'] == "5.0B"
        assert resultados['decimal_pct'] == "75.0%"  # Convierte 0.75 a 75%
        assert resultados['nulo_moneda'] == "$0.00"  # Maneja nulos
        assert resultados['delta_negativo'] == "-$50,000.00"
    
    def test_formateo_consistente_en_diferentes_contextos(self):
        """
        Test integración: formatos son consistentes en diferentes usos.
        """
        valor = 123456.789
        
        # Mismo valor formateado de diferentes maneras
        moneda_2dec = formato_moneda(valor, decimales=2)
        moneda_0dec = formato_moneda(valor, decimales=0)
        numero_2dec = formato_numero(valor, decimales=2)
        numero_0dec = formato_numero(valor, decimales=0)
        compacto = formato_compacto(valor)
        
        # Validar consistencia
        assert moneda_2dec == "$123,456.79"  # Redondea
        assert moneda_0dec == "$123,457"     # Sin decimales
        assert numero_2dec == "123,456.79"
        assert numero_0dec == "123,457"
        assert compacto == "123.5K"
        
        # Todos deben manejar el mismo número consistentemente
        # El valor base debe ser reconocible en todos los formatos


class TestIntegracionFormatosDashboard:
    """Tests de integración simulando uso real en dashboard."""
    
    def test_simulacion_metricas_dashboard_cxc(self):
        """
        Test integración: simula el formateo completo de métricas en el dashboard CxC.
        """
        # Simular métricas calculadas
        total = 2500000
        vigente = 1750000
        vencida = 750000
        
        # Formatear para mostrar en dashboard
        display_metricas = {
            'Total Adeudado': formato_moneda(total),
            'Vigente': formato_moneda(vigente),
            'Vencida': formato_moneda(vencida),
            '% Vigente': formato_porcentaje(vigente/total * 100),
            '% Vencida': formato_porcentaje(vencida/total * 100),
            'Total (Compacto)': formato_compacto(total)
        }
        
        # Validar que todos los formatos son strings válidos
        for key, value in display_metricas.items():
            assert isinstance(value, str), f"{key} debe ser string"
            assert len(value) > 0, f"{key} no debe estar vacío"
        
        # Validar formatos específicos
        assert display_metricas['Total Adeudado'] == "$2,500,000.00"
        assert display_metricas['% Vigente'] == "70.0%"
        assert display_metricas['Total (Compacto)'] == "2.5M"
    
    def test_simulacion_tabla_antiguedad(self):
        """
        Test integración: simula formateo de tabla de antigüedad de saldos.
        """
        # Datos de antigüedad
        antiguedad_data = [
            {'categoria': 'Vigente (0 días)', 'monto': 1000000, 'pct': 40.0},
            {'categoria': '1-30 días', 'monto': 500000, 'pct': 20.0},
            {'categoria': '31-60 días', 'monto': 400000, 'pct': 16.0},
            {'categoria': '61-90 días', 'monto': 300000, 'pct': 12.0},
            {'categoria': '90+ días', 'monto': 300000, 'pct': 12.0}
        ]
        
        # Formatear tabla completa
        tabla_formateada = []
        for row in antiguedad_data:
            tabla_formateada.append({
                'Categoría': row['categoria'],
                'Monto': formato_moneda(row['monto']),
                'Porcentaje': formato_porcentaje(row['pct']),
                'Monto Compacto': formato_compacto(row['monto'])
            })
        
        # Validar que toda la tabla está formateada
        assert len(tabla_formateada) == 5
        assert tabla_formateada[0]['Monto'] == "$1,000,000.00"
        assert tabla_formateada[0]['Porcentaje'] == "40.0%"
        assert tabla_formateada[4]['Monto Compacto'] == "300.0K"
    
    def test_simulacion_metricas_streamlit(self):
        """
        Test integración: simula valores formateados para st.metric() de Streamlit.
        """
        # Valores actuales y anteriores
        valor_actual = 2500000
        valor_anterior = 2300000
        delta = valor_actual - valor_anterior
        
        # Formatear para st.metric()
        metric_display = {
            'value': formato_moneda(valor_actual),
            'delta': formato_delta_moneda(delta),
            'delta_pct': formato_porcentaje((delta / valor_anterior) * 100)
        }
        
        # Validar formatos apropiados para Streamlit
        assert metric_display['value'] == "$2,500,000.00"
        assert metric_display['delta'] == "$200,000.00"  # Positivo sin signo +
        assert metric_display['delta_pct'] == "8.7%"
        
        # Test con delta negativo
        delta_negativo = -100000
        delta_fmt = formato_delta_moneda(delta_negativo)
        assert delta_fmt == "-$100,000.00"

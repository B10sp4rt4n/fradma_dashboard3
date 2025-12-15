"""
Tests de integración para el flujo completo de preparación de datos CxC.
Valida que el pipeline end-to-end funcione correctamente.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.cxc_helper import preparar_datos_cxc, calcular_metricas_basicas


class TestIntegracionPipelineCxC:
    """Tests de integración para el flujo completo de datos CxC."""
    
    def test_pipeline_completo_desde_datos_brutos(self):
        """
        Test de integración: datos brutos → preparación → métricas.
        Simula el flujo completo del dashboard.
        """
        # Datos brutos como llegarían de un CSV
        datos_brutos = pd.DataFrame({
            'cliente': ['Cliente A', 'Cliente B', 'Cliente C', 'Cliente D', 'Cliente E'],
            'saldo_adeudado': [100000, 50000, 75000, 30000, 20000],
            'dias_vencido': [0, 15, 45, 95, -10],  # Vigente, vencido, crítico, alto riesgo, futuro
            'estatus': ['PENDIENTE', 'PENDIENTE', 'PENDIENTE', 'PAGADO', 'PENDIENTE']
        })
        
        # Pipeline completo
        df_prep, df_np, mask_pagado = preparar_datos_cxc(datos_brutos)
        
        # Validaciones del pipeline
        assert len(df_prep) == 5, "Debe preservar todos los registros"
        assert len(df_np) == 4, "Debe excluir 1 pagado"
        assert 'dias_overdue' in df_prep.columns, "Debe crear columna dias_overdue"
        assert mask_pagado.sum() == 1, "Debe detectar 1 pagado"
        
        # Validar que dias_overdue se calculó correctamente
        assert df_prep['dias_overdue'].tolist() == [0, 15, 45, 95, -10]
        
        # Calcular métricas sobre datos preparados
        metricas = calcular_metricas_basicas(df_np)
        
        # Validar métricas
        assert metricas['total_adeudado'] == 245000, "Total sin pagados"
        # Vigente son los que tienen dias_overdue <= 0 (Cliente A con 0 y Cliente E con -10)
        assert metricas['vigente'] == 120000, "Cliente A (0) y Cliente E (-10) están vigentes"
        assert metricas['vencida'] == 125000, "Suma de B y C (vencidos)"
        assert metricas['pct_vigente'] == pytest.approx(48.98, rel=0.01)
        assert metricas['pct_vencida'] == pytest.approx(51.02, rel=0.01)
    
    def test_pipeline_con_multiples_metodos_calculo_dias(self):
        """
        Test integración: pipeline funciona con diferentes métodos de cálculo de días.
        """
        # Método 1: dias_vencido directo
        df1 = pd.DataFrame({
            'saldo_adeudado': [1000, 2000],
            'dias_vencido': [30, 60]
        })
        
        # Método 2: dias_restante (invertido)
        df2 = pd.DataFrame({
            'saldo_adeudado': [1000, 2000],
            'dias_restante': [-30, -60]  # Negativo = vencido
        })
        
        # Método 3: fecha_vencimiento
        hoy = pd.Timestamp.today().normalize()
        df3 = pd.DataFrame({
            'saldo_adeudado': [1000, 2000],
            'fecha_vencimiento': [
                (hoy - timedelta(days=30)).strftime('%Y-%m-%d'),
                (hoy - timedelta(days=60)).strftime('%Y-%m-%d')
            ]
        })
        
        # Procesar todos
        _, df_np1, _ = preparar_datos_cxc(df1)
        _, df_np2, _ = preparar_datos_cxc(df2)
        _, df_np3, _ = preparar_datos_cxc(df3)
        
        # Todos deben producir resultados similares
        metricas1 = calcular_metricas_basicas(df_np1)
        metricas2 = calcular_metricas_basicas(df_np2)
        metricas3 = calcular_metricas_basicas(df_np3)
        
        # Validar que todos calculan correctamente
        assert metricas1['total_adeudado'] == 3000
        assert metricas2['total_adeudado'] == 3000
        assert metricas3['total_adeudado'] == 3000
        
        # Todos deben tener 100% vencido (días > 0)
        assert metricas1['pct_vencida'] == 100
        assert metricas2['pct_vencida'] == 100
        assert metricas3['pct_vencida'] == 100
    
    def test_pipeline_con_datos_reales_complejos(self):
        """
        Test integración: simula datos más realistas con múltiples casos edge.
        """
        # Datos realistas con casos diversos
        datos_complejos = pd.DataFrame({
            'cliente': [f'Cliente {i}' for i in range(1, 21)],
            'saldo_adeudado': np.random.randint(10000, 200000, 20),
            'dias_vencido': [
                0, 5, 10, 15, 20,      # Vigentes y leves
                25, 30, 35, 40, 45,    # Vencidos
                50, 60, 70, 80, 90,    # Críticos
                100, 120, 150, 200, 300 # Alto riesgo
            ],
            'estatus': ['PENDIENTE'] * 15 + ['PAGADO'] * 5
        })
        
        # Pipeline
        df_prep, df_np, mask_pagado = preparar_datos_cxc(datos_complejos)
        metricas = calcular_metricas_basicas(df_np)
        
        # Validaciones
        assert len(df_np) == 15, "Debe excluir 5 pagados"
        assert metricas['total_adeudado'] > 0
        assert 0 <= metricas['pct_vigente'] <= 100
        assert 0 <= metricas['pct_vencida'] <= 100
        assert metricas['pct_vigente'] + metricas['pct_vencida'] == pytest.approx(100, rel=0.01)
        
        # Validar categorías (con datos realistas, no todos los rangos siempre tienen saldo)
        assert metricas['vencida'] > 0, "Debe haber deuda vencida"
        # Alto riesgo son días > 90, en nuestra data: 100, 120, 150, 200, 300
        # Pero pueden estar en los pagados, así que validamos que hay datos procesados
        assert metricas['critica'] >= 0, "Métrica crítica debe existir"
    
    def test_pipeline_maneja_datos_vacios(self):
        """Test integración: pipeline maneja DataFrames vacíos correctamente."""
        df_vacio = pd.DataFrame(columns=['saldo_adeudado', 'dias_vencido'])
        
        df_prep, df_np, mask_pagado = preparar_datos_cxc(df_vacio)
        
        assert len(df_np) == 0
        assert 'dias_overdue' in df_prep.columns
        
        # Métricas con datos vacíos deben ser 0
        metricas = calcular_metricas_basicas(df_np)
        assert metricas['total_adeudado'] == 0
        assert metricas['vigente'] == 0
        assert metricas['vencida'] == 0
    
    def test_pipeline_con_valores_nulos(self):
        """Test integración: pipeline maneja valores nulos correctamente."""
        df_con_nulos = pd.DataFrame({
            'saldo_adeudado': [100000, 50000, None, 30000],
            'dias_vencido': [10, None, 20, 30],
            'estatus': ['PENDIENTE', None, 'PENDIENTE', 'PAGADO']
        })
        
        df_prep, df_np, mask_pagado = preparar_datos_cxc(df_con_nulos)
        
        # Debe manejar nulos sin errores
        assert len(df_prep) == 4
        assert 'dias_overdue' in df_prep.columns
        
        # Calcular métricas (debe ignorar nulos en saldo)
        metricas = calcular_metricas_basicas(df_np)
        assert metricas['total_adeudado'] >= 0


class TestIntegracionScoreSalud:
    """Tests de integración para el cálculo de score de salud."""
    
    def test_score_salud_con_datos_completos(self):
        """Test integración: cálculo de score de salud con datos realistas."""
        from utils.cxc_helper import calcular_score_salud, clasificar_score_salud
        
        # Escenario 1: Cartera saludable (70% vigente, 5% crítica)
        score1 = calcular_score_salud(70, 5)
        status1, color1 = clasificar_score_salud(score1)
        
        assert score1 >= 70, "Score debe ser alto"
        assert status1 in ["Excelente", "Bueno"], "Estado debe ser positivo"
        
        # Escenario 2: Cartera regular (50% vigente, 30% crítica)
        score2 = calcular_score_salud(50, 30)
        status2, color2 = clasificar_score_salud(score2)
        
        assert 40 <= score2 <= 60, "Score debe ser medio"
        assert status2 in ["Regular", "Malo"], "Estado debe ser intermedio"
        
        # Escenario 3: Cartera crítica (20% vigente, 70% crítica)
        score3 = calcular_score_salud(20, 70)
        status3, color3 = clasificar_score_salud(score3)
        
        assert score3 < 40, "Score debe ser bajo"
        assert status3 in ["Malo", "Crítico"], "Estado debe ser negativo"
    
    def test_score_salud_limites_extremos(self):
        """Test integración: score de salud en casos extremos."""
        from utils.cxc_helper import calcular_score_salud
        
        # Mejor caso posible
        score_mejor = calcular_score_salud(100, 0)
        assert score_mejor == 100, "Score perfecto debe ser 100"
        
        # Peor caso posible
        score_peor = calcular_score_salud(0, 100)
        assert score_peor >= 0, "Score nunca debe ser negativo"
        assert score_peor < 50, "Score crítico debe ser bajo"


class TestIntegracionSemaforos:
    """Tests de integración para los semáforos de riesgo."""
    
    def test_semaforos_con_metricas_reales(self):
        """Test integración: semáforos funcionan con métricas calculadas."""
        from utils.cxc_helper import (
            obtener_semaforo_morosidad,
            obtener_semaforo_riesgo,
            obtener_semaforo_concentracion
        )
        
        # Crear datos de prueba
        df = pd.DataFrame({
            'saldo_adeudado': [100000, 50000, 75000, 30000],
            'dias_vencido': [0, 15, 45, 95]
        })
        
        _, df_np, _ = preparar_datos_cxc(df)
        metricas = calcular_metricas_basicas(df_np)
        
        # Obtener semáforos basados en métricas reales
        semaforo_morosidad = obtener_semaforo_morosidad(metricas['pct_vencida'])
        semaforo_riesgo = obtener_semaforo_riesgo(metricas['pct_alto_riesgo'])
        semaforo_concentracion = obtener_semaforo_concentracion(39.22)  # Cliente A
        
        # Validar que retornan emojis válidos
        assert semaforo_morosidad in ["🟢", "🟡", "🟠", "🔴"]
        assert semaforo_riesgo in ["🟢", "🟡", "🟠", "🔴"]
        assert semaforo_concentracion in ["🟢", "🟡", "🔴"]

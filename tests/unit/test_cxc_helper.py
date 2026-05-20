"""
Tests unitarios para utils/cxc_helper.py
Funciones críticas de cálculo de CxC.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import timedelta

from utils.cxc_helper import (
    calcular_dias_overdue,
    preparar_datos_cxc,
    preparar_metricas_cxc,
    calcular_cxc_aging,
    calcular_metricas_basicas,
    calcular_score_salud,
    clasificar_score_salud,
    obtener_semaforo_morosidad,
    obtener_semaforo_riesgo,
    obtener_semaforo_concentracion,
    excluir_pagados,
    detectar_columna
)
from utils.constantes import UmbralesCxC, ScoreSalud


class TestDetectarColumna:
    """Tests para detección de columnas."""
    
    def test_encuentra_primera_columna_existente(self):
        df = pd.DataFrame({'col_a': [1, 2], 'col_b': [3, 4]})
        result = detectar_columna(df, ['col_x', 'col_b', 'col_a'])
        assert result == 'col_b'
    
    def test_retorna_none_si_no_encuentra(self):
        df = pd.DataFrame({'col_a': [1, 2]})
        result = detectar_columna(df, ['col_x', 'col_y'])
        assert result is None
    
    def test_con_lista_vacia(self):
        df = pd.DataFrame({'col_a': [1, 2]})
        result = detectar_columna(df, [])
        assert result is None


class TestCalcularDiasOverdue:
    """Tests para la función más crítica - calcula días de atraso."""
    
    def test_con_dias_vencido_directo(self):
        """Método 1: Usa dias_vencido si existe"""
        df = pd.DataFrame({
            'dias_vencido': [10, 20, -5, 0]
        })
        result = calcular_dias_overdue(df)
        
        assert result.tolist() == [10, 20, -5, 0]
        assert len(result) == 4
    
    def test_con_dias_restante_invertido(self):
        """Método 2: Invierte dias_restante (negativo = vencido)"""
        df = pd.DataFrame({
            'dias_restante': [10, -20, 0]
        })
        result = calcular_dias_overdue(df)
        
        assert result.tolist() == [-10, 20, 0]

    def test_prioriza_dias_restante_sobre_dias_vencido(self):
        """Cuando ambas columnas existen, dias_restante debe tener prioridad."""
        df = pd.DataFrame({
            'dias_vencido': [0, 5],
            'dias_restante': [-15, 2],
        })

        result = calcular_dias_overdue(df)

        assert result.tolist() == [15, -2]
    
    def test_con_fecha_vencimiento(self):
        """Método 3: Calcula desde fecha_vencimiento vs hoy"""
        hoy = pd.Timestamp.today().normalize()
        df = pd.DataFrame({
            'fecha_vencimiento': [
                hoy - timedelta(days=30),
                hoy + timedelta(days=15),
                hoy
            ]
        })
        result = calcular_dias_overdue(df)
        
        assert result[0] == 30
        assert result[1] == -15
        assert result[2] == 0
    
    def test_con_fecha_pago_mas_credito(self):
        """Método 4: Fallback con fecha_pago + dias_de_credito"""
        hoy = pd.Timestamp.today().normalize()
        fecha_pago = hoy - timedelta(days=60)
        
        df = pd.DataFrame({
            'fecha_de_pago': [fecha_pago, fecha_pago],
            'dias_de_credito': [30, 90]
        })
        result = calcular_dias_overdue(df)
        
        # Ajuste: 30 días de crédito = día 1-30 vigente, día 31 vencido
        # 60 días desde fecha_pago, 30 de crédito: vencido = 60 - 30 + 1 = 31 días
        assert result[0] == 31  # 60 días - 30 crédito + 1 = 31 días vencido
        assert result[1] == -29  # 60 días - 90 crédito + 1 = -29 días vigente
    
    def test_valores_faltantes(self):
        """Maneja NaN correctamente"""
        df = pd.DataFrame({
            'dias_vencido': [10, np.nan, None, 20]
        })
        result = calcular_dias_overdue(df)
        
        assert result[0] == 10
        assert result[1] == 0  # NaN → 0
        assert result[2] == 0  # None → 0
        assert result[3] == 20
    
    def test_sin_columnas_relevantes(self):
        """Retorna 0 cuando no hay columnas para calcular"""
        df = pd.DataFrame({
            'columna_irrelevante': [1, 2, 3]
        })
        result = calcular_dias_overdue(df)
        
        assert result.tolist() == [0, 0, 0]


class TestExcluirPagados:
    """Tests para exclusión de registros pagados."""
    
    def test_excluye_estatus_pagado(self):
        df = pd.DataFrame({
            'estatus': ['Pendiente', 'Pagado', 'Vencido', 'PAGADO']
        })
        mask = excluir_pagados(df)
        
        assert mask.tolist() == [False, True, False, True]
    
    def test_sin_columna_estatus(self):
        df = pd.DataFrame({
            'otra_columna': [1, 2, 3]
        })
        mask = excluir_pagados(df)
        
        assert mask.tolist() == [False, False, False]
    
    def test_case_insensitive(self):
        df = pd.DataFrame({
            'estatus': ['pagado', 'PAGADO', 'Pagado', 'PaGaDo']
        })
        mask = excluir_pagados(df)
        
        assert all(mask)


class TestCalcularScoreSalud:
    """Tests para score de salud financiera."""
    
    def test_score_excelente(self):
        """100% vigente, 0% crítica = score perfecto"""
        score = calcular_score_salud(pct_vigente=100, pct_critica=0)
        assert score == 100.0
    
    def test_score_critico(self):
        """0% vigente, 50% crítica = score muy bajo"""
        score = calcular_score_salud(pct_vigente=0, pct_critica=50)
        assert score == 0.0
    
    def test_score_balanceado(self):
        """70% vigente, 10% crítica = 70*0.7 + 80*0.3 = 73"""
        score = calcular_score_salud(pct_vigente=70, pct_critica=10)
        expected = 70 * ScoreSalud.PESO_VIGENTE + max(0, 100 - 10 * 2) * ScoreSalud.PESO_CRITICA
        assert abs(score - expected) < 0.1
    
    def test_limites_del_score(self):
        """Score siempre entre 0 y 100"""
        assert calcular_score_salud(200, -50) == 100  # Max
        assert calcular_score_salud(-50, 200) >= 0   # Min
    
    def test_formula_exacta(self):
        """Verificar fórmula: pct_vigente*0.7 + max(0, 100-pct_critica*2)*0.3"""
        score = calcular_score_salud(80, 20)
        expected = 80 * 0.7 + max(0, 100 - 20 * 2) * 0.3
        assert abs(score - expected) < 0.01


class TestClasificarScoreSalud:
    """Tests para clasificación de score."""
    
    def test_clasificacion_excelente(self):
        status, color = clasificar_score_salud(85)
        assert status == "Excelente"
        assert color == ScoreSalud.COLOR_EXCELENTE
    
    def test_clasificacion_bueno(self):
        status, color = clasificar_score_salud(65)
        assert status == "Bueno"
        assert color == ScoreSalud.COLOR_BUENO
    
    def test_clasificacion_regular(self):
        status, color = clasificar_score_salud(50)
        assert status == "Regular"
        assert color == ScoreSalud.COLOR_REGULAR
    
    def test_clasificacion_malo(self):
        status, color = clasificar_score_salud(30)
        assert status == "Malo"
        assert color == ScoreSalud.COLOR_MALO
    
    def test_clasificacion_critico(self):
        status, color = clasificar_score_salud(15)
        assert status == "Crítico"
        assert color == ScoreSalud.COLOR_CRITICO
    
    def test_limites_exactos(self):
        """Verificar límites de las categorías"""
        assert clasificar_score_salud(80)[0] == "Excelente"
        assert clasificar_score_salud(79.9)[0] == "Bueno"
        assert clasificar_score_salud(60)[0] == "Bueno"
        assert clasificar_score_salud(59.9)[0] == "Regular"
        assert clasificar_score_salud(40)[0] == "Regular"
        assert clasificar_score_salud(39.9)[0] == "Malo"


class TestObtenerSemaforoMorosidad:
    """Tests para semáforos de morosidad."""
    
    def test_verde_morosidad_baja(self):
        assert obtener_semaforo_morosidad(5) == "🟢"
        assert obtener_semaforo_morosidad(9.9) == "🟢"
    
    def test_amarillo_morosidad_media(self):
        assert obtener_semaforo_morosidad(15) == "🟡"
        assert obtener_semaforo_morosidad(24.9) == "🟡"
    
    def test_naranja_morosidad_alta(self):
        assert obtener_semaforo_morosidad(30) == "🟠"
        assert obtener_semaforo_morosidad(49.9) == "🟠"
    
    def test_rojo_morosidad_critica(self):
        assert obtener_semaforo_morosidad(50) == "🔴"
        assert obtener_semaforo_morosidad(100) == "🔴"
    
    def test_limites_exactos_con_constantes(self):
        assert obtener_semaforo_morosidad(UmbralesCxC.MOROSIDAD_BAJA - 0.1) == "🟢"
        assert obtener_semaforo_morosidad(UmbralesCxC.MOROSIDAD_BAJA) == "🟡"


class TestObtenerSemaforoRiesgo:
    """Tests para semáforos de riesgo alto."""
    
    def test_verde_riesgo_bajo(self):
        assert obtener_semaforo_riesgo(3) == "🟢"
    
    def test_amarillo_riesgo_medio(self):
        assert obtener_semaforo_riesgo(10) == "🟡"
    
    def test_naranja_riesgo_alto(self):
        assert obtener_semaforo_riesgo(20) == "🟠"
    
    def test_rojo_riesgo_critico(self):
        assert obtener_semaforo_riesgo(40) == "🔴"


class TestObtenerSemaforoConcentracion:
    """Tests para semáforos de concentración."""
    
    def test_verde_concentracion_baja(self):
        assert obtener_semaforo_concentracion(20) == "🟢"
    
    def test_amarillo_concentracion_media(self):
        assert obtener_semaforo_concentracion(40) == "🟡"
    
    def test_rojo_concentracion_alta(self):
        assert obtener_semaforo_concentracion(60) == "🔴"


class TestPrepararDatosCxC:
    """Tests de integración para el pipeline completo."""
    
    def test_pipeline_completo(self):
        """Excluye pagados, calcula días, retorna DataFrames"""
        df = pd.DataFrame({
            'dias_vencido': [10, 20, 30],
            'estatus': ['Pendiente', 'Pagado', 'Vencido'],
            'saldo_adeudado': [1000, 2000, 3000]
        })
        
        df_prep, df_np, mask_pagado = preparar_datos_cxc(df)
        
        # Verificar que se calculó dias_overdue
        assert 'dias_overdue' in df_prep.columns
        
        # Verificar que se excluyeron pagados
        assert len(df_np) == 2
        assert df_np['estatus'].tolist() == ['Pendiente', 'Vencido']
        
        # Verificar máscara
        assert mask_pagado.tolist() == [False, True, False]
    
    def test_crea_dias_vencido_si_no_existe(self):
        """Compatibilidad: crea dias_vencido si no existe"""
        df = pd.DataFrame({
            'dias_restante': [10, -20],
            'estatus': ['Vigente', 'Vencido'],
            'saldo_adeudado': [1000, 2000]
        })
        
        df_prep, df_np, _ = preparar_datos_cxc(df)
        
        assert 'dias_vencido' in df_prep.columns
        assert 'dias_vencido' in df_np.columns


class TestCalcularCxCAgingUnificado:
    """Tests del helper unificado para aging y score CxC."""

    def test_usa_fecha_vencimiento_y_excluye_pagados(self):
        fecha_corte = pd.Timestamp("2025-05-01")
        df = pd.DataFrame({
            'fecha_vencimiento': [
                '2025-05-05',  # vigente
                '2025-04-20',  # 0-30
                '2025-03-10',  # 31-60
                '2025-02-01',  # 61-90
                '2024-12-01',  # >90 pero pagado
            ],
            'fecha': [
                '2024-01-01',
                '2024-01-01',
                '2024-01-01',
                '2024-01-01',
                '2024-01-01',
            ],
            'saldo_adeudado': [100, 50, 150, 200, 25],
            'estatus': ['Pendiente', 'Pendiente', 'Pendiente', 'Pendiente', 'Pagado'],
        })

        result = preparar_metricas_cxc(df, fecha_corte=fecha_corte)

        assert result['columna_fecha_usada'] == 'fecha_vencimiento'
        assert result['fecha_corte_usada'] == fecha_corte
        assert result['total_adeudado'] == 500
        assert result['vigente_monto'] == 100
        assert result['bucket_0_30'] == 50
        assert result['bucket_31_60'] == 150
        assert result['bucket_61_90'] == 200
        assert result['bucket_mas_90'] == 0
        assert result['critica_mas_30'] == 350
        assert result['diferencia_total_buckets'] == 0
        assert result['filas_consideradas'] == 4
        assert result['score_salud'] == pytest.approx(47.0, abs=0.01)

    def test_calcular_cxc_aging_retorna_df_y_mapa_estandar(self):
        df = pd.DataFrame({
            'fecha_vencimiento': ['2025-05-01'],
            'saldo_adeudado': [250],
            'estatus': ['Pendiente'],
        })

        result = calcular_cxc_aging(df, fecha_corte=pd.Timestamp('2025-05-01'))

        assert 'df_prep' in result
        assert 'df_np' in result
        assert 'mask_pagado' in result
        assert result['total_adeudado'] == 250
        assert result['vigente_monto'] == 250
        assert result['bucket_0_30'] == 0


class TestCalcularMetricasBasicas:
    """Tests para cálculo de métricas KPI."""
    
    @pytest.fixture
    def df_ejemplo(self):
        """Fixture con datos de ejemplo"""
        return pd.DataFrame({
            'saldo_adeudado': [1000, 2000, 3000, 4000],
            'dias_overdue': [-10, 15, 45, 120]  # vigente, vencida, crítica, alto riesgo
        })
    
    def test_metricas_basicas(self, df_ejemplo):
        metricas = calcular_metricas_basicas(df_ejemplo)
        
        assert metricas['total_adeudado'] == 10000
        assert metricas['vigente'] == 1000
        assert metricas['vencida'] == 9000
        assert metricas['critica'] == 7000
        assert metricas['alto_riesgo'] == 4000
    
    def test_porcentajes(self, df_ejemplo):
        metricas = calcular_metricas_basicas(df_ejemplo)
        
        assert metricas['pct_vigente'] == 10.0
        assert metricas['pct_vencida'] == 90.0
        assert metricas['pct_critica'] == 70.0
        assert metricas['pct_alto_riesgo'] == 40.0
    
    def test_vencida_0_30(self, df_ejemplo):
        metricas = calcular_metricas_basicas(df_ejemplo)
        assert metricas['vencida_0_30'] == 2000  # Solo el de 15 días
    
    def test_con_dataframe_vacio(self):
        """Maneja caso edge de DataFrame vacío"""
        df_vacio = pd.DataFrame({
            'saldo_adeudado': [],
            'dias_overdue': []
        })
        metricas = calcular_metricas_basicas(df_vacio)
        
        assert metricas['total_adeudado'] == 0
        assert metricas['pct_vigente'] == 0
        assert metricas['pct_vencida'] == 0
    
    def test_con_todo_vigente(self):
        df = pd.DataFrame({
            'saldo_adeudado': [1000, 2000],
            'dias_overdue': [-5, -10]
        })
        metricas = calcular_metricas_basicas(df)
        
        assert metricas['pct_vigente'] == 100.0
        assert metricas['pct_vencida'] == 0.0
        assert metricas['pct_critica'] == 0.0

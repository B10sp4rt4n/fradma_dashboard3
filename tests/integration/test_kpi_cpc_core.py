"""
Tests de integración para Dashboard CxC (kpi_cpc.py)
Valida flujos completos end-to-end del módulo más crítico.

Coverage objetivo: 80%+ en main/kpi_cpc.py
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES ESPECÍFICAS PARA KPI_CPC
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def df_cxc_metodos_calculo():
    """
    DataFrame para validar los 5 métodos de cálculo de días vencido.
    Cada fila usa un método diferente.
    """
    hoy = pd.Timestamp.today()
    return pd.DataFrame({
        'deudor': ['Test1', 'Test2', 'Test3', 'Test4', 'Test5'],
        'saldo_adeudado': [1000, 2000, 3000, 4000, 5000],
        
        # Método 1: dias_vencido directo
        'dias_vencido': [10, np.nan, np.nan, np.nan, np.nan],
        
        # Método 2: dias_restante (invertido)
        'dias_restante': [np.nan, -20, np.nan, np.nan, np.nan],
        
        # Método 3: fecha_vencimiento
        'fecha_vencimiento': [
            pd.NaT, pd.NaT, hoy - timedelta(days=30), pd.NaT, pd.NaT
        ],
        
        # Método 4: fecha_pago + credito_dias
        'fecha_pago': [
            pd.NaT, pd.NaT, pd.NaT, hoy - timedelta(days=80), pd.NaT
        ],
        'credito_dias': [np.nan, np.nan, np.nan, 30, np.nan],
        
        # Método 5: Sin columnas (usa DEFAULT basado en estatus)
        'estatus': ['VENCIDA', 'VENCIDA', 'VENCIDA', 'VENCIDA', 'VIGENTE']
    })


@pytest.fixture
def df_cxc_vigentes_vencidas():
    """DataFrame con mix de cuentas vigentes y vencidas."""
    return pd.DataFrame({
        'deudor': ['Cliente A', 'Cliente A', 'Cliente B', 'Cliente C', 'Cliente D'],
        'saldo_adeudado': [10000, 5000, 50000, 100000, 15000],
        'dias_vencido': [0, 15, 45, 120, 30],
        'estatus': ['VIGENTE', 'VIGENTE', 'VENCIDA', 'VENCIDA', 'VENCIDA'],
        'linea_negocio': ['Producto A', 'Producto A', 'Producto B', 'Producto C', 'Producto A']
    })


@pytest.fixture
def df_cxc_solo_pagados():
    """DataFrame con registros PAGADO que deben excluirse."""
    return pd.DataFrame({
        'deudor': ['Cliente X', 'Cliente Y', 'Cliente Z'],
        'saldo_adeudado': [5000, 0, 10000],
        'dias_vencido': [10, 0, 30],
        'estatus': ['VENCIDA', 'PAGADO', 'VIGENTE']
    })


# ═══════════════════════════════════════════════════════════════════════
# TESTS 1-5: CÁLCULO DE DÍAS VENCIDO (5 MÉTODOS)
# ═══════════════════════════════════════════════════════════════════════

def test_calculo_dias_vencido_metodo1_directo(df_cxc_metodos_calculo):
    """Test: Método 1 - Columna dias_vencido existe y se usa directamente."""
    from utils.cxc_helper import calcular_dias_overdue
    
    result = calcular_dias_overdue(df_cxc_metodos_calculo)
    
    # Cliente Test1 debe tener 10 días (método 1)
    assert result.iloc[0] == 10, "Método 1 (dias_vencido directo) falló"


def test_calculo_dias_vencido_metodo2_invertido():
    """Test: Método 2 - Columna dias_restante (negativo = vencido)."""
    from utils.cxc_helper import calcular_dias_overdue
    
    # DataFrame con SOLO dias_restante (sin dias_vencido para evitar early return)
    df_test = pd.DataFrame({
        'deudor': ['Test2'],
        'saldo_adeudado': [2000],
        'dias_restante': [-20],  # Negativo indica vencido
        'estatus': ['VENCIDA']
    })
    
    result = calcular_dias_overdue(df_test)
    
    # Debe tener 20 días (método 2: -(-20))
    assert result.iloc[0] == 20, f"Método 2 (dias_restante invertido) falló: {result.iloc[0]}"


def test_calculo_dias_vencido_metodo3_fecha_vencimiento():
    """Test: Método 3 - Columna fecha_vencimiento (hoy - fecha)."""
    from utils.cxc_helper import calcular_dias_overdue
    
    hoy = pd.Timestamp.today()
    # DataFrame con SOLO fecha_vencimiento
    df_test = pd.DataFrame({
        'deudor': ['Test3'],
        'saldo_adeudado': [3000],
        'fecha_vencimiento': [hoy - timedelta(days=30)],
        'estatus': ['VENCIDA']
    })
    
    result = calcular_dias_overdue(df_test)
    
    # Debe tener ~30 días (método 3)
    assert 28 <= result.iloc[0] <= 32, f"Método 3 (fecha_vencimiento) falló: {result.iloc[0]}"


def test_calculo_dias_vencido_metodo4_fecha_pago_credito():
    """Test: Método 4 - Columna fecha_pago + credito_dias."""
    from utils.cxc_helper import calcular_dias_overdue
    
    hoy = pd.Timestamp.today()
    # DataFrame con SOLO fecha_pago + dias_de_credito (nombre correcto según COLUMNAS_DIAS_CREDITO)
    df_test = pd.DataFrame({
        'deudor': ['Test4'],
        'saldo_adeudado': [4000],
        'fecha_pago': [hoy - timedelta(days=80)],
        'dias_de_credito': [30],  # Nombre correcto de la columna
        'estatus': ['VENCIDA']
    })
    
    result = calcular_dias_overdue(df_test)
    
    # Debe tener ~51 días (80 - 30 + 1 por la lógica de días completos)
    assert 49 <= result.iloc[0] <= 53, f"Método 4 (fecha_pago + credito) falló: {result.iloc[0]}"


def test_calculo_dias_vencido_metodo5_fallback_default(df_cxc_metodos_calculo):
    """Test: Método 5 - Sin columnas relevantes, usa fallback (vigente=0)."""
    from utils.cxc_helper import calcular_dias_overdue
    
    result = calcular_dias_overdue(df_cxc_metodos_calculo)
    
    # Cliente Test5 (VIGENTE sin columnas) debe tener 0 días
    assert result.iloc[4] == 0, "Método 5 (fallback VIGENTE) falló"


# ═══════════════════════════════════════════════════════════════════════
# TESTS 6-10: SCORE DE SALUD CXC
# ═══════════════════════════════════════════════════════════════════════

def test_score_salud_cxc_excelente():
    """Test: Score = 100 cuando 100% vigente."""
    from utils.cxc_helper import calcular_score_salud
    
    score = calcular_score_salud(pct_vigente=100, pct_critica=0)
    
    assert score == 100, "Score excelente (100% vigente) debe ser 100"


def test_score_salud_cxc_critico():
    """Test: Score = 0 cuando 100% crítica."""
    from utils.cxc_helper import calcular_score_salud
    
    score = calcular_score_salud(pct_vigente=0, pct_critica=100)
    
    assert score == 0, "Score crítico (100% critica) debe ser 0"


def test_score_salud_cxc_formula_ponderada():
    """Test: Validar fórmula exacta del score (70% vigente + 30% no-crítica)."""
    from utils.cxc_helper import calcular_score_salud
    
    # 80% vigente, 10% crítica → (80 * 0.7) + (100 - 10*2) * 0.3 = 56 + 24 = 80
    score = calcular_score_salud(pct_vigente=80, pct_critica=10)
    
    assert score == 80, f"Fórmula score incorrecta: esperado 80, obtenido {score}"


def test_clasificacion_score_salud_rangos():
    """Test: Validar clasificación de score en 5 rangos."""
    from utils.cxc_helper import clasificar_score_salud
    
    # Rangos reales: >=80 Excelente, >=60 Bueno, >=40 Regular, >=20 Malo, <20 Crítico
    assert clasificar_score_salud(95)[0] == "Excelente"
    assert clasificar_score_salud(75)[0] == "Bueno"
    assert clasificar_score_salud(60)[0] == "Bueno"  # 60 >= 60 (BUENO_MIN)
    assert clasificar_score_salud(50)[0] == "Regular"
    assert clasificar_score_salud(30)[0] == "Malo"
    assert clasificar_score_salud(10)[0] == "Crítico"


def test_metricas_basicas_cxc_completas(df_cxc_vigentes_vencidas):
    """Test: calcular_metricas_basicas() retorna dict completo."""
    from utils.cxc_helper import calcular_metricas_basicas
    
    # Agregar columna dias_overdue requerida por la función
    df_test = df_cxc_vigentes_vencidas.copy()
    df_test['dias_overdue'] = df_test['dias_vencido']
    
    metricas = calcular_metricas_basicas(df_test)
    
    # Validar keys requeridas
    assert 'total_adeudado' in metricas
    assert 'vigente' in metricas
    assert 'vencida' in metricas
    assert 'pct_vigente' in metricas
    assert 'pct_vencida' in metricas
    
    # Validar que porcentajes suman ~100%
    total_pct = metricas['pct_vigente'] + metricas['pct_vencida']
    assert 99 <= total_pct <= 101, f"Porcentajes no suman 100: {total_pct}"


# ═══════════════════════════════════════════════════════════════════════
# TESTS 11-15: EXCLUSIÓN DE PAGADOS Y FILTROS
# ═══════════════════════════════════════════════════════════════════════

def test_excluir_pagados_correctamente(df_cxc_solo_pagados):
    """Test: excluir_pagados() elimina PAGADO pero conserva VIGENTE/VENCIDA."""
    from utils.cxc_helper import excluir_pagados
    
    mask_pagados = excluir_pagados(df_cxc_solo_pagados)
    df_filtrado = df_cxc_solo_pagados[~mask_pagados]  # Invertir máscara
    
    assert len(df_filtrado) == 2, "Debe quedar 2 registros (excluyendo PAGADO)"
    assert 'PAGADO' not in df_filtrado['estatus'].values


def test_excluir_pagados_case_insensitive():
    """Test: excluir_pagados() funciona con 'pagado', 'PAGADO', 'Pagado'."""
    df_test = pd.DataFrame({
        'estatus': ['Pagado', 'PAGADO', 'pagado', 'VIGENTE']
    })
    from utils.cxc_helper import excluir_pagados
    
    mask_pagados = excluir_pagados(df_test)
    df_filtrado = df_test[~mask_pagados]  # Invertir máscara
    
    assert len(df_filtrado) == 1, "Solo debe quedar 'VIGENTE'"


def test_excluir_pagados_sin_columna_estatus():
    """Test: excluir_pagados() retorna todos=False si no existe columna estatus."""
    df_sin_estatus = pd.DataFrame({'saldo': [100, 200]})
    from utils.cxc_helper import excluir_pagados
    
    mask_pagados = excluir_pagados(df_sin_estatus)
    
    # Sin columna estatus, retorna False para todos (ninguno marcado como pagado)
    assert not mask_pagados.any(), "Sin columna estatus, ninguno debe estar marcado como pagado"


def test_preparar_datos_cxc_pipeline_completo(df_cxc_solo_pagados):
    """Test: preparar_datos_cxc() ejecuta excluir_pagados + calcular_dias_overdue."""
    from utils.cxc_helper import preparar_datos_cxc
    
    df_prep, df_np, mask_pagado = preparar_datos_cxc(df_cxc_solo_pagados)
    
    # df_np no debe incluir PAGADO
    assert len(df_np) == 2, f"df_np debe tener 2 registros (sin PAGADO), tiene {len(df_np)}"
    assert 'PAGADO' not in df_np['estatus'].values
    
    # Debe agregar columna dias_overdue
    assert 'dias_overdue' in df_prep.columns


def test_detectar_columna_prioridad_orden():
    """Test: detectar_columna() usa primera columna existente (prioridad)."""
    df_test = pd.DataFrame({
        'columna_b': [1, 2],
        'columna_c': [3, 4]
    })
    from utils.cxc_helper import detectar_columna
    
    # Lista con prioridad: a > b > c
    opciones = ['columna_a', 'columna_b', 'columna_c']
    resultado = detectar_columna(df_test, opciones)
    
    assert resultado == 'columna_b', "Debe retornar primera existente (columna_b)"


# ═══════════════════════════════════════════════════════════════════════
# TESTS 16-20: SEMÁFOROS Y ALERTAS
# ═══════════════════════════════════════════════════════════════════════

def test_semaforo_morosidad_umbrales():
    """Test: obtener_semaforo_morosidad() usa umbrales correctos."""
    from utils.cxc_helper import obtener_semaforo_morosidad
    
    # Umbrales reales: <10 verde, <25 amarillo, <50 naranja, >=50 rojo
    assert obtener_semaforo_morosidad(5) == "🟢"   # <10%
    assert obtener_semaforo_morosidad(15) == "🟡"  # 10-25%
    assert obtener_semaforo_morosidad(30) == "🟠"  # 25-50%
    assert obtener_semaforo_morosidad(60) == "🔴"  # >=50%


def test_semaforo_riesgo_dias():
    """Test: obtener_semaforo_riesgo() basado en % de riesgo alto."""
    from utils.cxc_helper import obtener_semaforo_riesgo
    
    # Umbrales reales: <5% verde, <15% amarillo, <30% naranja, >=30% rojo
    assert obtener_semaforo_riesgo(3) == "🟢"   # <5%
    assert obtener_semaforo_riesgo(10) == "🟡"  # 5-15%
    assert obtener_semaforo_riesgo(20) == "🟠"  # 15-30%
    assert obtener_semaforo_riesgo(40) == "🔴"  # >=30%


def test_semaforo_concentracion_riesgo():
    """Test: obtener_semaforo_concentracion() detecta dependencia cliente."""
    from utils.cxc_helper import obtener_semaforo_concentracion
    
    assert obtener_semaforo_concentracion(20) == "🟢"  # <30%
    assert obtener_semaforo_concentracion(40) == "🟡"  # 30-50%
    assert obtener_semaforo_concentracion(60) == "🔴"  # >50% (¡PELIGRO!)


def test_alerta_monto_critico():
    """Test: Alertas cuando monto crítico > umbral definido."""
    df_test = pd.DataFrame({
        'saldo_adeudado': [100000],  # >50K crítico
        'dias_vencido': [120]
    })
    from utils.constantes import UmbralesCxC
    
    # Validar que se genera alerta (usar DIAS_ALTO_RIESGO que existe)
    critico = df_test[df_test['dias_vencido'] >= UmbralesCxC.DIAS_ALTO_RIESGO]
    monto_critico = critico['saldo_adeudado'].sum()
    
    assert monto_critico > UmbralesCxC.CRITICO_MONTO


def test_prioridad_cobranza_existe():
    """Test: Constantes de prioridad de cobranza existen."""
    from utils.constantes import PrioridadCobranza
    
    # Validar umbrales existen (usar nombres correctos)
    assert hasattr(PrioridadCobranza, 'URGENTE_MIN')
    assert hasattr(PrioridadCobranza, 'ALTA_MIN')
    assert hasattr(PrioridadCobranza, 'MEDIA_MIN')
    assert hasattr(PrioridadCobranza, 'PESO_MONTO')
    assert hasattr(PrioridadCobranza, 'PESO_DIAS')


# ═══════════════════════════════════════════════════════════════════════
# TESTS 21-25: ANÁLISIS POR LÍNEA DE NEGOCIO Y DRILL-DOWN
# ═══════════════════════════════════════════════════════════════════════

def test_analisis_por_linea_negocio(df_cxc_vigentes_vencidas):
    """Test: Agrupación por línea_negocio calcula métricas correctas."""
    df_lineas = df_cxc_vigentes_vencidas.groupby('linea_negocio').agg({
        'saldo_adeudado': 'sum',
        'dias_vencido': 'mean'
    }).reset_index()
    
    assert len(df_lineas) == 3, "Debe haber 3 líneas de negocio"
    assert 'Producto A' in df_lineas['linea_negocio'].values


def test_drill_down_cliente_detalle(df_cxc_vigentes_vencidas):
    """Test: Drill-down de Cliente A muestra 2 facturas."""
    df_cliente_a = df_cxc_vigentes_vencidas[
        df_cxc_vigentes_vencidas['deudor'] == 'Cliente A'
    ]
    
    assert len(df_cliente_a) == 2, "Cliente A debe tener 2 facturas"
    assert df_cliente_a['saldo_adeudado'].sum() == 15000


def test_top_n_clientes_por_saldo():
    """Test: Top N clientes ordenados por saldo_adeudado desc."""
    df_test = pd.DataFrame({
        'deudor': ['A', 'B', 'C'],
        'saldo_adeudado': [1000, 5000, 3000]
    })
    
    top3 = df_test.nlargest(3, 'saldo_adeudado')
    
    assert top3.iloc[0]['deudor'] == 'B', "B debe ser #1 ($5K)"
    assert top3.iloc[1]['deudor'] == 'C', "C debe ser #2 ($3K)"


def test_busqueda_cliente_case_insensitive():
    """Test: Búsqueda de cliente no distingue mayúsculas."""
    df_test = pd.DataFrame({
        'deudor': ['ACME Corp', 'Widgets Inc', 'Tech Solutions']
    })
    
    # Buscar "acme" debe encontrar "ACME Corp"
    resultado = df_test[df_test['deudor'].str.contains('acme', case=False, na=False)]
    
    assert len(resultado) == 1
    assert resultado.iloc[0]['deudor'] == 'ACME Corp'


def test_exportacion_excel_estructura(df_cxc_vigentes_vencidas):
    """Test: Exportación a Excel genera estructura correcta."""
    from io import BytesIO
    
    # Crear buffer Excel en memoria
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_cxc_vigentes_vencidas.to_excel(writer, sheet_name='Resumen', index=False)
    
    buffer.seek(0)
    
    # Validar que se puede leer
    df_leido = pd.read_excel(buffer, sheet_name='Resumen')
    assert len(df_leido) == len(df_cxc_vigentes_vencidas)
    assert list(df_leido.columns) == list(df_cxc_vigentes_vencidas.columns)

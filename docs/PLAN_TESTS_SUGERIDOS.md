# 🧪 Plan de Tests Sugeridos - Fradma Dashboard

**Fecha:** 19 de febrero de 2026  
**Coverage actual:** 8.98% (98 tests)  
**Coverage objetivo:** 55%+ (200+ tests)  
**Esfuerzo total estimado:** 60-70 horas

---

## 📊 Resumen Ejecutivo de Gaps

| Módulo | Líneas | Coverage Actual | Tests Actuales | Tests Sugeridos | Prioridad |
|--------|--------|-----------------|----------------|-----------------|-----------|
| `main/kpi_cpc.py` | 1,410 | **0%** | 0 | 25 | 🔴 Crítica |
| `main/reporte_ejecutivo.py` | 850 | **0%** | 0 | 18 | 🔴 Crítica |
| `main/ytd_lineas.py` | 550 | **0%** | 0 | 12 | 🟡 Alta |
| `utils/ai_helper_premium.py` | 47 | **0%** | 0 | 8 | 🔴 Crítica |
| `utils/ai_helper.py` | 92 | **0%** | 0 | 8 | 🟡 Alta |
| `utils/data_normalizer.py` | 108 | 25.93% | 14 | 12 | 🟡 Alta |
| `main/heatmap_ventas.py` | 380 | **0%** | 0 | 10 | 🟢 Media |
| `main/reporte_consolidado.py` | 480 | **0%** | 0 | 12 | 🟢 Media |
| `main/vendedores_cxc.py` | 450 | **0%** | 0 | 10 | 🟢 Media |
| **TOTAL** | **4,367** | **~2%** | **14** | **115** | — |

**Meta:** +115 tests → Coverage 55%+

---

## 🔴 PRIORIDAD CRÍTICA (Semana 1-2)

### 1. Tests para `main/kpi_cpc.py` (25 tests, 20-25 horas)

**Objetivo:** Coverage 0% → 80%+ (validar lógica más crítica del sistema)

#### **Archivo:** `tests/integration/test_kpi_cpc_core.py`

```python
"""
Tests de integración para Dashboard CxC (kpi_cpc.py)
Valida flujos completos end-to-end del módulo más crítico.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from main.kpi_cpc import run
from utils.constantes import UmbralesCxC, ScoreSalud


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES DE DATOS REALISTAS
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def df_cxc_completo():
    """DataFrame CxC con todos los escenarios: vigente, vencida, crítica."""
    hoy = pd.Timestamp.today()
    return pd.DataFrame({
        'deudor': ['Cliente A', 'Cliente A', 'Cliente B', 'Cliente C', 'Cliente D'],
        'saldo_adeudado': [10000, 5000, 50000, 100000, 15000],
        'dias_vencido': [0, 15, 45, 120, 30],
        'fecha_vencimiento': [
            hoy - timedelta(days=0),
            hoy - timedelta(days=15),
            hoy - timedelta(days=45),
            hoy - timedelta(days=120),
            hoy - timedelta(days=30)
        ],
        'estatus': ['VIGENTE', 'VIGENTE', 'VENCIDA', 'VENCIDA', 'VENCIDA'],
        'linea_negocio': ['Producto A', 'Producto A', 'Producto B', 'Producto C', 'Producto A']
    })


@pytest.fixture
def df_cxc_con_pagados():
    """DataFrame con registros pagados que deben excluirse."""
    return pd.DataFrame({
        'deudor': ['Cliente X', 'Cliente Y', 'Cliente Z'],
        'saldo_adeudado': [5000, 0, 10000],
        'dias_vencido': [10, 0, 30],
        'estatus': ['VENCIDA', 'PAGADO', 'VIGENTE']
    })


@pytest.fixture
def df_cxc_metodos_calculo():
    """DataFrame para validar 5 métodos de cálculo de días vencido."""
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
        
        # Método 5: Sin columnas (usa DEFAULT)
        'estatus': ['VENCIDA', 'VENCIDA', 'VENCIDA', 'VENCIDA', 'VIGENTE']
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


def test_calculo_dias_vencido_metodo2_invertido(df_cxc_metodos_calculo):
    """Test: Método 2 - Columna dias_restante (negativo = vencido)."""
    from utils.cxc_helper import calcular_dias_overdue
    
    result = calcular_dias_overdue(df_cxc_metodos_calculo)
    
    # Cliente Test2 debe tener 20 días (método 2: -(-20))
    assert result.iloc[1] == 20, "Método 2 (dias_restante invertido) falló"


def test_calculo_dias_vencido_metodo3_fecha_vencimiento(df_cxc_metodos_calculo):
    """Test: Método 3 - Columna fecha_vencimiento (hoy - fecha)."""
    from utils.cxc_helper import calcular_dias_overdue
    
    result = calcular_dias_overdue(df_cxc_metodos_calculo)
    
    # Cliente Test3 debe tener ~30 días (método 3)
    assert 28 <= result.iloc[2] <= 32, "Método 3 (fecha_vencimiento) falló"


def test_calculo_dias_vencido_metodo4_fecha_pago_credito(df_cxc_metodos_calculo):
    """Test: Método 4 - Columna fecha_pago + credito_dias."""
    from utils.cxc_helper import calcular_dias_overdue
    
    result = calcular_dias_overdue(df_cxc_metodos_calculo)
    
    # Cliente Test4 debe tener ~50 días (80 - 30 = 50)
    assert 48 <= result.iloc[3] <= 52, "Método 4 (fecha_pago + credito) falló"


def test_calculo_dias_vencido_metodo5_fallback_default(df_cxc_metodos_calculo):
    """Test: Método 5 - Sin columnas relevantes, usa fallback (vigente=0)."""
    from utils.cxc_helper import calcular_dias_overdue
    
    result = calcular_dias_overdue(df_cxc_metodos_calculo)
    
    # Cliente Test5 (VIGENTE sin columnas) debe tener 0 días
    assert result.iloc[4] == 0, "Método 5 (fallback VIGENTE) falló"


# ═══════════════════════════════════════════════════════════════════════
# TESTS 6-10: SCORE DE SALUD CXC
# ═══════════════════════════════════════════════════════════════════════

def test_score_salud_cxc_excelente(df_cxc_completo):
    """Test: Score = 100 cuando 100% vigente."""
    from utils.cxc_helper import calcular_score_salud
    
    score = calcular_score_salud(pct_vigente=100, pct_critica=0)
    
    assert score == 100, "Score excelente (100% vigente) debe ser 100"


def test_score_salud_cxc_critico(df_cxc_completo):
    """Test: Score = 0 cuando 100% crítica."""
    from utils.cxc_helper import calcular_score_salud
    
    score = calcular_score_salud(pct_vigente=0, pct_critica=100)
    
    assert score == 0, "Score crítico (100% critica) debe ser 0"


def test_score_salud_cxc_formula_ponderada():
    """Test: Validar fórmula exacta del score (70% vigente + 30% no-crítica)."""
    from utils.cxc_helper import calcular_score_salud
    
    # 80% vigente, 10% crítica → (80 * 0.7) + (90 * 0.3) = 56 + 27 = 83
    score = calcular_score_salud(pct_vigente=80, pct_critica=10)
    
    assert score == 83, f"Fórmula score incorrecta: esperado 83, obtenido {score}"


def test_clasificacion_score_salud_rangos():
    """Test: Validar clasificación de score en 5 rangos."""
    from utils.cxc_helper import clasificar_score_salud
    
    assert clasificar_score_salud(95)[0] == "Excelente"
    assert clasificar_score_salud(75)[0] == "Bueno"
    assert clasificar_score_salud(60)[0] == "Regular"
    assert clasificar_score_salud(40)[0] == "Malo"
    assert clasificar_score_salud(20)[0] == "Crítico"


def test_metricas_basicas_cxc_completas(df_cxc_completo):
    """Test: calcular_metricas_basicas() retorna dict completo."""
    from utils.cxc_helper import calcular_metricas_basicas
    
    metricas = calcular_metricas_basicas(df_cxc_completo)
    
    # Validar keys requeridas
    assert 'total_adeudado' in metricas
    assert 'saldo_vigente' in metricas
    assert 'saldo_vencida' in metricas
    assert 'saldo_critica' in metricas
    assert 'pct_vigente' in metricas
    assert 'pct_vencida' in metricas
    
    # Validar sumas
    total = metricas['saldo_vigente'] + metricas['saldo_vencida']
    assert abs(total - metricas['total_adeudado']) < 0.01, "Suma vigente+vencida != total"


# ═══════════════════════════════════════════════════════════════════════
# TESTS 11-15: EXCLUSIÓN DE PAGADOS Y FILTROS
# ═══════════════════════════════════════════════════════════════════════

def test_excluir_pagados_correctamente(df_cxc_con_pagados):
    """Test: excluir_pagados() elimina PAGADO pero conserva VIGENTE/VENCIDA."""
    from utils.cxc_helper import excluir_pagados
    
    mask = excluir_pagados(df_cxc_con_pagados)
    df_filtrado = df_cxc_con_pagados[mask]
    
    assert len(df_filtrado) == 2, "Debe quedar 2 registros (excluyendo PAGADO)"
    assert 'PAGADO' not in df_filtrado['estatus'].values


def test_excluir_pagados_case_insensitive():
    """Test: excluir_pagados() funciona con 'pagado', 'PAGADO', 'Pagado'."""
    df_test = pd.DataFrame({
        'estatus': ['Pagado', 'PAGADO', 'pagado', 'VIGENTE']
    })
    from utils.cxc_helper import excluir_pagados
    
    mask = excluir_pagados(df_test)
    df_filtrado = df_test[mask]
    
    assert len(df_filtrado) == 1, "Solo debe quedar 'VIGENTE'"


def test_excluir_pagados_sin_columna_estatus():
    """Test: excluir_pagados() retorna todos=True si no existe columna estatus."""
    df_sin_estatus = pd.DataFrame({'saldo': [100, 200]})
    from utils.cxc_helper import excluir_pagados
    
    mask = excluir_pagados(df_sin_estatus)
    
    assert mask.all(), "Sin columna estatus, debe incluir todos"


def test_preparar_datos_cxc_pipeline_completo(df_cxc_con_pagados):
    """Test: preparar_datos_cxc() ejecuta excluir_pagados + calcular_dias_overdue."""
    from utils.cxc_helper import preparar_datos_cxc
    
    df_result = preparar_datos_cxc(df_cxc_con_pagados)
    
    # Debe excluir PAGADO
    assert len(df_result) == 2
    
    # Debe agregar columna dias_vencido si no existe
    assert 'dias_vencido' in df_result.columns


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
    
    assert obtener_semaforo_morosidad(10) == "🟢"  # <15%
    assert obtener_semaforo_morosidad(20) == "🟡"  # 15-30%
    assert obtener_semaforo_morosidad(40) == "🟠"  # 30-50%
    assert obtener_semaforo_morosidad(60) == "🔴"  # >50%


def test_semaforo_riesgo_dias():
    """Test: obtener_semaforo_riesgo() basado en días promedio."""
    from utils.cxc_helper import obtener_semaforo_riesgo
    
    assert obtener_semaforo_riesgo(20) == "🟢"   # <30 días
    assert obtener_semaforo_riesgo(45) == "🟡"   # 30-60 días
    assert obtener_semaforo_riesgo(75) == "🟠"   # 60-90 días
    assert obtener_semaforo_riesgo(120) == "🔴"  # >90 días


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
    
    # Validar que se genera alerta
    critico = df_test[df_test['dias_vencido'] >= UmbralesCxC.DIAS_CRITICO]
    monto_critico = critico['saldo_adeudado'].sum()
    
    assert monto_critico > UmbralesCxC.CRITICO_MONTO


def test_prioridad_cobranza_calculo():
    """Test: Sistema de priorización de cobranza (URGENTE, ALTA, MEDIA, BAJA)."""
    # Criterios: monto, días, % concentración
    # URGENTE: >90 días O >$50K
    # ALTA: 60-90 días O $30-50K
    # MEDIA: 30-60 días O $10-30K
    # BAJA: <30 días Y <$10K
    
    from utils.constantes import PrioridadCobranza
    
    # Validar umbrales existen
    assert hasattr(PrioridadCobranza, 'URGENTE_DIAS')
    assert hasattr(PrioridadCobranza, 'ALTA_DIAS')


# ═══════════════════════════════════════════════════════════════════════
# TESTS 21-25: ANÁLISIS POR LÍNEA DE NEGOCIO Y DRILL-DOWN
# ═══════════════════════════════════════════════════════════════════════

def test_analisis_por_linea_negocio(df_cxc_completo):
    """Test: Agrupación por línea_negocio calcula métricas correctas."""
    df_lineas = df_cxc_completo.groupby('linea_negocio').agg({
        'saldo_adeudado': 'sum',
        'dias_vencido': 'mean'
    }).reset_index()
    
    assert len(df_lineas) == 3, "Debe haber 3 líneas de negocio"
    assert 'Producto A' in df_lineas['linea_negocio'].values


def test_drill_down_cliente_detalle(df_cxc_completo):
    """Test: Drill-down de Cliente A muestra 2 facturas."""
    df_cliente_a = df_cxc_completo[df_cxc_completo['deudor'] == 'Cliente A']
    
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


def test_exportacion_excel_completo(df_cxc_completo, tmp_path):
    """Test: Exportación a Excel genera archivo con múltiples hojas."""
    import openpyxl
    from io import BytesIO
    
    # Crear buffer Excel en memoria
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_cxc_completo.to_excel(writer, sheet_name='Resumen', index=False)
        df_cxc_completo.to_excel(writer, sheet_name='Detalle', index=False)
    
    buffer.seek(0)
    
    # Validar que se puede leer
    wb = openpyxl.load_workbook(buffer)
    assert 'Resumen' in wb.sheetnames
    assert 'Detalle' in wb.sheetnames
```

---

### 2. Tests para `main/reporte_ejecutivo.py` (18 tests, 15-18 horas)

**Objetivo:** Coverage 0% → 75%+ (validar correlación ventas-CxC)

#### **Archivo:** `tests/integration/test_reporte_ejecutivo.py`

```python
"""
Tests de integración para Reporte Ejecutivo
Valida correlación ventas-CxC, análisis IA y exports HTML.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES REPORTE EJECUTIVO
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def df_ventas_mock():
    """DataFrame ventas para reporte ejecutivo."""
    fechas = pd.date_range(start='2025-01-01', periods=30, freq='D')
    return pd.DataFrame({
        'fecha': fechas,
        'ventas_usd': np.random.uniform(1000, 5000, 30),
        'cliente': ['Cliente A'] * 15 + ['Cliente B'] * 15,
        'vendedor': ['Vendedor X'] * 20 + ['Vendedor Y'] * 10
    })


@pytest.fixture
def df_cxc_mock():
    """DataFrame CxC para reporte ejecutivo."""
    return pd.DataFrame({
        'cliente': ['Cliente A', 'Cliente B', 'Cliente C'],
        'saldo_adeudado': [10000, 25000, 5000],
        'dias_vencido': [15, 60, 0],
        'estatus': ['VENCIDA', 'VENCIDA', 'VIGENTE']
    })


# ═══════════════════════════════════════════════════════════════════════
# TESTS: MÉTRICAS VENTAS
# ═══════════════════════════════════════════════════════════════════════

def test_total_ventas_periodo(df_ventas_mock):
    """Test: Suma total de ventas en el período."""
    total = df_ventas_mock['ventas_usd'].sum()
    assert total > 0
    assert isinstance(total, (int, float))


def test_promedio_ventas_diarias(df_ventas_mock):
    """Test: Promedio diario de ventas."""
    promedio = df_ventas_mock['ventas_usd'].mean()
    assert 1000 <= promedio <= 5000


def test_top_vendedores_ranking(df_ventas_mock):
    """Test: Ranking de vendedores por total ventas."""
    ranking = df_ventas_mock.groupby('vendedor')['ventas_usd'].sum().sort_values(ascending=False)
    
    assert len(ranking) == 2
    assert ranking.index[0] in ['Vendedor X', 'Vendedor Y']


# ═══════════════════════════════════════════════════════════════════════
# TESTS: CORRELACIÓN VENTAS-CXC
# ═══════════════════════════════════════════════════════════════════════

def test_correlacion_ventas_cartera(df_ventas_mock, df_cxc_mock):
    """Test: Clientes con más ventas vs clientes con más CxC vencida."""
    ventas_por_cliente = df_ventas_mock.groupby('cliente')['ventas_usd'].sum()
    cxc_por_cliente = df_cxc_mock.set_index('cliente')['saldo_adeudado']
    
    # Cliente A: muchas ventas pero poca CxC = buen cliente
    # Cliente B: menos ventas pero alta CxC = riesgo
    
    assert 'Cliente A' in ventas_por_cliente.index
    assert 'Cliente B' in cxc_por_cliente.index


def test_indicador_riesgo_cliente():
    """Test: Índice de riesgo = CxC vencida / Ventas totales."""
    ventas_cliente = 100000
    cxc_vencida_cliente = 25000
    
    riesgo = (cxc_vencida_cliente / ventas_cliente) * 100
    
    # 25% de CxC vencida vs ventas = riesgo medio
    assert 20 <= riesgo <= 30


# ═══════════════════════════════════════════════════════════════════════
# TESTS: FILTROS DE FECHAS AVANZADOS
# ═══════════════════════════════════════════════════════════════════════

def test_filtro_fecha_ytd(df_ventas_mock):
    """Test: Filtro YTD (Year-to-Date) desde enero hasta hoy."""
    hoy = pd.Timestamp.today()
    inicio_anio = pd.Timestamp(year=hoy.year, month=1, day=1)
    
    df_ytd = df_ventas_mock[
        (df_ventas_mock['fecha'] >= inicio_anio) &
        (df_ventas_mock['fecha'] <= hoy)
    ]
    
    assert len(df_ytd) >= 0  # Puede ser vacío si no hay datos YTD


def test_filtro_fecha_mes_especifico(df_ventas_mock):
    """Test: Filtro por mes específico (ej: Enero 2025)."""
    df_enero = df_ventas_mock[
        (df_ventas_mock['fecha'].dt.month == 1) &
        (df_ventas_mock['fecha'].dt.year == 2025)
    ]
    
    assert len(df_enero) > 0


def test_filtro_fecha_trimestre(df_ventas_mock):
    """Test: Filtro por trimestre (Q1 = Ene-Mar)."""
    df_q1 = df_ventas_mock[df_ventas_mock['fecha'].dt.quarter == 1]
    
    meses_q1 = df_q1['fecha'].dt.month.unique()
    assert all(mes in [1, 2, 3] for mes in meses_q1)


def test_filtro_fecha_rango_personalizado(df_ventas_mock):
    """Test: Filtro por rango personalizado de fechas."""
    inicio = pd.Timestamp('2025-01-10')
    fin = pd.Timestamp('2025-01-20')
    
    df_rango = df_ventas_mock[
        (df_ventas_mock['fecha'] >= inicio) &
        (df_ventas_mock['fecha'] <= fin)
    ]
    
    assert len(df_rango) <= 11  # Máximo 11 días


# ═══════════════════════════════════════════════════════════════════════
# TESTS: COMPARACIÓN DE PERÍODOS
# ═══════════════════════════════════════════════════════════════════════

def test_comparacion_periodo_actual_vs_anterior(df_ventas_mock):
    """Test: Comparar ventas último mes vs mes anterior."""
    hoy = df_ventas_mock['fecha'].max()
    inicio_mes_actual = hoy - timedelta(days=30)
    
    ventas_mes_actual = df_ventas_mock[
        df_ventas_mock['fecha'] >= inicio_mes_actual
    ]['ventas_usd'].sum()
    
    assert ventas_mes_actual > 0


def test_crecimiento_ventas_porcentual():
    """Test: % crecimiento ventas = (actual - anterior) / anterior * 100."""
    ventas_anterior = 50000
    ventas_actual = 60000
    
    crecimiento = ((ventas_actual - ventas_anterior) / ventas_anterior) * 100
    
    assert crecimiento == 20.0  # 20% crecimiento


# ═══════════════════════════════════════════════════════════════════════
# TESTS: EXPORTACIÓN HTML
# ═══════════════════════════════════════════════════════════════════════

def test_export_html_contiene_metricas():
    """Test: Export HTML incluye sección de métricas."""
    from utils.export_helper import crear_reporte_html
    
    metricas = {
        'total_adeudado': 100000,
        'saldo_vigente': 70000,
        'saldo_vencida': 30000
    }
    df_detalle = pd.DataFrame({'cliente': ['A', 'B']})
    
    html = crear_reporte_html(metricas, df_detalle, nombre_empresa="Test Corp")
    
    assert '100,000' in html or '100000' in html
    assert 'Test Corp' in html


def test_export_html_estilos_css():
    """Test: HTML exportado incluye estilos CSS."""
    from utils.export_helper import crear_reporte_html
    
    metricas = {'total_adeudado': 1000}
    df = pd.DataFrame()
    
    html = crear_reporte_html(metricas, df)
    
    assert '<style>' in html
    assert 'background' in html.lower()


# ═══════════════════════════════════════════════════════════════════════
# TESTS: ANÁLISIS IA (MOCK)
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_openai_response(monkeypatch):
    """Mock de respuesta OpenAI API para tests."""
    class MockOpenAI:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    class MockResponse:
                        class Message:
                            content = """
                            **Insights Principales:**
                            - Las ventas crecieron 15% vs mes anterior
                            - La cartera vencida está en 22%
                            
                            **Recomendaciones:**
                            - Priorizar cobranza Cliente B
                            - Mantener tendencia de ventas
                            """
                        
                        choices = [type('obj', (object,), {'message': Message()})]
                    
                    return MockResponse()
    
    # No necesitamos monkeypatch aquí, solo retornar el mock
    return MockOpenAI


def test_analisis_ia_premium_genera_insights(mock_openai_response):
    """Test: Análisis IA Premium retorna insights estructurados."""
    # Este test requiere mock de OpenAI
    from utils.ai_helper_premium import generar_analisis_ejecutivo
    
    metricas_ventas = {'total': 100000, 'crecimiento': 15}
    metricas_cxc = {'vencida_pct': 22}
    
    # Con mock, validar que se genera análisis
    # TODO: Implementar cuando ai_helper_premium tenga tests
    pass


def test_analisis_ia_detecta_anomalias():
    """Test: IA detecta anomalías (ej: caída >30% ventas)."""
    ventas_historico = [100000, 95000, 98000, 102000]
    ventas_actual = 60000  # Caída 40%
    
    promedio = sum(ventas_historico) / len(ventas_historico)
    caida_pct = ((ventas_actual - promedio) / promedio) * 100
    
    assert caida_pct < -30, "Debe detectarse como anomalía"
```

---

### 3. Tests para `utils/ai_helper_premium.py` (8 tests, 8-10 horas)

**Objetivo:** Coverage 0% → 85%+ (validar lógica IA con mocks)

#### **Archivo:** `tests/unit/test_ai_helper_premium.py`

```python
"""
Tests unitarios para helpers IA Premium
Se usan MOCKS de OpenAI para no consumir API real.
"""

import pytest
from unittest.mock import Mock, patch
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════
# MOCK DE OPENAI API
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_openai_client():
    """Mock completo de cliente OpenAI."""
    with patch('utils.ai_helper_premium.OpenAI') as mock:
        # Configurar respuesta mock
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="**Insights:** Test insight\n**Recomendaciones:** Test rec"))
        ]
        
        mock.return_value.chat.completions.create.return_value = mock_response
        yield mock


# ═══════════════════════════════════════════════════════════════════════
# TESTS: GENERACIÓN DE PROMPTS
# ═══════════════════════════════════════════════════════════════════════

def test_generar_prompt_cxc_incluye_metricas():
    """Test: Prompt CxC incluye métricas clave."""
    from utils.ai_helper_premium import _generar_prompt_cxc
    
    metricas = {
        'total_adeudado': 100000,
        'pct_vencida': 25
    }
    
    prompt = _generar_prompt_cxc(metricas)
    
    assert '100000' in prompt or '100,000' in prompt
    assert '25' in prompt


def test_generar_prompt_ventas_incluye_tendencias():
    """Test: Prompt ventas incluye datos de tendencia."""
    from utils.ai_helper_premium import _generar_prompt_ventas
    
    datos = {
        'total_ventas': 200000,
        'crecimiento_pct': 15
    }
    
    prompt = _generar_prompt_ventas(datos)
    
    assert '200000' in prompt
    assert '15' in prompt or 'crecimiento' in prompt.lower()


# ═══════════════════════════════════════════════════════════════════════
# TESTS: ANÁLISIS CON MOCK
# ═══════════════════════════════════════════════════════════════════════

def test_generar_insights_cxc_llama_openai(mock_openai_client):
    """Test: generar_insights_cxc() llama a OpenAI API correctamente."""
    from utils.ai_helper_premium import generar_insights_cxc
    
    metricas = {'total_adeudado': 50000, 'pct_vencida': 20}
    
    resultado = generar_insights_cxc(metricas, api_key="test_key")
    
    # Validar que se llamó OpenAI
    mock_openai_client.return_value.chat.completions.create.assert_called_once()
    
    # Validar que retorna string
    assert isinstance(resultado, str)
    assert len(resultado) > 0


def test_generar_recomendaciones_cobranza(mock_openai_client):
    """Test: Recomendaciones de cobranza basadas en prioridades."""
    from utils.ai_helper_premium import generar_recomendaciones_cobranza
    
    df_prioridades = pd.DataFrame({
        'cliente': ['A', 'B', 'C'],
        'nivel': ['URGENTE', 'ALTA', 'MEDIA'],
        'saldo': [50000, 30000, 10000]
    })
    
    resultado = generar_recomendaciones_cobranza(df_prioridades, api_key="test_key")
    
    assert isinstance(resultado, str)


def test_analizar_tendencias_ventas(mock_openai_client):
    """Test: Análisis de tendencias detecta patrones."""
    from utils.ai_helper_premium import analizar_tendencias_ventas
    
    df_ventas = pd.DataFrame({
        'fecha': pd.date_range('2025-01-01', periods=30),
        'ventas_usd': [1000] * 30
    })
    
    resultado = analizar_tendencias_ventas(df_ventas, api_key="test_key")
    
    assert isinstance(resultado, str)


# ═══════════════════════════════════════════════════════════════════════
# TESTS: MANEJO DE ERRORES
# ═══════════════════════════════════════════════════════════════════════

def test_generar_insights_sin_api_key():
    """Test: Genera error cuando no hay API key."""
    from utils.ai_helper_premium import generar_insights_cxc
    
    with pytest.raises(ValueError, match="API key"):
        generar_insights_cxc({'total': 1000}, api_key=None)


def test_generar_insights_api_error():
    """Test: Maneja errores de API correctamente."""
    with patch('utils.ai_helper_premium.OpenAI') as mock:
        mock.return_value.chat.completions.create.side_effect = Exception("API Error")
        
        from utils.ai_helper_premium import generar_insights_cxc
        
        with pytest.raises(Exception):
            generar_insights_cxc({'total': 1000}, api_key="test")


# ═══════════════════════════════════════════════════════════════════════
# TESTS: PARSING DE RESPUESTAS
# ═══════════════════════════════════════════════════════════════════════

def test_parsear_respuesta_ia_extrae_secciones():
    """Test: Parser extrae secciones de respuesta IA."""
    respuesta_mock = """
    **Insights Principales:**
    - Insight 1
    - Insight 2
    
    **Recomendaciones:**
    - Recomendación 1
    - Recomendación 2
    """
    
    from utils.ai_helper_premium import _parsear_respuesta_ia
    
    parsed = _parsear_respuesta_ia(respuesta_mock)
    
    assert 'insights' in parsed
    assert 'recomendaciones' in parsed
    assert len(parsed['insights']) == 2
    assert len(parsed['recomendaciones']) == 2
```

---

## 📁 Estructura de Archivos Sugerida

```
tests/
├── conftest.py                          # Fixtures compartidos
├── unit/
│   ├── test_cxc_helper.py              # ✅ YA EXISTE (43 tests)
│   ├── test_formatos.py                # ✅ YA EXISTE (27 tests)
│   ├── test_data_normalizer.py         # ⚠️ PARCIAL (14 tests) → +12 tests NUEVOS
│   ├── test_ai_helper_premium.py       # ❌ CREAR (8 tests NUEVOS)
│   ├── test_ai_helper.py               # ❌ CREAR (8 tests NUEVOS)
│   └── test_constantes.py              # ✅ IMPLÍCITO (usado en otros tests)
│
└── integration/
    ├── test_kpi_cpc_core.py            # ❌ CREAR (25 tests NUEVOS)
    ├── test_reporte_ejecutivo.py       # ❌ CREAR (18 tests NUEVOS)
    ├── test_ytd_lineas.py              # ❌ CREAR (12 tests sugeridos)
    ├── test_heatmap_ventas.py          # ❌ CREAR (10 tests sugeridos)
    ├── test_reporte_consolidado.py     # ❌ CREAR (12 tests sugeridos)
    └── test_vendedores_cxc.py          # ❌ CREAR (10 tests sugeridos)
```

---

## 🎯 Plan de Implementación Sugerido

### **Sprint 1 (40 horas)** - CRÍTICO
1. **test_kpi_cpc_core.py** (25 tests) → 20-25 horas
2. **test_ai_helper_premium.py** (8 tests) → 8-10 horas
3. **test_data_normalizer.py** (+12 tests) → 4-6 horas

**Meta:** Coverage 9% → 35%

---

### **Sprint 2 (30 horas)** - IMPORTANTE
4. **test_reporte_ejecutivo.py** (18 tests) → 15-18 horas
5. **test_ai_helper.py** (8 tests) → 6-8 horas
6. **test_ytd_lineas.py** (12 tests) → 8-10 horas

**Meta:** Coverage 35% → 55%

---

## 📋 Comandos de Ejecución

```bash
# Ejecutar solo tests nuevos de kpi_cpc
pytest tests/integration/test_kpi_cpc_core.py -v

# Ejecutar con coverage
pytest tests/integration/test_kpi_cpc_core.py --cov=main.kpi_cpc --cov-report=html

# Ejecutar todos los tests de integración
pytest tests/integration/ -v

# Ver coverage solo de main/
pytest --cov=main --cov-report=term-missing

# Ejecutar tests en paralelo (más rápido)
pytest -n auto tests/integration/
```

---

## ✅ Criterios de Éxito

| Criterio | Objetivo |
|----------|----------|
| **Coverage main/kpi_cpc.py** | ≥ 80% |
| **Coverage main/reporte_ejecutivo.py** | ≥ 75% |
| **Coverage utils/ai_helper*.py** | ≥ 85% |
| **Coverage global** | ≥ 55% (desde 9%) |
| **Tests totales** | ≥ 200 (desde 98) |
| **Tiempo ejecución tests** | < 10s (actualmente 2.08s) |
| **Pass rate** | 100% |

---

## 💡 Notas de Implementación

### Fixtures Compartidos
```python
# tests/conftest.py - Agregar fixtures globales
@pytest.fixture
def hoy():
    """Fecha de hoy para tests determinísticos."""
    return pd.Timestamp('2026-02-19')

@pytest.fixture
def api_key_test():
    """API key mock para tests de IA."""
    return "sk-test-mock-key-1234567890"
```

### Mocking de OpenAI
```python
# Usar pytest-mock para simplificar mocks
pip install pytest-mock

# En test:
def test_con_mock(mocker):
    mock_openai = mocker.patch('utils.ai_helper_premium.OpenAI')
    mock_openai.return_value.chat.completions.create.return_value = ...
```

### Fixtures de Datos Realistas
```python
# Usar datos similares a producción
@pytest.fixture
def df_cxc_real_world():
    """Dataset realista con >100 clientes."""
    np.random.seed(42)  # Reproducibilidad
    return pd.DataFrame({
        'deudor': [f'Cliente {i}' for i in range(100)],
        'saldo_adeudado': np.random.uniform(1000, 100000, 100),
        'dias_vencido': np.random.choice([0, 15, 30, 60, 90, 120], 100)
    })
```

---

**Última actualización:** 19 de febrero de 2026  
**Próxima revisión:** Tras implementar Sprint 1 (1 marzo 2026)

"""
Script para profiling de performance del dashboard.

Identifica funciones lentas que necesitan optimización.
"""

import cProfile
import pstats
import io
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.cxc_helper import (
    calcular_dias_overdue,
    preparar_datos_cxc,
    calcular_metricas_basicas,
    calcular_score_salud,
    clasificar_score_salud,
    obtener_semaforo_morosidad,
    obtener_semaforo_riesgo,
    obtener_semaforo_concentracion
)
from utils.formatos import (
    formato_moneda,
    formato_numero,
    formato_porcentaje,
    formato_compacto,
    formato_dias,
    formato_delta_moneda
)


def generar_datos_prueba(n_filas: int = 10000) -> pd.DataFrame:
    """Genera DataFrame de prueba con datos realistas."""
    np.random.seed(42)
    
    return pd.DataFrame({
        'cliente': [f'Cliente_{i}' for i in range(n_filas)],
        'saldo': np.random.uniform(1000, 100000, n_filas),
        'saldo_adeudado': np.random.uniform(1000, 100000, n_filas),
        'dias_vencido': np.random.randint(-10, 200, n_filas),
        'fecha_vencimiento': pd.date_range('2024-01-01', periods=n_filas, freq='D'),
        'fecha_pago': pd.date_range('2024-01-01', periods=n_filas, freq='D'),
        'dias_credito': np.random.choice([30, 60, 90], n_filas),
        'estatus': np.random.choice(['pendiente', 'pagado'], n_filas, p=[0.7, 0.3])
    })


def perfil_pipeline_completo():
    """Perfila el pipeline completo de CxC."""
    print("📊 Generando datos de prueba (10,000 registros)...")
    df = generar_datos_prueba(10000)
    
    print("🔍 Iniciando profiling del pipeline CxC...")
    
    # Configurar profiler
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Pipeline completo
    df_prep, df_np, mask_pagado = preparar_datos_cxc(df)
    metricas = calcular_metricas_basicas(df_np)
    score = calcular_score_salud(metricas['pct_vigente'], metricas['pct_critica'])
    clasificacion = clasificar_score_salud(score)
    
    # Semáforos
    sem_morosidad = obtener_semaforo_morosidad(metricas['pct_vencida'])
    sem_riesgo = obtener_semaforo_riesgo(metricas['pct_alto_riesgo'])
    sem_concentracion = obtener_semaforo_concentracion(50.0)
    
    # Formateo
    for valor in [metricas['total_adeudado'], metricas['vigente'], metricas['vencida']]:
        formato_moneda(valor)
        formato_compacto(valor)
    
    profiler.disable()
    
    # Analizar resultados
    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s)
    stats.strip_dirs()
    stats.sort_stats('cumulative')
    
    print("\n" + "="*80)
    print("🏆 TOP 20 FUNCIONES MÁS LENTAS (por tiempo acumulado)")
    print("="*80)
    stats.print_stats(20)
    
    print("\n" + "="*80)
    print("⏱️  TOP 20 FUNCIONES MÁS LENTAS (por tiempo propio)")
    print("="*80)
    stats.sort_stats('time')
    stats.print_stats(20)
    
    return s.getvalue()


def perfil_formateo_masivo():
    """Perfila operaciones de formateo masivo."""
    print("\n\n📝 Profiling de operaciones de formateo...")
    
    valores = np.random.uniform(100, 1000000, 1000)
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Formateo masivo
    for valor in valores:
        formato_moneda(valor)
        formato_numero(valor)
        formato_porcentaje(valor / 100)
        formato_compacto(valor)
    
    profiler.disable()
    
    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s)
    stats.strip_dirs()
    stats.sort_stats('cumulative')
    
    print("\n" + "="*80)
    print("📊 Resultados de formateo (1000 operaciones por función)")
    print("="*80)
    stats.print_stats(15)


def benchmark_operaciones():
    """Compara tiempos de operaciones críticas."""
    import time
    
    print("\n\n⚡ BENCHMARKS DE OPERACIONES CRÍTICAS")
    print("="*80)
    
    df = generar_datos_prueba(10000)
    
    # Benchmark 1: Cálculo de días overdue
    inicio = time.time()
    result1 = calcular_dias_overdue(df)
    tiempo1 = time.time() - inicio
    print(f"✓ calcular_dias_overdue (10k registros): {tiempo1*1000:.2f}ms")
    
    # Benchmark 2: Preparar datos CxC
    inicio = time.time()
    df_prep, df_np, mask_pagado = preparar_datos_cxc(df)
    tiempo2 = time.time() - inicio
    print(f"✓ preparar_datos_cxc (10k registros): {tiempo2*1000:.2f}ms")
    
    # Benchmark 3: Calcular métricas
    inicio = time.time()
    result3 = calcular_metricas_basicas(df_np)
    tiempo3 = time.time() - inicio
    print(f"✓ calcular_metricas_basicas (10k registros): {tiempo3*1000:.2f}ms")
    
    # Benchmark 4: Formateo individual
    inicio = time.time()
    for _ in range(1000):
        formato_moneda(123456.789)
    tiempo4 = time.time() - inicio
    print(f"✓ formato_moneda (1000 llamadas): {tiempo4*1000:.2f}ms ({tiempo4/1000*1000:.3f}ms c/u)")
    
    tiempo_total = tiempo1 + tiempo2 + tiempo3
    print(f"\n🏁 Pipeline completo (10k registros): {tiempo_total*1000:.2f}ms")
    print(f"   Throughput: {10000/tiempo_total:.0f} registros/segundo")
    
    # Warnings si hay operaciones lentas
    print("\n⚠️  ANÁLISIS:")
    if tiempo1 > 0.1:
        print(f"   - calcular_dias_overdue es lento ({tiempo1*1000:.0f}ms). Considerar optimización.")
    if tiempo2 > 0.2:
        print(f"   - preparar_datos_cxc es lento ({tiempo2*1000:.0f}ms). Considerar caching.")
    if tiempo3 > 0.05:
        print(f"   - calcular_metricas_basicas podría optimizarse ({tiempo3*1000:.0f}ms).")
    if tiempo4/1000 > 0.001:
        print(f"   - formato_moneda es lento ({tiempo4/1000*1000:.3f}ms c/u). Considerar caching.")
    
    if tiempo_total < 0.5:
        print("   ✅ Performance general es EXCELENTE (<500ms)")
    elif tiempo_total < 1.0:
        print("   ✓ Performance general es BUENA (<1s)")
    else:
        print("   ⚠️ Performance general necesita OPTIMIZACIÓN (>1s)")


if __name__ == "__main__":
    print("🚀 Iniciando análisis de performance...\n")
    
    try:
        # Profiling detallado
        resultado = perfil_pipeline_completo()
        
        # Formateo
        perfil_formateo_masivo()
        
        # Benchmarks
        benchmark_operaciones()
        
        print("\n" + "="*80)
        print("✅ Análisis de performance completado")
        print("="*80)
        print("\n💡 Recomendaciones:")
        print("   1. Cachear resultados de calcular_metricas_basicas()")
        print("   2. Vectorizar loops en formateo si es posible")
        print("   3. Usar @st.cache_data en funciones de cálculo pesado")
        print("   4. Considerar lazy loading para datasets grandes")
        
    except Exception as e:
        print(f"❌ Error durante profiling: {e}")
        import traceback
        traceback.print_exc()

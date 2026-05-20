"""
Funciones helper para cálculos de Cuentas por Cobrar (CxC).
Centraliza la lógica de negocio para evitar duplicación.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Optional, Dict
from .logger import configurar_logger
from .constantes import (
    COLUMNAS_FECHA_PAGO,
    COLUMNAS_DIAS_CREDITO,
    COLUMNAS_ESTATUS,
    UmbralesCxC,
    ScoreSalud,
    BINS_ANTIGUEDAD,
    LABELS_ANTIGUEDAD,
    BINS_ANTIGUEDAD_AGENTES,
    LABELS_ANTIGUEDAD_AGENTES
)


logger = configurar_logger("cxc_helper", nivel="INFO")


def detectar_columna(df: pd.DataFrame, lista_candidatos: List[str]) -> Optional[str]:
    """
    Detecta la primera columna existente de una lista de candidatos.
    
    Args:
        df: DataFrame donde buscar
        lista_candidatos: Lista de nombres de columnas posibles
        
    Returns:
        Nombre de la primera columna encontrada, o None
        
    Example:
        col = detectar_columna(df, ['estatus', 'status', 'pagado'])
    """
    for col in lista_candidatos:
        if col in df.columns:
            return col
    return None


def _parsear_fechas(series: pd.Series) -> pd.Series:
    """Parsea fechas ISO y formatos locales sin sesgar todo a dayfirst."""
    parsed = pd.to_datetime(series, errors='coerce')
    faltantes = parsed.isna() & series.notna()
    if faltantes.any():
        parsed.loc[faltantes] = pd.to_datetime(series.loc[faltantes], errors='coerce', dayfirst=True)
    return parsed


def _normalizar_fecha_corte(fecha_corte=None) -> pd.Timestamp:
    """Convierte la fecha de corte a Timestamp normalizado, o usa hoy."""
    if fecha_corte is None:
        return pd.Timestamp.today().normalize()
    return pd.Timestamp(fecha_corte).normalize()


def _detectar_columna_fecha_aging(df: pd.DataFrame, config: Optional[Dict] = None) -> Optional[str]:
    """Detecta la columna de fecha preferida para aging."""
    config = config or {}
    columna_config = config.get("columna_fecha") or config.get("fecha_columna")
    if columna_config and columna_config in df.columns:
        return columna_config

    candidatos = config.get("columnas_fecha") or [
        "fecha_vencimiento",
        "vencimiento",
        "fecha_venc",
        "vencimient",
        "fecha",
        "fecha_emision",
        "fecha_factura",
    ]

    for col in candidatos:
        if col in df.columns:
            return col
    return None


def excluir_pagados(df: pd.DataFrame, col_estatus: Optional[str] = None) -> pd.Series:
    """
    Crea una máscara booleana para excluir registros pagados.
    
    Args:
        df: DataFrame con datos de CxC
        col_estatus: Nombre de la columna de estatus (opcional, se detecta automáticamente)
        
    Returns:
        pd.Series con máscara booleana (True = pagado, False = no pagado)
    """
    if col_estatus is None:
        col_estatus = detectar_columna(df, COLUMNAS_ESTATUS)
    
    if col_estatus:
        col_valores = df[col_estatus].astype(str).str.strip().str.lower()

        # Caso especial: columna LLAMADA 'pagado' usa valores si/no, 1/0, true/false, x
        if str(col_estatus).lower() == 'pagado':
            return col_valores.isin(['si', 'sí', '1', 'true', 'yes', 'x', 'pagado', 'pagada'])

        # Patrón regex ampliado: cubre masculino/femenino y variantes de estatus liquidado
        # pagad   → pagado / pagada
        # liquid  → liquidado / liquidada
        # cancel  → cancelado / cancelada
        # cerrad  → cerrado / cerrada
        # finiquit→ finiquitado / finiquitada
        # cobrad  → cobrado / cobrada
        # saldad  → saldado / saldada
        # paid    → paid (inglés)
        patron = r'pagad|liquid|cancel|cerrad|finiquit|paid|cobrad|saldad'
        return col_valores.str.contains(patron, na=False, regex=True)

    return pd.Series(False, index=df.index)


def calcular_dias_overdue(df: pd.DataFrame, fecha_corte=None, config: Optional[Dict] = None) -> pd.Series:
    """
    Calcula días de atraso usando lógica unificada con fallback en cascada.
    
    LÓGICA MATEMÁTICA:
    - Si dias_credito = 30, el cliente tiene del día 1 al día 30 para pagar (30 días completos)
    - Día 31 = primer día vencido (1 día vencido)
    - Día 32 = 2 días vencido, etc.
    
    Prioridad de cálculo:
    1. dias_restante/dias_restantes (invertido, negativo = vencido)
    2. fecha_vencimiento (vs hoy) + ajuste
    3. dias_vencido (si existe y tiene valores congruentes)
    4. fecha_pago + dias_de_credito (calculado) + ajuste
    5. fecha + 30 días crédito estándar (estimado) + ajuste
    
    Args:
        df: DataFrame con datos de CxC
        
    Returns:
        pd.Series con días de atraso (positivo = vencido, negativo/cero = vigente)
        
    Example:
        df['dias_overdue'] = calcular_dias_overdue(df)
    """
    
    hoy = _normalizar_fecha_corte(fecha_corte)
    config = config or {}
    resultado = pd.Series(np.nan, index=df.index, dtype='float64')

    # Método 1: dias_restante/dias_restantes
    # Positivo = vigente, negativo = vencido, entonces invertir.
    for col_rest in ['dias_restante', 'dias_restantes']:
        if col_rest in df.columns:
            dias_restantes = pd.to_numeric(df[col_rest], errors='coerce')
            calculado = -dias_restantes
            resultado = resultado.where(~resultado.isna(), calculado)
            break

    # Método 2: dias_vencido directo
    # Se llena solo donde aún no haya valor y el resto continúa al fallback.
    if 'dias_vencido' in df.columns:
        dias = pd.to_numeric(df['dias_vencido'], errors='coerce')
        resultado = resultado.where(~resultado.isna(), dias)

    # Método 3: calcular desde fecha de vencimiento
    # fecha_vencimiento se interpreta como el último día válido para pagar.
    for col_venc in ['vencimiento', 'fecha_vencimiento', 'vencimient']:
        if col_venc in df.columns:
            fecha_venc = _parsear_fechas(df[col_venc])
            calculado = (hoy - fecha_venc).dt.days
            resultado = resultado.where(~resultado.isna(), pd.to_numeric(calculado, errors='coerce'))
            break

    # Método 4: fecha_pago + dias_de_credito
    # NOTA: dias_credito representa días COMPLETOS de gracia
    # Si dias_credito = 30, el cliente puede pagar del día 1 al 30, el día 31 ya está vencido
    col_fecha_pago = detectar_columna(df, COLUMNAS_FECHA_PAGO)
    col_credito = detectar_columna(df, COLUMNAS_DIAS_CREDITO)
    
    if col_fecha_pago:
        fecha_base = _parsear_fechas(df[col_fecha_pago])
        
        if col_credito:
            dias_credito = pd.to_numeric(df[col_credito], errors='coerce').fillna(0).astype(int)
        else:
            dias_credito = pd.Series(0, index=df.index)
        
        # fecha_base + dias_credito = primer día donde ya está vencido
        fecha_venc = fecha_base + pd.to_timedelta(dias_credito, unit='D')
        # Si hoy = fecha_base + 30 días: 1 día vencido (el día 31 desde factura)
        # Si hoy = fecha_base + 29 días: 0 días vencido (el día 30, aún vigente)
        dias = (hoy - fecha_venc).dt.days + 1
        resultado = resultado.where(~resultado.isna(), pd.to_numeric(dias, errors='coerce'))
    
    # Método 5: Si solo existe 'fecha' (fecha de factura), asumir 30 días de crédito estándar
    # NOTA: 30 días completos de gracia, el día 31 es el primer día vencido
    col_fecha = _detectar_columna_fecha_aging(df, config)
    if col_fecha:
        fecha_factura = _parsear_fechas(df[col_fecha])
        # fecha + 30 días = día 31 = primer día vencido
        fecha_venc_estimada = fecha_factura + pd.Timedelta(days=30)
        dias = (hoy - fecha_venc_estimada).dt.days + 1
        resultado = resultado.where(~resultado.isna(), pd.to_numeric(dias, errors='coerce'))
    
    # Fallback final: todos vigentes (días = 0)
    return pd.to_numeric(resultado, errors='coerce').fillna(0)


def calcular_score_salud_cxc(aging_result: Dict) -> float:
    """Calcula el score de salud a partir de un resultado de aging estandarizado."""
    return calcular_score_salud(
        aging_result.get('pct_vigente', 0),
        aging_result.get('pct_critica', 0),
        aging_result.get('pct_vencida_0_30', 0),
        aging_result.get('pct_vencida_31_60', 0),
        aging_result.get('pct_vencida_61_90', 0),
        aging_result.get('pct_alto_riesgo', 0),
    )


def calcular_cxc_aging(df: pd.DataFrame, fecha_corte=None, config: Optional[Dict] = None) -> Dict:
    """Calcula aging CxC unificado y devuelve métricas, datos y diagnóstico."""
    config = config or {}
    fecha_corte_usada = _normalizar_fecha_corte(fecha_corte)

    if df is None or df.empty:
        df_vacio = df.copy() if df is not None else pd.DataFrame()
        if 'saldo_adeudado' not in df_vacio.columns:
            df_vacio['saldo_adeudado'] = pd.Series(dtype='float64')
        if 'dias_overdue' not in df_vacio.columns:
            df_vacio['dias_overdue'] = pd.Series(dtype='float64')
        if 'dias_vencido' not in df_vacio.columns:
            df_vacio['dias_vencido'] = pd.Series(dtype='float64')
        mask_pagado = pd.Series(False, index=df_vacio.index, dtype=bool)
        return {
            'df_prep': df_vacio,
            'df_np': df_vacio.copy(),
            'mask_pagado': mask_pagado,
            'columna_fecha_usada': None,
            'columnas_monto_detectadas': [],
            'fecha_corte_usada': fecha_corte_usada,
            'fecha_min': None,
            'fecha_max': None,
            'filas_consideradas': 0,
            'monto_validado_total': 0.0,
            'total_adeudado': 0.0,
            'vigente_monto': 0.0,
            'vigente_pct': 0.0,
            'vencido_monto': 0.0,
            'vencido_pct': 0.0,
            'bucket_0_30': 0.0,
            'bucket_31_60': 0.0,
            'bucket_61_90': 0.0,
            'bucket_mas_90': 0.0,
            'critica_mas_30': 0.0,
            'pct_critica': 0.0,
            'pct_alto_riesgo': 0.0,
            'pct_vencida_0_30': 0.0,
            'pct_vencida_31_60': 0.0,
            'pct_vencida_61_90': 0.0,
            'score_salud': 0.0,
            'clasificacion_salud': 'Crítico',
            'diferencia_total_buckets': 0.0,
        }

    df_prep = df.copy()

    columnas_monto_detectadas = []
    if 'saldo_adeudado' not in df_prep.columns:
        for candidato in ['saldo', 'saldo_adeudo', 'adeudo', 'importe', 'monto', 'total', 'saldo_usd']:
            if candidato in df_prep.columns:
                columnas_monto_detectadas.append(candidato)
                df_prep = df_prep.rename(columns={candidato: 'saldo_adeudado'})
                break
    else:
        columnas_monto_detectadas.append('saldo_adeudado')

    if 'saldo_adeudado' in df_prep.columns:
        saldo_txt = df_prep['saldo_adeudado'].astype(str)
        saldo_txt = saldo_txt.str.replace(',', '', regex=False).str.replace('$', '', regex=False)
        df_prep['saldo_adeudado'] = pd.to_numeric(saldo_txt, errors='coerce').fillna(0)
    else:
        df_prep['saldo_adeudado'] = 0.0

    col_estatus = config.get('col_estatus')
    if col_estatus is None:
        col_estatus = detectar_columna(df_prep, COLUMNAS_ESTATUS)
    mask_pagado = excluir_pagados(df_prep, col_estatus)

    col_fecha = _detectar_columna_fecha_aging(df_prep, config)
    if col_fecha:
        fecha_base = _parsear_fechas(df_prep[col_fecha])
        if col_fecha in ('fecha_vencimiento', 'vencimiento', 'fecha_venc', 'vencimient'):
            dias_overdue = (fecha_corte_usada - fecha_base).dt.days
        else:
            dias_overdue = calcular_dias_overdue(df_prep, fecha_corte=fecha_corte_usada, config=config)
    else:
        dias_overdue = calcular_dias_overdue(df_prep, fecha_corte=fecha_corte_usada, config=config)

    df_prep['dias_overdue'] = pd.to_numeric(dias_overdue, errors='coerce').fillna(0)
    if 'dias_vencido' not in df_prep.columns:
        df_prep['dias_vencido'] = df_prep['dias_overdue']

    df_np = df_prep.loc[~mask_pagado].copy()
    monto_validado_total = float(df_prep['saldo_adeudado'].sum())
    total_adeudado = float(df_np['saldo_adeudado'].sum())

    vigente_monto = float(df_np.loc[df_np['dias_overdue'] <= 0, 'saldo_adeudado'].sum())
    bucket_0_30 = float(df_np.loc[(df_np['dias_overdue'] > 0) & (df_np['dias_overdue'] <= 30), 'saldo_adeudado'].sum())
    bucket_31_60 = float(df_np.loc[(df_np['dias_overdue'] > 30) & (df_np['dias_overdue'] <= 60), 'saldo_adeudado'].sum())
    bucket_61_90 = float(df_np.loc[(df_np['dias_overdue'] > 60) & (df_np['dias_overdue'] <= 90), 'saldo_adeudado'].sum())
    bucket_mas_90 = float(df_np.loc[df_np['dias_overdue'] > 90, 'saldo_adeudado'].sum())

    vencido_monto = float(total_adeudado - vigente_monto)
    critica_mas_30 = float(bucket_31_60 + bucket_61_90 + bucket_mas_90)

    vigente_pct = (vigente_monto / total_adeudado * 100) if total_adeudado > 0 else 0.0
    vencido_pct = (vencido_monto / total_adeudado * 100) if total_adeudado > 0 else 0.0
    pct_vencida_0_30 = (bucket_0_30 / total_adeudado * 100) if total_adeudado > 0 else 0.0
    pct_vencida_31_60 = (bucket_31_60 / total_adeudado * 100) if total_adeudado > 0 else 0.0
    pct_vencida_61_90 = (bucket_61_90 / total_adeudado * 100) if total_adeudado > 0 else 0.0
    pct_alto_riesgo = (bucket_mas_90 / total_adeudado * 100) if total_adeudado > 0 else 0.0
    pct_critica = (critica_mas_30 / total_adeudado * 100) if total_adeudado > 0 else 0.0

    score_salud = calcular_score_salud_cxc({
        'pct_vigente': vigente_pct,
        'pct_critica': pct_critica,
        'pct_vencida_0_30': pct_vencida_0_30,
        'pct_vencida_31_60': pct_vencida_31_60,
        'pct_vencida_61_90': pct_vencida_61_90,
        'pct_alto_riesgo': pct_alto_riesgo,
    })
    clasificacion_salud, _ = clasificar_score_salud(score_salud)

    fecha_min = None
    fecha_max = None
    if col_fecha and col_fecha in df_prep.columns:
        fechas = _parsear_fechas(df_prep[col_fecha])
        if not fechas.dropna().empty:
            fecha_min = fechas.min()
            fecha_max = fechas.max()

    suma_buckets = vigente_monto + bucket_0_30 + bucket_31_60 + bucket_61_90 + bucket_mas_90
    diferencia_total_buckets = float(total_adeudado - suma_buckets)

    resultado = {
        'df_prep': df_prep,
        'df_np': df_np,
        'mask_pagado': mask_pagado,
        'columna_fecha_usada': col_fecha,
        'columnas_monto_detectadas': columnas_monto_detectadas,
        'fecha_corte_usada': fecha_corte_usada,
        'fecha_min': fecha_min,
        'fecha_max': fecha_max,
        'filas_consideradas': int(len(df_np)),
        'monto_validado_total': monto_validado_total,
        'total_adeudado': total_adeudado,
        'vigente_monto': vigente_monto,
        'vigente_pct': vigente_pct,
        'vencido_monto': vencido_monto,
        'vencido_pct': vencido_pct,
        'bucket_0_30': bucket_0_30,
        'bucket_31_60': bucket_31_60,
        'bucket_61_90': bucket_61_90,
        'bucket_mas_90': bucket_mas_90,
        'critica_mas_30': critica_mas_30,
        'pct_vencida_0_30': pct_vencida_0_30,
        'pct_vencida_31_60': pct_vencida_31_60,
        'pct_vencida_61_90': pct_vencida_61_90,
        'pct_alto_riesgo': pct_alto_riesgo,
        'pct_critica': pct_critica,
        'score_salud': score_salud,
        'clasificacion_salud': clasificacion_salud,
        'diferencia_total_buckets': diferencia_total_buckets,
        'vigente': vigente_monto,
        'vencida': vencido_monto,
        'vencida_0_30': bucket_0_30,
        'vencida_31_60': bucket_31_60,
        'vencida_61_90': bucket_61_90,
        'alto_riesgo': bucket_mas_90,
        'critica': critica_mas_30,
        'pct_vigente': vigente_pct,
        'pct_vencida': vencido_pct,
    }

    logger.info(
        "CxC aging: filas=%s total=%.2f fecha_corte=%s fecha_col=%s saldo_cols=%s buckets=%.2f/%.2f/%.2f/%.2f/%.2f diff=%.2f",
        resultado['filas_consideradas'],
        resultado['total_adeudado'],
        fecha_corte_usada.date(),
        col_fecha,
        columnas_monto_detectadas,
        vigente_monto,
        bucket_0_30,
        bucket_31_60,
        bucket_61_90,
        bucket_mas_90,
        diferencia_total_buckets,
    )

    return resultado


def preparar_metricas_cxc(df: pd.DataFrame, fecha_corte=None, config: Optional[Dict] = None) -> Dict:
    """Alias semántico para la preparación estándar de métricas CxC."""
    return calcular_cxc_aging(df, fecha_corte=fecha_corte, config=config)



def preparar_datos_cxc(df: pd.DataFrame, fecha_corte=None, config: Optional[Dict] = None) -> tuple:
    """
    Prepara datos de CxC con lógica unificada del Reporte Ejecutivo.
    
    - Excluye registros pagados
    - Calcula dias_overdue
    - Crea DataFrame df_np (no pagados)
    
    Args:
        df: DataFrame con datos brutos de CxC
        
    Returns:
        tuple: (df_original_con_dias, df_no_pagados, mask_pagado)
    """
    resultado = calcular_cxc_aging(df, fecha_corte=fecha_corte, config=config)
    return resultado['df_prep'], resultado['df_np'], resultado['mask_pagado']


def calcular_score_salud(pct_vigente: float, pct_critica: float, pct_vencida_0_30: float = 0, 
                         pct_vencida_31_60: float = 0, pct_vencida_61_90: float = 0, 
                         pct_alto_riesgo: float = 0) -> float:
    """
    Calcula el score de salud financiera con consideración de todos los rangos.
    
    Fórmula mejorada:
    - Vigente (≤0 días): +100 puntos
    - Vencida 0-30 días: +70 puntos (bajo riesgo)
    - Vencida 31-60 días: +40 puntos (riesgo medio)
    - Vencida 61-90 días: +20 puntos (riesgo alto)
    - >90 días: +0 puntos (riesgo crítico)
    
    Score = Σ(porcentaje × puntos) / 100
    
    Args:
        pct_vigente: Porcentaje de cartera vigente (0-100)
        pct_critica: Porcentaje de cartera crítica >30 días (0-100) [deprecado, por compatibilidad]
        pct_vencida_0_30: Porcentaje vencida 0-30 días
        pct_vencida_31_60: Porcentaje vencida 31-60 días
        pct_vencida_61_90: Porcentaje vencida 61-90 días
        pct_alto_riesgo: Porcentaje >90 días
        
    Returns:
        float: Score de 0 a 100
        
    Examples:
        >>> # Cartera perfecta (100% vigente)
        >>> calcular_score_salud(100, 0, 0, 0, 0, 0)
        100.0
        
        >>> # 50% vigente, 50% en 0-30 días
        >>> calcular_score_salud(50, 50, 50, 0, 0, 0)
        85.0  # (50×100 + 50×70) / 100
    """
    # Si se proporcionan rangos detallados, usar la fórmula mejorada
    if pct_vencida_0_30 > 0 or pct_vencida_31_60 > 0 or pct_vencida_61_90 > 0 or pct_alto_riesgo > 0:
        score = (
            pct_vigente * 100 +           # Vigente: excelente
            pct_vencida_0_30 * 70 +       # 0-30 días: bueno
            pct_vencida_31_60 * 40 +      # 31-60 días: regular
            pct_vencida_61_90 * 20 +      # 61-90 días: malo
            pct_alto_riesgo * 0           # >90 días: crítico
        ) / 100
    else:
        # Fórmula legacy para compatibilidad
        score = pct_vigente * ScoreSalud.PESO_VIGENTE + \
                max(0, 100 - pct_critica * 2) * ScoreSalud.PESO_CRITICA
    
    return max(0, min(100, score))


def clasificar_score_salud(score: float) -> tuple:
    """
    Clasifica un score de salud en categoría y color.
    
    Args:
        score: Score numérico (0-100)
        
    Returns:
        tuple: (status_texto, color_hex)
    """
    if score >= ScoreSalud.EXCELENTE_MIN:
        return "Excelente", ScoreSalud.COLOR_EXCELENTE
    elif score >= ScoreSalud.BUENO_MIN:
        return "Bueno", ScoreSalud.COLOR_BUENO
    elif score >= ScoreSalud.REGULAR_MIN:
        return "Regular", ScoreSalud.COLOR_REGULAR
    elif score >= ScoreSalud.MALO_MIN:
        return "Malo", ScoreSalud.COLOR_MALO
    else:
        return "Crítico", ScoreSalud.COLOR_CRITICO


def clasificar_antiguedad(df: pd.DataFrame, columna_dias: str = 'dias_overdue', tipo: str = 'completo') -> pd.Series:
    """
    Clasifica deuda por antigüedad en categorías estándar.
    
    Args:
        df: DataFrame con datos de CxC
        columna_dias: Nombre de la columna con días de atraso
        tipo: 'completo' (6 categorías) o 'agentes' (5 categorías)
        
    Returns:
        pd.Series con categorías asignadas
    """
    if tipo == 'agentes':
        bins = BINS_ANTIGUEDAD_AGENTES
        labels = LABELS_ANTIGUEDAD_AGENTES
    else:
        bins = BINS_ANTIGUEDAD
        labels = LABELS_ANTIGUEDAD
    
    return pd.cut(
        df[columna_dias],
        bins=bins,
        labels=labels
    )


def calcular_metricas_basicas(df_np: pd.DataFrame, columna_saldo: str = 'saldo_adeudado') -> Dict[str, float]:
    """
    Calcula métricas básicas de CxC a partir de datos no pagados.
    
    Args:
        df_np: DataFrame sin registros pagados
        columna_saldo: Nombre de la columna de saldo
        
    Returns:
        dict con métricas: total_adeudado, vigente, vencida, vencida_0_30, 
                          critica, alto_riesgo, pct_vigente, pct_vencida, etc.
    """
    total_adeudado = df_np[columna_saldo].sum()
    vigente = df_np[df_np['dias_overdue'] <= 0][columna_saldo].sum()
    vencida = df_np[df_np['dias_overdue'] > 0][columna_saldo].sum()
    vencida_0_30 = df_np[
        (df_np['dias_overdue'] > 0) & 
        (df_np['dias_overdue'] <= UmbralesCxC.DIAS_VENCIDO_0_30)
    ][columna_saldo].sum()
    critica = df_np[
        df_np['dias_overdue'] > UmbralesCxC.DIAS_VENCIDO_0_30
    ][columna_saldo].sum()
    alto_riesgo = df_np[
        df_np['dias_overdue'] > UmbralesCxC.DIAS_ALTO_RIESGO
    ][columna_saldo].sum()
    
    # Calcular por rangos adicionales primero (vencida 31-60, 61-90)
    vencida_31_60 = df_np[
        (df_np['dias_overdue'] > 30) & 
        (df_np['dias_overdue'] <= 60)
    ][columna_saldo].sum()
    vencida_61_90 = df_np[
        (df_np['dias_overdue'] > 60) & 
        (df_np['dias_overdue'] <= 90)
    ][columna_saldo].sum()
    
    # Calcular porcentajes (TODOS antes de calcular el score)
    pct_vigente = (vigente / total_adeudado * 100) if total_adeudado > 0 else 0
    pct_vencida = (vencida / total_adeudado * 100) if total_adeudado > 0 else 0
    pct_critica = (critica / total_adeudado * 100) if total_adeudado > 0 else 0
    pct_alto_riesgo = (alto_riesgo / total_adeudado * 100) if total_adeudado > 0 else 0
    pct_vencida_0_30 = (vencida_0_30 / total_adeudado * 100) if total_adeudado > 0 else 0
    pct_vencida_31_60 = (vencida_31_60 / total_adeudado * 100) if total_adeudado > 0 else 0
    pct_vencida_61_90 = (vencida_61_90 / total_adeudado * 100) if total_adeudado > 0 else 0
    
    # AHORA sí calcular score de salud con TODOS los porcentajes disponibles
    score_salud = calcular_score_salud(
        pct_vigente, pct_critica,
        pct_vencida_0_30, pct_vencida_31_60, pct_vencida_61_90, pct_alto_riesgo
    )
    clasificacion_salud, _ = clasificar_score_salud(score_salud)
    
    return {
        'total_adeudado': total_adeudado,
        'vigente': vigente,
        'vencida': vencida,
        'vencida_0_30': vencida_0_30,
        'vencida_31_60': vencida_31_60,
        'vencida_61_90': vencida_61_90,
        'critica': critica,
        'alto_riesgo': alto_riesgo,
        'pct_vigente': pct_vigente,
        'pct_vencida': pct_vencida,
        'pct_vencida_0_30': pct_vencida_0_30,
        'pct_vencida_31_60': pct_vencida_31_60,
        'pct_vencida_61_90': pct_vencida_61_90,
        'pct_critica': pct_critica,
        'pct_alto_riesgo': pct_alto_riesgo,
        'score_salud': score_salud,
        'clasificacion_salud': clasificacion_salud
    }


def obtener_semaforo_morosidad(pct_morosidad: float) -> str:
    """
    Retorna emoji de semáforo según nivel de morosidad.
    
    Args:
        pct_morosidad: Porcentaje de morosidad
        
    Returns:
        str: Emoji de semáforo (🟢, 🟡, 🟠, 🔴)
    """
    if pct_morosidad < UmbralesCxC.MOROSIDAD_BAJA:
        return "🟢"
    elif pct_morosidad < UmbralesCxC.MOROSIDAD_MEDIA:
        return "🟡"
    elif pct_morosidad < UmbralesCxC.MOROSIDAD_ALTA:
        return "🟠"
    else:
        return "🔴"


def obtener_semaforo_riesgo(pct_riesgo: float) -> str:
    """
    Retorna emoji de semáforo según nivel de riesgo alto.
    
    Args:
        pct_riesgo: Porcentaje de deuda en riesgo alto (>90 días)
        
    Returns:
        str: Emoji de semáforo (🟢, 🟡, 🟠, 🔴)
    """
    if pct_riesgo < UmbralesCxC.RIESGO_BAJO:
        return "🟢"
    elif pct_riesgo < UmbralesCxC.RIESGO_MEDIO:
        return "🟡"
    elif pct_riesgo < UmbralesCxC.RIESGO_ALTO:
        return "🟠"
    else:
        return "🔴"


def obtener_semaforo_concentracion(pct_concentracion: float) -> str:
    """
    Retorna emoji de semáforo según nivel de concentración de cartera.
    
    Args:
        pct_concentracion: Porcentaje de concentración
        
    Returns:
        str: Emoji de semáforo (🟢, 🟡, 🔴)
    """
    if pct_concentracion <= UmbralesCxC.CONCENTRACION_BAJA:
        return "🟢"
    elif pct_concentracion <= UmbralesCxC.CONCENTRACION_MEDIA:
        return "🟡"
    else:
        return "🔴"

"""
Funciones helper para cálculos de Cuentas por Cobrar (CxC).
Centraliza la lógica de negocio para evitar duplicación.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Optional, Dict
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
        estatus_norm = df[col_estatus].astype(str).str.strip().str.lower()
        return estatus_norm.str.contains('pagado', na=False)
    
    return pd.Series(False, index=df.index)


def calcular_dias_overdue(df: pd.DataFrame) -> pd.Series:
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
    
    # Método 1: dias_restante/dias_restantes (PRIORITARIO - MÁS CONFIABLE)
    # Positivo = vigente, negativo = vencido, entonces invertir
    for col_rest in ['dias_restante', 'dias_restantes']:
        if col_rest in df.columns:
            dias_restantes = pd.to_numeric(df[col_rest], errors='coerce').fillna(0)
            # Invertir: si faltan 5 días = -5 overdue (vigente), si pasaron 10 días = +10 overdue (vencido)
            return -dias_restantes
    
    # Método 2: Calcular desde fecha de vencimiento (SEGUNDO MÁS CONFIABLE)
    # NOTA: fecha_vencimiento se interpreta como el ÚLTIMO DÍA VÁLIDO para pagar
    for col_venc in ['vencimiento', 'fecha_vencimiento', 'vencimient']:
        if col_venc in df.columns:
            fecha_venc = pd.to_datetime(df[col_venc], errors='coerce', dayfirst=True)
            # Si hoy = fecha_venc: 0 días vencido (aún válido)
            # Si hoy = fecha_venc + 1: 1 día vencido
            dias = (pd.Timestamp.today().normalize() - fecha_venc).dt.days
            return pd.to_numeric(dias, errors='coerce').fillna(0)
    
    # Método 3: dias_vencido directo (MENOS PRIORITARIO - puede tener convenciones diferentes)
    # IMPORTANTE: Solo usar si no hay dias_restante, porque dias_vencido puede significar cosas diferentes
    if 'dias_vencido' in df.columns:
        dias = pd.to_numeric(df['dias_vencido'], errors='coerce').fillna(0)
        # Solo usar si tiene al menos algún valor no-cero (indica datos reales)
        if (dias != 0).any():
            # Verificar si tiene valores negativos (indica convención correcta: positivo=vencido)
            if (dias < 0).any():
                return dias
            # Si NO tiene valores negativos, probablemente está mal nombrada o usa otra convención
            # Asumiriamos que valores positivos grandes (>100) son vencidos, valores cercanos a 0 son vigentes
            # PERO esto es ambiguo, así que mejor pasar al siguiente método
            pass
    
    # Método 4: fecha_pago + dias_de_credito
    # NOTA: dias_credito representa días COMPLETOS de gracia
    # Si dias_credito = 30, el cliente puede pagar del día 1 al 30, el día 31 ya está vencido
    col_fecha_pago = detectar_columna(df, COLUMNAS_FECHA_PAGO)
    col_credito = detectar_columna(df, COLUMNAS_DIAS_CREDITO)
    
    if col_fecha_pago:
        fecha_base = pd.to_datetime(df[col_fecha_pago], errors='coerce', dayfirst=True)
        
        if col_credito:
            dias_credito = pd.to_numeric(df[col_credito], errors='coerce').fillna(0).astype(int)
        else:
            dias_credito = pd.Series(0, index=df.index)
        
        # fecha_base + dias_credito = primer día donde ya está vencido
        fecha_venc = fecha_base + pd.to_timedelta(dias_credito, unit='D')
        # Si hoy = fecha_base + 30 días: 1 día vencido (el día 31 desde factura)
        # Si hoy = fecha_base + 29 días: 0 días vencido (el día 30, aún vigente)
        dias = (pd.Timestamp.today().normalize() - fecha_venc).dt.days + 1
        return pd.to_numeric(dias, errors='coerce').fillna(0)
    
    # Método 5: Si solo existe 'fecha' (fecha de factura), asumir 30 días de crédito estándar
    # NOTA: 30 días completos de gracia, el día 31 es el primer día vencido
    if 'fecha' in df.columns:
        fecha_factura = pd.to_datetime(df['fecha'], errors='coerce', dayfirst=True)
        # fecha + 30 días = día 31 = primer día vencido
        fecha_venc_estimada = fecha_factura + pd.Timedelta(days=30)
        dias = (pd.Timestamp.today().normalize() - fecha_venc_estimada).dt.days + 1
        return pd.to_numeric(dias, errors='coerce').fillna(0)
    
    # Fallback final: todos vigentes (días = 0)
    return pd.Series(0, index=df.index)



def preparar_datos_cxc(df: pd.DataFrame) -> tuple:
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
    df_prep = df.copy()
    
    # Calcular dias_overdue
    df_prep['dias_overdue'] = calcular_dias_overdue(df_prep)
    
    # Compatibilidad: si no existe dias_vencido, crearlo
    if 'dias_vencido' not in df_prep.columns:
        df_prep['dias_vencido'] = df_prep['dias_overdue']
    
    # Crear máscara de pagados
    mask_pagado = excluir_pagados(df_prep)
    
    # DataFrame sin pagados
    df_np = df_prep[~mask_pagado].copy()
    
    return df_prep, df_np, mask_pagado


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
    from utils.logger import configurar_logger
    logger = configurar_logger("cxc_helper", nivel="DEBUG")
    
    total_adeudado = df_np[columna_saldo].sum()
    
    # Debug logging para diagnosticar problema de vigente
    logger.info(f"📊 Diagnóstico CxC - Total registros: {len(df_np)}")
    logger.info(f"📊 Diagnóstico CxC - Total adeudado: ${total_adeudado:,.2f}")
    if 'dias_overdue' in df_np.columns:
        logger.info(f"📊 Diagnóstico CxC - Rango dias_overdue: [{df_np['dias_overdue'].min():.1f}, {df_np['dias_overdue'].max():.1f}]")
        logger.info(f"📊 Diagnóstico CxC - Registros con dias_overdue <=0: {(df_np['dias_overdue'] <= 0).sum()}")
        logger.info(f"📊 Diagnóstico CxC - Registros con dias_overdue >0: {(df_np['dias_overdue'] > 0).sum()}")
    
    vigente = df_np[df_np['dias_overdue'] <= 0][columna_saldo].sum()
    vencida = df_np[df_np['dias_overdue'] > 0][columna_saldo].sum()
    
    logger.info(f"📊 Diagnóstico CxC - Monto vigente: ${vigente:,.2f}")
    logger.info(f"📊 Diagnóstico CxC - Monto vencida: ${vencida:,.2f}")
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

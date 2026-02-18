"""
Módulo para calcular métricas avanzadas de CxC agrupadas por cliente.

Funciones:
- calcular_metricas_por_cliente(): Calcula días vencidos por cliente usando 3 métodos
"""

import pandas as pd
from typing import Dict
from utils.logger import configurar_logger

logger = configurar_logger("cxc_metricas_cliente", nivel="INFO")


def calcular_metricas_por_cliente(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula métricas de antigüedad por cliente usando 3 métodos:
    1. Promedio ponderado por monto
    2. Factura más antigua (peor caso)
    3. Factura más reciente (última actividad)
    
    Args:
        df: DataFrame con columnas 'deudor', 'saldo_adeudado', 'dias_overdue'
        
    Returns:
        DataFrame con columnas:
        - deudor: Nombre del cliente
        - saldo_total: Suma de saldos del cliente
        - num_facturas: Cantidad de facturas del cliente
        - dias_promedio_ponderado: Promedio de días vencidos ponderado por monto
        - dias_factura_mas_antigua: Días vencidos de la factura más vieja
        - dias_factura_mas_reciente: Días vencidos de la factura más nueva
        - rango_antiguedad: Clasificación (Vigente, 0-30, 31-60, 61-90, >90)
    """
    if df.empty:
        return pd.DataFrame()
    
    # Validar columnas requeridas
    required_cols = ['deudor', 'saldo_adeudado', 'dias_overdue']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        logger.warning(f"Columnas faltantes para métricas por cliente: {missing}")
        return pd.DataFrame()
    
    # Calcular métricas por cliente
    metricas = []
    
    for cliente, grupo in df.groupby('deudor'):
        saldo_total = grupo['saldo_adeudado'].sum()
        num_facturas = len(grupo)
        
        # 1. Promedio ponderado por monto
        dias_x_monto = (grupo['dias_overdue'] * grupo['saldo_adeudado']).sum()
        dias_promedio_ponderado = dias_x_monto / saldo_total if saldo_total > 0 else 0
        
        # 2. Factura más antigua (max días)
        dias_factura_mas_antigua = grupo['dias_overdue'].max()
        
        # 3. Factura más reciente (min días - última actividad)
        dias_factura_mas_reciente = grupo['dias_overdue'].min()
        
        # Clasificar por el promedio ponderado (métrica más realista)
        if dias_promedio_ponderado <= 0:
            rango = "Vigente"
        elif dias_promedio_ponderado <= 30:
            rango = "0-30 días"
        elif dias_promedio_ponderado <= 60:
            rango = "31-60 días"
        elif dias_promedio_ponderado <= 90:
            rango = "61-90 días"
        else:
            rango = ">90 días"
        
        metricas.append({
            'deudor': cliente,
            'saldo_total': saldo_total,
            'num_facturas': num_facturas,
            'dias_promedio_ponderado': round(dias_promedio_ponderado, 1),
            'dias_factura_mas_antigua': int(dias_factura_mas_antigua),
            'dias_factura_mas_reciente': int(dias_factura_mas_reciente),
            'rango_antiguedad': rango
        })
    
    df_metricas = pd.DataFrame(metricas)
    
    # Ordenar por saldo total descendente
    df_metricas = df_metricas.sort_values('saldo_total', ascending=False)
    
    return df_metricas


def obtener_top_n_clientes(df_metricas: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """
    Retorna los top N clientes por saldo total.
    
    Args:
        df_metricas: DataFrame retornado por calcular_metricas_por_cliente()
        n: Número de clientes a retornar
        
    Returns:
        DataFrame con los top N clientes
    """
    return df_metricas.head(n)


def obtener_clientes_por_rango(df_metricas: pd.DataFrame, rango: str) -> pd.DataFrame:
    """
    Filtra clientes por rango de antigüedad.
    
    Args:
        df_metricas: DataFrame retornado por calcular_metricas_por_cliente()
        rango: Uno de: "Vigente", "0-30 días", "31-60 días", "61-90 días", ">90 días"
        
    Returns:
        DataFrame filtrado
    """
    return df_metricas[df_metricas['rango_antiguedad'] == rango]

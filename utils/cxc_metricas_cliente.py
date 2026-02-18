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


def obtener_facturas_cliente(df: pd.DataFrame, nombre_cliente: str) -> pd.DataFrame:
    """
    Retorna el detalle de todas las facturas de un cliente específico.

    Args:
        df: DataFrame completo de CxC (df_np) con columnas normalizadas
        nombre_cliente: Nombre exacto del cliente (columna 'deudor')

    Returns:
        DataFrame con una fila por factura, columnas disponibles:
        - factura: número o ID de factura (si existe)
        - fecha: fecha de emisión (si existe)
        - saldo_adeudado: monto pendiente
        - dias_overdue: días vencidos
        - rango: clasificación individual de la factura
        - estatus: estado de pago (si existe)
    Ordenado por dias_overdue descendente (más vencidas primero).
    """
    if df.empty or 'deudor' not in df.columns:
        return pd.DataFrame()

    # Filtrar filas del cliente
    mask = df['deudor'].str.strip().str.lower() == nombre_cliente.strip().lower()
    df_cliente = df[mask].copy()

    if df_cliente.empty:
        return pd.DataFrame()

    # Columnas a incluir según disponibilidad
    col_map = {
        'factura':          ['factura', 'no_factura', 'num_factura', 'numero_factura',
                             'folio', 'documento', 'referencia', 'no_doc'],
        'fecha':            ['fecha', 'fecha_factura', 'fecha_emision', 'fecha_doc',
                             'fecha_vencimiento'],
        'linea_de_negocio': ['linea_de_negocio', 'linea', 'producto', 'descripcion'],
        'estatus':          ['estatus', 'status', 'estado'],
    }

    cols_output = []
    rename_map = {}

    for nombre_estandar, candidatos in col_map.items():
        for c in candidatos:
            if c in df_cliente.columns:
                cols_output.append(c)
                rename_map[c] = nombre_estandar
                break  # solo el primero que encuentre

    # Columnas obligatorias
    for col in ['saldo_adeudado', 'dias_overdue']:
        if col in df_cliente.columns and col not in cols_output:
            cols_output.append(col)

    df_detalle = df_cliente[cols_output].rename(columns=rename_map).copy()

    # Clasificar rango individual de cada factura
    def _rango(dias):
        if dias <= 0:
            return 'Vigente'
        elif dias <= 30:
            return '0-30 días'
        elif dias <= 60:
            return '31-60 días'
        elif dias <= 90:
            return '61-90 días'
        else:
            return '>90 días'

    if 'dias_overdue' in df_detalle.columns:
        df_detalle['rango'] = df_detalle['dias_overdue'].apply(_rango)
        df_detalle = df_detalle.sort_values('dias_overdue', ascending=False)

    df_detalle = df_detalle.reset_index(drop=True)
    return df_detalle

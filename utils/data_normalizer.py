"""
Módulo para normalización de datos.
Centraliza la lógica de limpieza y normalización de DataFrames.
"""

import pandas as pd
from typing import Tuple, Optional
from unidecode import unidecode
from .logger import configurar_logger
from .constantes import (
    COLUMNAS_SALDO_CANDIDATAS,
    COLUMNAS_VENTAS,
    ESTATUS_PAGADO_VARIANTES
)

logger = configurar_logger("data_normalizer", nivel="INFO")


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza nombres de columnas de un DataFrame.
    
    Convierte columnas a lowercase, reemplaza espacios por guiones bajos,
    elimina acentos y maneja duplicados agregando sufijos numéricos.
    
    Args:
        df: DataFrame con columnas a normalizar
        
    Returns:
        DataFrame con columnas normalizadas
        
    Example:
        df = normalizar_columnas(df)
        # "Saldo Adeudado" → "saldo_adeudado"
        # "Cliente", "Cliente" → "cliente", "cliente_2"
    """
    df = df.copy()
    nuevas_columnas = []
    contador = {}
    
    for col in df.columns:
        # Normalizar: lowercase, strip, reemplazar espacios, eliminar acentos
        col_str = str(col).lower().strip().replace(" ", "_")
        col_str = unidecode(col_str)
        
        # Manejar duplicados
        if col_str in contador:
            contador[col_str] += 1
            col_str = f"{col_str}_{contador[col_str]}"
        else:
            contador[col_str] = 1
            
        nuevas_columnas.append(col_str)
    
    df.columns = nuevas_columnas
    logger.debug(f"Columnas normalizadas: {len(nuevas_columnas)} columnas procesadas")
    
    return df


def normalizar_columna_saldo(df: pd.DataFrame, col_destino: str = 'saldo_adeudado') -> pd.DataFrame:
    """
    Normaliza columnas de saldo/adeudo a un nombre estándar.
    
    Args:
        df: DataFrame con datos de CxC
        col_destino: Nombre de columna destino (default: 'saldo_adeudado')
        
    Returns:
        DataFrame con columna normalizada
        
    Example:
        df = normalizar_columna_saldo(df)
        # Ahora df tiene columna 'saldo_adeudado'
    """
    df = df.copy()
    
    # Si ya existe la columna destino, solo limpiar valores
    if col_destino in df.columns:
        df[col_destino] = limpiar_valores_monetarios(df[col_destino])
        return df
    
    # Buscar columna candidata
    for candidato in COLUMNAS_SALDO_CANDIDATAS:
        if candidato in df.columns:
            df = df.rename(columns={candidato: col_destino})
            logger.info(f"Columna de saldo normalizada: '{candidato}' → '{col_destino}'")
            break
    
    # Limpiar valores si existe la columna
    if col_destino in df.columns:
        df[col_destino] = limpiar_valores_monetarios(df[col_destino])
    else:
        logger.warning(f"No se encontró columna de saldo. Candidatos: {COLUMNAS_SALDO_CANDIDATAS}")
        df[col_destino] = 0
    
    return df


def normalizar_columna_valor(df: pd.DataFrame, col_destino: str = 'valor_usd') -> pd.DataFrame:
    """
    Normaliza columnas de ventas/valor a un nombre estándar.
    
    Args:
        df: DataFrame con datos de ventas
        col_destino: Nombre de columna destino (default: 'valor_usd')
        
    Returns:
        DataFrame con columna normalizada
        
    Example:
        df = normalizar_columna_valor(df)
        # Ahora df tiene columna 'valor_usd'
    """
    df = df.copy()
    
    # Si ya existe la columna destino, solo limpiar valores
    if col_destino in df.columns:
        df[col_destino] = pd.to_numeric(df[col_destino], errors='coerce').fillna(0)
        return df
    
    # Buscar columna candidata
    for candidato in COLUMNAS_VENTAS:
        if candidato in df.columns:
            df = df.rename(columns={candidato: col_destino})
            logger.info(f"Columna de valor normalizada: '{candidato}' → '{col_destino}'")
            break
    
    # Convertir a numérico
    if col_destino in df.columns:
        df[col_destino] = pd.to_numeric(df[col_destino], errors='coerce').fillna(0)
    else:
        logger.warning(f"No se encontró columna de valor. Candidatos: {COLUMNAS_VENTAS}")
        df[col_destino] = 0
    
    return df


def limpiar_valores_monetarios(serie: pd.Series) -> pd.Series:
    """
    Limpia valores monetarios eliminando símbolos y formatos.
    
    Convierte: "$1,234.56" → 1234.56
    
    Args:
        serie: Serie de pandas con valores monetarios
        
    Returns:
        Serie con valores numéricos limpios
        
    Example:
        df['saldo'] = limpiar_valores_monetarios(df['saldo'])
    """
    # Convertir a string
    serie_str = serie.astype(str)
    
    # Eliminar símbolos de moneda y comas
    serie_str = serie_str.str.replace(',', '', regex=False)
    serie_str = serie_str.str.replace('$', '', regex=False)
    serie_str = serie_str.str.replace('€', '', regex=False)
    serie_str = serie_str.str.replace('£', '', regex=False)
    serie_str = serie_str.str.strip()
    
    # Convertir a numérico
    return pd.to_numeric(serie_str, errors='coerce').fillna(0)


def detectar_columnas_cxc(df: pd.DataFrame) -> bool:
    """
    Detecta si un DataFrame tiene columnas de CxC.
    
    Args:
        df: DataFrame a verificar
        
    Returns:
        True si tiene columnas de CxC, False en caso contrario
        
    Example:
        if detectar_columnas_cxc(df):
            print("Este DataFrame tiene datos de CxC")
    """
    columnas_cxc = {
        "saldo", "saldo_usd", "saldo_adeudado",
        "dias_restante", "dias_restantes", "dias_de_credito", "dias_de_credit",
        "vencimient", "vencimiento",
        "fecha_de_pago", "fecha_pago", "fecha_tentativa_de_pag", "fecha_tentativa_de_pago",
        "estatus", "status", "pagado",
    }
    
    columnas_presentes = set(df.columns)
    encontradas = columnas_cxc.intersection(columnas_presentes)
    
    if encontradas:
        logger.info(f"Columnas de CxC detectadas: {encontradas}")
        return True
    
    return False


def excluir_pagados(df: pd.DataFrame, col_estatus: Optional[str] = None) -> pd.DataFrame:
    """
    Excluye registros pagados de un DataFrame de CxC.
    
    Args:
        df: DataFrame con datos de CxC
        col_estatus: Nombre de columna de estatus (se detecta automáticamente si es None)
        
    Returns:
        DataFrame sin registros pagados
        
    Example:
        df_cxc_activos = excluir_pagados(df_cxc)
    """
    df = df.copy()
    
    # Detectar columna de estatus si no se proporciona
    if col_estatus is None:
        for col in ["estatus", "status", "pagado"]:
            if col in df.columns:
                col_estatus = col
                break
    
    if col_estatus is None:
        logger.warning("No se encontró columna de estatus. No se excluyen registros.")
        return df
    
    # Normalizar valores de estatus
    registros_original = len(df)
    estatus_norm = df[col_estatus].astype(str).str.strip().str.lower()
    
    # Crear máscara para excluir pagados
    mask_pagado = pd.Series(False, index=df.index)
    for variante in ESTATUS_PAGADO_VARIANTES:
        mask_pagado |= estatus_norm.str.contains(variante, na=False)
    
    df_filtrado = df[~mask_pagado]
    registros_excluidos = registros_original - len(df_filtrado)
    
    if registros_excluidos > 0:
        logger.info(f"Excluidos {registros_excluidos} registros pagados de {registros_original}")
    
    return df_filtrado


def normalizar_datos_cxc(df_ventas: pd.DataFrame, df_cxc: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Normaliza datos de ventas y CxC de forma consistente.
    
    Aplica todas las normalizaciones necesarias:
    - Normaliza columnas de saldo y valor
    - Detecta CxC en hoja de ventas si df_cxc está vacío
    - Excluye registros pagados
    - Limpia valores monetarios
    
    Args:
        df_ventas: DataFrame con datos de ventas
        df_cxc: DataFrame con datos de CxC (puede estar vacío)
        
    Returns:
        Tupla (df_ventas_normalizado, df_cxc_normalizado)
        
    Example:
        df_v, df_c = normalizar_datos_cxc(df_ventas, df_cxc)
    """
    df_ventas = df_ventas.copy() if df_ventas is not None else pd.DataFrame()
    df_cxc = df_cxc.copy() if df_cxc is not None else pd.DataFrame()
    
    # Normalizar columna de valor en ventas
    df_ventas = normalizar_columna_valor(df_ventas, col_destino='valor_usd')
    
    # Si no hay CxC separado, buscar en ventas
    if df_cxc.empty and detectar_columnas_cxc(df_ventas):
        logger.info("CxC no proporcionado. Usando datos de hoja de ventas.")
        df_cxc = df_ventas.copy()
    
    # Normalizar CxC si existe
    if not df_cxc.empty:
        df_cxc = normalizar_columna_saldo(df_cxc, col_destino='saldo_adeudado')
        df_cxc = excluir_pagados(df_cxc)
        
        logger.info(f"Datos normalizados - Ventas: {len(df_ventas)} registros, CxC: {len(df_cxc)} registros")
    
    return df_ventas, df_cxc


def normalizar_columna_fecha(df: pd.DataFrame, col_fecha: str = 'fecha') -> pd.DataFrame:
    """
    Normaliza columna de fecha a datetime.
    
    Args:
        df: DataFrame con columna de fecha
        col_fecha: Nombre de la columna de fecha
        
    Returns:
        DataFrame con columna datetime normalizada
    """
    df = df.copy()
    
    if col_fecha in df.columns:
        df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
        nulos = df[col_fecha].isna().sum()
        if nulos > 0:
            logger.warning(f"{nulos} fechas no pudieron ser parseadas y fueron convertidas a NaT")
    else:
        logger.warning(f"Columna '{col_fecha}' no encontrada en DataFrame")
    
    return df

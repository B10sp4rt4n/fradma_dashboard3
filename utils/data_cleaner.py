"""
Módulo de limpieza y normalización de datos para Fradma Dashboard.
Maneja nombres con variaciones de acentos, mayúsculas y errores tipográficos.
"""

import pandas as pd
from unidecode import unidecode
import json
import os


def normalizar_texto(texto):
    """
    Normaliza un texto eliminando acentos, convirtiendo a minúsculas y limpiando espacios.
    
    Args:
        texto: String a normalizar
        
    Returns:
        String normalizado (sin acentos, minúsculas, sin espacios extra)
        
    Examples:
        "José García" -> "jose garcia"
        "MARÍA  LÓPEZ" -> "maria lopez"
        "  Juan   Pérez  " -> "juan perez"
    """
    if pd.isna(texto):
        return texto
    
    texto_str = str(texto)
    # Convertir a minúsculas
    texto_str = texto_str.lower()
    # Limpiar espacios extra
    texto_str = ' '.join(texto_str.split())
    # Remover acentos
    texto_str = unidecode(texto_str)
    
    return texto_str


def cargar_aliases(archivo_aliases='config/aliases.json'):
    """
    Carga el archivo de aliases/mapeos desde JSON.
    
    Args:
        archivo_aliases: Ruta al archivo de configuración
        
    Returns:
        Diccionario con los mapeos {valor_normalizado: [variantes]}
    """
    ruta_completa = os.path.join(os.path.dirname(os.path.dirname(__file__)), archivo_aliases)
    
    if not os.path.exists(ruta_completa):
        return {}
    
    try:
        with open(ruta_completa, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def aplicar_aliases(serie, aliases_dict):
    """
    Aplica mapeo de aliases a una Serie de pandas.
    
    Args:
        serie: pd.Series con valores a mapear
        aliases_dict: Diccionario con estructura {nombre_correcto: [variantes]}
        
    Returns:
        pd.Series con valores mapeados
        
    Example:
        aliases = {
            "jose garcia": ["José García", "JOSE GARCIA", "jose garcia"],
            "maria lopez": ["María López", "MARIA LOPEZ"]
        }
        serie = pd.Series(["José García", "MARIA LOPEZ"])
        resultado -> pd.Series(["jose garcia", "maria lopez"])
    """
    # Crear diccionario inverso: variante -> valor_correcto
    mapeo = {}
    for valor_correcto, variantes in aliases_dict.items():
        for variante in variantes:
            mapeo[normalizar_texto(variante)] = valor_correcto
    
    # Aplicar mapeo
    return serie.apply(lambda x: mapeo.get(normalizar_texto(x), normalizar_texto(x)))


def limpiar_columnas_texto(df, columnas=None, usar_aliases=True):
    """
    Limpia y normaliza columnas de texto en un DataFrame.
    
    Args:
        df: DataFrame a limpiar
        columnas: Lista de columnas a normalizar. Si None, detecta automáticamente
        usar_aliases: Si True, aplica mapeo de aliases.json
        
    Returns:
        DataFrame con columnas normalizadas
        
    Example:
        df = pd.DataFrame({
            'agente': ['José García', 'MARIA LOPEZ', 'José García'],
            'valor_usd': [100, 200, 150]
        })
        df_limpio = limpiar_columnas_texto(df, columnas=['agente'])
        # agente ahora tiene: ['jose garcia', 'maria lopez', 'jose garcia']
    """
    df_limpio = df.copy()
    
    # Detectar columnas de texto si no se especifican
    if columnas is None:
        columnas = df_limpio.select_dtypes(include=['object']).columns.tolist()
        # Excluir columnas que no son nombres (fechas, códigos, etc.)
        columnas_excluir = ['fecha', 'periodo', 'mes_anio', 'trimestre']
        columnas = [col for col in columnas if col not in columnas_excluir]
    
    # Cargar aliases si están disponibles
    aliases = cargar_aliases() if usar_aliases else {}
    
    # Normalizar cada columna
    for col in columnas:
        if col in df_limpio.columns:
            if usar_aliases and col in aliases:
                # Aplicar aliases específicos de esta columna
                df_limpio[col] = aplicar_aliases(df_limpio[col], aliases[col])
            else:
                # Solo normalización automática
                df_limpio[col] = df_limpio[col].apply(normalizar_texto)
    
    return df_limpio


def detectar_duplicados_similares(serie, umbral_similitud=0.85):
    """
    Detecta valores similares que probablemente son duplicados.
    Útil para sugerir aliases al usuario.
    
    Args:
        serie: pd.Series con valores a analizar
        umbral_similitud: Umbral de similitud (0-1)
        
    Returns:
        Lista de tuplas con posibles duplicados [(valor1, valor2, similitud)]
    """
    from difflib import SequenceMatcher
    
    valores_unicos = serie.dropna().unique()
    duplicados_potenciales = []
    
    for i, val1 in enumerate(valores_unicos):
        for val2 in valores_unicos[i+1:]:
            similitud = SequenceMatcher(None, 
                                       normalizar_texto(val1), 
                                       normalizar_texto(val2)).ratio()
            if similitud >= umbral_similitud:
                duplicados_potenciales.append((val1, val2, round(similitud, 2)))
    
    return sorted(duplicados_potenciales, key=lambda x: x[2], reverse=True)

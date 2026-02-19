"""
Helper para manejo de filtros en análisis IA.

Proporciona funciones reutilizables para:
- Filtrar líneas de negocio excluyendo "Todas"
- Validar datos de entrada del multiselect
- Generar contexto descriptivo para la IA

Autor: Sistema
Fecha: 2026-02-19
"""

from typing import List, Optional


def obtener_lineas_filtradas(lineas_seleccionadas: Optional[List[str]]) -> List[str]:
    """
    Filtra líneas específicas removiendo 'Todas' y valores vacíos.
    
    Esta función es el patrón estándar para procesar la selección del usuario
    cuando usa el multiselect de líneas de negocio en el sidebar.
    
    Args:
        lineas_seleccionadas: Lista de líneas seleccionadas por el usuario.
                            Puede incluir "Todas" junto con líneas específicas.
                            Puede ser None si session_state no está inicializado.
    
    Returns:
        Lista de líneas específicas sin "Todas" ni valores vacíos.
        Lista vacía si solo estaba seleccionado "Todas" o si entrada es None.
    
    Examples:
        >>> obtener_lineas_filtradas(["Todas", "repi", "ultra plast"])
        ["repi", "ultra plast"]
        
        >>> obtener_lineas_filtradas(["Todas"])
        []
        
        >>> obtener_lineas_filtradas(None)
        []
        
        >>> obtener_lineas_filtradas(["repi", "", "ultra plast"])
        ["repi", "ultra plast"]
    
    Note:
        - Filtra strings vacíos para evitar errores en DataFrame.isin()
        - Usa (lineas_seleccionadas or []) para manejar None de forma segura
        - "Todas" se excluye porque significa "sin filtro" (mostrar todo)
    """
    return [l for l in (lineas_seleccionadas or []) if l and l != "Todas"]


def generar_contexto_filtros(lineas_filtrar: List[str]) -> Optional[str]:
    """
    Genera mensaje de contexto para la IA sobre el alcance del análisis.
    
    Este contexto se incluye en el prompt de la IA para que entienda que
    las métricas representan SOLO las líneas filtradas, no todo el negocio.
    
    Args:
        lineas_filtrar: Lista de líneas de negocio específicas (sin "Todas").
    
    Returns:
        Mensaje de contexto si hay filtros aplicados, None si no hay filtros.
    
    Examples:
        >>> generar_contexto_filtros(["repi", "ultra plast"])
        "Este análisis se enfoca ÚNICAMENTE en las siguientes líneas de negocio: repi, ultra plast. 
         Las ventas y métricas reflejan SOLO estas líneas, no todo el negocio."
        
        >>> generar_contexto_filtros([])
        None
    
    Note:
        - None indica a la IA que está analizando TODO el negocio
        - El mensaje enfatiza "ÚNICAMENTE" y "SOLO" para evitar confusión
    """
    if lineas_filtrar:
        lineas_texto = ", ".join(lineas_filtrar)
        return (
            f"Este análisis se enfoca ÚNICAMENTE en las siguientes líneas de negocio: {lineas_texto}. "
            f"Las ventas y métricas reflejan SOLO estas líneas, no todo el negocio."
        )
    return None


def aplicar_filtro_dataframe(df, columna: str, lineas_filtrar: List[str], validar_columna: bool = True):
    """
    Aplica filtro de líneas a un DataFrame de forma segura.
    
    Args:
        df: DataFrame a filtrar (pandas.DataFrame).
        columna: Nombre de la columna que contiene las líneas de negocio.
        lineas_filtrar: Lista de líneas específicas a mantener.
        validar_columna: Si True, valida que la columna existe antes de filtrar.
    
    Returns:
        DataFrame filtrado si hay líneas_filtrar y columna existe.
        DataFrame original si no hay filtros o columna no existe.
    
    Examples:
        >>> df_filtrado = aplicar_filtro_dataframe(
        ...     df, 
        ...     columna='linea_de_negocio',
        ...     lineas_filtrar=['repi', 'ultra plast']
        ... )
    
    Note:
        - Si validar_columna=False, asume que la columna existe (para performance)
        - Retorna el DataFrame original si lineas_filtrar está vacío (sin filtro)
    """
    if not lineas_filtrar:
        return df
    
    if validar_columna and columna not in df.columns:
        return df
    
    return df[df[columna].isin(lineas_filtrar)]

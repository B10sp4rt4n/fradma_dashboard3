"""
Utilidades de caché para optimización de performance en Streamlit.

Proporciona decoradores y funciones helper para cachear datos y cálculos pesados,
reduciendo tiempos de carga y mejorando la experiencia de usuario.
"""

import streamlit as st
import pandas as pd
import hashlib
from typing import Any, Optional, Callable
from functools import wraps
import time


def calcular_hash_dataframe(df: pd.DataFrame) -> str:
    """
    Calcula un hash único para un DataFrame.
    
    Útil para invalidación de caché cuando los datos cambian.
    
    Args:
        df: DataFrame de pandas
        
    Returns:
        String con hash MD5 del DataFrame
        
    Examples:
        >>> df = pd.DataFrame({'a': [1, 2, 3]})
        >>> hash1 = calcular_hash_dataframe(df)
        >>> df.loc[0, 'a'] = 999
        >>> hash2 = calcular_hash_dataframe(df)
        >>> hash1 != hash2
        True
    """
    # Usar valores + columnas + shape para el hash
    datos_str = f"{df.columns.tolist()}{df.shape}{df.values.tobytes()}"
    return hashlib.md5(datos_str.encode()).hexdigest()[:16]


def cache_con_timeout(ttl_segundos: int = 300):
    """
    Decorador para cachear resultados con timeout personalizado.
    
    Args:
        ttl_segundos: Tiempo de vida del caché en segundos (default: 5 min)
        
    Examples:
        >>> @cache_con_timeout(ttl_segundos=600)  # 10 minutos
        ... def calcular_metricas_pesadas(df):
        ...     # cálculos complejos
        ...     return resultado
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @st.cache_data(ttl=ttl_segundos, show_spinner=f"⚡ Calculando {func.__name__}...")
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def limpiar_cache_completo():
    """
    Limpia todo el caché de Streamlit.
    
    Útil cuando se detectan datos inconsistentes o se quiere
    forzar recálculo de todo.
    
    Examples:
        >>> if st.button("🔄 Limpiar caché"):
        ...     limpiar_cache_completo()
        ...     st.success("Caché limpiado!")
    """
    st.cache_data.clear()
    st.cache_resource.clear()


def mostrar_indicador_cache(esta_cacheado: bool, nombre_operacion: str = "Datos"):
    """
    Muestra un indicador visual del estado del caché.
    
    Args:
        esta_cacheado: Si los datos vienen del caché
        nombre_operacion: Descripción de la operación
        
    Examples:
        >>> if 'ultimo_hash' in st.session_state:
        ...     mostrar_indicador_cache(True, "Métricas CxC")
        ... else:
        ...     mostrar_indicador_cache(False, "Métricas CxC")
    """
    if esta_cacheado:
        st.caption(f"⚡ {nombre_operacion} cargados desde caché (más rápido)")
    else:
        st.caption(f"🔄 {nombre_operacion} calculados desde cero")


def decorador_medicion_tiempo(func: Callable) -> Callable:
    """
    Decorador para medir y mostrar tiempo de ejecución.
    
    Útil para identificar funciones lentas que necesitan optimización.
    
    Args:
        func: Función a medir
        
    Returns:
        Función decorada con medición de tiempo
        
    Examples:
        >>> @decorador_medicion_tiempo
        ... def procesar_datos_grandes(df):
        ...     # procesamiento pesado
        ...     return resultado
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        inicio = time.time()
        resultado = func(*args, **kwargs)
        duracion = time.time() - inicio
        
        # Mostrar warning si la función es muy lenta (> 2 segundos)
        if duracion > 2.0:
            st.warning(
                f"⚠️ {func.__name__}() tardó {duracion:.2f}s. "
                f"Considera optimizar o cachear."
            )
        
        return resultado
    return wrapper


@st.cache_data(ttl=600)
def cachear_dataframe(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """
    Cachea un DataFrame con una key personalizada.
    
    Args:
        df: DataFrame a cachear
        key: Identificador único del DataFrame
        
    Returns:
        El mismo DataFrame (ahora cacheado)
        
    Examples:
        >>> df_procesado = procesar_datos(df_raw)
        >>> df_cached = cachear_dataframe(df_procesado, "datos_procesados_v1")
    """
    return df.copy()


class GestorCache:
    """
    Gestor centralizado de caché con métricas de uso.
    
    Permite rastrear hits/misses de caché y optimizar basado en datos reales.
    
    Examples:
        >>> gestor = GestorCache()
        >>> resultado = gestor.obtener_o_calcular(
        ...     key="metricas_cxc",
        ...     funcion_calculo=lambda: calcular_metricas(df),
        ...     ttl=300
        ... )
    """
    
    def __init__(self):
        """Inicializa el gestor con contadores en session_state."""
        if 'cache_stats' not in st.session_state:
            st.session_state.cache_stats = {
                'hits': 0,
                'misses': 0,
                'total_tiempo_ahorrado': 0.0
            }
    
    def obtener_o_calcular(
        self, 
        key: str, 
        funcion_calculo: Callable, 
        ttl: int = 300,
        mostrar_stats: bool = False
    ) -> Any:
        """
        Obtiene dato del caché o lo calcula si no existe.
        
        Args:
            key: Clave única para el caché
            funcion_calculo: Función que genera el dato (solo se llama en cache miss)
            ttl: Tiempo de vida en segundos
            mostrar_stats: Si mostrar estadísticas de caché
            
        Returns:
            Resultado cacheado o recién calculado
        """
        cache_key = f"cache_{key}"
        timestamp_key = f"timestamp_{key}"
        
        # Verificar si está en caché y no expiró
        ahora = time.time()
        if (cache_key in st.session_state and 
            timestamp_key in st.session_state and
            ahora - st.session_state[timestamp_key] < ttl):
            
            # Cache HIT
            st.session_state.cache_stats['hits'] += 1
            if mostrar_stats:
                st.caption(f"⚡ Cache HIT para '{key}'")
            return st.session_state[cache_key]
        
        # Cache MISS - calcular
        st.session_state.cache_stats['misses'] += 1
        inicio = time.time()
        
        resultado = funcion_calculo()
        
        duracion = time.time() - inicio
        st.session_state.cache_stats['total_tiempo_ahorrado'] += duracion
        
        # Guardar en caché
        st.session_state[cache_key] = resultado
        st.session_state[timestamp_key] = ahora
        
        if mostrar_stats:
            st.caption(f"🔄 Cache MISS para '{key}' (calculado en {duracion:.3f}s)")
        
        return resultado
    
    def mostrar_estadisticas(self):
        """Muestra métricas de uso del caché."""
        stats = st.session_state.cache_stats
        total = stats['hits'] + stats['misses']
        
        if total == 0:
            st.info("Sin estadísticas de caché aún")
            return
        
        hit_rate = (stats['hits'] / total) * 100
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Cache Hits", stats['hits'])
        with col2:
            st.metric("Cache Misses", stats['misses'])
        with col3:
            st.metric("Hit Rate", f"{hit_rate:.1f}%")
        with col4:
            st.metric("Tiempo Ahorrado", f"{stats['total_tiempo_ahorrado']:.1f}s")
    
    def limpiar(self):
        """Limpia todo el caché gestionado."""
        keys_a_eliminar = [k for k in st.session_state.keys() if k.startswith('cache_') or k.startswith('timestamp_')]
        for key in keys_a_eliminar:
            del st.session_state[key]
        st.session_state.cache_stats = {
            'hits': 0,
            'misses': 0,
            'total_tiempo_ahorrado': 0.0
        }


# Instancia global del gestor
gestor_cache = GestorCache()


if __name__ == "__main__":
    # Demo del sistema de caché
    import pandas as pd
    
    print("🧪 Demo de cache_helper.py\n")
    
    # Test 1: Hash de DataFrame
    df = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
    hash1 = calcular_hash_dataframe(df)
    print(f"✅ Hash del DataFrame: {hash1}")
    
    df.loc[0, 'col1'] = 999
    hash2 = calcular_hash_dataframe(df)
    print(f"✅ Hash después de modificar: {hash2}")
    print(f"✅ Hashes diferentes: {hash1 != hash2}\n")
    
    # Test 2: Decorador de medición
    @decorador_medicion_tiempo
    def funcion_lenta():
        time.sleep(0.1)
        return "resultado"
    
    print("⏱️ Ejecutando función con medición de tiempo...")
    resultado = funcion_lenta()
    print(f"✅ Resultado: {resultado}\n")
    
    print("✅ Tests completados!")

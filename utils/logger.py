"""
Sistema de logging estructurado para el Dashboard FRADMA.

Proporciona configuración centralizada de logging con:
- Múltiples niveles (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Rotación automática de archivos
- Formato estructurado con timestamps
- Context tracking para debugging
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# Directorio para logs
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


class ColoredFormatter(logging.Formatter):
    """Formatter con colores para output de consola."""
    
    # Códigos ANSI para colores
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Verde
        'WARNING': '\033[33m',    # Amarillo
        'ERROR': '\033[31m',      # Rojo
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Formatear el log record con colores."""
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)


def configurar_logger(
    nombre: str = "dashboard_fradma",
    nivel: str = "INFO",
    habilitar_consola: bool = True,
    habilitar_archivo: bool = True
) -> logging.Logger:
    """
    Configura y retorna un logger estructurado.
    
    Args:
        nombre: Nombre del logger (usado para identificar componentes)
        nivel: Nivel mínimo de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        habilitar_consola: Si mostrar logs en consola
        habilitar_archivo: Si guardar logs en archivo
        
    Returns:
        Logger configurado y listo para usar
        
    Examples:
        >>> logger = configurar_logger("mi_modulo", "DEBUG")
        >>> logger.info("Aplicación iniciada")
        >>> logger.error("Error al procesar archivo", exc_info=True)
    """
    logger = logging.getLogger(nombre)
    
    # Evitar duplicar handlers si ya está configurado
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, nivel.upper()))
    logger.propagate = False
    
    # Formato detallado para archivos
    formato_archivo = (
        "%(asctime)s | %(name)s | %(levelname)-8s | "
        "%(filename)s:%(lineno)d | %(funcName)s() | %(message)s"
    )
    
    # Formato simplificado para consola
    formato_consola = "%(asctime)s | %(levelname)-8s | %(message)s"
    
    # Handler para consola con colores
    if habilitar_consola:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter(
            formato_consola,
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # Handler para archivo con rotación
    if habilitar_archivo:
        fecha_actual = datetime.now().strftime("%Y%m%d")
        archivo_log = LOG_DIR / f"{nombre}_{fecha_actual}.log"
        
        # RotatingFileHandler: max 10MB, mantener 5 backups
        file_handler = logging.handlers.RotatingFileHandler(
            archivo_log,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            formato_archivo,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def log_execution_time(logger: logging.Logger):
    """
    Decorador para medir y loggear el tiempo de ejecución de funciones.
    
    Args:
        logger: Logger a usar para el output
        
    Examples:
        >>> logger = configurar_logger("mi_app")
        >>> @log_execution_time(logger)
        ... def procesar_datos():
        ...     # procesamiento largo
        ...     pass
    """
    import functools
    import time
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nombre_func = func.__name__
            logger.debug(f"Iniciando {nombre_func}()")
            
            inicio = time.time()
            try:
                resultado = func(*args, **kwargs)
                duracion = time.time() - inicio
                logger.info(f"{nombre_func}() completado en {duracion:.3f}s")
                return resultado
            except Exception as e:
                duracion = time.time() - inicio
                logger.error(
                    f"{nombre_func}() falló después de {duracion:.3f}s: {e}",
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator


def log_dataframe_info(logger: logging.Logger, df, nombre: str = "DataFrame"):
    """
    Loggea información útil sobre un DataFrame.
    
    Args:
        logger: Logger a usar
        df: DataFrame de pandas
        nombre: Nombre descriptivo del DataFrame
        
    Examples:
        >>> import pandas as pd
        >>> logger = configurar_logger()
        >>> df = pd.DataFrame({'A': [1, 2, 3]})
        >>> log_dataframe_info(logger, df, "datos_cxc")
    """
    if df is None or df.empty:
        logger.warning(f"{nombre} está vacío o es None")
        return
    
    logger.info(
        f"{nombre}: {len(df)} filas, {len(df.columns)} columnas. "
        f"Memoria: {df.memory_usage(deep=True).sum() / 1024:.2f} KB"
    )
    
    # Log columnas con valores nulos
    nulos = df.isnull().sum()
    nulos_significativos = nulos[nulos > 0]
    if not nulos_significativos.empty:
        logger.debug(f"{nombre} - Columnas con nulos: {nulos_significativos.to_dict()}")


# Logger por defecto para la aplicación
default_logger = configurar_logger(
    nombre="dashboard_fradma",
    nivel=os.getenv("LOG_LEVEL", "INFO")
)


if __name__ == "__main__":
    # Demo del sistema de logging
    logger = configurar_logger("demo", "DEBUG")
    
    logger.debug("Mensaje de DEBUG (desarrollo)")
    logger.info("Mensaje de INFO (normal)")
    logger.warning("Mensaje de WARNING (advertencia)")
    logger.error("Mensaje de ERROR (error recuperable)")
    logger.critical("Mensaje de CRITICAL (error crítico)")
    
    # Demo de log_execution_time
    @log_execution_time(logger)
    def funcion_ejemplo():
        import time
        time.sleep(0.5)
        return "completado"
    
    resultado = funcion_ejemplo()
    
    # Demo de log_dataframe_info
    import pandas as pd
    df_test = pd.DataFrame({
        'col1': [1, 2, None, 4],
        'col2': ['a', 'b', 'c', 'd']
    })
    log_dataframe_info(logger, df_test, "datos_test")
    
    print(f"\n✅ Logs guardados en: {LOG_DIR.absolute()}")

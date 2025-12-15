"""
Constantes centralizadas para el Dashboard Fradma.
Define umbrales, listas de columnas y configuraciones globales.
"""

# =====================================================================
# DETECCIÓN DE COLUMNAS
# =====================================================================

# Columnas de ventas/montos
COLUMNAS_VENTAS = [
    'ventas_usd_con_iva',
    'ventas_usd',
    'importe',
    'valor_usd',
    'monto_usd',
    'total_usd',
    'valor',
    'venta'
]

# Columnas de fecha de pago
COLUMNAS_FECHA_PAGO = [
    'fecha_de_pago',
    'fecha_pago',
    'fecha_tentativa_de_pag',
    'fecha_tentativa_de_pago'
]

# Columnas de días de crédito
COLUMNAS_DIAS_CREDITO = [
    'dias_de_credito',
    'dias_de_credit',
    'dias_credito',
    'dias_credit'
]

# Columnas de estatus
COLUMNAS_ESTATUS = [
    'estatus',
    'status',
    'pagado'
]

# Columnas de cliente/deudor
COLUMNAS_CLIENTE = [
    'cliente',
    'razon_social',
    'deudor',
    'nombre_cliente'
]

# Columnas de línea de negocio
COLUMNAS_LINEA_NEGOCIO = [
    'linea_negocio',
    'linea_de_negocio',
    'linea_producto',
    'linea'
]

# Columnas de vendedor/agente
COLUMNAS_VENDEDOR = [
    'vendedor',
    'agente',
    'ejecutivo',
    'vendedor_asignado'
]

# =====================================================================
# UMBRALES DE CUENTAS POR COBRAR
# =====================================================================

class UmbralesCxC:
    """Umbrales para clasificación y alertas de CxC."""
    
    # Montos críticos
    CRITICO_MONTO = 50_000  # USD
    ALTO_RIESGO_MONTO = 100_000  # USD
    
    # Días de vencimiento
    DIAS_VENCIDO_0_30 = 30
    DIAS_VENCIDO_30_60 = 60
    DIAS_VENCIDO_60_90 = 90
    DIAS_ALTO_RIESGO = 90
    DIAS_DETERIORO_SEVERO = 120
    DIAS_INCOBRABILIDAD = 180
    
    # Porcentajes de morosidad
    MOROSIDAD_BAJA = 10  # % verde
    MOROSIDAD_MEDIA = 25  # % amarillo
    MOROSIDAD_ALTA = 50  # % rojo
    
    # Porcentajes de riesgo
    RIESGO_BAJO = 5  # %
    RIESGO_MEDIO = 15  # %
    RIESGO_ALTO = 30  # %
    
    # Concentración de cartera
    CONCENTRACION_BAJA = 30  # %
    CONCENTRACION_MEDIA = 50  # %
    CONCENTRACION_ALTA = 70  # %
    
    # Objetivos de KPIs
    DSO_OBJETIVO = 30  # días
    DSO_ACEPTABLE = 45  # días
    MOROSIDAD_OBJETIVO = 5  # %
    ROTACION_CXC_OBJETIVO = 12  # veces por año
    ROTACION_CXC_MINIMO = 8  # veces por año

# =====================================================================
# SCORE DE SALUD FINANCIERA
# =====================================================================

class ScoreSalud:
    """Rangos y pesos para el score de salud financiera."""
    
    # Pesos de componentes
    PESO_VIGENTE = 0.7
    PESO_CRITICA = 0.3
    
    # Rangos de clasificación
    EXCELENTE_MIN = 80
    BUENO_MIN = 60
    REGULAR_MIN = 40
    MALO_MIN = 20
    # < 20 = Crítico
    
    # Colores asociados
    COLOR_EXCELENTE = "#4CAF50"  # Verde
    COLOR_BUENO = "#8BC34A"  # Verde claro
    COLOR_REGULAR = "#FFEB3B"  # Amarillo
    COLOR_MALO = "#FF9800"  # Naranja
    COLOR_CRITICO = "#F44336"  # Rojo
    COLOR_CRITICO_OSCURO = "#B71C1C"  # Rojo oscuro

# =====================================================================
# PRIORIDADES DE COBRANZA
# =====================================================================

class PrioridadCobranza:
    """Umbrales para clasificación de prioridad de cobranza."""
    
    # Scores de prioridad
    URGENTE_MIN = 75
    ALTA_MIN = 50
    MEDIA_MIN = 25
    # < 25 = Baja
    
    # Pesos para cálculo de score
    PESO_MONTO = 0.4
    PESO_DIAS = 0.4
    PESO_DOCUMENTOS = 0.2
    
    # Referencias para normalización
    MONTO_REFERENCIA = 100_000  # USD
    DIAS_REFERENCIA = 180  # días
    DOCS_REFERENCIA = 10  # cantidad de documentos

# =====================================================================
# CATEGORÍAS DE ANTIGÜEDAD
# =====================================================================

# Bins para clasificación de antigüedad de deuda
BINS_ANTIGUEDAD = [-float('inf'), 0, 30, 60, 90, 180, float('inf')]

# Labels para las categorías
LABELS_ANTIGUEDAD = [
    'Por vencer',
    '1-30 días',
    '31-60 días',
    '61-90 días',
    '91-180 días',
    '>180 días'
]

# Bins simplificados para análisis de agentes
BINS_ANTIGUEDAD_AGENTES = [-float('inf'), 0, 30, 60, 90, float('inf')]

LABELS_ANTIGUEDAD_AGENTES = [
    'Por vencer',
    '1-30 días',
    '31-60 días',
    '61-90 días',
    '>90 días'
]

# =====================================================================
# PALETAS DE COLORES
# =====================================================================

# Colores para categorías de antigüedad (6 niveles)
COLORES_ANTIGUEDAD = [
    '#4CAF50',  # Verde - Por vencer
    '#8BC34A',  # Verde claro - 1-30
    '#FFEB3B',  # Amarillo - 31-60
    '#FF9800',  # Naranja - 61-90
    '#F44336',  # Rojo - 91-180
    '#B71C1C'   # Rojo oscuro - >180
]

# Colores para análisis de agentes (5 niveles)
COLORES_ANTIGUEDAD_AGENTES = [
    '#4CAF50',  # Verde - Por vencer
    '#8BC34A',  # Verde claro - 1-30
    '#FFEB3B',  # Amarillo - 31-60
    '#FF9800',  # Naranja - 61-90
    '#F44336'   # Rojo - >90
]

# Colores semáforo
COLORES_SEMAFORO = {
    'verde': '🟢',
    'amarillo': '🟡',
    'naranja': '🟠',
    'rojo': '🔴'
}

# =====================================================================
# CONFIGURACIÓN DE VISUALIZACIÓN
# =====================================================================

class ConfigVisualizacion:
    """Configuración para gráficos y tablas."""
    
    # Plotly
    PIE_HOLE = 0.4  # Tamaño del agujero en gráficos de dona
    PIE_HEIGHT = 350  # Altura de gráficos de pie
    GAUGE_HEIGHT = 250  # Altura de gauges
    CHART_HEIGHT = 400  # Altura de charts estándar
    
    # Tablas
    TOP_N_DEFAULT = 5  # Cantidad default de top items
    TOP_N_LINEAS_DEFAULT = 10  # Top líneas de negocio
    TOP_N_MIN = 5
    TOP_N_MAX = 20
    
    # Formato de números
    DECIMALES_MONEDA = 2
    DECIMALES_PORCENTAJE = 1
    DECIMALES_SCORE = 1

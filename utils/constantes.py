"""
Constantes centralizadas para el Dashboard Fradma.
Define umbrales, listas de columnas y configuraciones globales.
"""

# =====================================================================
# MODELO UNIFICADO — CAMPOS CANÓNICOS (ventas → facturas → cxc)
# =====================================================================
# REGLA OBLIGATORIA: el estatus de CxC es DERIVADO, nunca manual.
# Usar utils.modelo_unificado para calcular/aplicar estatus.

# Tabla: ventas
CAMPO_ID_VENTA       = "id_venta"
CAMPO_CLIENTE_ID     = "cliente_id"
CAMPO_VENDEDOR_ID    = "vendedor_id"
CAMPO_FECHA_VENTA    = "fecha_venta"
CAMPO_IMPORTE_TOTAL  = "importe_total"

# Tabla: facturas
CAMPO_ID_FACTURA         = "id_factura"
CAMPO_FOLIO              = "folio"
CAMPO_FECHA_EMISION      = "fecha_emision"
CAMPO_IMPORTE_FACTURADO  = "importe_facturado"

# Tabla: cxc (estatus = DERIVADO)
CAMPO_ID_CXC            = "id_cxc"
CAMPO_FECHA_VENCIMIENTO = "fecha_vencimiento"
CAMPO_SALDO_ACTUAL      = "saldo_actual"
CAMPO_ESTATUS_DERIVADO  = "estatus"   # Solo lectura — no capturar desde Excel

# Valores de estatus derivado
ESTATUS_CXC_PAGADA  = "Pagada"
ESTATUS_CXC_VIGENTE = "Vigente"
ESTATUS_CXC_VENCIDA = "Vencida"

# Columnas de estatus que NO deben cargarse desde Excel
COLUMNAS_ESTATUS_PROHIBIDAS_EXCEL = frozenset({
    "estatus", "status", "estado", "pagado", "pagada",
    "condicion", "situacion", "flag_pagado",
})

# =====================================================================
# DETECCIÓN DE COLUMNAS
# =====================================================================

# Columnas de ventas/montos
COLUMNAS_VENTAS = [
    'ventas_usd_con_iva',
    'ventas_usd',
    'importe',
    'valor_mxn',
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

# Variantes de estatus pagado
ESTATUS_PAGADO_VARIANTES = [
    'pagado',
    'paid',
    'cancelado',
    'cerrado',
    'liquidado',
    'finiquitado'
]

# Columnas de saldo/adeudo
COLUMNAS_SALDO_CANDIDATAS = [
    'saldo_adeudado',
    'saldo',
    'saldo_adeudo',
    'adeudo',
    'importe',
    'monto',
    'total',
    'saldo_usd'
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
# MAPA DE ALIAS → NOMBRE CANÓNICO
# Cualquier alias en las listas se renombra al campo canónico.
# Usado por homologar_columnas() para normalizar cualquier Excel cliente.
# =====================================================================
ALIAS_MAP: dict[str, list[str]] = {
    # ── Fecha ─────────────────────────────────────────────────────
    "fecha": [
        "fecha_emision", "fecha_factura", "date", "periodo",
        "fecha_documento", "fecha_venta", "fecha_registro",
    ],
    # ── Importe / ventas ──────────────────────────────────────────
    "importe": [
        "ventas_usd", "ventas_usd_con_iva", "ventas_usd_sin_iva",
        "valor_mxn", "monto_usd", "total_usd", "valor", "venta",
        "total", "monto", "importe_mxn", "importe_usd",
        "ventas", "venta_neta", "facturacion",
    ],
    # ── Línea de negocio ──────────────────────────────────────────
    "linea_de_negocio": [
        "linea_producto", "linea", "linea_negocio",
        "categoria", "familia", "grupo", "division",
        "linea_de_producto", "linea_prodcucto",  # typo CONTPAQi
    ],
    # ── Producto ──────────────────────────────────────────────────
    "producto": [
        "articulo", "descripcion", "item", "sku",
        "producto_nombre", "nombre_producto", "concepto",
        "descripcion_producto",
    ],
    # ── Cliente ───────────────────────────────────────────────────
    "cliente": [
        "razon_social", "receptor", "deudor", "nombre_cliente",
        "receptor_nombre", "nombre", "customer",
    ],
    # ── Vendedor ──────────────────────────────────────────────────
    "vendedor": [
        "agente", "ejecutivo", "rep", "seller",
        "vendedor_asignado", "representante", "responsable",
        "asesor", "account_manager",
    ],
    # ── Canal ─────────────────────────────────────────────────────
    "canal": [
        "canal_venta", "canal_comercial", "canal_de_venta",
        "tipo_venta", "modalidad",
    ],
    # ── Región ────────────────────────────────────────────────────
    "region": [
        "zona", "estado", "territorio", "plaza",
        "area_geografica", "sucursal",
    ],
    # ── Moneda ────────────────────────────────────────────────────
    "moneda": [
        "divisa", "currency", "tipo_moneda",
    ],
    # ── Tipo de cambio ────────────────────────────────────────────
    "tipo_cambio": [
        "fx", "tc", "tasa_cambio", "cambio",
    ],
    # ── Saldo adeudado (CxC) ─────────────────────────────────────
    "saldo_adeudado": [
        "saldo", "balance", "importe_pendiente", "saldo_usd",
        "saldo_adeudo", "adeudo", "deuda", "monto_pendiente",
    ],
    # ── Días vencido (CxC) ───────────────────────────────────────
    "dias_vencido": [
        "dias_vencidos", "overdue_days", "dias_overdue",
        "dias_de_vencimiento", "vencido_dias",
    ],
    # ── RFC ───────────────────────────────────────────────────────
    "rfc": [
        "rfc_receptor", "rfc_cliente", "tax_id",
    ],
    # ── Días crédito (catálogo) ───────────────────────────────────
    "credito_dias": [
        "plazo_credito", "dias_credito", "dias_de_credito",
        "terminos_pago", "payment_terms",
    ],
}

# Campos obligatorios por esquema (para validación)
SCHEMA_VENTAS = {
    "obligatorios": ["fecha", "importe", "linea_de_negocio", "producto", "cliente"],
    "recomendados": ["vendedor"],
    "opcionales":   ["canal", "region", "moneda", "tipo_cambio"],
}
SCHEMA_CXC = {
    "obligatorios": ["fecha", "cliente", "saldo_adeudado", "dias_vencido"],
    "recomendados": ["vendedor"],
    "opcionales":   ["linea_de_negocio", "moneda"],
}
SCHEMA_CATALOGO = {
    "obligatorios": ["cliente"],
    "recomendados": ["vendedor", "region"],
    "opcionales":   ["rfc", "canal", "credito_dias"],
}

# =====================================================================
# CONSTANTES DE NEGOCIO
# =====================================================================

# Días de crédito estándar cuando no existe columna en datos
DIAS_CREDITO_ESTANDAR = 30  # Estándar industrial B2B en México

# Límite para considerar un archivo grande (en filas)
LIMITE_FILAS_GRANDE = 10_000

# Separador para normalización de texto
SEPARADOR_NORMALIZADO = '_'

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
# THRESHOLDS DE NEGOCIO - CxC
# =====================================================================

# Días de vencimiento para clasificación de cartera
DIAS_VENCIDO_RIESGO = 30  # Después de este punto, la cuenta se considera en riesgo
DIAS_VENCIDO_CRITICO = 90  # Después de este punto, la cuenta se considera crítica/incobrable

# Scores de salud financiera
SCORE_SALUD_EXCELENTE = 80  # Score >= 80: Excelente salud financiera
SCORE_SALUD_BUENO = 60      # Score >= 60: Buena salud financiera
SCORE_SALUD_REGULAR = 40    # Score >= 40: Salud financiera regular
# Score < 40: Salud financiera crítica

# Límites de visualización
LIMITE_TOP_DEUDORES = 10    # Cantidad de deudores top a mostrar en reportes
LIMITE_TOP_PRODUCTOS = 10   # Cantidad de productos top a mostrar en reportes

# Colores para gráficos (paleta consistente)
COLORES_GRAFICO_VENTAS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
COLORES_GRAFICO_CXC = ['#2ecc71', '#f39c12', '#e74c3c', '#95a5a6']  # Verde, amarillo, rojo, gris

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

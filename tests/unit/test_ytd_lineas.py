"""
Tests unitarios para main/ytd_lineas.py
Valida cálculos YTD, métricas agregadas y generación de reportes.

Coverage objetivo: 40%+ en main/ytd_lineas.py (funciones core, sin UI)
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
import io


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def df_ventas_ytd():
    """DataFrame con ventas simuladas para 2 años completos."""
    fechas_2025 = pd.date_range('2025-01-01', '2025-12-31', freq='D')
    fechas_2026 = pd.date_range('2026-01-01', '2026-02-15', freq='D')  # Parcial
    
    datos_2025 = []
    for fecha in fechas_2025:
        datos_2025.append({
            'fecha': fecha,
            'ventas_usd': 10000 + (fecha.day * 100),  # Ventas varían por día
            'linea_de_negocio': 'Producto A' if fecha.month % 2 == 0 else 'Producto B',
            'producto': f'SKU-{fecha.month:02d}',
            'cliente': f'Cliente-{(fecha.day % 5) + 1}'
        })
    
    datos_2026 = []
    for fecha in fechas_2026:
        datos_2026.append({
            'fecha': fecha,
            'ventas_usd': 12000 + (fecha.day * 150),  # Crecimiento vs 2025
            'linea_de_negocio': 'Producto A' if fecha.month % 2 == 0 else 'Producto B',
            'producto': f'SKU-{fecha.month:02d}',
            'cliente': f'Cliente-{(fecha.day % 5) + 1}'
        })
    
    df = pd.DataFrame(datos_2025 + datos_2026)
    return df


@pytest.fixture
def df_ventas_sin_opcionales():
    """DataFrame sin columnas opcionales (producto, cliente)."""
    fechas = pd.date_range('2026-01-01', '2026-01-31', freq='D')
    
    datos = []
    for fecha in fechas:
        datos.append({
            'fecha': fecha,
            'ventas_usd': 5000,
            'linea_de_negocio': 'Producto A'
        })
    
    return pd.DataFrame(datos)


# ═══════════════════════════════════════════════════════════════════════
# TESTS: calcular_ytd
# ═══════════════════════════════════════════════════════════════════════

def test_calcular_ytd_año_completo(df_ventas_ytd):
    """Test: Calcula YTD para todo el año 2025."""
    from main.ytd_lineas import calcular_ytd
    
    fecha_corte = datetime(2025, 12, 31)
    resultado = calcular_ytd(df_ventas_ytd, año=2025, fecha_corte=fecha_corte)
    
    # Debe retornar todos los registros de 2025 (365 días)
    assert len(resultado) == 365
    assert all(resultado['fecha'].dt.year == 2025)
    assert resultado['ventas_usd'].sum() > 0


def test_calcular_ytd_fecha_parcial(df_ventas_ytd):
    """Test: Calcula YTD hasta fecha parcial (primeros 45 días)."""
    from main.ytd_lineas import calcular_ytd
    
    fecha_corte = datetime(2026, 2, 14)
    resultado = calcular_ytd(df_ventas_ytd, año=2026, fecha_corte=fecha_corte)
    
    # Debe retornar solo registros hasta el 14 de febrero (45 días)
    assert len(resultado) == 45
    assert all(resultado['fecha'] <= fecha_corte)
    assert resultado['fecha'].min() == pd.Timestamp('2026-01-01')
    assert resultado['fecha'].max() == pd.Timestamp('2026-02-14')


def test_calcular_ytd_sin_fecha_corte(df_ventas_ytd):
    """Test: Usa fecha actual si no se especifica fecha_corte."""
    from main.ytd_lineas import calcular_ytd
    
    # Sin fecha_corte, debe usar datetime.now()
    resultado = calcular_ytd(df_ventas_ytd, año=2026)
    
    # Debe retornar registros hasta fecha actual del año 2026
    assert len(resultado) > 0
    assert all(resultado['fecha'].dt.year == 2026)


def test_calcular_ytd_año_sin_datos(df_ventas_ytd):
    """Test: Retorna DataFrame vacío si no hay datos para el año."""
    from main.ytd_lineas import calcular_ytd
    
    fecha_corte = datetime(2024, 6, 30)
    resultado = calcular_ytd(df_ventas_ytd, año=2024, fecha_corte=fecha_corte)
    
    # No hay datos para 2024
    assert len(resultado) == 0
    assert resultado.empty


# ═══════════════════════════════════════════════════════════════════════
# TESTS: calcular_metricas_ytd
# ═══════════════════════════════════════════════════════════════════════

def test_calcular_metricas_ytd_basico(df_ventas_ytd):
    """Test: Calcula métricas correctas para período YTD."""
    from main.ytd_lineas import calcular_ytd, calcular_metricas_ytd
    
    # Calcular YTD para primeros 30 días de 2026
    fecha_corte = datetime(2026, 1, 30)
    df_ytd = calcular_ytd(df_ventas_ytd, año=2026, fecha_corte=fecha_corte)
    
    metricas = calcular_metricas_ytd(df_ytd)
    
    # Validar estructura
    assert 'total_ytd' in metricas
    assert 'dias_transcurridos' in metricas
    assert 'promedio_diario' in metricas
    assert 'proyeccion_anual' in metricas
    
    # Validar cálculos
    assert metricas['total_ytd'] == df_ytd['ventas_usd'].sum()
    assert metricas['dias_transcurridos'] >= 30
    assert metricas['promedio_diario'] == metricas['total_ytd'] / metricas['dias_transcurridos']
    assert metricas['proyeccion_anual'] == metricas['promedio_diario'] * 365


def test_calcular_metricas_ytd_año_historico(df_ventas_ytd):
    """Test: Para años históricos, usa 365 días (no fecha actual)."""
    from main.ytd_lineas import calcular_ytd, calcular_metricas_ytd
    
    # Año 2025 completo (histórico)
    fecha_corte = datetime(2025, 12, 31)
    df_ytd = calcular_ytd(df_ventas_ytd, año=2025, fecha_corte=fecha_corte)
    
    metricas = calcular_metricas_ytd(df_ytd)
    
    # Para año histórico, debe considerar 365 días
    assert metricas['dias_transcurridos'] == 365


def test_calcular_metricas_ytd_dataframe_vacio():
    """Test: Maneja DataFrame vacío sin errores."""
    from main.ytd_lineas import calcular_metricas_ytd
    
    df_vacio = pd.DataFrame(columns=['fecha', 'ventas_usd'])
    
    metricas = calcular_metricas_ytd(df_vacio)
    
    # Debe retornar métricas con valores por defecto
    assert metricas['total_ytd'] == 0
    assert metricas['dias_transcurridos'] == 1
    assert metricas['promedio_diario'] == 0
    assert metricas['proyeccion_anual'] == 0


# ═══════════════════════════════════════════════════════════════════════
# TESTS: crear_tabla_top_productos
# ═══════════════════════════════════════════════════════════════════════

def test_crear_tabla_top_productos_exitoso(df_ventas_ytd):
    """Test: Crea tabla con top productos ordenados por ventas."""
    from main.ytd_lineas import calcular_ytd, crear_tabla_top_productos
    
    df_ytd = calcular_ytd(df_ventas_ytd, año=2026, fecha_corte=datetime(2026, 2, 15))
    
    resultado = crear_tabla_top_productos(df_ytd, n=5)
    
    # Validar estructura
    assert resultado is not None
    assert len(resultado) <= 5
    assert list(resultado.columns) == ['Producto', 'Línea', 'Ventas USD']
    
    # Validar orden descendente
    ventas = resultado['Ventas USD'].values
    assert all(ventas[i] >= ventas[i+1] for i in range(len(ventas)-1))


def test_crear_tabla_top_productos_sin_columna_producto(df_ventas_sin_opcionales):
    """Test: Retorna None si no existe columna 'producto'."""
    from main.ytd_lineas import crear_tabla_top_productos
    
    resultado = crear_tabla_top_productos(df_ventas_sin_opcionales, n=10)
    
    assert resultado is None


def test_crear_tabla_top_productos_n_mayor_que_productos(df_ventas_ytd):
    """Test: Si n > cantidad de productos, retorna todos los disponibles."""
    from main.ytd_lineas import calcular_ytd, crear_tabla_top_productos
    
    df_ytd = calcular_ytd(df_ventas_ytd, año=2026, fecha_corte=datetime(2026, 2, 15))
    
    # Solicitar top 100, pero hay menos productos
    resultado = crear_tabla_top_productos(df_ytd, n=100)
    
    # Debe retornar todos los productos disponibles
    productos_unicos = df_ytd['producto'].nunique()
    assert len(resultado) == productos_unicos


# ═══════════════════════════════════════════════════════════════════════
# TESTS: crear_tabla_top_clientes
# ═══════════════════════════════════════════════════════════════════════

def test_crear_tabla_top_clientes_exitoso(df_ventas_ytd):
    """Test: Crea tabla con top clientes ordenados por ventas."""
    from main.ytd_lineas import calcular_ytd, crear_tabla_top_clientes
    
    df_ytd = calcular_ytd(df_ventas_ytd, año=2026, fecha_corte=datetime(2026, 2, 15))
    
    resultado = crear_tabla_top_clientes(df_ytd, n=3)
    
    # Validar estructura
    assert resultado is not None
    assert len(resultado) <= 3
    assert list(resultado.columns) == ['Cliente', 'Línea', 'Ventas USD']
    
    # Validar orden descendente
    ventas = resultado['Ventas USD'].values
    assert all(ventas[i] >= ventas[i+1] for i in range(len(ventas)-1))


def test_crear_tabla_top_clientes_sin_columna_cliente(df_ventas_sin_opcionales):
    """Test: Retorna None si no existe columna 'cliente'."""
    from main.ytd_lineas import crear_tabla_top_clientes
    
    resultado = crear_tabla_top_clientes(df_ventas_sin_opcionales, n=10)
    
    assert resultado is None


# ═══════════════════════════════════════════════════════════════════════
# TESTS: exportar_excel_ytd
# ═══════════════════════════════════════════════════════════════════════

def test_exportar_excel_ytd_estructura_basica(df_ventas_ytd):
    """Test: Genera archivo Excel con hojas correctas."""
    from main.ytd_lineas import calcular_ytd, exportar_excel_ytd
    
    df_ytd = calcular_ytd(df_ventas_ytd, año=2026, fecha_corte=datetime(2026, 2, 15))
    
    output_bytes = exportar_excel_ytd(df_ytd, año=2026)
    
    # Validar que se generó un BytesIO
    assert isinstance(output_bytes, io.BytesIO)
    assert output_bytes.tell() == 0  # Cursor al inicio
    
    # Leer Excel generado
    excel_data = pd.read_excel(output_bytes, sheet_name=None, engine='openpyxl')
    
    # Validar hojas mínimas
    assert 'Resumen Ejecutivo' in excel_data
    assert 'Por Línea' in excel_data
    assert 'Desglose Mensual' in excel_data
    assert 'Top Productos' in excel_data
    assert 'Top Clientes' in excel_data


def test_exportar_excel_ytd_resumen_ejecutivo(df_ventas_ytd):
    """Test: Hoja 'Resumen Ejecutivo' contiene métricas correctas."""
    from main.ytd_lineas import calcular_ytd, exportar_excel_ytd
    
    df_ytd = calcular_ytd(df_ventas_ytd, año=2026, fecha_corte=datetime(2026, 2, 15))
    
    output_bytes = exportar_excel_ytd(df_ytd, año=2026)
    
    # Leer hoja Resumen Ejecutivo
    df_resumen = pd.read_excel(output_bytes, sheet_name='Resumen Ejecutivo', engine='openpyxl')
    
    # Validar columnas
    assert 'Métrica' in df_resumen.columns
    assert 'Valor' in df_resumen.columns
    
    # Validar que contiene métricas esperadas
    metricas = df_resumen['Métrica'].tolist()
    assert 'Total Ventas YTD' in metricas
    assert 'Días Transcurridos' in metricas
    assert 'Promedio Diario' in metricas
    assert 'Proyección Anual' in metricas


def test_exportar_excel_ytd_con_comparativo(df_ventas_ytd):
    """Test: Incluye hoja 'Comparativo Años' si se proporciona."""
    from main.ytd_lineas import calcular_ytd, exportar_excel_ytd
    
    df_ytd = calcular_ytd(df_ventas_ytd, año=2026, fecha_corte=datetime(2026, 2, 15))
    
    # Crear DataFrame comparativo
    comparativo_df = pd.DataFrame({
        'Línea': ['Producto A', 'Producto B'],
        '2025': [1000000, 800000],
        '2026': [1200000, 950000]
    })
    
    output_bytes = exportar_excel_ytd(df_ytd, año=2026, comparativo_df=comparativo_df)
    
    # Leer Excel
    excel_data = pd.read_excel(output_bytes, sheet_name=None, engine='openpyxl')
    
    # Validar que incluye hoja comparativa
    assert 'Comparativo Años' in excel_data
    df_comp = excel_data['Comparativo Años']
    assert len(df_comp) == 2


def test_exportar_excel_ytd_sin_producto_ni_cliente(df_ventas_sin_opcionales):
    """Test: Genera Excel sin hojas Top Productos/Clientes si no existen."""
    from main.ytd_lineas import exportar_excel_ytd
    
    output_bytes = exportar_excel_ytd(df_ventas_sin_opcionales, año=2026)
    
    # Leer Excel
    excel_data = pd.read_excel(output_bytes, sheet_name=None, engine='openpyxl')
    
    # Hojas básicas deben existir
    assert 'Resumen Ejecutivo' in excel_data
    assert 'Por Línea' in excel_data
    
    # Hojas opcionales no deben existir (o estar vacías)
    # Nota: xlsxwriter puede crear hojas vacías, así que validamos contenido
    if 'Top Productos' in excel_data:
        assert len(excel_data['Top Productos']) == 0
    if 'Top Clientes' in excel_data:
        assert len(excel_data['Top Clientes']) == 0

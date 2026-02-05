"""
Módulo: AI Helper para Análisis Ejecutivo
Fecha: Febrero 2026

Funcionalidad:
- Generación de insights ejecutivos con OpenAI
- Análisis de tendencias y recomendaciones
- Resúmenes automáticos para CEO/Directivos
"""

import pandas as pd
from datetime import datetime
import json
from utils.logger import configurar_logger

logger = configurar_logger("ai_helper", nivel="INFO")

def generar_resumen_ejecutivo_ytd(df_ytd_actual, df_ytd_anterior, año_actual, año_anterior, openai_api_key):
    """
    Genera un resumen ejecutivo completo usando OpenAI.
    
    Args:
        df_ytd_actual: DataFrame con datos YTD del año actual
        df_ytd_anterior: DataFrame con datos del año anterior
        año_actual: Año en análisis
        año_anterior: Año de comparación
        openai_api_key: API key de OpenAI
    
    Returns:
        dict con secciones del reporte ejecutivo
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_api_key)
        
        # Preparar datos resumidos
        datos_analisis = preparar_datos_para_analisis(df_ytd_actual, df_ytd_anterior, año_actual, año_anterior)
        
        # Prompt estructurado para CEO
        prompt = f"""Eres un analista financiero senior reportando al CEO. Analiza los siguientes datos de ventas YTD y genera un reporte ejecutivo conciso y accionable.

DATOS:
{json.dumps(datos_analisis, indent=2)}

Genera un reporte ejecutivo con estas secciones EXACTAS (usa emojis):

1. 📊 RESUMEN EJECUTIVO (2-3 líneas)
   - Desempeño general del período

2. 🎯 HIGHLIGHTS CLAVE (bullet points)
   - Top 3 logros o métricas positivas

3. ⚠️ ÁREAS DE ATENCIÓN (bullet points)
   - Top 3 preocupaciones o áreas de mejora

4. 💡 INSIGHTS PRINCIPALES (bullet points)
   - 3-4 descubrimientos importantes de los datos

5. 🚀 RECOMENDACIONES EJECUTIVAS (bullet points)
   - 3-4 acciones específicas y priorizadas

Formato: Markdown limpio, directo, basado 100% en los datos proporcionados."""

        logger.info("Solicitando análisis ejecutivo a OpenAI...")
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un analista financiero experto que genera reportes ejecutivos concisos y accionables para CEOs."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        reporte = response.choices[0].message.content
        logger.info("Reporte ejecutivo generado exitosamente")
        
        return {
            "exito": True,
            "reporte": reporte,
            "tokens_usados": response.usage.total_tokens,
            "modelo": response.model
        }
        
    except Exception as e:
        logger.error(f"Error al generar reporte ejecutivo: {e}")
        return {
            "exito": False,
            "error": str(e)
        }

def preparar_datos_para_analisis(df_actual, df_anterior, año_actual, año_anterior):
    """Prepara un resumen de datos para enviar a OpenAI."""
    
    # Totales
    total_actual = df_actual['ventas_usd'].sum()
    total_anterior = df_anterior['ventas_usd'].sum() if not df_anterior.empty else 0
    
    crecimiento_pct = 0
    if total_anterior > 0:
        crecimiento_pct = ((total_actual - total_anterior) / total_anterior) * 100
    
    # Por línea de negocio
    ventas_linea_actual = df_actual.groupby('linea_de_negocio')['ventas_usd'].sum().sort_values(ascending=False)
    ventas_linea_anterior = df_anterior.groupby('linea_de_negocio')['ventas_usd'].sum() if not df_anterior.empty else pd.Series()
    
    # Calcular crecimiento por línea
    lineas_comparativo = []
    for linea in ventas_linea_actual.index:
        venta_actual = ventas_linea_actual[linea]
        venta_anterior = ventas_linea_anterior.get(linea, 0)
        
        crec = 0
        if venta_anterior > 0:
            crec = ((venta_actual - venta_anterior) / venta_anterior) * 100
        
        lineas_comparativo.append({
            "linea": linea,
            "ventas_actual": round(venta_actual, 2),
            "ventas_anterior": round(venta_anterior, 2),
            "crecimiento_pct": round(crec, 1),
            "participacion_pct": round((venta_actual / total_actual * 100), 1)
        })
    
    # Top clientes si existe la columna
    top_clientes = []
    if 'cliente' in df_actual.columns:
        top_clientes = df_actual.groupby('cliente')['ventas_usd'].sum().sort_values(ascending=False).head(5).to_dict()
        top_clientes = {k: round(v, 2) for k, v in top_clientes.items()}
    
    return {
        "periodo_analisis": f"YTD {año_actual}",
        "periodo_comparacion": f"Año completo {año_anterior}" if not df_anterior.empty else "Sin comparación",
        "total_ventas_actual": round(total_actual, 2),
        "total_ventas_anterior": round(total_anterior, 2),
        "crecimiento_pct": round(crecimiento_pct, 1),
        "numero_registros": len(df_actual),
        "lineas_negocio": lineas_comparativo[:10],  # Top 10
        "top_5_clientes": top_clientes
    }

def generar_analisis_linea_especifica(df_ytd, linea_negocio, año_actual, openai_api_key):
    """
    Genera análisis detallado de una línea de negocio específica.
    
    Args:
        df_ytd: DataFrame con datos YTD
        linea_negocio: Nombre de la línea a analizar
        año_actual: Año en análisis
        openai_api_key: API key de OpenAI
    
    Returns:
        Análisis detallado de la línea
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_api_key)
        
        # Filtrar datos de la línea
        df_linea = df_ytd[df_ytd['linea_de_negocio'] == linea_negocio].copy()
        
        if df_linea.empty:
            return {"exito": False, "error": "No hay datos para esta línea"}
        
        # Preparar datos
        total_ventas = df_linea['ventas_usd'].sum()
        num_transacciones = len(df_linea)
        
        # Por mes si existe fecha
        ventas_mes = {}
        if 'fecha' in df_linea.columns:
            df_linea['mes'] = pd.to_datetime(df_linea['fecha']).dt.month
            ventas_mes = df_linea.groupby('mes')['ventas_usd'].sum().to_dict()
            ventas_mes = {int(k): round(v, 2) for k, v in ventas_mes.items()}
        
        prompt = f"""Analiza el desempeño de la línea de negocio "{linea_negocio}" y genera un análisis ejecutivo breve.

DATOS YTD {año_actual}:
- Total ventas: ${total_ventas:,.2f}
- Número de transacciones: {num_transacciones}
- Ventas por mes: {json.dumps(ventas_mes)}

Genera un análisis breve (5-6 bullet points) que incluya:
- Evaluación del desempeño
- Tendencias mensuales identificadas
- Fortalezas observadas
- Oportunidades de mejora
- Recomendación específica

Formato: Markdown con bullets."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un analista de ventas experto que identifica patrones y oportunidades."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return {
            "exito": True,
            "analisis": response.choices[0].message.content,
            "tokens_usados": response.usage.total_tokens
        }
        
    except Exception as e:
        logger.error(f"Error al analizar línea específica: {e}")
        return {"exito": False, "error": str(e)}

def validar_api_key(api_key):
    """Valida que la API key de OpenAI sea válida."""
    if not api_key or len(api_key) < 20:
        return False, "API key inválida o muy corta"
    
    if not api_key.startswith("sk-"):
        return False, "API key debe comenzar con 'sk-'"
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        # Test simple
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        return True, "API key válida"
    except Exception as e:
        return False, f"Error al validar API key: {str(e)}"

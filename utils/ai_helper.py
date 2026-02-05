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
        
        # Prompt estructurado para CEO - Solicitar JSON
        prompt = f"""Eres un analista financiero senior reportando al CEO. Analiza los siguientes datos de ventas YTD y genera un reporte ejecutivo conciso y accionable.

DATOS:
{json.dumps(datos_analisis, indent=2, ensure_ascii=False)}

Genera un análisis ejecutivo y devuélvelo ÚNICAMENTE como un objeto JSON válido con esta estructura EXACTA:

{{
  "resumen_ejecutivo": "Párrafo de 2-3 líneas sobre desempeño general del período",
  "highlights_clave": [
    "Logro o métrica positiva 1",
    "Logro o métrica positiva 2",
    "Logro o métrica positiva 3"
  ],
  "areas_atencion": [
    "Preocupación o área de mejora 1",
    "Preocupación o área de mejora 2",
    "Preocupación o área de mejora 3"
  ],
  "insights_principales": [
    "Descubrimiento importante 1",
    "Descubrimiento importante 2",
    "Descubrimiento importante 3"
  ],
  "recomendaciones_ejecutivas": [
    "Acción específica y priorizada 1",
    "Acción específica y priorizada 2",
    "Acción específica y priorizada 3"
  ]
}}

IMPORTANTE: 
- Devuelve SOLO el JSON, sin texto adicional
- Basa tu análisis 100% en los datos proporcionados
- Sé específico con números y porcentajes
- Las recomendaciones deben ser accionables"""

        logger.info("Solicitando análisis ejecutivo a OpenAI...")
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un analista financiero experto. Respondes ÚNICAMENTE con JSON válido, sin texto adicional."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500,
            response_format={"type": "json_object"}
        )
        
        reporte_texto = response.choices[0].message.content
        logger.info("Reporte ejecutivo generado exitosamente")
        
        # Parsear JSON
        try:
            reporte_json = json.loads(reporte_texto)
            logger.info(f"JSON parseado exitosamente: {list(reporte_json.keys())}")
            return reporte_json
        except json.JSONDecodeError as e:
            logger.error(f"Error al parsear JSON de OpenAI: {e}")
            logger.error(f"Respuesta recibida: {reporte_texto[:500]}")
            return {
                "error": "Error al parsear respuesta de OpenAI",
                "reporte_raw": reporte_texto
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
        logger.warning("API key inválida: muy corta o vacía")
        return False, "API key inválida o muy corta"
    
    if not api_key.startswith("sk-"):
        logger.warning("API key no comienza con 'sk-'")
        return False, "API key debe comenzar con 'sk-'"
    
    logger.info("Validando API key con OpenAI...")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        # Test simple
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        logger.info("API key validada exitosamente")
        return True, "API key válida"
    except Exception as e:
        logger.error(f"Error al validar API key: {str(e)}")
        return False, f"Error: {str(e)[:100]}"

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

def generar_resumen_ejecutivo_ytd(df_ytd_actual, df_ytd_anterior, año_actual, año_anterior, openai_api_key, 
                                  modo_comparacion="año_completo", fecha_corte_actual=None, fecha_corte_anterior=None):
    """
    Genera un resumen ejecutivo completo usando OpenAI.
    
    Args:
        df_ytd_actual: DataFrame con datos YTD del año actual
        df_ytd_anterior: DataFrame con datos del año anterior
        año_actual: Año en análisis
        año_anterior: Año de comparación
        openai_api_key: API key de OpenAI
        modo_comparacion: "año_completo" o "ytd_equivalente"
        fecha_corte_actual: Fecha límite del período actual
        fecha_corte_anterior: Fecha límite del período anterior
    
    Returns:
        dict con secciones del reporte ejecutivo
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_api_key)
        
        # Preparar datos resumidos con información temporal
        datos_analisis = preparar_datos_para_analisis(
            df_ytd_actual, df_ytd_anterior, año_actual, año_anterior,
            modo_comparacion, fecha_corte_actual, fecha_corte_anterior
        )
        
        # Prompt estructurado para CEO - Solicitar JSON con recomendaciones 100% estructuradas
        prompt = f"""Eres un analista financiero senior reportando al CEO. Analiza los siguientes datos de ventas comparando PERÍODOS ESTRUCTURADOS.

DATOS DEL ANÁLISIS:
{json.dumps(datos_analisis, indent=2, ensure_ascii=False)}

GENERA un análisis ejecutivo y devuélvelo ÚNICAMENTE como JSON válido con esta estructura EXACTA:

{{
  "resumen_ejecutivo": "Párrafo de 2-3 líneas sobre desempeño general comparando EXPLÍCITAMENTE los dos períodos con fechas y números concretos",
  "highlights_clave": [
    "Logro específico con número/porcentaje y período",
    "Métrica positiva con cambio cuantificado entre períodos",
    "Éxito destacable con contexto temporal preciso"
  ],
  "areas_atencion": [
    "Preocupación con datos específicos y comparación entre períodos",
    "Área de mejora con métrica cuantificada y tendencia temporal",
    "Riesgo identificado con números concretos y contexto"
  ],
  "insights_principales": [
    "Descubrimiento con análisis comparativo entre períodos",
    "Patrón identificado con evidencia cuantitativa",
    "Tendencia relevante con datos específicos de ambos períodos",
    "Oportunidad estratégica basada en la comparación temporal"
  ],
  "recomendaciones_ejecutivas": [
    {{
      "accion": "Acción específica y concreta",
      "prioridad": "Alta/Media/Baja",
      "plazo": "Inmediato (1-2 semanas) / Corto (1 mes) / Mediano (3 meses)",
      "area_responsable": "Ventas/Operaciones/Finanzas/General",
      "impacto_esperado": "Descripción cuantificable del resultado esperado",
      "justificacion": "Razón específica basada en los datos de los períodos comparados"
    }},
    {{
      "accion": "Segunda acción estructurada",
      "prioridad": "Alta/Media/Baja",
      "plazo": "Inmediato/Corto/Mediano",
      "area_responsable": "Área específica",
      "impacto_esperado": "Resultado cuantificable",
      "justificacion": "Fundamento basado en datos"
    }},
    {{
      "accion": "Tercera acción estructurada",
      "prioridad": "Alta/Media/Baja",
      "plazo": "Inmediato/Corto/Mediano",
      "area_responsable": "Área específica",
      "impacto_esperado": "Resultado cuantificable",
      "justificacion": "Fundamento basado en datos"
    }}
  ]
}}

REQUISITOS CRÍTICOS:
- SIEMPRE menciona los períodos exactos comparados (fechas)
- TODOS los números deben incluir símbolo $ y formato con comas
- TODOS los porcentajes deben ser explícitos
- Las recomendaciones DEBEN estar 100% estructuradas como objetos JSON
- Cada recomendación DEBE tener los 6 campos obligatorios
- Basa TODO en los datos proporcionados, sin especulaciones
- Sé específico, directo y orientado a acción"""

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

def preparar_datos_para_analisis(df_actual, df_anterior, año_actual, año_anterior,
                                 modo_comparacion="año_completo", fecha_corte_actual=None, fecha_corte_anterior=None):
    """Prepara un resumen detallado de datos para enviar a OpenAI con información temporal estructurada."""
    
    # Información temporal estructurada
    if fecha_corte_actual:
        fecha_inicio_actual = df_actual['fecha'].min() if 'fecha' in df_actual.columns else None
        fecha_fin_actual = fecha_corte_actual.strftime('%d/%m/%Y') if fecha_corte_actual else "Presente"
        fecha_inicio_actual_str = fecha_inicio_actual.strftime('%d/%m/%Y') if fecha_inicio_actual else "01/01/" + str(año_actual)
    else:
        fecha_inicio_actual_str = f"01/01/{año_actual}"
        fecha_fin_actual = "Presente"
    
    if fecha_corte_anterior:
        fecha_inicio_anterior = df_anterior['fecha'].min() if not df_anterior.empty and 'fecha' in df_anterior.columns else None
        fecha_fin_anterior = fecha_corte_anterior.strftime('%d/%m/%Y') if fecha_corte_anterior else "31/12/" + str(año_anterior)
        fecha_inicio_anterior_str = fecha_inicio_anterior.strftime('%d/%m/%Y') if fecha_inicio_anterior else "01/01/" + str(año_anterior)
    else:
        fecha_inicio_anterior_str = f"01/01/{año_anterior}"
        fecha_fin_anterior = f"31/12/{año_anterior}"
    
    # Descripción del tipo de comparación
    tipo_comparacion = "Año Anterior Completo vs Avance Año Actual" if modo_comparacion == "año_completo" else "Período vs Período Anterior Equivalente"
    
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
        "tipo_analisis": tipo_comparacion,
        "periodo_actual": {
            "descripcion": f"Avance año {año_actual}",
            "fecha_inicio": fecha_inicio_actual_str,
            "fecha_fin": fecha_fin_actual,
            "total_ventas_usd": round(total_actual, 2),
            "numero_transacciones": len(df_actual)
        },
        "periodo_anterior": {
            "descripcion": f"{'Año completo' if modo_comparacion == 'año_completo' else 'Período anterior'} {año_anterior}",
            "fecha_inicio": fecha_inicio_anterior_str,
            "fecha_fin": fecha_fin_anterior,
            "total_ventas_usd": round(total_anterior, 2),
            "numero_transacciones": len(df_anterior) if not df_anterior.empty else 0
        },
        "comparativo": {
            "diferencia_absoluta_usd": round(total_actual - total_anterior, 2),
            "crecimiento_porcentual": round(crecimiento_pct, 1),
            "interpretacion": "Crecimiento" if crecimiento_pct > 0 else "Decrecimiento" if crecimiento_pct < 0 else "Sin cambio"
        },
        "lineas_negocio_detalle": lineas_comparativo[:10],
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

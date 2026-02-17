"""
Módulo: AI Helper - Integración con OpenAI GPT-4o-mini
Autor: Dashboard Fradma
Fecha: Febrero 2026

Funcionalidad:
- Validación de API key de OpenAI
- Generación de análisis ejecutivos automáticos
- Insights estratégicos basados en datos YTD
"""

import json
import os
from openai import OpenAI
from utils.logger import configurar_logger

# Configurar logger
logger = configurar_logger("ai_helper", nivel="INFO")


def validar_api_key(api_key: str) -> bool:
    """
    Valida que la API key de OpenAI sea válida.
    
    Args:
        api_key: String con la API key
        
    Returns:
        True si es válida, False en caso contrario
    """
    try:
        logger.info("Validando API key con OpenAI...")
        client = OpenAI(api_key=api_key)
        # Hacer una llamada simple para validar
        client.models.list()
        logger.info("API key validada exitosamente")
        return True
    except Exception as e:
        logger.error(f"Error validando API key: {e}")
        return False


def generar_resumen_ejecutivo_ytd(
    ventas_ytd_actual: float,
    ventas_ytd_anterior: float,
    crecimiento_pct: float,
    dias_transcurridos: int,
    proyeccion_anual: float,
    linea_top: str,
    ventas_linea_top: float,
    api_key: str,
    datos_lineas: dict = None
) -> dict:
    """
    Genera un análisis ejecutivo estructurado usando OpenAI GPT-4o-mini.
    
    Args:
        ventas_ytd_actual: Total de ventas YTD año actual
        ventas_ytd_anterior: Total de ventas YTD año anterior
        crecimiento_pct: Porcentaje de crecimiento
        dias_transcurridos: Días transcurridos en el año
        proyeccion_anual: Proyección de ventas para fin de año
        linea_top: Nombre de la línea de negocio con mayor venta
        ventas_linea_top: Ventas de la línea top
        api_key: API key de OpenAI
        datos_lineas: Diccionario opcional con datos detallados por línea
        
    Returns:
        Diccionario con el análisis estructurado
    """
    try:
        logger.info("Solicitando análisis ejecutivo a OpenAI...")
        
        # Preparar contexto para el análisis
        contexto = f"""
Analiza los siguientes datos YTD (Year-to-Date) de ventas y genera un análisis ejecutivo profesional:

⚠️ IMPORTANTE - CONTEXTO DE COMPARACIÓN:
- Estamos comparando PERIODOS EQUIVALENTES (mismo rango de días del año)
- YTD Actual = Primeros {dias_transcurridos} días del año ACTUAL
- YTD Anterior = Primeros {dias_transcurridos} días del año ANTERIOR
- NO estamos comparando contra el año anterior COMPLETO

MÉTRICAS PRINCIPALES:
- Ventas YTD Actual ({dias_transcurridos} días): ${ventas_ytd_actual:,.2f}
- Ventas YTD Año Anterior (mismos {dias_transcurridos} días): ${ventas_ytd_anterior:,.2f}
- Crecimiento YTD vs mismo período: {crecimiento_pct:+.1f}%
- Progreso en el año: {dias_transcurridos}/365 días ({dias_transcurridos/365*100:.1f}%)
- Proyección Anual (a este ritmo): ${proyeccion_anual:,.2f}

LÍNEA DE NEGOCIO TOP:
- {linea_top}: ${ventas_linea_top:,.2f}
"""
        
        if datos_lineas:
            contexto += "\n\nDETALLE POR LÍNEA DE NEGOCIO:\n"
            for linea, data in list(datos_lineas.items())[:5]:  # Top 5
                contexto += f"- {linea}: ${data.get('ventas', 0):,.2f} ({data.get('crecimiento', 0):+.1f}%)\n"
        
        # Definir el prompt del sistema
        system_prompt = """Eres un analista financiero senior experto en interpretar datos de ventas YTD. 
Tu tarea es generar análisis ejecutivos concisos, accionables y estratégicos.

INSTRUCCIONES:
1. Responde ÚNICAMENTE con un objeto JSON válido
2. Usa lenguaje ejecutivo, directo y profesional
3. Enfócate en insights accionables, no solo descripción de datos
4. Identifica tendencias, riesgos y oportunidades
5. Sé específico con números cuando sea relevante

FORMATO DE RESPUESTA (JSON):
{
  "resumen_ejecutivo": "Párrafo de 2-3 líneas con el panorama general",
  "highlights_clave": ["Punto 1", "Punto 2", "Punto 3"],
  "areas_atencion": ["Riesgo/área 1", "Riesgo/área 2"],
  "insights_principales": ["Insight estratégico 1", "Insight estratégico 2"],
  "recomendaciones_ejecutivas": ["Acción recomendada 1", "Acción recomendada 2"]
}"""
        
        # Llamar a OpenAI API
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": contexto}
            ],
            temperature=0.7,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        
        # Extraer respuesta
        resultado_raw = response.choices[0].message.content
        logger.info("Reporte ejecutivo generado exitosamente")
        
        # Parsear JSON
        try:
            resultado = json.loads(resultado_raw)
            logger.info(f"JSON parseado exitosamente: {list(resultado.keys())}")
            return resultado
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de OpenAI: {e}")
            logger.debug(f"Respuesta raw: {resultado_raw}")
            return {
                "resumen_ejecutivo": "Error al procesar el análisis de IA",
                "highlights_clave": [],
                "areas_atencion": [],
                "insights_principales": [],
                "recomendaciones_ejecutivas": []
            }
            
    except Exception as e:
        logger.error(f"Error al generar reporte ejecutivo: {e}")
        return {
            "resumen_ejecutivo": f"Error al generar análisis: {str(e)}",
            "highlights_clave": [],
            "areas_atencion": [],
            "insights_principales": [],
            "recomendaciones_ejecutivas": []
        }

def generar_analisis_consolidado_ia(
    total_ventas: float,
    crecimiento_ventas_pct: float,
    total_cxc: float,
    pct_vigente_cxc: float,
    pct_critica_cxc: float,
    score_salud_cxc: float,
    periodo_analisis: str,
    api_key: str
) -> dict:
    """
    Genera un análisis ejecutivo consolidado integrando ventas y CxC.
    
    Args:
        total_ventas: Total de ventas en el período
        crecimiento_ventas_pct: Crecimiento % vs período anterior
        total_cxc: Total de cuentas por cobrar
        pct_vigente_cxc: Porcentaje de cartera vigente
        pct_critica_cxc: Porcentaje de cartera crítica (>90 días)
        score_salud_cxc: Score de salud financiera (0-100)
        periodo_analisis: Descripción del período (semanal/mensual/trimestral/anual)
        api_key: API key de OpenAI
        
    Returns:
        Diccionario con el análisis estructurado
    """
    try:
        logger.info("Solicitando análisis ejecutivo consolidado a OpenAI...")
        
        # Inicializar cliente OpenAI
        client = OpenAI(api_key=api_key)
        
        # Construir prompt
        prompt = f"""Eres un CFO experto analizando el desempeño integral del negocio.

DATOS DEL PERÍODO - {periodo_analisis}:

VENTAS:
- Total ventas: ${total_ventas:,.2f} USD
- Crecimiento vs período anterior: {crecimiento_ventas_pct:+.1f}%

CUENTAS POR COBRAR (CxC):
- Total adeudado: ${total_cxc:,.2f} USD
- Cartera vigente: {pct_vigente_cxc:.1f}%
- Cartera crítica (>90d): {pct_critica_cxc:.1f}%
- Score de salud: {score_salud_cxc:.0f}/100

ANÁLISIS REQUERIDO:
Genera un análisis ejecutivo que integre ambas dimensiones (ventas y liquidez/cobro). 
Identifica la relación entre el crecimiento de ventas y la salud de cobros.
Evalúa si el crecimiento es sostenible dada la situación de CxC.

Formato de respuesta (JSON):
{{
    "resumen_ejecutivo": "Párrafo ejecutivo de 3-4 líneas integrando ventas y CxC",
    "highlights_clave": ["3-4 puntos positivos destacados"],
    "areas_atencion": ["2-3 áreas que requieren atención inmediata"],
    "insights_principales": ["3-4 insights estratégicos conectando ventas con cobros"],
    "recomendaciones_ejecutivas": ["3-4 acciones concretas priorizadas"]
}}"""

        # Llamar a la API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un CFO experto en análisis financiero integral."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        resultado_raw = response.choices[0].message.content.strip()
        
        # Limpiar markdown si viene envuelto
        if resultado_raw.startswith("```json"):
            resultado_raw = resultado_raw[7:]
        if resultado_raw.startswith("```"):
            resultado_raw = resultado_raw[3:]
        if resultado_raw.endswith("```"):
            resultado_raw = resultado_raw[:-3]
        resultado_raw = resultado_raw.strip()
        
        logger.info("Análisis consolidado generado exitosamente")
        
        # Parsear JSON
        try:
            resultado = json.loads(resultado_raw)
            logger.info(f"JSON consolidado parseado exitosamente: {list(resultado.keys())}")
            return resultado
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON consolidado: {e}")
            logger.debug(f"Respuesta raw: {resultado_raw}")
            return {
                "resumen_ejecutivo": "Error al procesar el análisis de IA",
                "highlights_clave": [],
                "areas_atencion": [],
                "insights_principales": [],
                "recomendaciones_ejecutivas": []
            }
            
    except Exception as e:
        logger.error(f"Error al generar análisis consolidado: {e}")
        return {
            "resumen_ejecutivo": f"Error al generar análisis: {str(e)}",
            "highlights_clave": [],
            "areas_atencion": [],
            "insights_principales": [],
            "recomendaciones_ejecutivas": []
        }

def generar_resumen_ejecutivo_cxc(
    total_adeudado: float,
    vigente: float,
    vencida: float,
    critica: float,
    pct_vigente: float,
    pct_critica: float,
    score_salud: float,
    score_status: str,
    top_deudor: str,
    monto_top_deudor: float,
    indice_morosidad: float,
    casos_urgentes: int,
    alertas_count: int,
    api_key: str,
    datos_top_deudores: list = None
) -> dict:
    """
    Genera un análisis ejecutivo estructurado de CxC usando OpenAI GPT-4o-mini.
    
    Args:
        total_adeudado: Monto total de cuentas por cobrar
        vigente: Monto de cartera vigente
        vencida: Monto de cartera vencida
        critica: Monto de cartera crítica (>90 días)
        pct_vigente: Porcentaje de cartera vigente
        pct_critica: Porcentaje de cartera crítica
        score_salud: Score de salud financiera (0-100)
        score_status: Estado del score (Excelente, Buena, Regular, etc.)
        top_deudor: Nombre del principal deudor
        monto_top_deudor: Monto que adeuda el principal deudor
        indice_morosidad: Índice de morosidad
        casos_urgentes: Cantidad de casos que requieren acción urgente
        alertas_count: Cantidad de alertas activas
        api_key: API key de OpenAI
        datos_top_deudores: Lista opcional con datos de top deudores
        
    Returns:
        Diccionario con el análisis estructurado
    """
    try:
        logger.info("Solicitando análisis ejecutivo CxC a OpenAI...")
        
        # Preparar contexto para el análisis
        contexto = f"""
Analiza los siguientes datos de Cuentas por Cobrar (CxC) y genera un análisis ejecutivo profesional:

MÉTRICAS PRINCIPALES:
- Total Adeudado: ${total_adeudado:,.2f}
- Cartera Vigente: ${vigente:,.2f} ({pct_vigente:.1f}%)
- Cartera Vencida: ${vencida:,.2f} ({100-pct_vigente:.1f}%)
- Cartera Crítica (>90 días): ${critica:,.2f} ({pct_critica:.1f}%)

EVALUACIÓN DE SALUD:
- Score de Salud: {score_salud:.0f}/100
- Calificación: {score_status}
- Índice de Morosidad: {indice_morosidad:.1f}%

ALERTAS Y RIESGOS:
- Casos Urgentes: {casos_urgentes}
- Alertas Activas: {alertas_count}

PRINCIPAL DEUDOR:
- {top_deudor}: ${monto_top_deudor:,.2f} ({(monto_top_deudor/total_adeudado*100):.1f}% del total)
"""
        
        if datos_top_deudores:
            contexto += "\n\nTOP 5 DEUDORES:\n"
            for deudor_info in datos_top_deudores[:5]:
                nombre = deudor_info.get('nombre', 'N/A')
                monto = deudor_info.get('monto', 0)
                pct = deudor_info.get('porcentaje', 0)
                contexto += f"- {nombre}: ${monto:,.2f} ({pct:.1f}%)\n"
        
        # Definir el prompt del sistema
        system_prompt = """Eres un analista financiero senior experto en gestión de cuentas por cobrar y riesgo crediticio.
Tu tarea es generar análisis ejecutivos concisos, accionables y estratégicos sobre la salud de la cartera de CxC.

INSTRUCCIONES:
1. Responde ÚNICAMENTE con un objeto JSON válido
2. Usa lenguaje ejecutivo, directo y profesional
3. Enfócate en riesgos de liquidez y acciones concretas de cobranza
4. Identifica concentraciones de riesgo y deterioro de cartera
5. Prioriza recomendaciones por impacto financiero
6. Sé específico con números cuando sea relevante

FORMATO DE RESPUESTA (JSON):
{
  "resumen_ejecutivo": "Párrafo de 2-3 líneas con diagnóstico de la cartera",
  "highlights_clave": ["Punto positivo 1", "Punto positivo 2", "Punto positivo 3"],
  "areas_atencion": ["Riesgo crítico 1", "Riesgo crítico 2", "Riesgo crítico 3"],
  "insights_principales": ["Insight estratégico 1", "Insight estratégico 2"],
  "recomendaciones_ejecutivas": ["Acción prioritaria 1", "Acción prioritaria 2", "Acción prioritaria 3"]
}"""
        
        # Llamar a OpenAI API
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": contexto}
            ],
            temperature=0.7,
            max_tokens=900,
            response_format={"type": "json_object"}
        )
        
        # Extraer respuesta
        resultado_raw = response.choices[0].message.content
        logger.info("Reporte ejecutivo CxC generado exitosamente")
        
        # Parsear JSON
        try:
            resultado = json.loads(resultado_raw)
            logger.info(f"JSON CxC parseado exitosamente: {list(resultado.keys())}")
            return resultado
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de OpenAI CxC: {e}")
            logger.debug(f"Respuesta raw: {resultado_raw}")
            return {
                "resumen_ejecutivo": "Error al procesar el análisis de IA",
                "highlights_clave": [],
                "areas_atencion": [],
                "insights_principales": [],
                "recomendaciones_ejecutivas": []
            }
            
    except Exception as e:
        logger.error(f"Error al generar reporte ejecutivo CxC: {e}")
        return {
            "resumen_ejecutivo": f"Error al generar análisis: {str(e)}",
            "highlights_clave": [],
            "areas_atencion": [],
            "insights_principales": [],
            "recomendaciones_ejecutivas": []
        }
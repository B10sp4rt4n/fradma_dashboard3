"""
Módulo: AI Helper Premium - Funciones avanzadas de IA para análisis ejecutivo
Autor: Dashboard Fradma
Fecha: Febrero 2026

Funcionalidad:
- Insights estratégicos para equipo de ventas
- Análisis ejecutivo consolidado ventas + CxC
- Recomendaciones accionables sin repetir métricas
"""

import json
from openai import OpenAI
from utils.logger import configurar_logger

logger = configurar_logger("ai_helper_premium", nivel="INFO")


def generar_insights_kpi_vendedores(
    num_vendedores: int,
    ticket_promedio_general: float,
    eficiencia_general: float,
    vendedor_top: str,
    ventas_vendedor_top: float,
    vendedor_bottom: str,
    ventas_vendedor_bottom: float,
    concentracion_top3_pct: float,
    api_key: str,
    datos_vendedores: list = None,
    contexto_filtros: str = None
) -> dict:
    """
    Genera insights estratégicos sobre el desempeño del equipo de ventas.
    Enfocado en patrones, oportunidades de entrenamiento y optimización.
    
    Args:
        num_vendedores: Número total de vendedores activos
        ticket_promedio_general: Ticket promedio de ventas
        eficiencia_general: Eficiencia promedio del equipo
        vendedor_top: Nombre del mejor vendedor
        ventas_vendedor_top: Total de ventas del top performer
        vendedor_bottom: Nombre del vendedor con menor desempeño
        ventas_vendedor_bottom: Total de ventas del bottom performer
        concentracion_top3_pct: Porcentaje de ventas concentrado en top 3
        api_key: API key de OpenAI
        datos_vendedores: Lista opcional con datos detallados por vendedor
        
    Returns:
        Diccionario con insights estratégicos
    """
    try:
        logger.info("Generando insights estratégicos de vendedores con IA...")
        
        client = OpenAI(api_key=api_key)
        
        contexto_base = "Analiza el desempeño del equipo de ventas y genera insights estratégicos (NO repetir métricas)."
        
        if contexto_filtros:
            contexto_base += f"""

⚠️ IMPORTANTE - ALCANCE DEL ANÁLISIS:
{contexto_filtros}

TODOS los números y métricas presentados corresponden ÚNICAMENTE al alcance definido arriba.
"""
        
        contexto = contexto_base + f"""

EQUIPO DE VENTAS:
- Total de vendedores activos: {num_vendedores}
- Ticket promedio general: ${ticket_promedio_general:,.2f}
- Eficiencia promedio del equipo: {eficiencia_general:.1f}%

DESEMPEÑO INDIVIDUAL:
- Mejor vendedor: {vendedor_top} con ${ventas_vendedor_top:,.2f}
- Menor desempeño: {vendedor_bottom} con ${ventas_vendedor_bottom:,.2f}
- Concentración top 3: {concentracion_top3_pct:.1f}% del total
"""
        
        if datos_vendedores:
            contexto += "\n\nDETALLE DE VENDEDORES:\n"
            for vendedor in datos_vendedores[:8]:
                nombre = vendedor.get('nombre', 'N/A')
                ventas = vendedor.get('ventas', 0)
                ticket = vendedor.get('ticket_avg', 0)
                contexto += f"- {nombre}: ${ventas:,.0f} (ticket: ${ticket:,.0f})\n"
        
        system_prompt = """Eres un consultor de ventas experto en optimización de equipos comerciales.

OBJETIVO: Genera análisis ESTRATÉGICOS y ACCIONABLES (NO repitas las métricas dadas).

EN FÓCATE EN:
1. Patrones de desempeño (identificar vendedores en zona de riesgo)
2. Oportunidades de entrenamiento y capacitación
3. Estrategias para equilibrar la distribución de cartera
4. Recomendaciones específicas de coaching
5. Alertas sobre concentración de riesgo

EVITA:
- Repetir cifras ya mostradas en el dashboard
- Análisis genéricos sin acción concreta
- Recomendaciones vagas

Formato JSON:
{
  "insight_clave": "Una frase con el insight más importante detectado",
  "recomendaciones_equipos": ["Acción específica 1", "Acción específica 2", "Acción específica 3"],
  "alertas_estrategicas": ["Alerta de riesgo 1", "Alerta de riesgo 2"],
  "oportunidades_mejora": ["Oportunidad táctica 1", "Oportunidad táctica 2"]
}"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": contexto}
            ],
            temperature=0.8,
            max_tokens=600,
            response_format={"type": "json_object"}
        )
        
        resultado_raw = response.choices[0].message.content
        logger.info("Insights de vendedores generados exitosamente")
        
        try:
            resultado = json.loads(resultado_raw)
            return resultado
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de insights vendedores: {e}")
            return {
                "insight_clave": "Error al procesar insights",
                "recomendaciones_equipos": [],
                "alertas_estrategicas": [],
                "oportunidades_mejora": []
            }
            
    except Exception as e:
        logger.error(f"Error generando insights de vendedores: {e}")
        return {
            "insight_clave": f"Error: {str(e)}",
            "recomendaciones_equipos": [],
            "alertas_estrategicas": [],
            "oportunidades_mejora": []
        }


def generar_insights_ejecutivo_consolidado(
    total_ventas_periodo: float,
    crecimiento_ventas_pct: float,
    score_salud_cxc: float,
    pct_morosidad: float,
    top_linea_ventas: str,
    top_linea_cxc_critica: str,
    casos_urgentes_cxc: int,
    api_key: str
) -> dict:
    """
    Genera insights ejecutivos de alto nivel integrando ventas y CxC.
    Enfocado en correlaciones, riesgos sistémicos y decisiones estratégicas.
    
    Args:
        total_ventas_periodo: Total de ventas en el período
        crecimiento_ventas_pct: Crecimiento % vs período anterior
        score_salud_cxc: Score de salud de cartera (0-100)
        pct_morosidad: Porcentaje de morosidad
        top_linea_ventas: Línea de negocio con mayor venta
        top_linea_cxc_critica: Línea con mayor cartera crítica
        casos_urgentes_cxc: Número de casos urgentes
        api_key: API key de OpenAI
        
    Returns:
        Diccionario con insights ejecutivos
    """
    try:
        logger.info("Generando insights ejecutivos consolidados con IA...")
        
        client = OpenAI(api_key=api_key)
        
        contexto = f"""
Analiza la salud integral del negocio y genera insights ESTRATÉGICOS de alto nivel:

⚠️ IMPORTANTE - CONTEXTO DE LA DATA:
- El "crecimiento" mostrado compara PERIODOS EQUIVALENTES (ej: enero 2026 vs enero 2025)
- Si el crecimiento parece bajo/negativo, considera que NO es vs el año completo anterior
- Evita alarmas de "catástrofe" si es simplemente inicio de año vs año completo

VENTAS:
- Total del período actual: ${total_ventas_periodo:,.2f}
- Crecimiento vs mismo período año anterior: {crecimiento_ventas_pct:+.1f}%
- Línea top en ventas: {top_linea_ventas}

CUENTAS POR COBRAR:
- Score de salud: {score_salud_cxc:.0f}/100
- Morosidad: {pct_morosidad:.1f}%
- Casos urgentes: {casos_urgentes_cxc}
- Línea con mayor cartera crítica: {top_linea_cxc_critica}
"""
        
        system_prompt = """Eres un CFO experto en análisis integral de negocios.

OBJETIVO: Genera insights ESTRATÉGICOS que conecten ventas con liquidez (NO repitas cifras).

ENFÓCATE EN:
1. Correlaciones entre crecimiento de ventas y salud de cobros
2. Riesgos sistémicos no evidentes a primera vista
3. Oportunidades de mejora en políticas comerciales
4. Recomendaciones de decisiones ejecutivas prioritarias
5. Proyección de escenarios futuros

EVITA:
- Repetir métricas ya mostradas
- Análisis descriptivo sin valor estratégico
- Recomendaciones obvias

Formato JSON:
{
  "diagnostico_integral": "Evaluación de la relación ventas-cobro en 2-3 líneas",
  "riesgos_ocultos": ["Riesgo no obvio 1", "Riesgo no obvio 2"],
  "decisiones_criticas": ["Decisión ejecutiva 1", "Decisión ejecutiva 2"],
  "escenario_proyectado": "Proyección de 30-60 días basada en tendencias actuales"
}"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": contexto}
            ],
            temperature=0.8,
            max_tokens=700,
            response_format={"type": "json_object"}
        )
        
        resultado_raw = response.choices[0].message.content
        logger.info("Insights ejecutivos consolidados generados exitosamente")
        
        try:
            resultado = json.loads(resultado_raw)
            return resultado
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de insights ejecutivos: {e}")
            return {
                "diagnostico_integral": "Error al procesar análisis",
                "riesgos_ocultos": [],
                "decisiones_criticas": [],
                "escenario_proyectado": "No disponible"
            }
            
    except Exception as e:
        logger.error(f"Error generando insights ejecutivos consolidados: {e}")
        return {
            "diagnostico_integral": f"Error: {str(e)}",
            "riesgos_ocultos": [],
            "decisiones_criticas": [],
            "escenario_proyectado": "No disponible"
        }

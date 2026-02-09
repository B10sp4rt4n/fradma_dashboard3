# 🤖 Análisis Ejecutivo con IA - Módulos YTD y CxC

## 📋 Descripción

Se ha integrado análisis ejecutivo automático usando **OpenAI GPT-4o-mini** en dos módulos clave:

1. **📆 Reporte YTD (Year-to-Date)**: Análisis de ventas acumuladas y tendencias
2. **💳 KPI Cartera CxC**: Análisis de salud financiera y riesgos de cartera

Esta funcionalidad genera insights estratégicos, identifica tendencias y proporciona recomendaciones accionables basadas en los datos de negocio.

## ✨ Características

### 🎯 Análisis Estructurado

El sistema genera análisis completos que incluyen:

1. **📊 Resumen Ejecutivo**: Panorama general del desempeño en 2-3 líneas
2. **⭐ Highlights Clave**: 3 puntos destacados más importantes
3. **⚠️ Áreas de Atención**: Identificación de riesgos y áreas críticas
4. **💡 Insights Principales**: Análisis estratégicos profundos sobre tendencias
5. **🎯 Recomendaciones Ejecutivas**: Acciones concretas recomendadas

### 📊 Módulos Disponibles

#### 📆 YTD (Year-to-Date) - Análisis de Ventas

**Datos Analizados:**
- Total de ventas YTD actual vs año anterior
- Porcentaje de crecimiento/decrecimiento
- Días transcurridos del año
- Proyección anual estimada
- Desempeño por línea de negocio (top 5)
- Análisis de tendencias y patrones

**Enfoque del Análisis:**
- Identificación de oportunidades de crecimiento
- Evaluación de líneas de negocio con mejor desempeño
- Detección de productos o segmentos en declive
- Proyecciones y escenarios futuros

#### 💳 CxC (Cuentas por Cobrar) - Salud Financiera

**Datos Analizados:**
- Monto total de cartera por cobrar
- Distribución: vigente, vencida y crítica (>90 días)
- Score de salud financiera (0-100)
- Índice de morosidad
- Top 5 deudores y concentración de riesgo
- Casos urgentes y alertas activas

**Enfoque del Análisis:**
- Evaluación de riesgos de liquidez
- Identificación de concentraciones peligrosas
- Priorización de acciones de cobranza
- Recomendaciones para mejorar flujo de efectivo
- Detección de deterioro de cartera

#### 📊 Reporte Consolidado - Dashboard Ejecutivo

**Datos Analizados:**
- Ventas totales por período (semanal/mensual/trimestral/anual)
- Estado completo de cuentas por cobrar
- Métricas de crecimiento inter-período
- Distribución de cartera (vigente/vencida/crítica)
- Tendencias y proyecciones

**Enfoque del Análisis:**
- Visión integral del negocio (ventas + liquidez)
- Balance entre crecimiento y flujo de caja
- Identificación de riesgos sistémicos
- Recomendaciones estratégicas holísticas
- Optimización del ciclo completo de conversión

## 🚀 Cómo Usar

### Paso 1: Obtener API Key de OpenAI

1. Crea una cuenta en [OpenAI](https://platform.openai.com/)
2. Ve a [API Keys](https://platform.openai.com/api-keys)
3. Crea una nueva API key y cópiala

### Paso 2: Configurar en la Aplicación

#### Opción A: Variable de Entorno (Recomendada)

```bash
export OPENAI_API_KEY="tu-api-key-aqui"
python -m streamlit run app.py
```

#### Opción B: Ingreso Manual en la Interfaz

**Para módulo YTD:**
1. Abre la aplicación Streamlit
2. Navega al módulo "📆 YTD por Línea de Negocio"
3. En la barra lateral, busca la sección "🤖 Análisis con IA"
4. Activa el checkbox "Habilitar Análisis Ejecutivo con IA"
5. Ingresa tu OpenAI API Key en el campo de texto (si no está en variable de entorno)

**Para módulo CxC:**
1. Abre la aplicación Streamlit
2. Navega al módulo "💳 KPI Cartera CxC"
3. En la barra lateral, busca la sección "🤖 Análisis con IA"
4. Activa el checkbox "Habilitar Análisis Ejecutivo con IA"
5. Ingresa tu OpenAI API Key en el campo de texto (si no está en variable de entorno)

**Para módulo Reporte Consolidado:**
1. Abre la aplicación Streamlit
2. Navega al módulo "📊 Reporte Consolidado"
3. En la barra lateral, selecciona la periodicidad deseada (semanal/mensual/trimestral/anual)
4. En la sección "🤖 Análisis con IA", activa el checkbox
5. Ingresa tu OpenAI API Key en el campo de texto (si no está en variable de entorno)

### Paso 3: Generar Análisis

1. Configura los filtros necesarios (año, líneas de negocio, etc.)
2. El análisis se generará automáticamente al activar la opción
3. El proceso toma aproximadamente 5-10 segundos
4. Los resultados aparecen en una sección dedicada debajo de las métricas principales

## 💰 Costos

El análisis utiliza **GPT-4o-mini**, que es económico:
- ~$0.15 por millón de tokens de entrada
- ~$0.60 por millón de tokens de salida
- **Costo promedio por análisis: < $0.01 USD**

## 🔒 Seguridad

- Las API keys nunca se almacenan en la aplicación
- Se recomienda usar variables de entorno en producción
- La comunicación con OpenAI está encriptada (HTTPS)
- No se envían datos sensibles de clientes individuales

## 📝 Ejemplos de Análisis Generados

### Ejemplo 1: Análisis YTD (Ventas)

```
🤖 Análisis Ejecutivo con IA

📋 Resumen Ejecutivo
El desempeño YTD muestra un crecimiento sólido del 15.3% comparado con 
el año anterior, impulsado principalmente por Ultra Plast y Dykem. La 
proyección anual sugiere superar los objetivos del año.

⭐ Highlights Clave
- Ultra Plast lidera con $2.5M en ventas (+22% vs año anterior)
- Crecimiento consistente en 7 de 10 líneas de negocio
- 45% del año transcurrido con 52% de las ventas proyectadas

⚠️ Áreas de Atención
- Repi muestra una caída del 8% que requiere intervención inmediata
- La estacionalidad indica un posible desaceleramiento en Q3

💡 Insights Principales
- La diversificación de líneas reduce el riesgo de concentración
- El ritmo actual sugiere cerrar el año con un 18% de crecimiento

🎯 Recomendaciones Ejecutivas
- Investigar las causas de la caída en Repi y diseñar plan de acción
- Capitalizar el momentum de Ultra Plast con campañas agresivas
```

### Ejemplo 2: Análisis CxC (Cuentas por Cobrar)

```
🤖 Análisis Ejecutivo con IA

📋 Resumen Ejecutivo
La cartera de CxC presenta una salud financiera Regular (62/100) con 
$1.2M en cuentas por cobrar. El 35% de la cartera está vencida y 
existen 8 casos urgentes que requieren acción inmediata.

⭐ Highlights Clave
- 65% de la cartera se mantiene vigente ($780K)
- Solo 12% en categoría crítica (>90 días)
- Score de salud mejoró 5 puntos vs mes anterior

⚠️ Áreas de Atención
- Cliente ABC concentra el 28% del total ($336K) - riesgo alto
- 8 casos urgentes sin gestión reciente de cobranza
- Incremento del 15% en cartera vencida 30-60 días

💡 Insights Principales
- La concentración en top 3 clientes (45%) representa vulnerabilidad
- El índice de morosidad del 35% está por encima del benchmark (25%)
- La cartera crítica es manejable pero requiere seguimiento constante

🎯 Recomendaciones Ejecutivas
- Priorizar cobranza inmediata a los 8 casos urgentes
- Establecer límites de crédito más estrictos para Cliente ABC
- Implementar llamadas de seguimiento semanales para cartera 30-60 días
- Considerar incentivos por pronto pago para reducir morosidad
```

### Ejemplo 3: Análisis Consolidado (Integración Ventas + CxC)

```
🤖 Análisis Ejecutivo con IA

📋 Resumen Ejecutivo
El negocio muestra un crecimiento sostenido del 12% en ventas mensuales, pero 
presenta riesgos en liquidez con un 38% de CxC vencida. Es crítico balancear 
el crecimiento comercial con mejoras inmediatas en eficiencia de cobranza.

⭐ Highlights Clave
- Ventas mensuales crecieron 12% vs período anterior
- Se mantiene momentum comercial positivo en 3 trimestres consecutivos
- 62% de cartera CxC permanece vigente

⚠️ Áreas de Atención
- 38% de cartera vencida compromete flujo de caja operativo
- Riesgo de descalce entre ingresos y liquidez disponible
- Crecimiento en ventas no se refleja proporcionalmente en cobros

💡 Insights Principales
- Existe desconexión entre área comercial y cobranza
- El crecimiento sin control de CxC puede generar crisis de liquidez
- Score de salud CxC (65/100) requiere acciones correctivas inmediatas

🎯 Recomendaciones Ejecutivas
- Implementar política de crédito más estricta para nuevos clientes
- Vincular bonos de ventas a indicadores de cobranza efectiva
- Establecer comité semanal de revisión de cartera vencida
- Considerar factoring para cartera >60 días si persiste el problema
```

```
🤖 Análisis Ejecutivo con IA

📋 Resumen Ejecutivo
La cartera de CxC presenta una salud financiera Regular (62/100) con 
$1.2M en cuentas por cobrar. El 35% de la cartera está vencida y 
existen 8 casos urgentes que requieren acción inmediata.

⭐ Highlights Clave
- 65% de la cartera se mantiene vigente ($780K)
- Solo 12% en categoría crítica (>90 días)
- Score de salud mejoró 5 puntos vs mes anterior

⚠️ Áreas de Atención
- Cliente ABC concentra el 28% del total ($336K) - riesgo alto
- 8 casos urgentes sin gestión reciente de cobranza
- Incremento del 15% en cartera vencida 30-60 días

💡 Insights Principales
- La concentración en top 3 clientes (45%) representa vulnerabilidad
- El índice de morosidad del 35% está por encima del benchmark (25%)
- La cartera crítica es manejable pero requiere seguimiento constante

🎯 Recomendaciones Ejecutivas
- Priorizar cobranza inmediata a los 8 casos urgentes
- Establecer límites de crédito más estrictos para Cliente ABC
- Implementar llamadas de seguimiento semanales para cartera 30-60 días
- Considerar incentivos por pronto pago para reducir morosidad
```

## 🛠️ Solución de Problemas

### Error: "API key inválida"
- Verifica que copiaste la API key completa
- Asegúrate de que la key no haya expirado
- Revisa que tienes créditos disponibles en OpenAI

### Error: "No se pudo generar el análisis"
- Verifica tu conexión a internet
- Revisa los logs en `/logs/ai_helper_*.log`
- Asegúrate de tener datos YTD disponibles

### El análisis tarda mucho
- GPT-4o-mini generalmente responde en 5-10 segundos
- Si tarda más, puede ser un problema de conectividad
- Intenta refrescar la página

## 📚 Documentación Técnica

### Archivos Modificados

- `utils/ai_helper.py`: Módulo de integración con OpenAI (2 funciones de análisis)
- `main/ytd_lineas.py`: Integración del análisis YTD en la UI
- `main/kpi_cpc.py`: Integración del análisis CxC en la UI
- `requirements.txt`: Agregado `openai`

### Funciones Principales

```python
# Validar API key
validar_api_key(api_key: str) -> bool

# Generar análisis ejecutivo YTD
generar_resumen_ejecutivo_ytd(
    ventas_ytd_actual: float,
    ventas_ytd_anterior: float,
    crecimiento_pct: float,
    dias_transcurridos: int,
    proyeccion_anual: float,
    linea_top: str,
    ventas_linea_top: float,
    api_key: str,
    datos_lineas: dict = None
) -> dict

# Generar análisis ejecutivo CxC
generar_resumen_ejecutivo_cxc(
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
) -> dict
```

## 🔄 Actualizaciones Futuras

Próximas mejoras planeadas:
- [x] Análisis ejecutivo para módulo CxC ✅
- [ ] Análisis comparativo multi-año
- [ ] Detección automática de anomalías con ML
- [ ] Generación de reportes PDF con IA
- [ ] Análisis predictivo de tendencias
- [ ] Recomendaciones personalizadas por línea de negocio
- [ ] Análisis de comparativo año vs año con insights
- [ ] Integración con análisis de heatmap de ventas

## 📞 Soporte

Para problemas o sugerencias:
- Revisa los logs en `/logs/ai_helper_*.log`
- Consulta la documentación de OpenAI
- Abre un issue en el repositorio

---

**Versión:** 1.0  
**Fecha:** Febrero 2026  
**Modelo:** GPT-4o-mini  
**Estado:** ✅ Producción

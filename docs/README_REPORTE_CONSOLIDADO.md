# 📊 Módulo de Reporte Consolidado

## 🎯 Descripción

El **Reporte Consolidado** es un dashboard ejecutivo que integra datos de ventas y cuentas por cobrar (CxC) en una sola vista, proporcionando una visión holística del desempeño del negocio.

## ✨ Características Principales

### 📈 Análisis de Ventas por Período
- **Periodicidad flexible**: Semanal, mensual, trimestral o anual
- **Gráficos combinados**: Barras + línea de tendencia
- **Métricas clave**: Total ventas, promedio por período, crecimiento
- **Tabla detallada**: Con crecimiento inter-período

### 💳 Estado de Cuentas por Cobrar
- **Gráfico de pie**: Distribución vigente/vencida/crítica
- **Métricas de salud**: Score 0-100 y clasificación
- **Integración visual**: Datos CxC junto a ventas

### 🤖 Análisis con IA (Opcional)
- **GPT-4o-mini**: Análisis ejecutivo consolidado
- **Enfoque integral**: Conecta ventas con liquidez
- **Recomendaciones estratégicas**: Acciones para optimizar el ciclo completo

## 📊 Métricas Mostradas

### KPIs Principales (4 Cards)
1. **💰 Total Ventas**: Monto total del período + crecimiento
2. **📊 Promedio por Período**: Promedio de ventas + cantidad de períodos
3. **💳 Total CxC**: Cartera total + % vigente
4. **🏥 Salud CxC**: Score de salud + clasificación

### Visualizaciones
1. **Gráfico de Ventas**: Barras + línea de tendencia por período
2. **Gráfico Pie CxC**: Distribución en 5 categorías
   - Vigente (verde)
   - Vencida 0-30 días (amarillo)
   - Vencida 30-60 días (naranja)
   - Vencida 60-90 días (rojo claro)
   - Crítica >90 días (rojo)

### Tabla Detallada
- Período
- Ventas USD
- Crecimiento % vs período anterior
- Formato condicional (gradiente rojo-verde)

## 🚀 Cómo Usar

### 1. Cargar Datos

El módulo requiere:
- ✅ **Datos de Ventas**: Obligatorio (archivo principal)
- ⚠️ **Datos de CxC**: Opcional (si no están, solo muestra ventas)

**Formato de Datos de Ventas:**
- Columnas: `fecha`, `ventas_usd` (o variantes)
- Archivo: CSV o Excel

**Formato de Datos de CxC:**
- Hojas: `CXC VIGENTES` y `CXC VENCIDAS`
- Archivo: Excel con las hojas requeridas

### 2. Seleccionar Periodicidad

En el sidebar, selecciona:
- 📆 **Semanal**: Análisis semana por semana
- 📅 **Mensual**: Análisis mes por mes (recomendado)
- 📊 **Trimestral**: Análisis trimestral
- 📈 **Anual**: Análisis año por año

### 3. Activar Análisis con IA (Opcional)

Si quieres insights automáticos:
1. Habilita el checkbox "🤖 Análisis Consolidado con IA"
2. Ingresa tu OpenAI API Key (o configúrala como variable de entorno)
3. El análisis se genera automáticamente

## 📋 Ejemplo de Uso

### Caso 1: Solo Ventas
```
1. Sube archivo de ventas (CSV/Excel)
2. Selecciona "📊 Reporte Consolidado" en el menú
3. Elige periodicidad: "Mensual"
4. Visualiza:
   - Total ventas y tendencias
   - Promedio mensual
   - Gráfico de evolución
   - Tabla detallada
```

### Caso 2: Ventas + CxC
```
1. Sube archivo Excel con:
   - Datos de ventas en hoja principal
   - CXC VIGENTES y CXC VENCIDAS en hojas adicionales
2. Selecciona "📊 Reporte Consolidado"
3. Elige periodicidad: "Mensual"
4. Visualiza:
   - Todo lo anterior +
   - Distribución de CxC (pie chart)
   - Score de salud financiera
   - Estado de cartera
```

### Caso 3: Análisis Completo con IA
```
1. Carga archivo completo (ventas + CxC)
2. Selecciona periodicidad deseada
3. Activa análisis con IA
4. Obtén:
   - Resumen ejecutivo automático
   - Highlights clave
   - Áreas de atención identificadas
   - Insights estratégicos
   - Recomendaciones accionables
```

## 💡 Tips y Mejores Prácticas

### Selección de Periodicidad
- **Semanal**: Para negocios con alta volatilidad o estacionalidad
- **Mensual**: Ideal para la mayoría de negocios (recomendado)
- **Trimestral**: Para análisis de tendencias de mediano plazo
- **Anual**: Para reportes de junta directiva

### Interpretación de Resultados
- **Ventas creciendo + CxC saludable**: 🟢 Excelente situación
- **Ventas creciendo + CxC deteriorada**: 🟡 Cuidado con liquidez
- **Ventas cayendo + CxC saludable**: 🟡 Enfoque en comercial
- **Ventas cayendo + CxC deteriorada**: 🔴 Crisis inminente

### Uso del Análisis con IA
- Úsalo para identificar patrones no obvios
- Las recomendaciones son guías, no mandatos absolutos
- Combina insights de IA con tu conocimiento del negocio
- Revisa mensualmente para detectar cambios de tendencia

## ⚙️ Configuración Técnica

### Variables de Entorno
```bash
# Para habilitar IA sin ingresar API key manualmente
export OPENAI_API_KEY="tu-api-key-aqui"

# Ejecutar aplicación
python -m streamlit run app.py
```

### Requisitos de Datos

**Mínimo (solo ventas):**
```
fecha, ventas_usd
2025-01-15, 1500.00
2025-01-16, 2300.50
```

**Completo (ventas + CxC):**
```
Archivo Excel con hojas:
- Hoja principal: datos de ventas
- CXC VIGENTES: cuentas vigentes
- CXC VENCIDAS: cuentas vencidas
```

## 🎯 Casos de Uso Recomendados

### 1. Reunión de Dirección Mensual
- Usa periodicidad "Mensual"
- Activa análisis con IA
- Presenta dashboard consolidado
- Discute recomendaciones estratégicas

### 2. Revisión Semanal de Operaciones
- Usa periodicidad "Semanal"
- Monitorea tendencias de corto plazo
- Detecta anomalías rápidamente

### 3. Cierre Trimestral
- Usa periodicidad "Trimestral"
- Evalúa cumplimiento de objetivos
- Ajusta estrategia para próximo trimestre

### 4. Presentación Anual
- Usa periodicidad "Anual"
- Muestra evolución histórica
- Documenta logros y áreas de mejora

## 📞 Soporte

Para problemas o preguntas:
- Revisa logs en `/logs/reporte_consolidado_*.log`
- Consulta [README_AI_ANALYSIS.md](./README_AI_ANALYSIS.md) para configuración de IA
- Verifica formato de datos en [ESPECIFICACION_INPUTS_EXCEL.md](../ESPECIFICACION_INPUTS_EXCEL.md)

---

**Módulo:** reporte_consolidado.py  
**Ubicación:** /main/reporte_consolidado.py  
**Versión:** 1.0  
**Fecha:** Febrero 2026


# 📊 Módulo: `main/heatmap_ventas.py`

Este README documenta exclusivamente el archivo:

```python
main/heatmap_ventas.py
```

---

## ✅ Descripción general

El módulo construye una vista comercial de ventas por línea de negocio con foco en:

- **segmentación comercial opcional** por vendedor, cliente, canal y región
- **evolución temporal visible** mediante heatmap por período
- **comparabilidad explícita** contra período anterior o mismo período del año previo
- **concentración comercial** con ranking y Pareto
- **drill-down accionable** por línea seleccionada
- **exportación** de la tabla filtrada visible

La intención ya no es solo mostrar una matriz de color, sino permitir lectura ejecutiva rápida y luego bajar al detalle de una línea específica.

---

## ✅ Flujo actual de la vista

La sección se renderiza en este orden:

Antes del render principal, el sidebar organiza los controles en tres bloques:

1. **Corte comercial**
	- vendedor
	- cliente
	- canal
	- región

2. **Corte temporal**
	- tipo de período
	- comparación
	- rango personalizado cuando aplica

3. **Visualización**
	- líneas visibles
	- rango visible por importe
	- máximo de líneas en heatmap

En el cuerpo principal, la lectura queda así:

1. **Lectura rápida**
	- ventas visibles
	- períodos visibles
	- línea líder
	- mayor crecimiento comparable

2. **Heatmap principal**
	- eje Y con `periodo_id - periodo`
	- anotaciones en moneda
	- estados de comparación por celda

3. **Ranking y concentración**
	- top de líneas visibles
	- concentración Top 1 / Top 3
	- número de líneas con peso comercial relevante

4. **Pareto de líneas**
	- barras de ventas visibles
	- línea de porcentaje acumulado
	- referencia de concentración al 80%

5. **Detalle por línea**
	- métricas de la línea seleccionada
	- serie visible de ventas por período
	- tabla de apoyo

---

## ✅ Tipos de análisis soportados

- **Mensual**
- **Trimestral**
- **Anual**
- **Rango Personalizado**

En rango personalizado se mantiene la lectura visible del heatmap, pero no se calcula crecimiento comparable entre períodos.

---

## ✅ Lógica actual de comparación

Cuando el usuario activa crecimiento, puede elegir entre:

- **Período anterior**
  - mensual: mes contra mes previo
  - trimestral: trimestre contra trimestre previo
  - anual: año contra año previo

- **Mismo período año anterior**
  - mensual: ene-24 vs ene-23
  - trimestral: Q1-24 vs Q1-23
  - anual: 2024 vs 2023

La comparación ya no depende de `pct_change(periods=n)` sobre secuencia posicional, sino de una búsqueda explícita del período base usando `periodo_inicio` y offsets de calendario.

---

## ✅ Estados semánticos por celda

El heatmap distingue cuatro estados de comparación:

- **comparable**: existe base y se muestra `%` de variación
- **nuevo**: la base era cero y el período actual tiene ventas
- **sin_comparable**: no existe período base disponible
- **sin_actividad**: base y actual sin actividad relevante

En UI estos estados se muestran como:

- `Nuevo`
- `Sin base`
- valor con `%` cuando sí hay comparación válida

---

## ✅ Reglas de negocio consolidadas

Actualmente el módulo centraliza estas reglas:

- **Objetivo Pareto:** `80%`
- **Línea relevante:** `>= 10%` del total visible
- **Color principal barras detalle:** verde comercial
- **Color tendencia detalle:** azul de alto contraste

Estas reglas quedaron encapsuladas en constantes y helpers para facilitar mantenimiento y ajuste posterior.

---

## ✅ Requisitos mínimos del DataFrame de entrada

El DataFrame debe contener como mínimo:

- una columna de **fecha**
- una columna de **línea de negocio**
- una columna de **importe**

La detección de nombres es flexible. Variantes soportadas incluyen:

- línea: `linea_prodcucto`, `linea_producto`, `linea_de_negocio`, `linea producto`
- importe: `valor_usd`, `ventas_usd`, `importe`
- producto: `producto`, `articulo`, `item`, `descripcion`, `producto_nombre`
- cliente: `cliente`, `razon_social`, `deudor`, `nombre_cliente`
- vendedor: `vendedor`, `agente`, `ejecutivo`, `vendedor_asignado`, `seller`, `rep`
- canal: `canal`, `canal_venta`, `canal_comercial`
- región: `region`, `zona`, `estado`, `territorio`

Antes de procesar, el módulo:

- limpia nombres de columnas
- normaliza acentos y espacios
- convierte `fecha` con `pd.to_datetime(errors="coerce")`

---

## ✅ Helpers relevantes del módulo

Helpers clave hoy cubiertos por tests unitarios:

- `preparar_dataframe_base()`
- `resolver_columnas_clave()`
- `aplicar_filtros_comerciales()`
- `construir_periodo_y_lags()`
- `calcular_tabla_crecimiento()`
- `calcular_metricas_concentracion()`
- `construir_pareto_dataframe()`
- `resumir_pareto()`

La función `run()` sigue siendo principalmente orchestration + UI Streamlit.

---

## ✅ Ejemplo de uso

```python
from main import heatmap_ventas

heatmap_ventas.run(df)
```

---

## ✅ Exportación

Si el usuario tiene permisos de exportación, el módulo genera:

```text
heatmap_filtrado.xlsx
```

El archivo contiene la tabla visible filtrada del heatmap.

---

## ✅ Estado actual de testing

Existe cobertura unitaria en:

```python
tests/unit/test_heatmap_ventas.py
```

La cobertura se enfoca en helpers de transformación y reglas de negocio. La capa `run()` no se cubre en profundidad porque corresponde principalmente a UI Streamlit.

---

## ✅ Próximos ajustes razonables

- exportar visuales del heatmap o del Pareto
- ampliar segmentación a otras dimensiones si aparecen en el dataset, por ejemplo categoría o familia
- evaluar una capa de insights automáticos por línea o por concentración

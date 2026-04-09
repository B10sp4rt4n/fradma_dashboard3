# Wiki Activo — Fradma Dashboard (Cima Analytics)

> Generado automáticamente: **2026-04-09T04:57:16**
> Este documento se regenera desde el código fuente real.

---

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| Líneas de código Python | **32,170** |
| Módulos Python | **41** |
| Tests | **538** en 25 archivos |
| Cobertura | **10.5%** |
| Commits | **397** |
| Último commit | 2026-04-09 04:43:28 |
| Inicio del proyecto | 2025-06-05 |
| Items del menú | **17** módulos |

## Menú de la Aplicación

1. 🎯 Reporte Ejecutivo
2. 📊 Reporte Consolidado
3. 📈 KPIs Generales
4. 📊 Comparativo Año vs Año
5. 📉 YTD por Línea de Negocio
6. 🔷 YTD por Producto
7. 🔥 Heatmap Ventas
8. 💳 KPI Cartera CxC
9. 👥 Vendedores + CxC
10. 🧰 Herramientas Financieras
11. 📂 Cargar mis facturas
12. 📋 Universo de CFDIs
13. 🧾 Desglose Fiscal
14. 📍 Mapa de Clientes
15. 📚 Knowledge Base
16. ⚙️ Gestión de Usuarios
17. 🔧 Configuración

## 📊 Módulos Principales (main/)

**Total: 18,434 líneas en 18 módulos**

### `data_assistant.py` (2,611 líneas)
_Módulo: Asistente de Datos — Consultas en lenguaje natural sobre CFDIs._

- **Funciones públicas (1):**
  - `run()` (L2532) — _Punto de entrada del módulo Asistente de Datos._
- Funciones privadas (36): `_get_engine`, `_invalidate_engine`, `_render_stats_kpi`, `_render_smart_table`, `_render_kpi_tab`, `_render_plotly_chart_and_save`, `_auto_chart`, `_render_stats_chart`, `_render_hero`, `_auto_connect_from_env` +26

### `fiscal.py` (540 líneas)
_Módulo: Desglose Fiscal_

- **Funciones públicas (1):**
  - `run()` (L144)
- Funciones privadas (4): `_get_neon_url`, `_cargar_fiscal`, `_cargar_tendencia_fiscal`, `_cargar_retenciones`

### `heatmap_ventas.py` (404 líneas)
__Sin docstring__

- **Funciones públicas (5):**
  - `run()` (L11)
  - `clean_columns()` (L14)
  - `detectar_columna()` (L22)
  - `generar_periodo_id()` (L66) — _Genera el identificador del periodo de forma segura_
  - `format_currency()` (L205)

### `herramientas_financieras.py` (1,690 líneas)
_Módulo: Herramientas Financieras_

- **class `FakeFile`** (línea 1316): 
  - Métodos: `__init__`, `read`
- **Funciones públicas (14):**
  - `obtener_tasas_cambio()` (L32) — _Obtiene tasas de cambio actualizadas desde API gratuita._
  - `get_tasas_fallback()` (L60) — _Tasas de respaldo en caso de fallo de API._
  - `get_nombres_monedas()` (L80) — _Retorna diccionario con nombres completos de monedas._
  - `mostrar_conversor_monedas()` (L118) — _Muestra interfaz del conversor de monedas._
  - `mostrar_calculadora_descuento_pronto_pago()` (L326) — _Calculadora para evaluar si conviene dar descuento por pronto pago._
  - `mostrar_calculadora_dso()` (L486) — _Calculadora de DSO - Días de ventas pendientes de cobro._
  - `mostrar_calculadora_interes_moratorio()` (L708) — _Calculadora de interés moratorio por pagos vencidos._
  - `obtener_indicadores_economicos()` (L954) — _Obtiene indicadores económicos básicos._
  - `mostrar_indicadores_economicos()` (L986) — _Muestra panel con indicadores económicos de referencia._
  - `parsear_xml_cfdi()` (L1114) — _Parsea un archivo XML de factura CFDI (México)._
  - `mostrar_digestor_xml()` (L1236) — _Muestra interfaz para digerir facturas XML (CFDI)._
  - `run()` (L1657) — _Función principal del módulo de herramientas financieras._
  - `format_moneda()` (L178)
  - `read()` (L1320)
- Funciones privadas (1): `__init__`

### `ingesta_cfdi.py` (1,418 líneas)
_Módulo de ingesta de CFDIs desde ZIP._

- **Funciones públicas (8):**
  - `extract_zip_to_temp()` (L38) — _Extrae un ZIP subido a una carpeta temporal._
  - `read_xml_contents()` (L64) — _Lee el contenido de múltiples archivos XML._
  - `mostrar_estadisticas_procesamiento()` (L79) — _Muestra estadísticas generales del procesamiento._
  - `crear_dataframe_conceptos()` (L240) — _Crea un DataFrame completo con todos los conceptos de las facturas._
  - `mostrar_distribuciones()` (L298) — _Muestra distribuciones por empresa y producto._
  - `mostrar_analisis_avanzados()` (L456) — _Muestra análisis avanzados sin IA: Pareto, tickets promedio, frecuencia, etc._
  - `mostrar_analisis_precios()` (L752) — _Muestra análisis de precios y variaciones._
  - `main()` (L918) — _Función principal de la página._
- Funciones privadas (1): `_render_ingesta_summary`

### `knowledge_base.py` (769 líneas)
_Módulo: Knowledge Base / Wiki — Interfaz Streamlit_

- **Funciones públicas (1):**
  - `run()` (L729) — _Punto de entrada del módulo Knowledge Base._
- Funciones privadas (15): `_badge_html`, `_short_path`, `_fmt_words`, `_clean_anchor_links`, `_render_explorer`, `_render_search`, `_render_document`, `_render_full_content`, `_render_stats`, `_render_history` +5

### `kpi_cpc.py` (2,391 líneas)
__Sin docstring__

- **Funciones públicas (2):**
  - `run()` (L61) — _Función principal del módulo KPI CxC (Cuentas por Cobrar)._
  - `clasificar_riesgo()` (L1432)
- Funciones privadas (4): `_detectar_col_vendedor`, `_es_vigente`, `_es_vencida`, `_rango_evol`

### `main_comparativo.py` (113 líneas)
__Sin docstring__

- **Funciones públicas (1):**
  - `run()` (L7)

### `main_comparativo_funcional110625_no configAnios.py` (61 líneas)
__Sin docstring__

- **Funciones públicas (1):**
  - `run()` (L6)

### `main_kpi.py` (602 líneas)
__Sin docstring__

- **Funciones públicas (2):**
  - `run()` (L12)
  - `clasificar_vendedor()` (L148)

### `main_kpi_backpup.py` (68 líneas)
__Sin docstring__

- **Funciones públicas (1):**
  - `run()` (L5)

### `mapa_clientes.py` (362 líneas)
_Módulo: Mapa de Clientes_

- **Funciones públicas (1):**
  - `run()` (L200)
- Funciones privadas (5): `_cp_a_estado`, `_get_neon_url`, `_cargar_datos`, `_geocodificar_cp_online`, `_cargar_coords`

### `reporte_consolidado.py` (669 líneas)
_Módulo: Reporte Consolidado - Dashboard Ejecutivo_

- **Funciones públicas (4):**
  - `agrupar_por_periodo()` (L32) — _Agrupa un DataFrame de ventas por el período especificado._
  - `crear_grafico_ventas_periodo()` (L65) — _Crea un gráfico de barras/líneas de ventas por período._
  - `crear_pie_cxc()` (L116) — _Crea un gráfico de pie para distribución de CxC._
  - `run()` (L546) — _Función principal del Reporte Consolidado._
- Funciones privadas (8): `_preparar_datos_iniciales`, `_obtener_configuracion_ui`, `_calcular_metricas_ventas`, `_calcular_metricas_cxc`, `_renderizar_kpis`, `_renderizar_visualizaciones`, `_renderizar_analisis_ia`, `_renderizar_tabla_detalle`

### `reporte_ejecutivo.py` (1,148 líneas)
_Módulo de Reporte Ejecutivo para el Dashboard Fradma._

- **Funciones públicas (1):**
  - `mostrar_reporte_ejecutivo()` (L21) — _Muestra el reporte ejecutivo consolidado con métricas clave de negocio._

### `universo_cfdi.py` (675 líneas)
_Módulo: Universo de CFDIs_

- **Funciones públicas (1):**
  - `run()` (L225)
- Funciones privadas (8): `_get_neon_url`, `_cargar_datos`, `_cargar_detalle`, `_cargar_tendencia`, `_cargar_pue_ppd`, `_clasificar_ppd`, `_color_estatus`, `_color_clasif`

### `vendedores_cxc.py` (1,360 líneas)
_Módulo: Vendedores + CxC_

- **Funciones públicas (2):**
  - `run()` (L136)
  - `clasificar_antiguedad_detallado()` (L380)
- Funciones privadas (5): `_normalizar_nombre_cliente`, `_detectar_col_vendedor`, `_detectar_col_ventas`, `_detectar_col_cliente`, `_score_calidad`

### `ytd_lineas.py` (1,548 líneas)
_Módulo: Reporte YTD (Year-to-Date) por Línea de Negocio_

- **Funciones públicas (13):**
  - `calcular_ytd()` (L61) — _Calcula ventas YTD hasta una fecha específica._
  - `calcular_metricas_ytd()` (L101) — _Calcula métricas agregadas YTD._
  - `crear_grafico_lineas_acumulado()` (L128) — _Crea gráfico de líneas con ventas acumuladas por mes._
  - `crear_grafico_barras_comparativo()` (L230) — _Crea gráfico de barras comparando año actual vs anterior por línea._
  - `crear_treemap_participacion()` (L378) — _Crea treemap mostrando participación de cada línea._
  - `crear_grafico_comparativo_anos_completos()` (L412) — _Crea gráfico de barras comparando ventas totales de años completos._
  - `crear_tabla_top_productos()` (L519) — _Crea tabla con top productos del período._
  - `crear_tabla_top_clientes()` (L532) — _Crea tabla con top clientes del período._
  - `exportar_excel_ytd()` (L545) — _Genera archivo Excel con reporte YTD completo._
  - `run()` (L610) — _Función principal del módulo YTD por Líneas._
  - `calcular_crecimiento_seguro()` (L279)
  - `aplicar_color_fondo()` (L1307)
  - `aplicar_color_fondo_local()` (L1371)

### `ytd_productos.py` (2,005 líneas)
_Módulo: Reporte YTD (Year-to-Date) por Producto_

- **Funciones públicas (15):**
  - `calcular_ytd()` (L61) — _Calcula ventas YTD hasta una fecha específica._
  - `calcular_metricas_ytd()` (L101) — _Calcula métricas agregadas YTD._
  - `crear_grafico_temporal_producto()` (L128) — _Crea gráfico de evolución temporal de un producto específico._
  - `crear_treemap_clientes_producto()` (L225) — _Crea treemap de clientes que compran un producto específico._
  - `crear_treemap_productos_top()` (L294) — _Crea treemap de productos top con resto agrupado como 'Otros'._
  - `crear_grafico_lineas_acumulado()` (L364) — _Crea gráfico de productos con ventas acumuladas por mes._
  - `crear_grafico_barras_comparativo()` (L466) — _Crea gráfico de barras comparando año actual vs anterior por producto._
  - `crear_treemap_participacion()` (L614) — _Crea treemap mostrando participación de cada línea._
  - `crear_grafico_comparativo_anos_completos()` (L648) — _Crea gráfico de barras comparando ventas totales de años completos._
  - `crear_tabla_top_productos()` (L755) — _Crea tabla con top productos del período._
  - `crear_tabla_top_clientes()` (L768) — _Crea tabla con top clientes del período._
  - `exportar_excel_ytd()` (L781) — _Genera archivo Excel con reporte YTD completo._
  - `run()` (L846) — _Función principal del módulo YTD por Líneas._
  - `calcular_crecimiento_seguro()` (L515)
  - `highlight_selected()` (L1413)

## 🔧 Utilidades (utils/)

**Total: 10,227 líneas en 19 módulos**

### `admin_panel.py` (757 líneas)
_Panel de administración de usuarios para FRADMA Dashboard._

- **Funciones públicas (3):**
  - `mostrar_panel_usuarios()` (L20) — _Panel completo de gestión de usuarios._
  - `mostrar_panel_configuracion()` (L567) — _Panel de configuración del sistema._
  - `mostrar_info_usuario()` (L656) — _Muestra información del usuario en el sidebar._
- Funciones privadas (1): `_fmt_dt`

### `ai_helper.py` (452 líneas)
_Módulo: AI Helper - Integración con OpenAI GPT-4o-mini_

- **Funciones públicas (4):**
  - `validar_api_key()` (L21) — _Valida que la API key de OpenAI sea válida._
  - `generar_resumen_ejecutivo_ytd()` (L43) — _Genera un análisis ejecutivo estructurado usando OpenAI GPT-4o-mini._
  - `generar_analisis_consolidado_ia()` (L178) — _Genera un análisis ejecutivo consolidado integrando ventas y CxC._
  - `generar_resumen_ejecutivo_cxc()` (L301) — _Genera un análisis ejecutivo estructurado de CxC usando OpenAI GPT-4o-mini._

### `ai_helper_premium.py` (257 líneas)
_Módulo: AI Helper Premium - Funciones avanzadas de IA para análisis ejecutivo_

- **Funciones públicas (2):**
  - `generar_insights_kpi_vendedores()` (L19) — _Genera insights estratégicos sobre el desempeño del equipo de ventas._
  - `generar_insights_ejecutivo_consolidado()` (L148) — _Genera insights ejecutivos de alto nivel integrando ventas y CxC._

### `auth.py` (948 líneas)
_Sistema de autenticación multi-usuario para FRADMA Dashboard._

- **class `UserRole`** (línea 30): Roles disponibles en el sistema
- **class `User`** (línea 38): Representa un usuario del sistema
  - Métodos: `can_export`, `can_use_ai`, `can_manage_users`, `can_edit_config`, `is_superadmin`, `tiene_multiples_empresas`
- **class `AuthManager`** (línea 75): Gestor centralizado de autenticación y usuarios — Neon PostgreSQL.
  - Métodos: `__init__`, `_ensure_schema`, `_ensure_default_empresa`, `_hash_password`, `_verify_password`, `_ensure_admin`, `_log_login`, `authenticate` +18 más
- **Funciones públicas (31):**
  - `get_current_user()` (L867) — _Obtiene usuario actual de la sesión_
  - `require_auth()` (L872) — _Decorador para requerir autenticación._
  - `require_role()` (L890) — _Decorador para requerir rol específico._
  - `can_export()` (L52)
  - `can_use_ai()` (L55)
  - `can_manage_users()` (L58)
  - `can_edit_config()` (L61)
  - `is_superadmin()` (L65) — _Superadmin = admin sin empresa asignada → ve todos los datos._
  - `tiene_multiples_empresas()` (L70) — _True si el usuario tiene acceso a más de una empresa._
  - `authenticate()` (L251) — _Autentica usuario; retorna User si válido, None si falla._
  - `create_user()` (L335)
  - `list_users()` (L408) — _Lista usuarios. Si empresa_id, filtra los que pertenecen a ese tenant_
  - `get_user()` (L453)
  - `update_user()` (L457)
  - `change_password()` (L481)
- Funciones privadas (8): `_get_conn`, `__init__`, `_ensure_schema`, `_ensure_default_empresa`, `_hash_password`, `_verify_password`, `_ensure_admin`, `_log_login`

### `cache_helper.py` (292 líneas)
_Utilidades de caché para optimización de performance en Streamlit._

- **class `GestorCache`** (línea 153): Gestor centralizado de caché con métricas de uso.
  - Métodos: `__init__`, `obtener_o_calcular`, `mostrar_estadisticas`, `limpiar`
- **Funciones públicas (13):**
  - `calcular_hash_dataframe()` (L16) — _Calcula un hash único para un DataFrame._
  - `cache_con_timeout()` (L41) — _Decorador para cachear resultados con timeout personalizado._
  - `limpiar_cache_completo()` (L63) — _Limpia todo el caché de Streamlit._
  - `mostrar_indicador_cache()` (L79) — _Muestra un indicador visual del estado del caché._
  - `decorador_medicion_tiempo()` (L99) — _Decorador para medir y mostrar tiempo de ejecución._
  - `cachear_dataframe()` (L135) — _Cachea un DataFrame con una key personalizada._
  - `decorator()` (L54)
  - `wrapper()` (L118)
  - `obtener_o_calcular()` (L177) — _Obtiene dato del caché o lo calcula si no existe._
  - `mostrar_estadisticas()` (L229) — _Muestra métricas de uso del caché._
  - `limpiar()` (L250) — _Limpia todo el caché gestionado._
  - `funcion_lenta()` (L284)
  - `wrapper()` (L57)
- Funciones privadas (1): `__init__`

### `constantes.py` (297 líneas)
_Constantes centralizadas para el Dashboard Fradma._

- **class `UmbralesCxC`** (línea 108): Umbrales para clasificación y alertas de CxC.
- **class `ScoreSalud`** (línea 149): Rangos y pesos para el score de salud financiera.
- **class `PrioridadCobranza`** (línea 175): Umbrales para clasificación de prioridad de cobranza.
- **class `ConfigVisualizacion`** (línea 279): Configuración para gráficos y tablas.

### `cxc_helper.py` (449 líneas)
_Funciones helper para cálculos de Cuentas por Cobrar (CxC)._

- **Funciones públicas (11):**
  - `detectar_columna()` (L23) — _Detecta la primera columna existente de una lista de candidatos._
  - `excluir_pagados()` (L52) — _Crea una máscara booleana para excluir registros pagados._
  - `calcular_dias_overdue()` (L88) — _Calcula días de atraso usando lógica unificada con fallback en cascada._
  - `preparar_datos_cxc()` (L176) — _Prepara datos de CxC con lógica unificada del Reporte Ejecutivo._
  - `calcular_score_salud()` (L221) — _Calcula el score de salud financiera con consideración de todos los rangos._
  - `clasificar_score_salud()` (L273) — _Clasifica un score de salud en categoría y color._
  - `clasificar_antiguedad()` (L295) — _Clasifica deuda por antigüedad en categorías estándar._
  - `calcular_metricas_basicas()` (L321) — _Calcula métricas básicas de CxC a partir de datos no pagados._
  - `obtener_semaforo_morosidad()` (L394) — _Retorna emoji de semáforo según nivel de morosidad._
  - `obtener_semaforo_riesgo()` (L414) — _Retorna emoji de semáforo según nivel de riesgo alto._
  - `obtener_semaforo_concentracion()` (L434) — _Retorna emoji de semáforo según nivel de concentración de cartera._
- Funciones privadas (1): `_parsear_fechas`

### `cxc_metricas_cliente.py` (193 líneas)
_Módulo para calcular métricas avanzadas de CxC agrupadas por cliente._

- **Funciones públicas (4):**
  - `calcular_metricas_por_cliente()` (L15) — _Calcula métricas de antigüedad por cliente usando 3 métodos:_
  - `obtener_top_n_clientes()` (L92) — _Retorna los top N clientes por saldo total._
  - `obtener_clientes_por_rango()` (L106) — _Filtra clientes por rango de antigüedad._
  - `obtener_facturas_cliente()` (L120) — _Retorna el detalle de todas las facturas de un cliente específico._
- Funciones privadas (1): `_rango`

### `data_cleaner.py` (162 líneas)
_Módulo de limpieza y normalización de datos para Fradma Dashboard._

- **Funciones públicas (5):**
  - `normalizar_texto()` (L12) — _Normaliza un texto eliminando acentos, convirtiendo a minúsculas y limpiando espacios._
  - `cargar_aliases()` (L41) — _Carga el archivo de aliases/mapeos desde JSON._
  - `aplicar_aliases()` (L63) — _Aplica mapeo de aliases a una Serie de pandas._
  - `limpiar_columnas_texto()` (L92) — _Limpia y normaliza columnas de texto en un DataFrame._
  - `detectar_duplicados_similares()` (L137) — _Detecta valores similares que probablemente son duplicados._

### `data_normalizer.py` (307 líneas)
_Módulo para normalización de datos._

- **Funciones públicas (8):**
  - `normalizar_columnas()` (L19) — _Normaliza nombres de columnas de un DataFrame._
  - `normalizar_columna_saldo()` (L61) — _Normaliza columnas de saldo/adeudo a un nombre estándar._
  - `normalizar_columna_valor()` (L100) — _Normaliza columnas de ventas/valor a un nombre estándar._
  - `limpiar_valores_monetarios()` (L139) — _Limpia valores monetarios eliminando símbolos y formatos._
  - `detectar_columnas_cxc()` (L168) — _Detecta si un DataFrame tiene columnas de CxC._
  - `excluir_pagados()` (L200) — _Excluye registros pagados de un DataFrame de CxC._
  - `normalizar_datos_cxc()` (L245) — _Normaliza datos de ventas y CxC de forma consistente._
  - `normalizar_columna_fecha()` (L286) — _Normaliza columna de fecha a datetime._

### `export_helper.py` (1,606 líneas)
_Utilidades para exportar reportes del dashboard a Excel y PDF._

- **Funciones públicas (6):**
  - `crear_excel_metricas_cxc()` (L20) — _Crea un archivo Excel con múltiples hojas de métricas CxC._
  - `crear_reporte_html()` (L166) — _Crea un reporte HTML ejecutivo profesional con métricas configurables._
  - `preparar_datos_para_export()` (L786) — _Prepara DataFrame para exportación limpiando y formateando datos._
  - `crear_excel_cobranza_semanal()` (L827) — _Crea un Excel de lista semanal de cobranza listo para compartir con el equipo._
  - `crear_reporte_pdf_ejecutivo()` (L1056) — _Crea un reporte ejecutivo en PDF a partir de una consulta del Data Assistant._
  - `limpiar_texto_para_pdf()` (L1207) — _Limpia texto removiendo markdown y escapando caracteres para ReportLab._
- Funciones privadas (5): `_fmt_nivel`, `_is_ck`, `_is_mk`, `_is_pk`, `_fmtk`

### `filters.py` (669 líneas)
_Componentes de filtrado avanzado para el dashboard Streamlit._

- **Funciones públicas (5):**
  - `aplicar_filtro_fechas()` (L14) — _Aplica filtro de fechas al DataFrame con múltiples modos de comparación._
  - `aplicar_filtro_cliente()` (L339) — _Aplica filtro de selección de clientes con búsqueda intuitiva._
  - `aplicar_filtro_monto()` (L415) — _Aplica filtro de rango de montos._
  - `aplicar_filtro_categoria_riesgo()` (L509) — _Aplica filtro por categoría de riesgo basado en días de atraso._
  - `mostrar_resumen_filtros()` (L595) — _Muestra un resumen de los filtros aplicados._

### `filters_helper.py` (118 líneas)
_Helper para manejo de filtros en análisis IA._

- **Funciones públicas (3):**
  - `obtener_lineas_filtradas()` (L16) — _Filtra líneas específicas removiendo 'Todas' y valores vacíos._
  - `generar_contexto_filtros()` (L53) — _Genera mensaje de contexto para la IA sobre el alcance del análisis._
  - `aplicar_filtro_dataframe()` (L87) — _Aplica filtro de líneas a un DataFrame de forma segura._

### `formatos.py` (187 líneas)
_Módulo de utilidades para formateo consistente de datos en el dashboard._

- **Funciones públicas (7):**
  - `now_mx()` (L13) — _Retorna la hora actual en la zona horaria de México (America/Mexico_City)._
  - `formato_moneda()` (L19) — _Formatea un valor numérico como moneda USD con separadores de miles._
  - `formato_numero()` (L45) — _Formatea un número con separadores de miles._
  - `formato_porcentaje()` (L69) — _Formatea un valor como porcentaje._
  - `formato_delta_moneda()` (L99) — _Formatea un delta de moneda para usar en st.metric()._
  - `formato_compacto()` (L128) — _Formatea números grandes de manera compacta (K, M, B)._
  - `formato_dias()` (L158) — _Formatea días con texto descriptivo._

### `knowledge_base.py` (744 líneas)
_Módulo: Knowledge Base - Motor de Búsqueda e Indexación Wiki_

- **class `Document`** (línea 32): Representa un documento indexado.
- **class `SearchResult`** (línea 47): Resultado de búsqueda con contexto.
- **class `SearchStats`** (línea 56): Estadísticas de una búsqueda.
- **class `MarkdownParser`** (línea 69): Parsea archivos Markdown en documentos estructurados.
  - Métodos: `parse_file`, `_extract_title`, `_parse_sections`, `_categorize`, `_extract_metadata`
- **class `SearchEngine`** (línea 240): Motor de búsqueda full-text sobre documentos indexados.
  - Métodos: `__init__`, `_load_stopwords`, `index_directory`, `index_file`, `_build_inverted_index`, `_tokenize`, `search`, `_extract_snippet` +9 más
- **Funciones públicas (15):**
  - `get_search_engine()` (L707) — _Obtiene o crea la instancia del SearchEngine._
  - `invalidate_cache()` (L741) — _Invalida el cache del SearchEngine para forzar re-indexación._
  - `parse_file()` (L87) — _Parsea un archivo Markdown y retorna un Document._
  - `index_directory()` (L267) — _Indexa todos los archivos Markdown en un directorio._
  - `index_file()` (L298) — _Indexa un archivo individual._
  - `search()` (L347) — _Búsqueda full-text con ranking por relevancia._
  - `get_categories()` (L501) — _Retorna categorías con conteo de documentos._
  - `get_document_by_id()` (L508) — _Obtiene un documento por su ID._
  - `get_all_documents()` (L512) — _Retorna todos los documentos, opcionalmente filtrados._
  - `get_search_history()` (L519) — _Retorna historial de búsquedas recientes._
  - `get_stats()` (L523) — _Retorna estadísticas del índice._
  - `get_related_documents()` (L540) — _Encuentra documentos relacionados basado en tokens compartidos._
  - `get_document_history()` (L562) — _Obtiene el historial de cambios (git log) de un documento._
  - `save_document()` (L629) — _Guarda cambios en un documento existente._
  - `create_document()` (L671) — _Crea un nuevo documento markdown._
- Funciones privadas (9): `_extract_title`, `_parse_sections`, `_categorize`, `_extract_metadata`, `__init__`, `_load_stopwords`, `_build_inverted_index`, `_tokenize`, `_extract_snippet`

### `logger.py` (232 líneas)
_Sistema de logging estructurado para el Dashboard FRADMA._

- **class `ColoredFormatter`** (línea 26): Formatter con colores para output de consola.
  - Métodos: `format`
- **Funciones públicas (7):**
  - `configurar_logger()` (L47) — _Configura y retorna un logger estructurado._
  - `log_execution_time()` (L126) — _Decorador para medir y loggear el tiempo de ejecución de funciones._
  - `log_dataframe_info()` (L167) — _Loggea información útil sobre un DataFrame._
  - `format()` (L39) — _Formatear el log record con colores._
  - `decorator()` (L143)
  - `funcion_ejemplo()` (L217)
  - `wrapper()` (L145)

### `neon_loader.py` (145 líneas)
_Carga de datos CFDI desde Neon hacia session_state["df"]._

- **Funciones públicas (1):**
  - `cargar_cfdi_como_df()` (L41) — _Lee cfdi_ventas de Neon filtrado por empresa_id y devuelve un DataFrame_
- Funciones privadas (1): `_streamlit_neon_url`

### `nl2sql.py` (2,043 líneas)
_Motor NL2SQL — Consultas en Lenguaje Natural sobre Base de Datos CFDI._

- **class `NL2SQLResult`** (línea 147): Resultado de una consulta en lenguaje natural.
  - Métodos: `success`, `to_dict`
- **class `NL2SQLEngine`** (línea 424): Motor de consultas en lenguaje natural sobre base de datos CFDI.
  - Métodos: `__init__`, `generate_sql`, `_build_system_prompt`, `_clean_sql`, `_detect_month`, `_detect_explicit_year`, `_detect_date_range`, `_ensure_month_filter` +12 más
- **Funciones públicas (15):**
  - `validate_sql_static()` (L1986) — _Validación estática de SQL sin necesidad de instanciar el engine._
  - `get_example_questions()` (L2041) — _Retorna las preguntas de ejemplo organizadas por categoría._
  - `success()` (L161)
  - `to_dict()` (L164)
  - `generate_sql()` (L472) — _Genera SQL a partir de una pregunta en lenguaje natural._
  - `validate_sql()` (L1042) — _Valida que el SQL sea seguro para ejecución._
  - `execute_query()` (L1180) — _Ejecuta una query SQL contra la base de datos._
  - `interpret_results()` (L1239) — _Genera una interpretación en lenguaje natural de los resultados._
  - `ask()` (L1758) — _Pipeline completo: pregunta → SQL → ejecución → interpretación._
  - `get_history()` (L1894) — _Retorna el historial de consultas._
  - `clear_history()` (L1898) — _Limpia el historial de consultas._
  - `test_connection()` (L1902) — _Prueba la conexión a la base de datos._
  - `get_table_counts()` (L1923) — _Obtiene el conteo de registros por tabla._
  - `get_date_range()` (L1955) — _Obtiene el rango de fechas de los datos._
  - `wrap_div()` (L1142)
- Funciones privadas (12): `_normalize_highlights`, `_protect`, `__init__`, `_build_system_prompt`, `_clean_sql`, `_detect_month`, `_detect_explicit_year`, `_detect_date_range`, `_ensure_month_filter`, `_fix_year_contradictions` +2

### `roi_tracker.py` (369 líneas)
_ROI Tracker - Sistema de seguimiento de retorno de inversión_

- **class `ROITracker`** (línea 10): Tracker de ROI para medir el valor generado por el uso de la plataforma.
  - Métodos: `__init__`, `_init_session`, `get_user_hourly_rate`, `track_action`, `track_risk_avoided`, `get_analyst_salary`, `set_analyst_salary`, `hrs_to_workdays` +4 más
- **Funciones públicas (12):**
  - `init_roi_tracker()` (L343) — _Inicializa el ROI tracker en el session state_
  - `quick_track()` (L358) — _Función rápida para trackear una acción_
  - `get_user_hourly_rate()` (L107) — _Obtiene el costo por hora del usuario actual_
  - `track_action()` (L126) — _Rastrea una acción y calcula el ROI automáticamente_
  - `track_risk_avoided()` (L197) — _Rastrea un riesgo detectado y evitado (requiere IA Premium)_
  - `get_analyst_salary()` (L238) — _Obtiene el sueldo configurado de analista o el default_
  - `set_analyst_salary()` (L242) — _Configura el sueldo de referencia del analista_
  - `hrs_to_workdays()` (L246) — _Convierte horas a días laborales (8 hrs = 1 día)_
  - `calculate_analyst_cost_equivalent()` (L250) — _Calcula el costo equivalente en sueldos de analista_
  - `get_summary()` (L279) — _Obtiene resumen del ROI acumulado con días laborales calculados_
  - `get_recent_actions()` (L322) — _Obtiene las últimas acciones rastreadas_
  - `reset_session()` (L335) — _Reinicia el tracking de la sesión actual (útil para testing)_
- Funciones privadas (2): `__init__`, `_init_session`

## 📄 CFDI (cfdi/)

**Total: 1,463 líneas en 3 módulos**

### `enrichment.py` (520 líneas)
_Módulo de enriquecimiento de datos CFDI con IA._

- **class `CFDIEnrichment`** (línea 105): Clase para enriquecimiento de conceptos CFDI con IA.
  - Métodos: `__init__`, `_get_cache_key`, `_clasificar_por_keywords`, `_clasificar_con_gpt`, `clasificar_concepto`, `enriquecer_conceptos_batch`, `detectar_anomalias`, `generar_resumen` +2 más
- **Funciones públicas (7):**
  - `clasificar_rapido()` (L504) — _Función helper para clasificación rápida sin instanciar clase._
  - `clasificar_concepto()` (L236) — _Clasifica un concepto en una línea de negocio._
  - `enriquecer_conceptos_batch()` (L287) — _Enriquece una lista de conceptos con clasificación._
  - `detectar_anomalias()` (L364) — _Detecta posibles anomalías en un concepto._
  - `generar_resumen()` (L432) — _Genera un resumen estadístico de conceptos enriquecidos._
  - `export_cache()` (L476) — _Exporta el caché a un archivo JSON._
  - `import_cache()` (L487) — _Importa un caché desde un archivo JSON._
- Funciones privadas (4): `__init__`, `_get_cache_key`, `_clasificar_por_keywords`, `_clasificar_con_gpt`

### `ingestion.py` (595 líneas)
_Módulo de ingesta de datos CFDI a Neon PostgreSQL._

- **class `NeonIngestion`** (línea 24): Clase para manejar la ingesta de datos CFDI a Neon PostgreSQL.
  - Métodos: `__init__`, `__enter__`, `__exit__`, `connect`, `close`, `_uuid_exists`, `_upsert_cliente`, `insert_venta` +3 más
- **Funciones públicas (7):**
  - `verify_connection()` (L566) — _Verifica la conexión a Neon._
  - `connect()` (L62) — _Establece conexión a Neon._
  - `close()` (L71) — _Cierra conexión a Neon._
  - `insert_venta()` (L127) — _Inserta una factura de venta (CFDI) con sus conceptos y actualiza clientes._
  - `insert_ventas_batch()` (L305) — _Inserta múltiples facturas en batch._
  - `insert_pago()` (L387) — _Inserta un complemento de pago._
  - `get_empresa_stats()` (L489) — _Obtiene estadísticas de la empresa._
- Funciones privadas (5): `__init__`, `__enter__`, `__exit__`, `_uuid_exists`, `_upsert_cliente`

### `parser.py` (348 líneas)
_Parser de CFDI 4.0 - Extrae datos estructurados de XMLs de SAT_

- **class `CFDIParser`** (línea 25): Parser para CFDI 4.0
  - Métodos: `__init__`, `parse_cfdi_venta`, `_extract_comprobante`, `_extract_emisor`, `_extract_receptor`, `_extract_conceptos`, `_extract_impuestos`, `_extract_timbre` +1 más
- **class `ComplementoPagoParser`** (línea 224): Parser para Complemento de Pagos 2.0
  - Métodos: `__init__`, `parse_complemento_pago`, `_parse_datetime`
- **Funciones públicas (3):**
  - `parse_cfdi_batch()` (L297) — _Procesa múltiples CFDIs en batch_
  - `parse_cfdi_venta()` (L31) — _Parsea un CFDI de venta (emitido) y extrae datos estructurados_
  - `parse_complemento_pago()` (L230) — _Parsea un complemento de pago y extrae registros de cobranza_
- Funciones privadas (10): `__init__`, `_extract_comprobante`, `_extract_emisor`, `_extract_receptor`, `_extract_conceptos`, `_extract_impuestos`, `_extract_timbre`, `_parse_datetime`, `__init__`, `_parse_datetime`

## 📦 Dependencias

### Producción

- `streamlit==1.52.1`
- `pandas==2.3.3`
- `numpy==2.3.5`
- `matplotlib==3.10.8`
- `seaborn==0.13.2`
- `plotly==6.5.0`
- `kaleido==0.2.1`
- `openpyxl==3.1.5`
- `xlsxwriter==3.2.9`
- `Unidecode==1.4.0`
- `requests==2.32.3`
- `openai==2.17.0`
- `python-dotenv==1.0.1`
- `bcrypt==5.0.0`
- `lxml==6.0.2`
- `psycopg2-binary==2.9.11`
- `reportlab==4.2.5`

### Desarrollo

- `pytest==9.0.2`
- `pytest-cov==7.0.0`
- `pytest-mock==3.15.1`
- `coverage==7.13.0`

## 👥 Contribuidores

| Autor | Commits |
|-------|---------|
| B10sp4rt4n | 390 |

## 🧪 Estado de Tests

- **538 tests** en 25 archivos
- Cobertura: **10.5%**

---
_Wiki generado por `scripts/generate_wiki.py` el 2026-04-09T04:57:16_
_Para regenerar: `python scripts/generate_wiki.py`_

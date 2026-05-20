"""
carga_inteligente_datos.py
Pantalla de Carga Inteligente de Datos del CIMA Schema Engine by FixCel.

Permite al usuario:
  - Seleccionar tipo de carga y esquema esperado
  - Subir archivo CSV/XLSX
  - Validar estructura contra schemas declarados
  - Ver columnas detectadas y mapeo canonico
  - Calcular score de contexto
  - Determinar modulos activables
  - Descargar plantillas base y reporte de validacion
  - Asignar archivo validado como DataFrame activo en session_state

RESTRICCIONES:
  - No toca dashboards existentes
  - No modifica calculos de CxC, aging ni score de salud
  - No implementa conexiones reales a SAE, CONTPAQi, ERPs
  - No escribe en Neon ni S3
"""

import json
import os
from datetime import datetime, timezone
from io import StringIO

import pandas as pd
import streamlit as st

# ── Schema Engine ──────────────────────────────────────────────────────────
try:
    from schema_engine.schema_registry import get_schema, list_schemas
    from schema_engine.schema_validator import validate_dataframe_against_schema
    from schema_engine.context_score import calculate_context_score, score_label
    from schema_engine.module_requirements import get_activable_modules, MODULE_REQUIREMENTS
    from schema_engine.column_mapper import map_columns, get_detected_canonical_fields
    _SCHEMA_ENGINE_OK = True
except ImportError as _e:
    _SCHEMA_ENGINE_OK = False
    _SCHEMA_ENGINE_ERROR = str(_e)

# ── Ruta base del proyecto ─────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMPLATES_DIR = os.path.join(_ROOT, "templates")

# ── Mapas de apoyo ─────────────────────────────────────────────────────────
_TIPO_A_SCHEMAS = {
    "Ventas":               ["ventas_minimo_v1", "ventas_comercial_v1"],
    "Cuentas por Cobrar":   ["cxc_minimo_v1", "cxc_aging_v1"],
    "CFDI / XML":           ["cfdi_xml_basico_v1", "cfdi_neon_mapa_clientes_v1"],
    "Herramientas / Manual":["manual_financial_tools_v1"],
    "DataFrame flexible":   ["data_assistant_flexible_v1"],
    "Deteccion automatica": ["ventas_minimo_v1", "ventas_comercial_v1",
                             "cxc_minimo_v1", "cxc_aging_v1",
                             "data_assistant_flexible_v1"],
}

_TIPO_A_FUENTE = {
    "Ventas":               "ventas_excel",
    "Cuentas por Cobrar":   "cxc_excel",
    "CFDI / XML":           "cfdi_xml",
    "Herramientas / Manual":"manual_input",
    "DataFrame flexible":   "dataframe_flexible",
    "Deteccion automatica": "dataframe_flexible",
}

_TEMPLATES_DISPONIBLES = [
    ("Ventas minimo",    "ventas_minimo.csv"),
    ("Ventas comercial", "ventas_comercial.csv"),
    ("CxC minimo",       "cxc_minimo.csv"),
    ("CxC aging",        "cxc_aging.csv"),
]

_SCORE_COLORES = {
    "Critico":   "#e74c3c",
    "Limitado":  "#e67e22",
    "Funcional": "#f1c40f",
    "Bueno":     "#27ae60",
    "Completo":  "#1abc9c",
}

_SCORE_ICONOS = {
    "Critico":   "🔴",
    "Limitado":  "🟠",
    "Funcional": "🟡",
    "Bueno":     "🟢",
    "Completo":  "✅",
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _leer_csv_seguro(archivo) -> tuple:
    """Lee CSV con manejo de encoding. Retorna (df, error_str|None)."""
    for enc in ("utf-8", "latin-1", "utf-8-sig", "cp1252"):
        try:
            archivo.seek(0)
            df = pd.read_csv(archivo, encoding=enc)
            if df.empty:
                return None, "El archivo CSV esta vacio."
            return df, None
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            return None, "El archivo CSV no contiene datos."
        except Exception as e:
            return None, f"Error al leer CSV: {e}"
    return None, "No se pudo decodificar el CSV. Verifica el encoding del archivo."


def _leer_excel_seguro(archivo) -> tuple:
    """
    Lee Excel con deteccion de multiples hojas.
    Retorna (df, hojas_disponibles, hoja_leida, error_str|None).
    """
    try:
        archivo.seek(0)
        raw = archivo.read()
        xls = pd.ExcelFile(raw)
        hojas = xls.sheet_names
    except Exception as e:
        return None, [], None, f"Error al abrir Excel: {e}"

    return None, hojas, None, None  # sin df todavia — se carga con hoja elegida


def _leer_excel_hoja(archivo_bytes, hoja: str) -> tuple:
    """Lee una hoja especifica del Excel. Retorna (df, error_str|None)."""
    try:
        df = pd.read_excel(archivo_bytes, sheet_name=hoja)
        if df.empty:
            return None, f"La hoja '{hoja}' esta vacia."
        return df, None
    except Exception as e:
        return None, f"Error al leer hoja '{hoja}': {e}"


def _score_badge(score: int, label: str) -> str:
    color = _SCORE_COLORES.get(label, "#7f8c8d")
    icono = _SCORE_ICONOS.get(label, "⚪")
    return (
        f"<div style='display:inline-block;background:{color};color:white;"
        f"border-radius:8px;padding:4px 14px;font-weight:700;font-size:15px;"
        f"margin:4px 0;'>{icono} {score}/100 — {label}</div>"
    )


def _dim_bar(nombre: str, detectada: bool) -> str:
    color = "#27ae60" if detectada else "#e74c3c"
    texto = "✅ Presente" if detectada else "❌ Ausente"
    return (
        f"<div style='display:flex;justify-content:space-between;"
        f"background:#1a2a3a;border-radius:5px;padding:4px 10px;"
        f"margin:3px 0;font-size:13px;'>"
        f"<span style='color:#90CAF9;'>{nombre}</span>"
        f"<span style='color:{color};font-weight:600;'>{texto}</span></div>"
    )


def _construir_reporte_json(
    schema_id: str,
    validation_result: dict,
    activable_result: dict,
    context_result: dict,
) -> str:
    """Construye el JSON del reporte de validacion."""
    reporte = {
        "cima_schema_validation_report": {
            "schema_id":                      schema_id,
            "timestamp":                      datetime.now(tz=timezone.utc).isoformat(),
            "valido":                         validation_result.get("valido"),
            "score_contexto":                 validation_result.get("score_contexto"),
            "score_label":                    score_label(validation_result.get("score_contexto", 0)),
            "campos_detectados":              validation_result.get("campos_detectados", []),
            "campos_faltantes_obligatorios":  validation_result.get("campos_faltantes_obligatorios", []),
            "campos_faltantes_recomendados":  validation_result.get("campos_faltantes_recomendados", []),
            "campos_opcionales_detectados":   validation_result.get("campos_opcionales_detectados", []),
            "columnas_mapeadas":              validation_result.get("columnas_mapeadas", {}),
            "columnas_no_mapeadas":           validation_result.get("columnas_no_mapeadas", []),
            "diagnosticos_disponibles":       validation_result.get("diagnosticos_disponibles", []),
            "diagnosticos_limitados":         validation_result.get("diagnosticos_limitados", []),
            "observaciones":                  validation_result.get("observaciones", []),
            "modulos_activables":             activable_result.get("modulos_activables", []),
            "modulos_parciales":              [
                m["modulo"] for m in activable_result.get("modulos_parciales", [])
            ],
            "modulos_no_activables":          [
                m["modulo"] for m in activable_result.get("modulos_no_activables", [])
            ],
            "context_score_detalle":          context_result.get("detalle", {}),
        }
    }
    return json.dumps(reporte, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

def run():
    # ── Verificar schema_engine ────────────────────────────────────────────
    if not _SCHEMA_ENGINE_OK:
        st.error(
            f"❌ El modulo schema_engine no esta disponible: {_SCHEMA_ENGINE_ERROR}\n\n"
            "Verifica que el directorio `schema_engine/` exista en el proyecto."
        )
        return

    # ── Titulo ────────────────────────────────────────────────────────────
    st.title("🗂️ Carga Inteligente de Datos")
    st.markdown(
        "_Valida tus archivos, detecta columnas, mide el contexto disponible y "
        "descubre qué módulos de CIMA pueden activarse._"
    )

    # ── Flujo visual siempre visible ──────────────────────────────────────
    _tiene_archivo = st.session_state.get("cima_uploaded_df") is not None
    _tiene_activo  = st.session_state.get("df") is not None

    _paso1_color = "#27ae60" if _tiene_archivo else "#3498db"
    _paso2_color = "#27ae60" if _tiene_archivo else "#7f8c8d"
    _paso3_color = "#27ae60" if _tiene_activo  else "#7f8c8d"
    _paso1_icono = "✅" if _tiene_archivo else "1️⃣"
    _paso2_icono = "✅" if _tiene_archivo else "2️⃣"
    _paso3_icono = "✅" if _tiene_activo  else "3️⃣"

    st.markdown(
        f"""
        <div style='display:flex;align-items:center;gap:0;margin:10px 0 18px 0;flex-wrap:wrap;'>
          <div style='background:{_paso1_color};color:white;border-radius:8px 0 0 8px;
               padding:8px 18px;font-weight:700;font-size:14px;'>
            {_paso1_icono} Sube tu archivo
          </div>
          <div style='background:#1a2a3a;color:#90CAF9;padding:8px 10px;
               font-size:18px;font-weight:700;'>›</div>
          <div style='background:{_paso2_color};color:white;padding:8px 18px;
               font-weight:700;font-size:14px;'>
            {_paso2_icono} Valida el esquema
          </div>
          <div style='background:#1a2a3a;color:#90CAF9;padding:8px 10px;
               font-size:18px;font-weight:700;'>›</div>
          <div style='background:{_paso3_color};color:white;border-radius:0 8px 8px 0;
               padding:8px 18px;font-weight:700;font-size:14px;'>
            {_paso3_icono} Activa el DataFrame y ve al módulo
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Mensajes de ayuda ─────────────────────────────────────────────────
    with st.expander("💡 ¿Cómo funciona?", expanded=False):
        st.markdown("""
CIMA no necesita datos perfectos para iniciar.
Con campos mínimos puede generar diagnósticos básicos y sugerir qué información
falta para mejorar el análisis.

**Mientras más campos agregues, más módulos y reportes se podrán activar.**

Este validador **no modifica tus datos**. Solo evalúa estructura, contexto y compatibilidad.

**Pasos sugeridos:**
1. Selecciona el tipo de datos que quieres cargar
2. Elige el esquema esperado (o usa *Detección automática*)
3. Sube tu archivo CSV o Excel
4. Revisa el diagnóstico y score de contexto
5. Descarga el reporte o usa el archivo como DataFrame activo
        """)

    # ════════════════════════════════════════════════════════════════════
    # PANEL DE CASOS DE USO — ¿qué quiero analizar? → plantilla
    # ════════════════════════════════════════════════════════════════════
    with st.expander("🗺️ ¿Qué quiero analizar? — casos de uso y plantillas", expanded=True):
        st.caption(
            "Elige el caso de uso que describe tu necesidad. "
            "Descarga la plantilla, llénala con tus datos y súbela aquí."
        )

        # ── Definición de casos de uso ────────────────────────────────
        _CASOS_USO = [
            {
                "id":          "ventas_basico",
                "titulo":      "📈 Ver desempeño de ventas",
                "descripcion": "¿Cómo van mis ventas mes a mes? ¿Quiénes son mis mejores clientes?",
                "obtienes":    ["📊 Desempeño Comercial", "📆 Comparativo Año vs Año"],
                "campos":      ["fecha", "monto"],
                "campos_plus": ["cliente", "vendedor", "linea_de_negocio", "producto"],
                "plantillas":  [("ventas_minimo.csv", "Plantilla Ventas Mínimo")],
                "color":       "#1565C0",
            },
            {
                "id":          "ventas_avanzado",
                "titulo":      "🏢 Análisis comercial completo",
                "descripcion": "Tendencias, líneas de negocio, productos top, YTD y heatmap de ventas.",
                "obtienes":    ["📈 Desempeño Comercial", "📅 YTD por Línea", "🏷️ YTD por Producto", "🔥 Heatmap"],
                "campos":      ["fecha", "monto", "linea_de_negocio"],
                "campos_plus": ["producto", "vendedor", "cliente", "region"],
                "plantillas":  [("ventas_comercial.csv", "Plantilla Ventas Comercial")],
                "color":       "#0D47A1",
            },
            {
                "id":          "cxc_basico",
                "titulo":      "💳 Saber quién me debe",
                "descripcion": "¿Cuánto me deben en total? ¿Está vencido? Listado de deudores.",
                "obtienes":    ["💳 KPI Cartera CxC (básico)"],
                "campos":      ["cliente", "saldo_adeudado"],
                "campos_plus": ["estatus", "vendedor", "dias_vencido"],
                "plantillas":  [("cxc_minimo.csv", "Plantilla CxC Mínimo")],
                "color":       "#4A148C",
            },
            {
                "id":          "cxc_aging",
                "titulo":      "📅 Aging y riesgo de cobranza",
                "descripcion": "Antigüedad de deuda por bucket, score de salud y clientes en riesgo.",
                "obtienes":    ["💳 KPI Cartera CxC completo", "📋 Reporte Consolidado CxC", "🏥 Score de salud"],
                "campos":      ["cliente", "saldo_adeudado", "fecha_vencimiento"],
                "campos_plus": ["fecha_emision", "dias_credito", "vendedor", "factura", "estatus"],
                "nota":        "dias_vencido se calcula automáticamente (hoy − fecha_vencimiento)",
                "plantillas":  [("cxc_aging.csv", "Plantilla CxC Aging")],
                "color":       "#6A1B9A",
            },
            {
                "id":          "ejecutivo",
                "titulo":      "🎯 Reporte Ejecutivo completo",
                "descripcion": "Ventas + cartera CxC en un solo archivo. Todos los campos → todos los módulos.",
                "obtienes":    ["🎯 Reporte Ejecutivo", "📋 Reporte Consolidado", "🤝 Vendedores + CxC",
                                "📈 Desempeño Comercial", "📅 YTD", "🔥 Heatmap", "💳 KPI CxC + Aging"],
                "campos":      ["fecha", "monto", "cliente", "vendedor", "linea_de_negocio", "producto",
                                "saldo_adeudado", "fecha_vencimiento"],
                "campos_plus": ["region", "canal", "fecha_emision", "dias_credito", "factura", "estatus"],
                "nota":        "dias_vencido se calcula automáticamente (hoy − fecha_vencimiento)",
                "plantillas":  [("plantilla_maestra.xlsx", "📥 Plantilla Maestra (Excel 3 hojas)")],
                "color":       "#1B5E20",
            },
        ]

        # ── Renderizar cards — fila 1: ventas (2 cols) + cxc básico ──
        _row1 = st.columns([1, 1, 1])
        _row2 = st.columns([1, 2])
        _layout = [
            (_row1[0], _CASOS_USO[0]),
            (_row1[1], _CASOS_USO[1]),
            (_row1[2], _CASOS_USO[2]),
            (_row2[0], _CASOS_USO[3]),
            (_row2[1], _CASOS_USO[4]),
        ]

        for _col, _caso in _layout:
            with _col:
                # Cabecera de color
                st.markdown(
                    f"<div style='background:{_caso['color']};color:white;"
                    f"border-radius:8px 8px 0 0;padding:10px 14px;"
                    f"font-weight:700;font-size:14px;'>"
                    f"{_caso['titulo']}</div>",
                    unsafe_allow_html=True,
                )
                # Cuerpo de la card
                st.markdown(
                    f"<div style='border:1px solid {_caso['color']};border-top:none;"
                    f"border-radius:0 0 8px 8px;padding:10px 14px;margin-bottom:8px;"
                    f"background:#0e1117;'>"
                    f"<p style='color:#ccc;font-size:13px;margin:0 0 8px 0;'>"
                    f"{_caso['descripcion']}</p>"
                    f"<p style='color:#90CAF9;font-size:12px;margin:0 0 4px 0;'>"
                    f"<b>Obtienes:</b></p>"
                    + "".join(
                        f"<span style='display:inline-block;background:#1a2a3a;"
                        f"color:#e0e0e0;border-radius:4px;padding:2px 8px;"
                        f"margin:2px 2px;font-size:12px;'>{m}</span>"
                        for m in _caso["obtienes"]
                    )
                    + f"<p style='color:#90CAF9;font-size:12px;margin:8px 0 2px 0;'>"
                    f"<b>Campos mínimos:</b> "
                    f"<code style='color:#fff;'>"
                    + " · ".join(_caso["campos"])
                    + f"</code></p>"
                    f"<p style='color:#888;font-size:11px;margin:0;'>"
                    f"Mejora con: {' · '.join(_caso['campos_plus'])}</p>"
                    + (
                        f"<p style='color:#F9A825;font-size:11px;margin:4px 0 0 0;'>"
                        f"⚡ {_caso['nota']}</p>"
                        if _caso.get("nota") else ""
                    )
                    + f"</div>",
                    unsafe_allow_html=True,
                )
                # Botones de descarga de plantilla
                for _fname, _label in _caso["plantillas"]:
                    _fpath = os.path.join(_TEMPLATES_DIR, _fname)
                    if os.path.exists(_fpath):
                        _mime = (
                            "application/vnd.openxmlformats-officedocument"
                            ".spreadsheetml.sheet"
                            if _fname.endswith(".xlsx") else "text/csv"
                        )
                        with open(_fpath, "rb") as _f:
                            st.download_button(
                                label=_label,
                                data=_f.read(),
                                file_name=_fname,
                                mime=_mime,
                                key=f"uc_{_caso['id']}_{_fname}",
                                use_container_width=True,
                            )
                    else:
                        st.caption(f"_{_label} (no disponible)_")

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════
    # SECCIÓN A — Configuración de carga
    # ════════════════════════════════════════════════════════════════════
    st.subheader("1. Configuración de carga")

    col_tipo, col_schema = st.columns([1, 1])

    with col_tipo:
        tipo_carga = st.selectbox(
            "Tipo de datos",
            options=list(_TIPO_A_SCHEMAS.keys()),
            index=0,
            key="cid_tipo_carga",
            help="Selecciona qué tipo de datos vas a cargar para filtrar los esquemas disponibles.",
        )

    with col_schema:
        schemas_disponibles = _TIPO_A_SCHEMAS.get(tipo_carga, [])

        if tipo_carga == "CFDI / XML":
            st.info(
                "📌 Los archivos CFDI/XML se procesan en el módulo "
                "**'📂 Cargar mis facturas'**. "
                "Aquí puedes validar datos CFDI ya exportados en CSV/XLSX."
            )

        schema_id = st.selectbox(
            "Esquema esperado",
            options=schemas_disponibles,
            key="cid_schema_id",
            help="El esquema define los campos obligatorios, recomendados y opcionales esperados.",
        )

    # Mostrar descripcion del schema seleccionado
    if schema_id:
        try:
            _schema_meta = get_schema(schema_id)
            st.caption(
                f"**{_schema_meta.get('nombre', schema_id)}** — "
                f"{_schema_meta.get('descripcion', '')}"
            )
            _campos_oblig = _schema_meta.get("campos_obligatorios", [])
            if _campos_oblig:
                st.caption(f"🔴 Obligatorios: `{'`, `'.join(_campos_oblig)}`")
        except Exception:
            pass

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════
    # SECCIÓN B — Plantillas descargables
    # ════════════════════════════════════════════════════════════════════
    st.subheader("2. Plantillas base")
    st.caption("Descarga una plantilla con el formato correcto para comenzar.")

    cols_tmpl = st.columns(len(_TEMPLATES_DISPONIBLES))
    for idx, (nombre, fname) in enumerate(_TEMPLATES_DISPONIBLES):
        fpath = os.path.join(_TEMPLATES_DIR, fname)
        with cols_tmpl[idx]:
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    st.download_button(
                        label=f"📥 {nombre}",
                        data=f.read(),
                        file_name=fname,
                        mime="text/csv",
                        key=f"cid_tmpl_{idx}",
                        use_container_width=True,
                    )
            else:
                st.warning(f"⚠️ {fname} no disponible")

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════
    # SECCIÓN C — Carga de archivo
    # ════════════════════════════════════════════════════════════════════
    st.subheader("3. Cargar archivo")

    archivo = st.file_uploader(
        "Sube tu archivo (CSV o Excel)",
        type=["csv", "xlsx", "xls"],
        key="cid_archivo",
        help="Formatos soportados: CSV, Excel (.xlsx, .xls). Tamaño máximo recomendado: 50 MB.",
    )

    df: pd.DataFrame | None = None
    hoja_leida: str | None = None

    if archivo is not None:
        nombre = archivo.name
        ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""

        if ext == "csv":
            df, error = _leer_csv_seguro(archivo)
            if error:
                st.error(f"❌ {error}")
                df = None
            else:
                hoja_leida = "CSV"

        elif ext in ("xlsx", "xls"):
            archivo_bytes = archivo.getvalue()

            # Obtener lista de hojas
            try:
                xls = pd.ExcelFile(archivo_bytes)
                hojas = xls.sheet_names
            except Exception as e:
                st.error(f"❌ No se pudo abrir el archivo Excel: {e}")
                hojas = []

            if hojas:
                _CXC_KEYWORDS = ("cxc", "vigente", "vencid", "vg", "vcd", "cuenta", "cobrar")
                _hojas_cxc = [h for h in hojas if any(k in h.lower() for k in _CXC_KEYWORDS)]

                if len(hojas) == 1:
                    hoja_sel = hojas[0]
                elif tipo_carga == "Cuentas por Cobrar" and _hojas_cxc:
                    st.warning(
                        f"⚠️ Se detectaron {len(_hojas_cxc)} hojas CxC: "
                        f"**{', '.join(_hojas_cxc)}**. "
                        "Este módulo valida una hoja a la vez. "
                        "Para fusionar hojas, usa el módulo **KPI Cartera CxC**."
                    )
                    hoja_sel = st.selectbox(
                        "Selecciona la hoja a validar",
                        options=hojas,
                        key="cid_hoja_sel",
                    )
                elif len(hojas) > 1:
                    hoja_sel = st.selectbox(
                        "📄 El archivo tiene múltiples hojas. Selecciona la hoja a validar:",
                        options=hojas,
                        key="cid_hoja_multi",
                    )
                else:
                    hoja_sel = hojas[0]

                df, error = _leer_excel_hoja(archivo_bytes, hoja_sel)
                if error:
                    st.error(f"❌ {error}")
                    df = None
                else:
                    hoja_leida = hoja_sel

        else:
            st.error(f"❌ Formato '{ext}' no soportado. Usa CSV o Excel (.xlsx).")

    # ════════════════════════════════════════════════════════════════════
    # SECCIÓN D — Procesamiento y validación
    # ════════════════════════════════════════════════════════════════════
    if df is not None and not df.empty:

        # Guardar en session_state
        st.session_state["cima_uploaded_df"]     = df
        st.session_state["cima_selected_schema"] = schema_id

        st.success(
            f"✅ Archivo cargado: **{archivo.name}** "
            f"| Hoja: **{hoja_leida}** "
            f"| {len(df):,} filas × {len(df.columns)} columnas"
        )

        # ── Vista previa ──────────────────────────────────────────────
        st.markdown("---")
        st.subheader("4. Vista previa del archivo")

        col_meta1, col_meta2, col_meta3 = st.columns(3)
        with col_meta1:
            st.metric("Filas", f"{len(df):,}")
        with col_meta2:
            st.metric("Columnas", len(df.columns))
        with col_meta3:
            _n_num = df.select_dtypes(include="number").shape[1]
            st.metric("Columnas numéricas", _n_num)

        with st.expander("📋 Primeras 10 filas", expanded=True):
            st.dataframe(df.head(10), use_container_width=True)

        with st.expander("📊 Tipos de datos y columnas", expanded=False):
            _tipos_df = pd.DataFrame({
                "Columna original": df.columns.tolist(),
                "Tipo":             [str(t) for t in df.dtypes.tolist()],
                "Nulos":            df.isnull().sum().tolist(),
                "% Nulos":          [
                    f"{v/len(df)*100:.1f}%" for v in df.isnull().sum().tolist()
                ],
            })
            st.dataframe(_tipos_df, use_container_width=True)

        # ── Mapeo canonico ────────────────────────────────────────────
        st.markdown("---")
        st.subheader("5. Mapeo de columnas")

        _mapping = map_columns(df.columns.tolist())
        _canonicos = [v for v in _mapping.values() if v is not None]
        _no_mapeadas = [k for k, v in _mapping.items() if v is None]

        col_map1, col_map2 = st.columns(2)
        with col_map1:
            st.markdown("**Columnas mapeadas a canónico:**")
            for orig, can in _mapping.items():
                if can:
                    st.markdown(
                        f"<span style='font-size:13px;'>"
                        f"<code>{orig}</code> → <code style='color:#27ae60;'>{can}</code>"
                        f"</span>",
                        unsafe_allow_html=True,
                    )

        with col_map2:
            if _no_mapeadas:
                st.markdown(
                    f"**⚠️ Sin mapeo canónico ({len(_no_mapeadas)}):**  \n"
                    "_Estas columnas no se reconocen en el diccionario de aliases. "
                    "Puedes agregarlas como alias en `schema_engine/column_mapper.py`._"
                )
                for col in _no_mapeadas:
                    st.markdown(
                        f"<code style='color:#e67e22;'>{col}</code>",
                        unsafe_allow_html=True,
                    )
            else:
                st.success("✅ Todas las columnas tienen mapeo canónico.")

        # ── Validación de esquema ─────────────────────────────────────
        st.markdown("---")
        st.subheader("6. Validación de esquema")

        try:
            validation_result = validate_dataframe_against_schema(df, schema_id)
            st.session_state["cima_validation_result"] = validation_result
        except Exception as e:
            st.error(f"❌ Error al validar esquema: {e}")
            return

        _valido = validation_result["valido"]
        _falt_oblig = validation_result["campos_faltantes_obligatorios"]
        _falt_recom = validation_result["campos_faltantes_recomendados"]
        _detectados = validation_result["campos_detectados"]
        _opcionales = validation_result["campos_opcionales_detectados"]
        _observaciones = validation_result.get("observaciones", [])

        # Estado general
        if _valido:
            st.success("✅ El archivo es **válido** para el esquema seleccionado.")
        else:
            st.error(
                f"❌ El archivo **no es válido** para el esquema `{schema_id}`. "
                f"Faltan campos obligatorios: `{'`, `'.join(_falt_oblig)}`"
            )
            st.info(
                "💡 El diagnóstico continúa aunque el archivo no sea totalmente válido. "
                "Puedes ver qué módulos se activarán con los datos disponibles."
            )

        col_val1, col_val2, col_val3 = st.columns(3)
        with col_val1:
            st.metric("Campos detectados", len(_detectados))
        with col_val2:
            st.metric("Obligatorios faltantes", len(_falt_oblig),
                      delta=f"-{len(_falt_oblig)}" if _falt_oblig else None,
                      delta_color="inverse")
        with col_val3:
            st.metric("Recomendados faltantes", len(_falt_recom),
                      delta=f"-{len(_falt_recom)}" if _falt_recom else None,
                      delta_color="inverse")

        with st.expander("📋 Detalle de validación", expanded=_falt_oblig != []):
            if _detectados:
                st.markdown(f"**Campos detectados:** `{'`, `'.join(_detectados)}`")
            if _falt_oblig:
                st.markdown(
                    f"**🔴 Obligatorios faltantes:** `{'`, `'.join(_falt_oblig)}`  \n"
                    "_Sin estos campos el módulo no puede activarse._"
                )
            if _falt_recom:
                st.markdown(
                    f"**🟠 Recomendados faltantes:** `{'`, `'.join(_falt_recom)}`  \n"
                    "_Sin estos campos el análisis estará limitado._"
                )
            if _opcionales:
                st.markdown(f"**🔵 Opcionales detectados:** `{'`, `'.join(_opcionales)}`")

            if _observaciones:
                st.markdown("**Observaciones:**")
                for obs in _observaciones:
                    st.caption(obs)

            if validation_result.get("diagnosticos_disponibles"):
                st.markdown(
                    f"**Diagnósticos disponibles:** "
                    f"`{'`, `'.join(validation_result['diagnosticos_disponibles'])}`"
                )
            if validation_result.get("diagnosticos_limitados"):
                st.markdown(
                    f"**Diagnósticos limitados:** "
                    f"`{'`, `'.join(validation_result['diagnosticos_limitados'])}`"
                )

        # ── Score de contexto ─────────────────────────────────────────
        st.markdown("---")
        st.subheader("7. Score de contexto")

        _detected_set = set(_detectados)
        try:
            context_result = calculate_context_score(_detected_set, schema_id=schema_id)
            st.session_state["cima_context_score"] = context_result
        except Exception as e:
            st.error(f"❌ Error al calcular score: {e}")
            context_result = {"score": 0, "detalle": {}}

        _score = context_result.get("score", 0)
        _label = score_label(_score)

        # Badge de score
        st.markdown(_score_badge(_score, _label), unsafe_allow_html=True)
        st.markdown("")

        # Barra de progreso
        st.progress(_score / 100, text=f"Contexto: {_score}%")

        # Descripcion
        _SCORE_DESC = {
            "Critico":   "No hay suficiente información para activar módulos de análisis.",
            "Limitado":  "Contexto básico. Solo se pueden generar diagnósticos generales.",
            "Funcional": "Contexto funcional. La mayoría de módulos comerciales pueden activarse.",
            "Bueno":     "Buen contexto. Análisis ejecutivo y cartera disponibles.",
            "Completo":  "Contexto robusto. Todos los módulos disponibles con estos datos.",
        }
        st.caption(_SCORE_DESC.get(_label, ""))

        # Desglose por dimension
        with st.expander("📊 Desglose por dimensión", expanded=True):
            _detalle = context_result.get("detalle", {})
            _DIM_NOMBRES = {
                "tiempo":        "⏱️ Tiempo",
                "valor":         "💰 Valor económico",
                "actor":         "👤 Actor",
                "clasificacion": "🏷️ Clasificación",
                "estado":        "📊 Estado / Condición",
            }
            if _detalle:
                for dim_key, dim_data in _detalle.items():
                    _nombre = _DIM_NOMBRES.get(dim_key, dim_key)
                    _presente = dim_data.get("presente", False)
                    st.markdown(_dim_bar(_nombre, _presente), unsafe_allow_html=True)
            else:
                st.caption("Sin desglose disponible para este esquema.")

        # ── Modulos activables ────────────────────────────────────────
        st.markdown("---")
        st.subheader("8. Módulos activables")

        _fuente_id = _TIPO_A_FUENTE.get(tipo_carga, "dataframe_flexible")
        try:
            activable_result = get_activable_modules(
                available_sources={_fuente_id},
                detected_fields=_detected_set,
                df_columns=df.columns.tolist(),
            )
            st.session_state["cima_activable_modules"] = activable_result
        except Exception as e:
            st.error(f"❌ Error al calcular módulos activables: {e}")
            activable_result = {
                "modulos_activables": [],
                "modulos_parciales": [],
                "modulos_no_activables": [],
                "detalle": {},
            }

        _act    = activable_result.get("modulos_activables", [])
        _parc   = activable_result.get("modulos_parciales", [])
        _no_act = activable_result.get("modulos_no_activables", [])
        _total  = len(_act) + len(_parc) + len(_no_act)

        # Resumen
        if _total > 0:
            st.info(
                f"**Con este archivo puedes activar {len(_act)} de {_total} módulos.** "
                + (
                    f"Otros {len(_parc)} módulos pueden activarse parcialmente."
                    if _parc else ""
                )
            )

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Activables", len(_act))
        with col_m2:
            st.metric("Parciales", len(_parc))
        with col_m3:
            st.metric("No activables", len(_no_act))

        # A) Activables
        if _act:
            with st.expander(f"✅ Módulos activables ({len(_act)})", expanded=True):
                for m in _act:
                    st.markdown(f"- ✅ **{m}**")

        # B) Parciales
        if _parc:
            with st.expander(f"⚠️ Módulos parcialmente activables ({len(_parc)})", expanded=False):
                for item in _parc:
                    if isinstance(item, dict):
                        _m = item.get("modulo", item)
                        _lim = item.get("limitacion", "")
                        _falt = item.get("campos_recomendados_faltantes", [])
                        st.markdown(f"- 🟠 **{_m}**")
                        if _lim:
                            st.caption(f"  Limitación: {_lim}")
                        if _falt:
                            st.caption(f"  Para mejorar, agrega: `{'`, `'.join(_falt)}`")
                    else:
                        st.markdown(f"- 🟠 **{item}**")

        # C) No activables
        if _no_act:
            with st.expander(f"❌ Módulos no activables ({len(_no_act)})", expanded=False):
                for item in _no_act:
                    if isinstance(item, dict):
                        _m = item.get("modulo", item)
                        _fuente_falt = item.get("fuente_faltante", "")
                        _campos_falt = item.get("campos_obligatorios_faltantes", [])
                        st.markdown(f"- ❌ **{_m}**")
                        if _fuente_falt:
                            st.caption(f"  Fuente requerida: `{_fuente_falt}`")
                        if _campos_falt:
                            st.caption(
                                f"  Campos obligatorios faltantes: "
                                f"`{'`, `'.join(_campos_falt)}`"
                            )
                    else:
                        st.markdown(f"- ❌ **{item}**")

        # ── Reporte descargable ───────────────────────────────────────
        st.markdown("---")
        st.subheader("9. Reporte de validación")

        try:
            _reporte_json = _construir_reporte_json(
                schema_id=schema_id,
                validation_result=validation_result,
                activable_result=activable_result,
                context_result=context_result,
            )
            st.download_button(
                label="📥 Descargar reporte JSON",
                data=_reporte_json,
                file_name="cima_schema_validation_report.json",
                mime="application/json",
                key="cid_download_report",
                use_container_width=False,
                help="Descarga el diagnóstico estructural. No incluye datos del archivo.",
            )
        except Exception as e:
            st.warning(f"⚠️ No se pudo generar el reporte: {e}")

        # ── Usar como DataFrame activo ────────────────────────────────
        st.markdown("---")
        st.subheader("10. Usar archivo como DataFrame activo")

        st.markdown(
            "Si quieres que este archivo sea el que usan los módulos de análisis "
            "(Desempeño Comercial, Comparativo, YTD, etc.), presiona el botón."
        )

        _df_activo = st.session_state.get("df")
        if _df_activo is not None:
            st.info(
                f"📌 Actualmente hay un DataFrame activo con "
                f"**{len(_df_activo):,} filas × {len(_df_activo.columns)} columnas**. "
                "Al presionar el botón, será reemplazado."
            )

        if st.button(
            "✅ Usar este archivo como DataFrame activo",
            key="cid_usar_como_activo",
            type="primary",
        ):
            st.session_state["df"] = df.copy()
            st.session_state["_df_fuente"] = "carga_inteligente"
            st.session_state.pop("archivo_path", None)

            # Reconstruir indice soberano si el modulo esta disponible
            try:
                from utils.sovereign_periods import build_sovereign_index
                _sov = build_sovereign_index(df)
                st.session_state["sovereign_index"] = _sov
                _meses = _sov.get("meses", [])
                if _meses:
                    st.session_state["sovereign_desde"] = _meses[0]
                    st.session_state["sovereign_hasta"] = _meses[-1]
                    st.session_state.setdefault("sovereign_granularidad", "mensual")
            except Exception:
                pass  # No critico

            st.success(
                "✅ Archivo asignado como DataFrame activo para módulos compatibles."
            )

            # ── Próximos pasos ────────────────────────────────────────────
            _act_mods = st.session_state.get("cima_activable_modules", {})
            _mods_ok  = _act_mods.get("modulos_activables", [])
            _mods_par = [m.get("modulo", m) if isinstance(m, dict) else m
                         for m in _act_mods.get("modulos_parciales", [])]

            # Mapa módulo CIMA → ítem de menú con emoji
            _MOD_MENU = {
                "Reporte Ejecutivo":      "🎯 Reporte Ejecutivo",
                "Reporte Consolidado":    "📋 Reporte Consolidado",
                "KPI Cartera CxC":        "💳 KPI Cartera CxC",
                "Desempeño Comercial":    "📈 Desempeño Comercial",
                "Comparativo Anual":      "📊 Comparativo Anual",
                "YTD vs Año Anterior":    "📅 YTD vs Año Anterior",
                "Mapa de Clientes":       "📍 Mapa de Clientes",
                "Asistente de Datos":     "🤖 Asistente de Datos",
            }

            _sugeridos = [
                _MOD_MENU[m] for m in _mods_ok if m in _MOD_MENU
            ] or [
                _MOD_MENU[m] for m in _mods_par if m in _MOD_MENU
            ]

            if _sugeridos:
                st.markdown("**👉 Próximos pasos — módulos disponibles con este archivo:**")
                for _item in _sugeridos:
                    st.markdown(
                        f"- Usa el menú lateral y selecciona **{_item}**"
                    )
            else:
                st.markdown(
                    "**👉 Usa el menú lateral para ir al módulo que desees analizar.**"
                )

    elif archivo is not None:
        st.warning("⚠️ El archivo fue recibido pero no pudo procesarse. Revisa el formato.")

    else:
        # Sin archivo — mostrar estado actual del session_state
        _df_prev = st.session_state.get("cima_uploaded_df")
        if _df_prev is not None:
            st.info(
                f"📌 Último archivo cargado en esta sesión: "
                f"**{len(_df_prev):,} filas × {len(_df_prev.columns)} columnas** "
                f"(schema: `{st.session_state.get('cima_selected_schema', '—')}`)"
            )
            if st.button("🔄 Ver diagnóstico del archivo anterior", key="cid_ver_previo"):
                st.rerun()
        else:
            st.info(
                "👆 Sube un archivo CSV o Excel para comenzar la validación. "
                "O descarga una plantilla base para empezar desde cero."
            )

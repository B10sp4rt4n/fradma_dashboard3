"""
Módulo: Asistente de Datos — Consultas en lenguaje natural sobre CFDIs.

Interfaz conversacional que permite hacer preguntas sobre los datos
de facturación ingestados en Neon PostgreSQL y obtener respuestas
con tablas, gráficas e interpretación IA.

Autor: Fradma Dashboard Team
Fecha: Febrero 2026
"""

import os
import streamlit as st
import pandas as pd

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from utils.nl2sql import (
    NL2SQLEngine,
    NL2SQLResult,
    validate_sql_static,
    get_example_questions,
    ALLOWED_TABLES,
    SCHEMA_CONTEXT,
    PSYCOPG2_AVAILABLE,
    OPENAI_AVAILABLE,
)


# =====================================================================
# CSS personalizado
# =====================================================================
ASSISTANT_CSS = """
<style>
.assistant-hero {
    background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
    padding: 2rem 2.5rem;
    border-radius: 16px;
    color: white;
    margin-bottom: 1.5rem;
}
.assistant-hero h2 {
    margin: 0 0 0.5rem 0;
    font-size: 1.8rem;
}
.assistant-hero p {
    margin: 0;
    opacity: 0.85;
    font-size: 1rem;
}
.chat-msg-user {
    background: #e8f4f8;
    border-left: 4px solid #2196F3;
    padding: 1rem 1.25rem;
    border-radius: 0 12px 12px 0;
    margin: 0.5rem 0;
}
.chat-msg-assistant {
    background: #f0f7f0;
    border-left: 4px solid #4CAF50;
    padding: 1rem 1.25rem;
    border-radius: 0 12px 12px 0;
    margin: 0.5rem 0;
}
.sql-block {
    background: #1e1e2e;
    color: #cdd6f4;
    padding: 1rem;
    border-radius: 8px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 0.85rem;
    overflow-x: auto;
    margin: 0.5rem 0;
}
.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 1.5rem;
    border-radius: 12px;
    text-align: center;
}
.metric-card .value {
    font-size: 2rem;
    font-weight: 700;
}
.metric-card .label {
    font-size: 0.9rem;
    opacity: 0.85;
}
.example-btn {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 0.5rem 1rem;
    cursor: pointer;
    transition: all 0.2s;
    margin: 0.25rem 0;
    width: 100%;
    text-align: left;
}
.example-btn:hover {
    background: #e9ecef;
    border-color: #adb5bd;
}
.schema-table {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin: 0.25rem 0;
    font-size: 0.85rem;
}
.history-entry {
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    cursor: pointer;
}
.status-badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
}
.status-ok { background: #d4edda; color: #155724; }
.status-err { background: #f8d7da; color: #721c24; }
</style>
"""


# =====================================================================
# Inicialización del engine
# =====================================================================
def _get_engine() -> NL2SQLEngine:
    """Obtiene o crea la instancia del engine NL2SQL."""
    if "nl2sql_engine" not in st.session_state:
        neon_url = st.session_state.get("nl2sql_neon_url", "")
        api_key = st.session_state.get("nl2sql_api_key", "")

        if not neon_url or not api_key:
            return None

        try:
            engine = NL2SQLEngine(
                connection_string=neon_url,
                api_key=api_key,
                model=st.session_state.get("nl2sql_model", "gpt-4o"),
            )
            st.session_state["nl2sql_engine"] = engine
        except Exception as e:
            st.error(f"Error inicializando motor: {e}")
            return None

    return st.session_state.get("nl2sql_engine")


def _invalidate_engine():
    """Invalida la instancia del engine para recrearla."""
    if "nl2sql_engine" in st.session_state:
        del st.session_state["nl2sql_engine"]


# =====================================================================
# Visualización automática
# =====================================================================
def _auto_chart(df: pd.DataFrame, chart_type: str, question: str):
    """
    Genera automáticamente la gráfica más apropiada.

    Args:
        df: DataFrame con resultados
        chart_type: Tipo sugerido (bar, line, pie, table, metric, scatter)
        question: Pregunta original para título
    """
    if not PLOTLY_AVAILABLE or df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    # Identificar columnas numéricas y categóricas
    num_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'datetime64']).columns.tolist()

    # Si es solo 1 fila con 1 columna numérica → metric
    if len(df) == 1 and len(num_cols) >= 1:
        chart_type = "metric"

    # Si solo tiene 1 fila sin numéricos → table
    if len(df) <= 2 and not num_cols:
        chart_type = "table"

    try:
        if chart_type == "metric" and num_cols:
            cols = st.columns(min(len(num_cols), 4))
            for i, col_name in enumerate(num_cols[:4]):
                value = df[col_name].iloc[0]
                with cols[i]:
                    if isinstance(value, (int, float)):
                        if abs(value) >= 1000:
                            st.metric(col_name, f"${value:,.2f}")
                        else:
                            st.metric(col_name, f"{value:,.2f}")
                    else:
                        st.metric(col_name, str(value))
            return

        if chart_type == "bar" and cat_cols and num_cols:
            x_col = cat_cols[0]
            y_col = num_cols[0]
            fig = px.bar(
                df.head(30),
                x=x_col,
                y=y_col,
                title=question[:80],
                color=y_col,
                color_continuous_scale="Viridis",
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            return

        if chart_type == "line" and num_cols:
            x_col = cat_cols[0] if cat_cols else df.columns[0]
            y_col = num_cols[0]
            fig = px.line(
                df,
                x=x_col,
                y=y_col,
                title=question[:80],
                markers=True,
            )
            fig.update_traces(line_width=3)
            st.plotly_chart(fig, use_container_width=True)
            return

        if chart_type == "pie" and cat_cols and num_cols:
            fig = px.pie(
                df.head(15),
                names=cat_cols[0],
                values=num_cols[0],
                title=question[:80],
                hole=0.4,
            )
            st.plotly_chart(fig, use_container_width=True)
            return

        if chart_type == "scatter" and len(num_cols) >= 2:
            fig = px.scatter(
                df,
                x=num_cols[0],
                y=num_cols[1],
                title=question[:80],
                hover_data=cat_cols[:1] if cat_cols else None,
            )
            st.plotly_chart(fig, use_container_width=True)
            return

    except Exception as e:
        # Fallback a tabla si la gráfica falla
        pass

    # Default: tabla con formato
    col_config = {}
    for col in num_cols:
        if any(kw in col.lower() for kw in ['total', 'monto', 'factur', 'venta', 'importe', 'saldo', 'mxn']):
            col_config[col] = st.column_config.NumberColumn(format="$%.2f")
        elif 'pct' in col.lower() or 'porcentaje' in col.lower() or '%' in col:
            col_config[col] = st.column_config.NumberColumn(format="%.1f%%")

    st.dataframe(df, use_container_width=True, hide_index=True, column_config=col_config)


# =====================================================================
# Componentes de UI
# =====================================================================
def _render_hero():
    """Hero banner."""
    st.markdown(ASSISTANT_CSS, unsafe_allow_html=True)
    st.markdown("""
    <div class="assistant-hero">
        <h2>🤖 Asistente de Datos</h2>
        <p>Haz preguntas en español sobre tus datos de facturación CFDI y obtén 
        respuestas instantáneas con tablas, gráficas e interpretación inteligente.</p>
    </div>
    """, unsafe_allow_html=True)


def _render_connection_setup():
    """Panel de configuración de conexión."""
    st.markdown("### 🔌 Configurar Conexión")

    st.info(
        "Para usar el Asistente de Datos necesitas:\n"
        "1. **URL de Neon PostgreSQL** con datos CFDI ingestados\n"
        "2. **API Key de OpenAI** para la generación de SQL e interpretación"
    )

    col1, col2 = st.columns(2)

    with col1:
        neon_url = st.text_input(
            "URL de Neon PostgreSQL",
            type="password",
            value=st.session_state.get("nl2sql_neon_url", os.getenv("NEON_DATABASE_URL", "")),
            help="postgresql://user:pass@host/db?sslmode=require",
            key="input_neon_url",
        )

    with col2:
        api_key = st.text_input(
            "API Key de OpenAI",
            type="password",
            value=st.session_state.get("nl2sql_api_key", os.getenv("OPENAI_API_KEY", "")),
            help="sk-...",
            key="input_api_key",
        )

    col_model, col_btn = st.columns([2, 1])

    with col_model:
        model = st.selectbox(
            "Modelo de IA",
            ["gpt-4o", "gpt-4o-mini"],
            index=0,
            help="gpt-4o genera SQL más preciso; gpt-4o-mini es más económico",
            key="input_model",
        )

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔌 Conectar", type="primary", use_container_width=True):
            if not neon_url:
                st.error("Ingresa la URL de Neon")
                return False
            if not api_key:
                st.error("Ingresa la API Key de OpenAI")
                return False

            # Sanitizar URL: quitar prefijo "psql " si el usuario copió el comando CLI
            neon_url = neon_url.strip()
            if neon_url.lower().startswith("psql "):
                neon_url = neon_url[5:].strip()
            # Quitar comillas envolventes
            if (neon_url.startswith('"') and neon_url.endswith('"')) or \
               (neon_url.startswith("'") and neon_url.endswith("'")):
                neon_url = neon_url[1:-1]
            # Validar formato básico
            if not neon_url.startswith(("postgresql://", "postgres://")):
                st.error(
                    "La URL debe comenzar con `postgresql://` o `postgres://`.\n\n"
                    "Ejemplo: `postgresql://user:pass@host/db?sslmode=require`"
                )
                return False

            st.session_state["nl2sql_neon_url"] = neon_url
            st.session_state["nl2sql_api_key"] = api_key
            st.session_state["nl2sql_model"] = model
            _invalidate_engine()

            engine = _get_engine()
            if engine:
                with st.spinner("Probando conexión..."):
                    ok, msg = engine.test_connection()
                if ok:
                    st.success(f"✅ {msg}")
                    st.session_state["nl2sql_connected"] = True
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
                    st.session_state["nl2sql_connected"] = False
            return False

    return st.session_state.get("nl2sql_connected", False)


def _render_sidebar_examples():
    """Preguntas de ejemplo en la barra lateral derecha."""
    examples = get_example_questions()

    st.markdown("### 💡 Preguntas de ejemplo")
    st.caption("Haz clic para copiar una pregunta")

    for cat in examples:
        with st.expander(f"{cat['icon']} {cat['category']}", expanded=False):
            for q in cat["questions"]:
                if st.button(
                    q,
                    key=f"ex_{hash(q)}",
                    use_container_width=True,
                ):
                    st.session_state["nl2sql_pending_question"] = q
                    st.rerun()


def _render_schema_explorer():
    """Explorador del esquema de base de datos."""
    st.markdown("### 🗄️ Esquema de Datos")
    st.caption("Tablas y vistas disponibles para consulta")

    engine = _get_engine()
    if not engine:
        st.warning("Conecta primero a la base de datos")
        return

    # Obtener conteos
    with st.spinner("Obteniendo información del esquema..."):
        counts = engine.get_table_counts()
        date_range = engine.get_date_range()

    # Mostrar rango de datos
    if date_range:
        st.success(f"📅 Datos disponibles: **{date_range[0]}** a **{date_range[1]}**")

    # Tablas
    for table in ALLOWED_TABLES:
        icon = "📋" if not table.startswith("v_") else "👁️"
        count = counts.get(table, "—")
        count_str = f"{count:,}" if isinstance(count, int) and count >= 0 else "N/A"

        st.markdown(
            f"""<div class="schema-table">
            {icon} <strong>{table}</strong> — {count_str} registros
            </div>""",
            unsafe_allow_html=True,
        )

    # Schema completo en expander
    with st.expander("📖 Ver esquema completo"):
        st.code(SCHEMA_CONTEXT, language="markdown")


def _render_chat_interface():
    """Interfaz principal de chat."""
    engine = _get_engine()
    if not engine:
        return

    # Inicializar historial de mensajes
    if "nl2sql_messages" not in st.session_state:
        st.session_state["nl2sql_messages"] = []

    # Mostrar mensajes existentes
    for msg_idx, msg in enumerate(st.session_state["nl2sql_messages"]):
        if msg["role"] == "user":
            with st.chat_message("user", avatar="🧑‍💼"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                _render_result_message(msg, msg_idx)

    # Verificar si hay pregunta pendiente (de ejemplo)
    pending = st.session_state.pop("nl2sql_pending_question", None)

    # Input de chat
    question = st.chat_input(
        "Escribe tu pregunta sobre los datos...",
        key="nl2sql_chat_input"
    )

    # Usar la pregunta pendiente si existe
    if pending and not question:
        question = pending

    if question:
        # Mostrar pregunta del usuario
        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(question)

        st.session_state["nl2sql_messages"].append({
            "role": "user",
            "content": question,
        })

        # Procesar con el engine
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🔍 Analizando pregunta y consultando datos..."):
                empresa_id = st.session_state.get("nl2sql_empresa_id")
                result = engine.ask(question, empresa_id=empresa_id)

            # Renderizar resultado
            msg_data = _build_result_message(result)
            new_idx = len(st.session_state["nl2sql_messages"])
            _render_result_message(msg_data, new_idx)

            st.session_state["nl2sql_messages"].append(msg_data)


def _build_result_message(result: NL2SQLResult) -> dict:
    """Construye un mensaje de resultado para almacenar en session_state."""
    msg = {
        "role": "assistant",
        "content": result.interpretation or result.error or "Sin resultado",
        "sql": result.sql,
        "success": result.success,
        "execution_time": result.execution_time,
        "row_count": result.row_count,
        "chart_suggestion": result.chart_suggestion,
        "error": result.error,
    }

    # Serializar DataFrame para session_state
    if result.dataframe is not None and not result.dataframe.empty:
        msg["dataframe_json"] = result.dataframe.to_json(orient="split", date_format="iso")

    return msg


def _render_result_message(msg: dict, msg_idx: int = 0):
    """Renderiza un mensaje de resultado del asistente."""
    if msg.get("error"):
        st.error(msg["error"])
        if msg.get("sql"):
            with st.expander("🔍 SQL generado"):
                st.code(msg["sql"], language="sql")
        return

    # Interpretación
    st.markdown(msg["content"])

    # DataFrame
    df = None
    if "dataframe_json" in msg:
        try:
            df = pd.read_json(msg["dataframe_json"], orient="split")
        except Exception:
            df = None

    if df is not None and not df.empty:
        # Gráfica automática
        chart_type = msg.get("chart_suggestion", "table")
        question = msg.get("content", "")

        # Pestañas: Gráfica | Tabla | SQL
        tab_chart, tab_table, tab_sql = st.tabs(["📊 Gráfica", "📋 Tabla", "🔍 SQL"])

        with tab_chart:
            _auto_chart(df, chart_type, question)

        with tab_table:
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Exportar
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Descargar CSV",
                csv,
                "resultado_consulta.csv",
                "text/csv",
                key=f"dl_{msg_idx}_{hash(msg.get('sql', ''))}",
            )

        with tab_sql:
            st.code(msg.get("sql", ""), language="sql")
            exec_time = msg.get("execution_time", 0)
            row_count = msg.get("row_count", 0)
            st.caption(f"⏱️ {exec_time:.2f}s · {row_count} filas")
    else:
        # Solo SQL si no hay datos
        if msg.get("sql"):
            with st.expander("🔍 SQL generado"):
                st.code(msg["sql"], language="sql")


def _render_history():
    """Panel de historial de consultas."""
    st.markdown("### 🕰️ Historial de Consultas")

    engine = _get_engine()
    if not engine:
        st.info("Conecta primero para ver el historial")
        return

    history = engine.get_history()

    if not history:
        st.info("Aún no has hecho consultas. ¡Pregunta algo!")
        return

    col_clear, _ = st.columns([1, 3])
    with col_clear:
        if st.button("🗑️ Limpiar historial"):
            engine.clear_history()
            st.session_state["nl2sql_messages"] = []
            st.rerun()

    for i, result in enumerate(history[:20]):
        status = "✅" if result.success else "❌"
        time_str = result.timestamp.strftime("%H:%M")

        with st.expander(
            f"{status} {time_str} — {result.question[:60]}...",
            expanded=False,
        ):
            if result.success:
                st.markdown(f"**Interpretación:** {result.interpretation}")
                st.code(result.sql, language="sql")
                st.caption(
                    f"⏱️ {result.execution_time:.2f}s · "
                    f"{result.row_count} filas · "
                    f"📊 {result.chart_suggestion}"
                )
            else:
                st.error(result.error)
                if result.sql:
                    st.code(result.sql, language="sql")

            # Re-ejecutar pregunta
            if st.button(
                "🔁 Repetir consulta",
                key=f"retry_{i}_{hash(result.question)}",
            ):
                st.session_state["nl2sql_pending_question"] = result.question
                st.rerun()


def _render_sql_playground():
    """Playground para escribir SQL directamente."""
    st.markdown("### 🛠️ SQL Playground")
    st.caption("Escribe y ejecuta SQL directamente (solo SELECT)")

    engine = _get_engine()
    if not engine:
        st.warning("Conecta primero a la base de datos")
        return

    sql_input = st.text_area(
        "Escribe tu consulta SQL:",
        height=150,
        placeholder="SELECT receptor_nombre, COUNT(*) AS facturas, SUM(total) AS total\nFROM cfdi_ventas\nGROUP BY receptor_nombre\nORDER BY total DESC\nLIMIT 10;",
        key="sql_playground_input",
    )

    col1, col2 = st.columns([1, 3])

    with col1:
        execute_btn = st.button("▶️ Ejecutar", type="primary", use_container_width=True)

    with col2:
        # Validación en tiempo real
        if sql_input:
            is_valid, err_msg = validate_sql_static(sql_input)
            if is_valid:
                st.success("✅ SQL válido")
            else:
                st.error(f"🛡️ {err_msg}")

    if execute_btn and sql_input:
        is_valid, err_msg = validate_sql_static(sql_input)
        if not is_valid:
            st.error(f"🛡️ Validación fallida: {err_msg}")
            return

        with st.spinner("Ejecutando consulta..."):
            try:
                import time
                t0 = time.time()
                df = engine.execute_query(sql_input)
                elapsed = time.time() - t0

                st.success(f"✅ {len(df)} filas en {elapsed:.2f}s")

                # Mostrar formato de moneda automáticamente
                num_cols = df.select_dtypes(include=['int64', 'float64']).columns
                col_config = {}
                for col in num_cols:
                    if any(kw in col.lower() for kw in ['total', 'monto', 'venta', 'importe', 'saldo']):
                        col_config[col] = st.column_config.NumberColumn(format="$%.2f")

                st.dataframe(df, use_container_width=True, hide_index=True, column_config=col_config)

                # Exportar
                csv = df.to_csv(index=False)
                st.download_button("📥 Descargar CSV", csv, "sql_result.csv", "text/csv")

            except Exception as e:
                st.error(f"❌ Error: {e}")


# =====================================================================
# Función principal
# =====================================================================
def run():
    """Punto de entrada del módulo Asistente de Datos."""

    # Verificar dependencias
    if not PSYCOPG2_AVAILABLE:
        st.error("❌ psycopg2 no está instalado. Ejecuta: `pip install psycopg2-binary`")
        return
    if not OPENAI_AVAILABLE:
        st.error("❌ openai no está instalado. Ejecuta: `pip install openai`")
        return

    # Hero
    _render_hero()

    # Verificar conexión
    is_connected = st.session_state.get("nl2sql_connected", False)

    if not is_connected:
        _render_connection_setup()
        return

    # Barra de estado de conexión
    col_status, col_disconnect = st.columns([4, 1])
    with col_status:
        model = st.session_state.get("nl2sql_model", "gpt-4o")
        st.success(f"🟢 Conectado a Neon · Modelo: **{model}**")
    with col_disconnect:
        if st.button("🔌 Desconectar"):
            st.session_state["nl2sql_connected"] = False
            _invalidate_engine()
            st.session_state["nl2sql_messages"] = []
            st.rerun()

    # Navegación horizontal
    mode = st.radio(
        "Modo:",
        ["💬 Chat", "🛠️ SQL Playground", "🗄️ Esquema", "🕰️ Historial"],
        horizontal=True,
        key="nl2sql_mode",
    )

    st.markdown("---")

    # Layout: contenido principal + sidebar de ejemplos
    if mode == "💬 Chat":
        col_main, col_side = st.columns([3, 1])

        with col_main:
            _render_chat_interface()

        with col_side:
            _render_sidebar_examples()

    elif mode == "🛠️ SQL Playground":
        _render_sql_playground()

    elif mode == "🗄️ Esquema":
        _render_schema_explorer()

    elif mode == "🕰️ Historial":
        _render_history()


if __name__ == "__main__":
    run()

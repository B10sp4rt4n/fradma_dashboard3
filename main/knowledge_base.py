"""
Módulo: Knowledge Base / Wiki — Interfaz Streamlit
===================================================
Buscador tipo wiki integrado al dashboard para navegar y buscar
en toda la documentación interna del sistema.

Features:
- Búsqueda full-text con ranking por relevancia
- Navegación por categorías
- Vista de documento completa con tabla de contenidos
- Documentos relacionados
- Estadísticas del índice
- Historial de búsquedas
"""

import streamlit as st
import re
import os
from datetime import datetime
from utils.knowledge_base import get_search_engine, invalidate_cache, SearchResult, Document


# =====================================================================
# CONSTANTES Y CONFIGURACIÓN
# =====================================================================

CATEGORY_ICONS = {
    "arquitectura": "🏗️",
    "análisis": "📊",
    "guía": "📖",
    "roadmap": "🗺️",
    "especificación": "📋",
    "reporte": "📄",
    "testing": "🧪",
    "configuración": "⚙️",
    "usuario": "👤",
    "refactoring": "🔧",
    "general": "📝",
}

CATEGORY_COLORS = {
    "arquitectura": "#4A90D9",
    "análisis": "#E67E22",
    "guía": "#27AE60",
    "roadmap": "#8E44AD",
    "especificación": "#2C3E50",
    "reporte": "#C0392B",
    "testing": "#16A085",
    "configuración": "#7F8C8D",
    "usuario": "#2980B9",
    "refactoring": "#D35400",
    "general": "#95A5A6",
}


# =====================================================================
# FUNCIONES AUXILIARES DE RENDERIZADO
# =====================================================================

def _render_category_badge(category: str) -> str:
    """Retorna HTML para badge de categoría."""
    icon = CATEGORY_ICONS.get(category, "📝")
    color = CATEGORY_COLORS.get(category, "#95A5A6")
    return (
        f'<span style="background-color: {color}; color: white; '
        f'padding: 2px 10px; border-radius: 12px; font-size: 0.8em; '
        f'font-weight: 500;">{icon} {category.title()}</span>'
    )


def _render_score_bar(score: float, max_score: float) -> str:
    """Retorna HTML para barra de relevancia."""
    pct = min(100, (score / max_score * 100)) if max_score > 0 else 0
    color = "#27AE60" if pct >= 70 else "#E67E22" if pct >= 40 else "#95A5A6"
    return (
        f'<div style="background: #eee; border-radius: 4px; height: 6px; width: 100px; display: inline-block;">'
        f'<div style="background: {color}; height: 100%; width: {pct}%; border-radius: 4px;"></div></div>'
        f' <span style="font-size: 0.75em; color: #888;">{pct:.0f}%</span>'
    )


def _format_word_count(count: int) -> str:
    """Formatea conteo de palabras."""
    if count >= 1000:
        return f"{count / 1000:.1f}K palabras"
    return f"{count} palabras"


def _shorten_path(path: str) -> str:
    """Acorta la ruta para mostrar solo la parte relevante."""
    parts = path.replace('\\', '/').split('/')
    # Buscar desde docs/ o la raíz del proyecto
    for i, part in enumerate(parts):
        if part in ('docs', 'main', 'cfdi', 'fradma_dashboard3'):
            return '/'.join(parts[i:])
    return parts[-1] if parts else path


# =====================================================================
# VISTAS PRINCIPALES
# =====================================================================

def _render_search_view(engine):
    """Vista principal de búsqueda."""

    # Barra de búsqueda prominente
    st.markdown("""
    <style>
    .search-container {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem 2rem 1.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
    }
    .search-title {
        color: #E8E8E8;
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .search-subtitle {
        color: #A0A0B0;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
    .result-card {
        background: #0E1117;
        border: 1px solid #262730;
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
        transition: border-color 0.2s;
    }
    .result-card:hover {
        border-color: #4A90D9;
    }
    .result-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #FAFAFA;
        margin-bottom: 0.3rem;
    }
    .result-path {
        font-size: 0.75rem;
        color: #6B7280;
        margin-bottom: 0.5rem;
    }
    .result-snippet {
        font-size: 0.9rem;
        color: #D1D5DB;
        line-height: 1.5;
        margin-top: 0.5rem;
    }
    .section-match {
        background: rgba(74, 144, 217, 0.1);
        border-left: 3px solid #4A90D9;
        padding: 0.5rem 0.8rem;
        margin: 0.4rem 0;
        border-radius: 0 6px 6px 0;
        font-size: 0.85rem;
    }
    .stat-box {
        background: rgba(255,255,255,0.05);
        border-radius: 8px;
        padding: 0.8rem;
        text-align: center;
    }
    .stat-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #4A90D9;
    }
    .stat-label {
        font-size: 0.75rem;
        color: #999;
        text-transform: uppercase;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="search-container">
        <div class="search-title">🔍 Knowledge Base</div>
        <div class="search-subtitle">Busca en toda la documentación del sistema — {} documentos indexados</div>
    </div>
    """.format(len(engine.documents)), unsafe_allow_html=True)

    # Controles de búsqueda
    col_search, col_cat, col_max = st.columns([5, 2, 1])

    with col_search:
        query = st.text_input(
            "Buscar",
            placeholder="Ej: arquitectura, CFDI, multi-usuario, ROI, pricing...",
            label_visibility="collapsed",
            key="kb_search_query"
        )

    categories = engine.get_categories()
    cat_options = ["Todas las categorías"] + [
        f"{CATEGORY_ICONS.get(c, '📝')} {c.title()} ({n})"
        for c, n in categories.items()
    ]

    with col_cat:
        selected_cat_display = st.selectbox(
            "Categoría", cat_options, label_visibility="collapsed",
            key="kb_search_cat"
        )

    with col_max:
        max_results = st.selectbox(
            "Max", [5, 10, 20, 50], index=1, label_visibility="collapsed",
            key="kb_search_max"
        )

    # Parsear categoría seleccionada
    selected_category = None
    if selected_cat_display != "Todas las categorías":
        # Extraer nombre de categoría del display
        cat_name = selected_cat_display.split(" ", 1)[-1].rsplit(" (", 1)[0].lower()
        selected_category = cat_name

    # Ejecutar búsqueda
    if query and query.strip():
        results = engine.search(query, max_results=max_results, category=selected_category)

        if results:
            max_score = results[0].score if results else 1

            st.markdown(f"**{len(results)} resultado{'s' if len(results) > 1 else ''}** para *\"{query}\"*")
            st.markdown("---")

            for i, result in enumerate(results):
                doc = result.document
                badge = _render_category_badge(doc.category)
                score_bar = _render_score_bar(result.score, max_score)
                short_path = _shorten_path(doc.path)

                st.markdown(f"""
                <div class="result-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div class="result-title">{doc.title}</div>
                        <div>{badge}</div>
                    </div>
                    <div class="result-path">📁 {short_path} · {_format_word_count(doc.word_count)} · {score_bar}</div>
                </div>
                """, unsafe_allow_html=True)

                # Mostrar secciones matcheadas con expander
                if result.matched_sections:
                    with st.expander(f"📑 {len(result.matched_sections)} secciones relevantes", expanded=(i < 2)):
                        for ms in result.matched_sections[:4]:
                            st.markdown(f"""
                            <div class="section-match">
                                <strong>§ {ms['heading']}</strong> <span style="color:#666; font-size:0.75em;">(línea ~{ms['line_number']})</span>
                                <div class="result-snippet">{ms['snippet'][:300]}{'...' if len(ms['snippet']) > 300 else ''}</div>
                            </div>
                            """, unsafe_allow_html=True)

                        # Botón para ver documento completo
                        if st.button(f"📖 Ver documento completo", key=f"view_doc_{doc.id}_{i}"):
                            st.session_state["kb_view_doc"] = doc.id
                            st.session_state["kb_current_tab"] = "document"
                            st.rerun()
        else:
            st.info(f"🔍 No se encontraron resultados para \"{query}\"")
            st.markdown("""
            **Sugerencias:**
            - Intenta con palabras clave más generales
            - Revisa la ortografía
            - Prueba sinónimos (ej: "usuario" → "multi-usuario")
            """)

    else:
        # Sin búsqueda: mostrar resumen y categorías
        _render_homepage(engine)


def _render_homepage(engine):
    """Vista de inicio cuando no hay búsqueda activa."""
    stats = engine.get_stats()

    # KPIs del Knowledge Base
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📚 Documentos", stats["total_documents"])
    with col2:
        st.metric("📝 Palabras", f"{stats['total_words']:,}")
    with col3:
        st.metric("📑 Secciones", stats["total_sections"])
    with col4:
        st.metric("🔤 Tokens únicos", f"{stats['unique_tokens']:,}")

    st.markdown("---")

    # Navegación por categorías
    st.subheader("📂 Navegar por Categoría")

    categories = engine.get_categories()

    # Grid de categorías
    cols = st.columns(min(4, len(categories)))
    for i, (cat, count) in enumerate(categories.items()):
        col_idx = i % len(cols)
        with cols[col_idx]:
            icon = CATEGORY_ICONS.get(cat, "📝")
            color = CATEGORY_COLORS.get(cat, "#95A5A6")
            if st.button(
                f"{icon} {cat.title()} ({count})",
                key=f"cat_btn_{cat}",
                use_container_width=True
            ):
                st.session_state["kb_browse_category"] = cat

    # Mostrar documentos de categoría seleccionada
    browse_cat = st.session_state.get("kb_browse_category", None)
    if browse_cat:
        st.markdown(f"### {CATEGORY_ICONS.get(browse_cat, '📝')} {browse_cat.title()}")
        docs = engine.get_all_documents(category=browse_cat)

        for doc in docs:
            col_title, col_info, col_action = st.columns([4, 3, 1])
            with col_title:
                st.markdown(f"**{doc.title}**")
            with col_info:
                st.caption(f"{_format_word_count(doc.word_count)} · {_shorten_path(doc.path)}")
            with col_action:
                if st.button("📖", key=f"browse_{doc.id}", help="Ver documento"):
                    st.session_state["kb_view_doc"] = doc.id
                    st.session_state["kb_current_tab"] = "document"
                    st.rerun()
    else:
        # Documentos recientes (por fecha de modificación)
        st.subheader("🕐 Documentos Recientes")
        all_docs = sorted(
            engine.documents.values(),
            key=lambda d: d.last_modified,
            reverse=True
        )[:8]

        for doc in all_docs:
            col_title, col_cat, col_info = st.columns([4, 2, 2])
            with col_title:
                if st.button(f"📄 {doc.title}", key=f"recent_{doc.id}", use_container_width=True):
                    st.session_state["kb_view_doc"] = doc.id
                    st.session_state["kb_current_tab"] = "document"
                    st.rerun()
            with col_cat:
                st.markdown(_render_category_badge(doc.category), unsafe_allow_html=True)
            with col_info:
                st.caption(f"{_format_word_count(doc.word_count)}")


def _render_document_view(engine):
    """Vista de documento completo tipo wiki."""
    doc_id = st.session_state.get("kb_view_doc", None)

    if not doc_id:
        st.info("Selecciona un documento para visualizar.")
        return

    doc = engine.get_document_by_id(doc_id)
    if not doc:
        st.error("Documento no encontrado.")
        return

    # Botón de regreso
    if st.button("← Volver a búsqueda", key="kb_back"):
        st.session_state.pop("kb_view_doc", None)
        st.session_state["kb_current_tab"] = "search"
        st.rerun()

    # Header del documento
    badge = _render_category_badge(doc.category)
    st.markdown(f"# {doc.title}")
    st.markdown(f"""
    {badge} &nbsp; 📁 `{_shorten_path(doc.path)}` &nbsp; 
    📝 {_format_word_count(doc.word_count)} &nbsp;
    🕐 {doc.last_modified[:10]}
    """, unsafe_allow_html=True)

    # Metadata si existe
    meta = doc.metadata
    if meta.get("version") or meta.get("author"):
        meta_parts = []
        if meta.get("version"):
            meta_parts.append(f"**Versión:** {meta['version']}")
        if meta.get("author"):
            meta_parts.append(f"**Autor:** {meta['author']}")
        if meta.get("doc_date"):
            meta_parts.append(f"**Fecha:** {meta['doc_date']}")
        st.caption(" · ".join(meta_parts))

    st.markdown("---")

    # Layout: TOC + Contenido
    col_toc, col_content = st.columns([1, 3])

    with col_toc:
        st.markdown("#### 📋 Contenido")
        for section in doc.sections:
            indent = "&nbsp;" * (section["level"] * 2) if section["level"] > 1 else ""
            heading = section["heading"][:50]
            st.markdown(
                f'{indent}{"•" if section["level"] > 1 else "▸"} {heading}',
                help=f'Línea ~{section["line_number"]}'
            )

    with col_content:
        # Renderizar contenido completo (Markdown nativo de Streamlit)
        # Limitar el contenido para no sobrecargar la UI
        content = doc.content
        if len(content) > 50000:
            # Para docs muy largos, mostrar por secciones
            st.warning(f"Documento grande ({_format_word_count(doc.word_count)}). Mostrando por secciones.")
            for section in doc.sections:
                with st.expander(f"**{section['heading']}**", expanded=False):
                    st.markdown(section["content"][:5000])
        else:
            st.markdown(content)

    # Documentos relacionados
    st.markdown("---")
    st.subheader("🔗 Documentos Relacionados")
    related = engine.get_related_documents(doc_id, max_results=5)

    if related:
        cols = st.columns(min(5, len(related)))
        for i, (rel_doc, rel_score) in enumerate(related):
            with cols[i % len(cols)]:
                icon = CATEGORY_ICONS.get(rel_doc.category, "📝")
                if st.button(
                    f"{icon} {rel_doc.title[:30]}{'...' if len(rel_doc.title) > 30 else ''}",
                    key=f"related_{rel_doc.id}",
                    use_container_width=True,
                    help=f"{rel_doc.category.title()} · {_format_word_count(rel_doc.word_count)}"
                ):
                    st.session_state["kb_view_doc"] = rel_doc.id
                    st.rerun()
    else:
        st.caption("No se encontraron documentos relacionados.")


def _render_stats_view(engine):
    """Vista de estadísticas del Knowledge Base."""
    stats = engine.get_stats()

    st.subheader("📊 Estadísticas del Knowledge Base")

    # KPIs principales
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📚 Documentos", stats["total_documents"])
    with col2:
        st.metric("📝 Palabras totales", f"{stats['total_words']:,}")
    with col3:
        st.metric("📑 Secciones", stats["total_sections"])
    with col4:
        st.metric("🔤 Tokens indexados", f"{stats['unique_tokens']:,}")
    with col5:
        st.metric("🔍 Búsquedas", stats["total_searches"])

    st.markdown("---")

    col_cats, col_docs = st.columns(2)

    with col_cats:
        st.markdown("#### 📂 Documentos por Categoría")
        categories = stats["categories"]
        for cat, count in categories.items():
            icon = CATEGORY_ICONS.get(cat, "📝")
            pct = count / stats["total_documents"] * 100 if stats["total_documents"] > 0 else 0
            st.markdown(
                f'{icon} **{cat.title()}**: {count} doc{"s" if count > 1 else ""} ({pct:.0f}%)'
            )
            st.progress(pct / 100)

    with col_docs:
        st.markdown("#### 📏 Top Documentos por Tamaño")
        all_docs = sorted(engine.documents.values(), key=lambda d: d.word_count, reverse=True)[:10]
        for i, doc in enumerate(all_docs, 1):
            icon = CATEGORY_ICONS.get(doc.category, "📝")
            st.markdown(
                f'{i}. {icon} **{doc.title[:40]}{"..." if len(doc.title) > 40 else ""}** — '
                f'{_format_word_count(doc.word_count)}'
            )

    # Historial de búsquedas
    st.markdown("---")
    st.markdown("#### 🕐 Historial de Búsquedas Recientes")
    history = engine.get_search_history(limit=15)
    if history:
        for entry in history:
            col_q, col_r, col_t = st.columns([4, 1, 2])
            with col_q:
                st.markdown(f'🔍 **"{entry.query}"**')
            with col_r:
                st.caption(f"{entry.total_results} resultados")
            with col_t:
                st.caption(f"⚡ {entry.search_time_ms:.1f}ms · {entry.timestamp[:16]}")
    else:
        st.caption("Aún no hay búsquedas registradas. ¡Prueba buscar algo!")

    # Botón reindexar
    st.markdown("---")
    if st.button("🔄 Re-indexar documentos", help="Vuelve a leer todos los archivos MD"):
        invalidate_cache()
        st.rerun()


# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================

def run():
    """Punto de entrada del módulo Knowledge Base."""

    st.title("📚 Knowledge Base")
    st.caption("Wiki interna y buscador de documentación del sistema")

    # Inicializar engine
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    engine = get_search_engine(base_dir)

    if not engine.documents:
        st.error("❌ No se encontraron documentos para indexar.")
        st.info("Asegúrate de tener archivos .md en el directorio docs/")
        return

    # Tabs de navegación dentro del módulo
    current_tab = st.session_state.get("kb_current_tab", "search")

    # Si hay un documento seleccionado, ir a la vista de documento
    if st.session_state.get("kb_view_doc"):
        current_tab = "document"

    tab_search, tab_browse, tab_stats = st.tabs([
        "🔍 Buscar",
        "📖 Documento",
        "📊 Estadísticas"
    ])

    with tab_search:
        _render_search_view(engine)

    with tab_browse:
        _render_document_view(engine)

    with tab_stats:
        _render_stats_view(engine)

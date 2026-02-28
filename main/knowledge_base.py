"""
Módulo: Knowledge Base / Wiki — Interfaz Streamlit
===================================================
Buscador tipo wiki integrado al dashboard para navegar y buscar
en toda la documentación interna del sistema.

Features:
- Búsqueda full-text con ranking por relevancia
- Selector dinámico de documentos (selectbox)
- Vista de documento completa con tabla de contenidos navegable
- Documentos relacionados con navegación cruzada
- Navegación por categorías interactiva
- Estadísticas del índice
"""

import streamlit as st
import re
import os
from datetime import datetime
from utils.knowledge_base import get_search_engine, invalidate_cache, SearchResult, Document


# =====================================================================
# CONSTANTES
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


def _badge_html(category: str) -> str:
    icon = CATEGORY_ICONS.get(category, "📝")
    color = CATEGORY_COLORS.get(category, "#95A5A6")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:0.78em;font-weight:500;">'
        f'{icon} {category.title()}</span>'
    )


def _short_path(path: str) -> str:
    parts = path.replace('\\', '/').split('/')
    for i, p in enumerate(parts):
        if p in ('docs', 'main', 'cfdi', 'fradma_dashboard3'):
            return '/'.join(parts[i:])
    return parts[-1] if parts else path


def _fmt_words(n: int) -> str:
    return f"{n/1000:.1f}K" if n >= 1000 else str(n)


# =====================================================================
# CSS
# =====================================================================

_CSS = """
<style>
.kb-hero {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 1.5rem 2rem 1rem;
    border-radius: 14px;
    margin-bottom: 1rem;
}
.kb-hero h3 { color:#E8E8E8; margin:0 0 .3rem; }
.kb-hero p  { color:#A0A0B0; font-size:.88rem; margin:0; }
.doc-header {
    background: linear-gradient(135deg, #0f3460 0%, #1a1a2e 100%);
    padding: 1.2rem 1.5rem;
    border-radius: 12px;
    margin-bottom: 1rem;
}
.doc-header h2 { color:#FAFAFA; margin:0 0 .4rem; font-size:1.4rem; }
.doc-meta { color:#9CA3AF; font-size:.8rem; }
.section-card {
    background: rgba(74,144,217,0.08);
    border-left: 3px solid #4A90D9;
    padding: .6rem .9rem;
    margin: .35rem 0;
    border-radius: 0 8px 8px 0;
}
.section-card strong { color:#E8E8E8; }
.section-card .snippet { color:#D1D5DB; font-size:.85rem; line-height:1.45; margin-top:.3rem; }
</style>
"""


# =====================================================================
# VISTA: EXPLORADOR DE DOCUMENTOS
# =====================================================================

def _render_explorer(engine):
    """Navegador de documentos con selector y categorías."""

    all_docs = sorted(engine.documents.values(), key=lambda d: d.title)
    categories = engine.get_categories()

    # ── Filtro por categoría ──
    cat_options = ["📂 Todas las categorías"] + [
        f"{CATEGORY_ICONS.get(c, '📝')} {c.title()} ({n})"
        for c, n in categories.items()
    ]
    selected_cat_str = st.selectbox(
        "Filtrar por categoría",
        cat_options,
        key="kb_explorer_cat",
        label_visibility="collapsed"
    )

    # Parsear categoría
    if selected_cat_str == "📂 Todas las categorías":
        filtered_docs = all_docs
    else:
        cat_name = selected_cat_str.split(" ", 1)[-1].rsplit(" (", 1)[0].lower()
        filtered_docs = [d for d in all_docs if d.category == cat_name]

    if not filtered_docs:
        st.info("No hay documentos en esta categoría.")
        return

    # ── Lista de documentos seleccionable ──
    doc_labels = [
        f"{CATEGORY_ICONS.get(d.category, '📝')} {d.title}  ({_fmt_words(d.word_count)} palabras)"
        for d in filtered_docs
    ]

    # Preseleccionar si hay un doc activo
    default_idx = 0
    active_doc_id = st.session_state.get("kb_view_doc")
    if active_doc_id:
        for i, d in enumerate(filtered_docs):
            if d.id == active_doc_id:
                default_idx = i
                break

    selected_idx = st.selectbox(
        "Selecciona un documento para visualizar:",
        range(len(doc_labels)),
        format_func=lambda i: doc_labels[i],
        index=default_idx,
        key="kb_doc_selector",
    )

    doc = filtered_docs[selected_idx]
    st.session_state["kb_view_doc"] = doc.id

    st.markdown("---")

    # ── Renderizar documento seleccionado ──
    _render_document(engine, doc)


# =====================================================================
# VISTA: BÚSQUEDA
# =====================================================================

def _render_search(engine):
    """Búsqueda full-text con resultados y vista de documento inline."""

    col_q, col_max = st.columns([6, 1])
    with col_q:
        query = st.text_input(
            "Buscar",
            placeholder="Ej: arquitectura, CFDI, multi-usuario, ROI, treemap, pricing...",
            label_visibility="collapsed",
            key="kb_search_q"
        )
    with col_max:
        max_res = st.selectbox("Max", [5, 10, 20, 50], index=1,
                               label_visibility="collapsed", key="kb_max")

    if not query or not query.strip():
        st.caption("Escribe una consulta para buscar en todos los documentos indexados.")
        return

    results = engine.search(query, max_results=max_res)

    if not results:
        st.warning(f'Sin resultados para "{query}". Intenta otras palabras clave.')
        return

    max_score = results[0].score
    history = engine.get_search_history(1)
    search_ms = history[0].search_time_ms if history else 0

    st.markdown(f"**{len(results)} resultado{'s' if len(results)>1 else ''}** · "
                f"_{search_ms:.1f}ms_")
    st.markdown("---")

    # ── Selector de resultado ──
    result_labels = [
        f"#{i+1} — {r.document.title}  (relevancia: {min(100, r.score/max_score*100):.0f}%)"
        for i, r in enumerate(results)
    ]

    chosen = st.radio(
        "Selecciona un resultado para ver el documento:",
        range(len(result_labels)),
        format_func=lambda i: result_labels[i],
        key="kb_result_pick",
        horizontal=False,
    )

    result = results[chosen]
    doc = result.document

    # ── Secciones relevantes (snippets) ──
    if result.matched_sections:
        with st.expander(f"📑 {len(result.matched_sections)} secciones con coincidencias", expanded=True):
            for ms in result.matched_sections[:5]:
                snippet = ms['snippet'][:350]
                # Resaltar tokens de la query
                for token in engine._tokenize(query):
                    pattern = re.compile(re.escape(token), re.IGNORECASE)
                    snippet = pattern.sub(lambda m: f"**{m.group()}**", snippet)

                st.markdown(f"""<div class="section-card">
                    <strong>§ {ms['heading']}</strong>
                    <span style="color:#666;font-size:.72em;"> (línea ~{ms['line_number']})</span>
                    <div class="snippet">{snippet}</div>
                </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Documento completo inline ──
    _render_document(engine, doc)


# =====================================================================
# RENDERIZADOR DE DOCUMENTO
# =====================================================================

def _render_document(engine, doc: Document):
    """Renderiza un documento completo con TOC, contenido y docs relacionados."""

    badge = _badge_html(doc.category)
    path_short = _short_path(doc.path)
    meta = doc.metadata

    # Header
    st.markdown(f"""<div class="doc-header">
        <h2>{doc.title}</h2>
        <div class="doc-meta">
            {badge} &nbsp;&nbsp; 📁 {path_short} &nbsp;&nbsp;
            📝 {_fmt_words(doc.word_count)} palabras &nbsp;&nbsp;
            📑 {len(doc.sections)} secciones &nbsp;&nbsp;
            🕐 {doc.last_modified[:10]}
            {f" &nbsp;&nbsp; 📌 v{meta['version']}" if meta.get('version') else ""}
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Layout: TOC a la izquierda, contenido a la derecha ──
    col_toc, col_content = st.columns([1, 3])

    with col_toc:
        st.markdown("##### 📋 Índice")

        # Generar TOC como radio buttons por sección
        section_labels = []
        for s in doc.sections:
            prefix = "  " * max(0, s["level"] - 1)
            heading_short = s["heading"][:45]
            section_labels.append(f"{prefix}{'▸' if s['level'] <= 2 else '•'} {heading_short}")

        # Agregar opción de "documento completo" al inicio
        view_options = ["📄 Documento completo"] + section_labels

        sec_choice = st.radio(
            "Navegar:",
            range(len(view_options)),
            format_func=lambda i: view_options[i],
            key=f"toc_{doc.id}",
            label_visibility="collapsed",
        )

        # Metadata
        st.markdown("---")
        st.caption("**Info:**")
        if meta.get("author"):
            st.caption(f"✍️ {meta['author']}")
        if meta.get("doc_date"):
            st.caption(f"📅 {meta['doc_date']}")
        if meta.get("tables"):
            st.caption(f"📊 {meta['tables']} tablas")
        if meta.get("code_blocks"):
            st.caption(f"💻 {meta['code_blocks']} bloques de código")
        st.caption(f"📏 {doc.word_count:,} palabras")

    with col_content:
        if sec_choice == 0:
            # ── Documento completo ──
            _render_full_content(doc)
        else:
            # ── Sección individual ──
            section = doc.sections[sec_choice - 1]

            st.markdown(f"### {section['heading']}")
            st.caption(f"Línea ~{section['line_number']} · Nivel H{section['level']}")

            content = section["content"]
            if len(content) > 10000:
                st.markdown(content[:10000])
                st.info(f"⚠️ Sección truncada ({len(content):,} chars). "
                        "Selecciona '📄 Documento completo' para ver todo.")
            else:
                st.markdown(content)

            # Navegación rápida entre secciones
            st.markdown("---")
            col_prev, col_next = st.columns(2)
            sec_idx = sec_choice - 1
            with col_prev:
                if sec_idx > 0:
                    prev_name = doc.sections[sec_idx - 1]["heading"][:30]
                    if st.button(f"⬅️ {prev_name}", key=f"prev_{doc.id}",
                                 use_container_width=True):
                        st.session_state[f"toc_{doc.id}"] = sec_choice - 1
                        st.rerun()
            with col_next:
                if sec_idx < len(doc.sections) - 1:
                    next_name = doc.sections[sec_idx + 1]["heading"][:30]
                    if st.button(f"{next_name} ➡️", key=f"next_{doc.id}",
                                 use_container_width=True):
                        st.session_state[f"toc_{doc.id}"] = sec_choice + 1
                        st.rerun()

    # ── Documentos relacionados ──
    st.markdown("---")
    st.markdown("#### 🔗 Documentos Relacionados")
    related = engine.get_related_documents(doc.id, max_results=6)

    if related:
        cols = st.columns(min(3, len(related)))
        for i, (rel_doc, rel_score) in enumerate(related):
            with cols[i % len(cols)]:
                icon = CATEGORY_ICONS.get(rel_doc.category, "📝")
                if st.button(
                    f"{icon} {rel_doc.title[:35]}{'...' if len(rel_doc.title)>35 else ''}",
                    key=f"rel_{doc.id}_{rel_doc.id}",
                    use_container_width=True,
                    help=f"{rel_doc.category.title()} · {_fmt_words(rel_doc.word_count)} palabras"
                ):
                    st.session_state["kb_view_doc"] = rel_doc.id
                    st.rerun()
    else:
        st.caption("No se encontraron documentos relacionados.")


def _render_full_content(doc: Document):
    """Renderiza el contenido completo de un documento."""
    content = doc.content
    if len(content) > 60000:
        # Docs muy grandes: renderizar por secciones colapsables
        st.warning(f"Documento grande ({doc.word_count:,} palabras). Mostrando por secciones.")
        for section in doc.sections:
            with st.expander(f"**{section['heading']}**", expanded=False):
                sec_content = section["content"]
                st.markdown(sec_content[:6000])
                if len(sec_content) > 6000:
                    st.caption(f"... ({len(sec_content):,} caracteres)")
    else:
        st.markdown(content)


# =====================================================================
# VISTA: ESTADÍSTICAS
# =====================================================================

def _render_stats(engine):
    """Panel de estadísticas del Knowledge Base."""
    stats = engine.get_stats()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📚 Docs", stats["total_documents"])
    col2.metric("📝 Palabras", f"{stats['total_words']:,}")
    col3.metric("📑 Secciones", stats["total_sections"])
    col4.metric("🔤 Tokens", f"{stats['unique_tokens']:,}")
    col5.metric("🔍 Búsquedas", stats["total_searches"])

    st.markdown("---")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### 📂 Por Categoría")
        for cat, count in stats["categories"].items():
            icon = CATEGORY_ICONS.get(cat, "📝")
            pct = count / stats["total_documents"] * 100
            st.markdown(f'{icon} **{cat.title()}**: {count} ({pct:.0f}%)')
            st.progress(pct / 100)

    with c2:
        st.markdown("##### 📏 Top por Tamaño")
        top_docs = sorted(engine.documents.values(), key=lambda d: d.word_count, reverse=True)[:10]
        for i, d in enumerate(top_docs, 1):
            icon = CATEGORY_ICONS.get(d.category, "📝")
            st.markdown(f'{i}. {icon} **{d.title[:40]}** — {_fmt_words(d.word_count)}')

    st.markdown("---")
    st.markdown("##### 🕐 Historial de Búsquedas")
    history = engine.get_search_history(15)
    if history:
        for h in history:
            st.markdown(
                f'🔍 **"{h.query}"** → {h.total_results} resultados '
                f'· ⚡{h.search_time_ms:.1f}ms · {h.timestamp[:16]}'
            )
    else:
        st.caption("Sin búsquedas registradas aún.")

    st.markdown("---")
    if st.button("🔄 Re-indexar todos los documentos"):
        invalidate_cache()
        st.rerun()


# =====================================================================
# FUNCIÓN PRINCIPAL — SINGLE PAGE DINÁMICA
# =====================================================================

def run():
    """Punto de entrada del módulo Knowledge Base."""

    st.markdown(_CSS, unsafe_allow_html=True)

    # Inicializar engine
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    engine = get_search_engine(base_dir)

    if not engine.documents:
        st.error("❌ No se encontraron documentos para indexar.")
        return

    # ── Header ──
    total_words = sum(d.word_count for d in engine.documents.values())
    st.markdown(f"""<div class="kb-hero">
        <h3>📚 Knowledge Base</h3>
        <p>Wiki interna — {len(engine.documents)} documentos · {total_words:,} palabras indexadas</p>
    </div>""", unsafe_allow_html=True)

    # ── Modo de navegación ──
    modo = st.radio(
        "Modo",
        ["📂 Explorar Documentos", "🔍 Buscar", "📊 Estadísticas"],
        horizontal=True,
        key="kb_mode",
        label_visibility="collapsed"
    )

    st.markdown("---")

    if modo == "📂 Explorar Documentos":
        _render_explorer(engine)
    elif modo == "🔍 Buscar":
        _render_search(engine)
    else:
        _render_stats(engine)

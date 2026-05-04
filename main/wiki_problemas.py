"""
main/wiki_problemas.py
──────────────────────
Módulo Streamlit: Wiki de Problemas Resueltos.

Funcionalidades:
- Buscador fulltext tipo Google
- Detalle de cada problema (síntoma, causa, solución, intentos, lección)
- Formulario para registrar nuevos problemas
"""

from __future__ import annotations

import os
import streamlit as st

from utils.problem_wiki import (
    Problema,
    add_problem,
    get_all_problems,
    get_next_codigo,
    get_problem,
    search_problems,
)


def _get_conn() -> str:
    return (
        st.session_state.get("neon_url")
        or os.environ.get("NEON_DATABASE_URL", "")
    )


def _render_problema_card(p: dict):
    """Tarjeta expandible con todos los datos de un problema."""
    tags_str = " · ".join([f"`{t}`" for t in (p.get("tags") or [])])
    modulo = p.get("modulo") or "—"
    fecha = str(p.get("fecha") or "")[:10]
    estado = "✅ Resuelto" if p.get("resuelto") else "🔄 Pendiente"

    with st.expander(f"**{p['codigo']}** — {p['titulo']}  |  {estado}  |  {fecha}"):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**📁 Módulo:** `{modulo}`")
            if tags_str:
                st.markdown(f"**🏷️ Tags:** {tags_str}")
        with col2:
            st.markdown(f"**📅 Fecha:** {fecha}")

        st.markdown("---")

        if p.get("sintoma"):
            st.markdown("#### 🔍 Síntoma")
            st.markdown(p["sintoma"])

        if p.get("causa_raiz"):
            st.markdown("#### 🧬 Causa Raíz")
            st.markdown(p["causa_raiz"])

        if p.get("solucion"):
            st.markdown("#### ✅ Solución")
            st.markdown(p["solucion"])

        intentos = p.get("intentos") or []
        if intentos:
            st.markdown("#### ❌ Intentos Fallidos")
            for i, intento in enumerate(intentos, 1):
                st.markdown(
                    f"**{i}.** {intento.get('intento', '')}\n\n"
                    f"> *¿Por qué falló?* {intento.get('por_que_fallo', '')}"
                )

        if p.get("leccion"):
            st.markdown("#### 💡 Lección Aprendida")
            st.info(p["leccion"])


def _render_form(conn: str):
    """Formulario para registrar un nuevo problema."""
    st.subheader("➕ Registrar nuevo problema")

    next_codigo = get_next_codigo(conn)

    with st.form("form_nuevo_problema", clear_on_submit=True):
        col1, col2 = st.columns([1, 3])
        with col1:
            codigo = st.text_input("Código", value=next_codigo, help="#001, #002...")
        with col2:
            titulo = st.text_input("Título *", placeholder="Resumen del problema en una línea")

        modulo = st.text_input("Módulo / Archivo", placeholder="main/data_assistant.py")
        tags_raw = st.text_input("Tags (separados por coma)", placeholder="streamlit, dtype, sort")

        sintoma = st.text_area("Síntoma *", placeholder="Qué veía o hacía el usuario que estaba mal", height=80)
        causa_raiz = st.text_area("Causa Raíz *", placeholder="Por qué ocurría el problema técnicamente", height=100)
        solucion = st.text_area("Solución *", placeholder="Qué se cambió y cómo lo resolvió", height=100)
        leccion = st.text_area("Lección Aprendida", placeholder="Qué no volver a hacer o qué tener en cuenta", height=80)

        st.markdown("**Intentos fallidos** (opcional)")
        n_intentos = st.number_input("¿Cuántos intentos fallidos documentar?", min_value=0, max_value=5, value=0)
        intentos = []
        for i in range(int(n_intentos)):
            c1, c2 = st.columns(2)
            with c1:
                intento_desc = st.text_input(f"Intento {i+1}", key=f"intento_{i}")
            with c2:
                intento_fallo = st.text_input(f"Por qué falló {i+1}", key=f"fallo_{i}")
            if intento_desc:
                intentos.append({"intento": intento_desc, "por_que_fallo": intento_fallo})

        resuelto = st.checkbox("Problema resuelto", value=True)
        submitted = st.form_submit_button("💾 Guardar problema", type="primary")

        if submitted:
            if not titulo or not sintoma or not causa_raiz or not solucion:
                st.error("Los campos con * son obligatorios.")
                return

            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            p = Problema(
                codigo=codigo.strip(),
                titulo=titulo.strip(),
                modulo=modulo.strip(),
                sintoma=sintoma.strip(),
                causa_raiz=causa_raiz.strip(),
                solucion=solucion.strip(),
                intentos=intentos,
                leccion=leccion.strip(),
                tags=tags,
                resuelto=resuelto,
            )
            ok = add_problem(conn, p)
            if ok:
                st.success(f"✅ Problema {codigo} guardado correctamente.")
                st.cache_data.clear()
            else:
                st.error("Error al guardar. Revisa la conexión a la base de datos.")


def run():
    st.title("🧠 Wiki de Problemas Resueltos")
    st.caption("Inteligencia acumulada del equipo. Busca antes de reinventar la rueda.")

    conn = _get_conn()
    if not conn:
        st.error("❌ No hay conexión a la base de datos configurada.")
        return

    # ─── Buscador tipo Google ─────────────────────────────────────────
    st.markdown("### 🔍 Buscar")
    query = st.text_input(
        "Buscar problema",
        placeholder="ej: sort dataframe  /  dtype string  /  ordenar columna  /  streamlit",
        label_visibility="collapsed",
    )

    if query and query.strip():
        with st.spinner("Buscando..."):
            resultados = search_problems(conn, query.strip(), limit=10)

        if resultados:
            st.success(f"**{len(resultados)}** resultado(s) para: *{query}*")
            for p in resultados:
                rank = p.get("rank", 0)
                st.markdown(f"*Relevancia: {rank:.3f}*")
                _render_problema_card(p)
        else:
            st.info("Sin resultados. Intenta con otras palabras clave o registra este problema nuevo.")

    # ─── Todos los problemas ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📚 Todos los problemas")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filtro_modulo = st.text_input("Filtrar por módulo", placeholder="data_assistant")
    with col_f2:
        filtro_tag = st.text_input("Filtrar por tag", placeholder="streamlit")

    todos = get_all_problems(
        conn,
        modulo=filtro_modulo or None,
        tag=filtro_tag or None,
    )

    if todos:
        st.caption(f"{len(todos)} problema(s) registrado(s)")
        for row in todos:
            full = get_problem(conn, row["codigo"])
            if full:
                _render_problema_card(full)
    else:
        st.info("No hay problemas registrados aún.")

    # ─── Formulario de captura ─────────────────────────────────────────
    st.markdown("---")
    _render_form(conn)

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


def _seed_problemas(conn: str):
    """Inserta los problemas recurrentes resueltos por el equipo de desarrollo."""
    SEED = [
        Problema(
            codigo="#001",
            titulo="Ordenamiento de columnas en tabla de resultados se comportaba como texto",
            modulo="main/data_assistant.py",
            sintoma="Al hacer clic en encabezados como facturas o ranking, el orden era incorrecto (9 > 7 > 575) porque se ordenaba como string en lugar de número.",
            causa_raiz="El DataFrame se serializa a JSON en session_state. Al deserializar, columnas numéricas de PostgreSQL (COUNT, NUMERIC) llegan como object. Streamlit ordena interactivamente por el dtype real; si es object, ordena lexicográficamente. Además, convertir a tipos nullable de pandas (Int64/Float64) no es detectado por select_dtypes(include=number) que solo reconoce tipos numpy.",
            solucion="Pipeline de 3 pasos: 1) _coerce_numeric_like_columns() convierte columnas numéricas-por-nombre a float64 numpy tras deserializar JSON. 2) sort_values() se aplica sobre datos ya numéricos. 3) _format_numeric_display_dataframe() formatea a string DESPUÉS del sort para visualización.",
            intentos=[
                {"intento": "Usar column_config=NumberColumn sobre df con dtype object", "por_que_fallo": "column_config es solo presentación visual, no cambia el tipo subyacente para el sort"},
                {"intento": "Convertir a Int64/Float64 pandas nullable y usar column_config", "por_que_fallo": "select_dtypes(include=number) ignora tipos nullable de pandas, nunca aplica el formato"},
                {"intento": "Usar _format_numeric_display_dataframe y column_config juntos", "por_que_fallo": "Se contradicen: el primero convierte a str, el segundo espera número"},
            ],
            leccion="En Streamlit, el sort interactivo opera sobre el dtype en memoria. column_config es solo cosmético. Siempre convertir a dtype numpy (float64/int64) antes de renderizar si se necesita orden numérico. El formato visual debe aplicarse DESPUÉS del sort, no antes.",
            tags=["streamlit", "dtype", "sort", "dataframe", "pandas", "column_config", "session_state", "json_serialization"],
            resuelto=True,
        ),
        Problema(
            codigo="#002",
            titulo="Donut chart muestra % incorrectos cuando hay muchos clientes",
            modulo="main/data_assistant.py",
            sintoma="La gráfica donut en concentración de clientes muestra al cliente top como 44-45% cuando en realidad es ~32%. El texto de interpretación del LLM muestra números distintos a la gráfica.",
            causa_raiz="El renderer del donut hacía head(15) antes de pasar a Plotly. Plotly recalcula los porcentajes sobre las filas visibles, descartando el resto del universo del denominador. Además el LLM a veces elige pct_del_total como y_col, lo que infla los % al dividir pct_cliente / suma_pcts_subconjunto.",
            solucion="1) Siempre buscar columna de monto absoluto (total_mxn, total, monto...) como values del donut — Plotly calcula elem/grand_total correctamente. 2) SQL devuelve top10 + fila 'Otros' con COALESCE/HAVING>0 para que sumen 100% y no haya denominador partido.",
            intentos=[
                {"intento": "Aumentar head(15) a head(25)", "por_que_fallo": "No resuelve, sigue descartando clientes pequeños del denominador"},
                {"intento": "Usar pct_del_total como values en px.pie", "por_que_fallo": "Plotly divide pct_cliente / suma_pcts_visibles, no sobre 100, inflando los valores"},
            ],
            leccion="Para gráficas de distribución (pie/donut) SIEMPRE usar valores absolutos como values. Nunca pct_* como values en px.pie. Agregar fila 'Otros' en el SQL garantiza que el denominador sea el universo completo.",
            tags=["donut", "pie", "porcentajes", "concentración", "data_assistant", "plotly", "grand_total"],
            resuelto=True,
        ),
        Problema(
            codigo="#003",
            titulo="Columnas pct_* llegan como Decimal/object y no muestran signo %",
            modulo="main/data_assistant.py",
            sintoma="La tabla del asistente muestra valores como '32.8' en columnas pct_del_total en lugar de '32.80%'. El signo % nunca aparece aunque el valor es correcto.",
            causa_raiz="_coerce_numeric_like_columns() solo convertía a float64 columnas cuyos nombres coincidieran con count_keywords o money_keywords. Las columnas pct_*/porcentaje_* no estaban en ninguna lista. Decimal de psycopg2 no es detectado por select_dtypes(include='number') hasta convertirlo explícitamente.",
            solucion="Agregar condición 'pct' in col_lower or 'porcentaje' in col_lower or col_lower.endswith('_pct') al check looks_numeric en _coerce_numeric_like_columns(). Además _format_numeric_display_dataframe() ahora itera sobre todos los nombres de columna (no solo select_dtypes) para cubrir Decimal residuales.",
            intentos=[
                {"intento": "Agregar 'pct' a money_keywords", "por_que_fallo": "Hubiera funcionado pero semánticamente incorrecto, puede generar $ en columnas de porcentaje"},
            ],
            leccion="Al agregar nuevas columnas SQL con prefijo pct_, verificar que _coerce_numeric_like_columns las reconozca. Los tipos Decimal de psycopg2 no son detectados por select_dtypes('number') hasta convertirlos a float64 numpy.",
            tags=["pct", "porcentaje", "formato", "tabla", "data_assistant", "decimal", "psycopg2"],
            resuelto=True,
        ),
        Problema(
            codigo="#004",
            titulo="Coverage en CI falla al agregar módulos de infraestructura a utils/",
            modulo="pytest.ini / CI",
            sintoma="El pipeline de GitHub Actions reporta 'Coverage failure: total of 55% is less than fail-under=85%'. Tests pasan localmente pero CI falla.",
            causa_raiz="pytest.ini medía cobertura sobre todo utils/ incluyendo módulos que requieren infraestructura externa (DB Neon, OpenAI API, Streamlit UI). Estos tienen 0-15% cobertura al no poder ejecutarse en CI sin sus dependencias.",
            solucion="Agregar sección [coverage:run] omit en pytest.ini excluyendo: admin_panel.py, nl2sql.py, auth.py, neon_loader.py, sovereign_periods.py, problem_wiki.py, guided_usage_metrics.py, guided_catalog_store.py.",
            intentos=[],
            leccion="Al crear módulo nuevo que dependa de Neon/OpenAI/Streamlit, agregarlo de inmediato al omit de [coverage:run] en pytest.ini para no romper el threshold de cobertura en CI.",
            tags=["coverage", "pytest", "CI", "infraestructura", "neon", "omit", "github_actions"],
            resuelto=True,
        ),
    ]

    ok, fail = 0, 0
    for p in SEED:
        # Solo insertar si no existe ya
        existing = get_problem(conn, p.codigo)
        if existing:
            st.info(f"ℹ️ {p.codigo} ya existe — omitido.")
            continue
        if add_problem(conn, p):
            st.success(f"✅ {p.codigo} — {p.titulo[:60]}")
            ok += 1
        else:
            st.error(f"❌ {p.codigo} — error al insertar")
            fail += 1

    if ok:
        st.success(f"**{ok}** problema(s) cargado(s) correctamente.")
        st.cache_data.clear()
    if fail:
        st.error(f"**{fail}** fallo(s). Revisa la conexión a Neon.")


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

    # ─── Seed de datos iniciales ──────────────────────────────────────
    st.markdown("---")
    with st.expander("⚙️ Administración — Cargar problemas semilla"):
        st.caption("Carga los problemas recurrentes documentados por el equipo de desarrollo.")
        if st.button("📥 Cargar problemas semilla", key="btn_seed_wiki"):
            _seed_problemas(conn)

    # ─── Formulario de captura ─────────────────────────────────────────
    st.markdown("---")
    _render_form(conn)

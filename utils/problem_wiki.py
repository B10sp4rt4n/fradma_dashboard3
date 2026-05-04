"""
utils/problem_wiki.py
─────────────────────
Sistema de inteligencia acumulada de problemas resueltos.

Funciones principales:
- add_problem()              → insertar/actualizar un problema
- search_problems()          → búsqueda fulltext (GIN tsvector)
- get_context_for_ai()       → devuelve texto de contexto para inyectar en system prompt
- get_all_problems()         → listar todos (para UI)
- get_problem()              → obtener uno por código
- auto_generate_entry()      → genera entrada wiki con GPT a partir de intentos fallidos
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Modelo de datos
# ─────────────────────────────────────────────

@dataclass
class Problema:
    codigo: str
    titulo: str
    modulo: str = ""
    sintoma: str = ""
    causa_raiz: str = ""
    solucion: str = ""
    intentos: list[dict] = field(default_factory=list)
    leccion: str = ""
    tags: list[str] = field(default_factory=list)
    resuelto: bool = True
    fecha: Optional[str] = None

    def to_ai_context(self) -> str:
        """Formato compacto para inyectar en system prompt."""
        return (
            f"[{self.codigo}] {self.titulo}\n"
            f"Síntoma: {self.sintoma}\n"
            f"Causa: {self.causa_raiz}\n"
            f"Solución: {self.solucion}\n"
            f"Lección: {self.leccion}"
        )


# ─────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────

def _connect(connection_string: str) -> psycopg2.extensions.connection:
    return psycopg2.connect(connection_string, cursor_factory=psycopg2.extras.RealDictCursor)


def add_problem(connection_string: str, problema: Problema) -> bool:
    """
    Inserta o actualiza un problema en wiki.problema.
    Si ya existe el código, hace UPDATE.
    Retorna True si éxito, False si error.
    """
    sql = """
        INSERT INTO wiki.problema
            (codigo, titulo, modulo, sintoma, causa_raiz, solucion, intentos, leccion, tags, resuelto)
        VALUES
            (%(codigo)s, %(titulo)s, %(modulo)s, %(sintoma)s, %(causa_raiz)s,
             %(solucion)s, %(intentos)s, %(leccion)s, %(tags)s, %(resuelto)s)
        ON CONFLICT (codigo) DO UPDATE SET
            titulo     = EXCLUDED.titulo,
            modulo     = EXCLUDED.modulo,
            sintoma    = EXCLUDED.sintoma,
            causa_raiz = EXCLUDED.causa_raiz,
            solucion   = EXCLUDED.solucion,
            intentos   = EXCLUDED.intentos,
            leccion    = EXCLUDED.leccion,
            tags       = EXCLUDED.tags,
            resuelto   = EXCLUDED.resuelto;
    """
    try:
        conn = _connect(connection_string)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql, {
                "codigo":     problema.codigo,
                "titulo":     problema.titulo,
                "modulo":     problema.modulo,
                "sintoma":    problema.sintoma,
                "causa_raiz": problema.causa_raiz,
                "solucion":   problema.solucion,
                "intentos":   json.dumps(problema.intentos, ensure_ascii=False),
                "leccion":    problema.leccion,
                "tags":       problema.tags,
                "resuelto":   problema.resuelto,
            })
        conn.close()
        logger.info(f"wiki: upsert {problema.codigo} OK")
        return True
    except Exception as exc:
        logger.error(f"wiki add_problem error: {exc}")
        return False


def search_problems(
    connection_string: str,
    query: str,
    limit: int = 5,
    only_resolved: bool = True,
) -> list[dict]:
    """
    Búsqueda fulltext GIN (tsvector) sobre todos los campos del problema.
    Retorna lista de dicts ordenados por relevancia.
    """
    if not query or not query.strip():
        return []

    sql = """
        SELECT
            id, codigo, titulo, modulo, sintoma, causa_raiz, solucion,
            intentos, leccion, tags, resuelto, fecha,
            ts_rank_cd(fts, query) AS rank
        FROM wiki.problema, plainto_tsquery('spanish', %(query)s) query
        WHERE fts @@ query
          AND (%(only_resolved)s = FALSE OR resuelto = TRUE)
        ORDER BY rank DESC
        LIMIT %(limit)s;
    """
    try:
        conn = _connect(connection_string)
        with conn.cursor() as cur:
            cur.execute(sql, {"query": query, "only_resolved": only_resolved, "limit": limit})
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as exc:
        logger.error(f"wiki search_problems error: {exc}")
        return []


def get_all_problems(
    connection_string: str,
    modulo: Optional[str] = None,
    tag: Optional[str] = None,
    only_resolved: bool = False,
) -> list[dict]:
    """Lista todos los problemas con filtros opcionales."""
    filters = []
    params: dict = {}

    if only_resolved:
        filters.append("resuelto = TRUE")
    if modulo:
        filters.append("modulo ILIKE %(modulo)s")
        params["modulo"] = f"%{modulo}%"
    if tag:
        filters.append("%(tag)s = ANY(tags)")
        params["tag"] = tag

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    sql = f"""
        SELECT id, codigo, titulo, modulo, tags, resuelto, fecha
        FROM wiki.problema
        {where}
        ORDER BY fecha DESC, id DESC;
    """
    try:
        conn = _connect(connection_string)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as exc:
        logger.error(f"wiki get_all_problems error: {exc}")
        return []


def get_problem(connection_string: str, codigo: str) -> Optional[dict]:
    """Obtiene un problema completo por código."""
    sql = "SELECT * FROM wiki.problema WHERE codigo = %s;"
    try:
        conn = _connect(connection_string)
        with conn.cursor() as cur:
            cur.execute(sql, (codigo,))
            row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as exc:
        logger.error(f"wiki get_problem error: {exc}")
        return None


def get_next_codigo(connection_string: str) -> str:
    """Genera el siguiente código correlativo (#001, #002...)."""
    sql = "SELECT codigo FROM wiki.problema ORDER BY id DESC LIMIT 1;"
    try:
        conn = _connect(connection_string)
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
        conn.close()
        if row:
            last_num = int(str(row["codigo"]).lstrip("#"))
            return f"#{last_num + 1:03d}"
    except Exception:
        pass
    return "#001"


# ─────────────────────────────────────────────
# Contexto para IA
# ─────────────────────────────────────────────

def get_context_for_ai(
    connection_string: str,
    question: str,
    max_problems: int = 3,
) -> str:
    """
    Dado el texto de una pregunta/situación, busca problemas similares
    y devuelve un bloque de texto listo para inyectar en el system prompt.
    Retorna string vacío si no hay coincidencias o no hay conexión.
    """
    if not connection_string or not question:
        return ""

    hits = search_problems(connection_string, question, limit=max_problems, only_resolved=True)
    if not hits:
        return ""

    lines = ["### Problemas similares ya resueltos (wiki interna):"]
    for h in hits:
        lines.append(
            f"\n[{h['codigo']}] {h['titulo']}\n"
            f"  Causa: {h['causa_raiz']}\n"
            f"  Solución: {h['solucion']}\n"
            f"  Lección: {h['leccion']}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Auto-generación con IA
# ─────────────────────────────────────────────

def auto_generate_entry(
    connection_string: str,
    openai_api_key: str,
    failed_attempts: list[dict],
    successful_attempt: Optional[dict] = None,
) -> Optional[Problema]:
    """
    Genera automáticamente una entrada wiki estructurada usando GPT.

    Args:
        connection_string: URL Neon para obtener el código correlativo
        openai_api_key:    API key de OpenAI
        failed_attempts:   Lista de dicts con {question, sql, error}
        successful_attempt: Dict con {question, sql, interpretation} si se resolvió

    Returns:
        Problema estructurado listo para guardar, o None si falla
    """
    if not failed_attempts:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_api_key)
    except Exception as e:
        logger.error(f"wiki auto_generate_entry: OpenAI init error: {e}")
        return None

    # Construir contexto para GPT
    context_parts = []
    for i, attempt in enumerate(failed_attempts, 1):
        context_parts.append(
            f"Intento {i}:\n"
            f"  Pregunta: {attempt.get('question', '')}\n"
            f"  SQL generado: {attempt.get('sql', 'N/A')}\n"
            f"  Error: {attempt.get('error', 'N/A')}"
        )

    context = "\n\n".join(context_parts)

    if successful_attempt:
        context += (
            f"\n\nRESOLUCIÓN FINAL:\n"
            f"  SQL que funcionó: {successful_attempt.get('sql', 'N/A')}\n"
            f"  Interpretación: {successful_attempt.get('interpretation', 'N/A')}"
        )
        resuelto = True
        status_hint = "El problema fue resuelto eventualmente."
    else:
        resuelto = False
        status_hint = "El problema NO fue resuelto. Documentar para análisis futuro."

    prompt = f"""Analiza los siguientes intentos fallidos de consulta SQL en un sistema de facturación CFDI México 
y genera una entrada estructurada para una wiki de problemas técnicos.

{status_hint}

INTENTOS:
{context}

Responde ÚNICAMENTE con un JSON con esta estructura exacta (sin markdown, sin ```json):
{{
  "titulo": "Título conciso del problema (máx 80 chars)",
  "modulo": "utils/nl2sql.py o el módulo más relevante",
  "sintoma": "Qué veía o hacía el usuario que estaba mal",
  "causa_raiz": "Por qué ocurría técnicamente el problema",
  "solucion": "Qué se cambió para resolverlo (o vacío si no resuelto)",
  "leccion": "Qué aprender de este problema para el futuro",
  "tags": ["tag1", "tag2", "tag3"]
}}"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=800,
        )
        raw = resp.choices[0].message.content.strip()
        # Limpiar posible markdown
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
    except Exception as e:
        logger.error(f"wiki auto_generate_entry: GPT parse error: {e}")
        return None

    codigo = get_next_codigo(connection_string)

    # Construir lista de intentos fallidos para guardar
    intentos_estructurados = [
        {
            "intento": f"SQL: {a.get('sql', 'N/A')[:200]}",
            "por_que_fallo": a.get("error", "Error desconocido")[:300],
        }
        for a in failed_attempts
    ]

    return Problema(
        codigo=codigo,
        titulo=data.get("titulo", "Problema sin título"),
        modulo=data.get("modulo", "utils/nl2sql.py"),
        sintoma=data.get("sintoma", ""),
        causa_raiz=data.get("causa_raiz", ""),
        solucion=data.get("solucion", ""),
        intentos=intentos_estructurados,
        leccion=data.get("leccion", ""),
        tags=data.get("tags", []),
        resuelto=resuelto,
    )

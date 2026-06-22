"""
Tracking local (v1) para recomendaciones prescriptivas.

Alcance actual:
- Persistencia temporal en st.session_state
- Sin base de datos
- Sin IA
"""

from __future__ import annotations

from datetime import datetime
import hashlib
from typing import Any, Dict, List, Optional

import streamlit as st


_SESSION_KEY = "acciones_tracking_registros"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        txt = str(value).strip()
    except Exception:
        return ""
    return txt


def _get_store() -> Dict[str, Dict[str, Any]]:
    store = st.session_state.get(_SESSION_KEY)
    if not isinstance(store, dict):
        store = {}
        st.session_state[_SESSION_KEY] = store
    return store


def generar_id_recomendacion(accion: Optional[Dict[str, Any]]) -> str:
    """Genera un ID estable basado en el contenido funcional de la accion."""
    if not isinstance(accion, dict):
        return hashlib.sha1(_now_iso().encode("utf-8")).hexdigest()[:12]

    base = "|".join(
        [
            _safe_text(accion.get("prioridad")),
            _safe_text(accion.get("rol")),
            _safe_text(accion.get("tipo")),
            _safe_text(accion.get("hallazgo")),
            _safe_text(accion.get("accion_sugerida")),
            _safe_text(accion.get("fuente")),
        ]
    )
    if not base:
        base = _now_iso()
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def preparar_registro_accion(accion: Optional[Dict[str, Any]], estado: str = "sugerida") -> Dict[str, Any]:
    """Normaliza una recomendacion para almacenarla en seguimiento."""
    accion = accion if isinstance(accion, dict) else {}
    timestamp = _now_iso()
    return {
        "id_recomendacion": generar_id_recomendacion(accion),
        "fecha_generacion": timestamp,
        "prioridad": _safe_text(accion.get("prioridad")),
        "rol": _safe_text(accion.get("rol")),
        "tipo": _safe_text(accion.get("tipo")),
        "hallazgo": _safe_text(accion.get("hallazgo")),
        "accion_sugerida": _safe_text(accion.get("accion_sugerida")),
        "impacto_estimado": _safe_text(accion.get("impacto_estimado")),
        "fuente": _safe_text(accion.get("fuente")),
        "estado": _safe_text(estado) or "sugerida",
        "resultado": "",
        "comentario": "",
        "fecha_actualizacion": timestamp,
    }


def registrar_accion_en_memoria(accion: Optional[Dict[str, Any]], estado: str = "sugerida") -> Dict[str, Any]:
    """Crea o actualiza una accion en session_state."""
    registro = preparar_registro_accion(accion, estado=estado)
    store = _get_store()
    rid = registro["id_recomendacion"]

    prev = store.get(rid)
    if isinstance(prev, dict):
        # Mantener fecha original y enriquecer campos faltantes.
        registro["fecha_generacion"] = prev.get("fecha_generacion", registro["fecha_generacion"])
        registro["resultado"] = prev.get("resultado", "")
        registro["comentario"] = prev.get("comentario", "")
        if prev.get("estado") and estado == "sugerida":
            registro["estado"] = prev.get("estado")

    store[rid] = registro
    return registro


def obtener_acciones_registradas() -> List[Dict[str, Any]]:
    """Retorna acciones registradas ordenadas por ultima actualizacion."""
    store = _get_store()
    registros = [v for v in store.values() if isinstance(v, dict)]
    registros.sort(key=lambda r: _safe_text(r.get("fecha_actualizacion")), reverse=True)
    return registros


def render_tracking_acciones() -> None:
    """Render discreto de seguimiento para estados de acciones."""
    st.markdown("### Seguimiento de acciones")

    registros = obtener_acciones_registradas()
    if not registros:
        st.info("Aún no hay acciones en seguimiento")
        return

    total = len(registros)
    en_proceso = sum(1 for r in registros if _safe_text(r.get("estado")) == "en_proceso")
    ejecutadas = sum(1 for r in registros if _safe_text(r.get("estado")) == "ejecutada")
    descartadas = sum(1 for r in registros if _safe_text(r.get("estado")) == "descartada")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de acciones registradas", total)
    c2.metric("En proceso", en_proceso)
    c3.metric("Ejecutadas", ejecutadas)
    c4.metric("Descartadas", descartadas)

    st.markdown("**Últimas acciones actualizadas**")
    for item in registros[:5]:
        prioridad = _safe_text(item.get("prioridad")) or "Sin prioridad"
        rol = _safe_text(item.get("rol")) or "Sin rol"
        estado = _safe_text(item.get("estado")) or "sugerida"
        hallazgo = _safe_text(item.get("hallazgo")) or "No disponible"
        with st.container(border=True):
            st.markdown(f"**{rol} · Prioridad {prioridad} · Estado {estado}**")
            st.markdown(hallazgo)

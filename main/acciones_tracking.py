"""
Tracking local (v1) para recomendaciones prescriptivas.

Alcance actual:
- Persistencia temporal en st.session_state
- Sin base de datos
- Sin IA
"""

from __future__ import annotations

from datetime import date, datetime
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


def _safe_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").strip()
        return float(value)
    except Exception:
        return 0.0


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
        "monto_recuperado": 0.0,
        "proxima_fecha": "",
        "actualizado_por": "",
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
        registro["monto_recuperado"] = _safe_float(prev.get("monto_recuperado", 0))
        registro["proxima_fecha"] = prev.get("proxima_fecha", "")
        registro["actualizado_por"] = prev.get("actualizado_por", "")
        if prev.get("estado") and estado == "sugerida":
            registro["estado"] = prev.get("estado")
        registro["fecha_actualizacion"] = prev.get("fecha_actualizacion", registro["fecha_actualizacion"])

    store[rid] = registro
    return registro


def actualizar_estado_accion(id_recomendacion: Optional[str], nuevo_estado: str) -> Optional[Dict[str, Any]]:
    """Actualiza el estado de una accion ya registrada sin duplicarla."""
    rid = _safe_text(id_recomendacion)
    if not rid:
        return None

    store = _get_store()
    registro = store.get(rid)
    if not isinstance(registro, dict):
        return None

    registro["estado"] = _safe_text(nuevo_estado) or registro.get("estado", "sugerida")
    registro["fecha_actualizacion"] = _now_iso()
    store[rid] = registro
    return registro


def actualizar_resultado_accion(
    id_recomendacion: Optional[str],
    comentario: Optional[str] = None,
    resultado: Optional[str] = None,
    monto_recuperado: Optional[Any] = None,
    proxima_fecha: Optional[Any] = None,
    actualizado_por: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Actualiza datos operativos de seguimiento para una accion registrada."""
    rid = _safe_text(id_recomendacion)
    if not rid:
        return None

    store = _get_store()
    registro = store.get(rid)
    if not isinstance(registro, dict):
        return None

    if comentario is not None:
        registro["comentario"] = _safe_text(comentario)
    if resultado is not None:
        registro["resultado"] = _safe_text(resultado)
    if monto_recuperado is not None:
        registro["monto_recuperado"] = _safe_float(monto_recuperado)
    if proxima_fecha is not None:
        if isinstance(proxima_fecha, date):
            registro["proxima_fecha"] = proxima_fecha.isoformat()
        else:
            registro["proxima_fecha"] = _safe_text(proxima_fecha)
    if actualizado_por is not None:
        registro["actualizado_por"] = _safe_text(actualizado_por)

    registro["fecha_actualizacion"] = _now_iso()
    store[rid] = registro
    return registro


def obtener_acciones_registradas() -> List[Dict[str, Any]]:
    """Retorna acciones registradas ordenadas por ultima actualizacion."""
    store = _get_store()
    registros = [v for v in store.values() if isinstance(v, dict)]
    registros.sort(key=lambda r: _safe_text(r.get("fecha_actualizacion")), reverse=True)
    return registros


def obtener_resumen_resultados() -> Dict[str, Any]:
    """Agrega métricas de seguimiento para el bloque ejecutivo."""
    registros = obtener_acciones_registradas()
    return {
        "total": len(registros),
        "en_proceso": sum(1 for r in registros if _safe_text(r.get("estado")) == "en_proceso"),
        "ejecutadas": sum(1 for r in registros if _safe_text(r.get("estado")) == "ejecutada"),
        "descartadas": sum(1 for r in registros if _safe_text(r.get("estado")) == "descartada"),
        "monto_recuperado_total": sum(_safe_float(r.get("monto_recuperado", 0)) for r in registros),
    }


def render_formulario_resultado_accion(accion: Optional[Dict[str, Any]]) -> None:
    """Renderiza formulario para captura operativa de resultado por accion."""
    if not isinstance(accion, dict):
        return

    rid = _safe_text(accion.get("id_recomendacion"))
    if not rid:
        return

    comentario_default = _safe_text(accion.get("comentario"))
    resultado_default = _safe_text(accion.get("resultado"))
    monto_default = _safe_float(accion.get("monto_recuperado", 0))
    fecha_default_txt = _safe_text(accion.get("proxima_fecha"))
    actualizado_por_default = _safe_text(accion.get("actualizado_por"))
    fecha_default = None
    if fecha_default_txt:
        try:
            fecha_default = date.fromisoformat(fecha_default_txt)
        except Exception:
            fecha_default = None

    with st.expander("Actualizar resultado"):
        comentario = st.text_area(
            "Comentario",
            value=comentario_default,
            key=f"tracking_comentario_{rid}",
            placeholder="Ej. Se contactó al cliente",
        )
        resultado = st.text_area(
            "Resultado",
            value=resultado_default,
            key=f"tracking_resultado_{rid}",
            placeholder="Ej. Prometió pago el viernes",
        )
        c1, c2 = st.columns(2)
        with c1:
            monto_recuperado = st.number_input(
                "Monto recuperado",
                min_value=0.0,
                value=float(monto_default),
                step=1000.0,
                key=f"tracking_monto_{rid}",
            )
        with c2:
            proxima_fecha = st.date_input(
                "Próxima fecha",
                value=fecha_default,
                key=f"tracking_fecha_{rid}",
                format="YYYY-MM-DD",
            )
        actualizado_por = st.text_input(
            "Actualizado por",
            value=actualizado_por_default,
            key=f"tracking_por_{rid}",
            placeholder="Ej. Cobranza / Dirección",
        )

        if st.button("Guardar resultado", key=f"tracking_guardar_{rid}"):
            actualizar_resultado_accion(
                rid,
                comentario=comentario,
                resultado=resultado,
                monto_recuperado=monto_recuperado,
                proxima_fecha=proxima_fecha if proxima_fecha else "",
                actualizado_por=actualizado_por,
            )
            st.success("Resultado actualizado")
            st.rerun()


def render_tracking_acciones() -> None:
    """Render discreto de seguimiento para estados de acciones."""
    st.markdown("### Seguimiento de acciones")

    registros = obtener_acciones_registradas()
    if not registros:
        st.info("Aún no hay acciones en seguimiento")
        return

    resumen = obtener_resumen_resultados()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total acciones", resumen["total"])
    c2.metric("En proceso", resumen["en_proceso"])
    c3.metric("Ejecutadas", resumen["ejecutadas"])
    c4.metric("Descartadas", resumen["descartadas"])
    c5.metric("Monto recuperado total", f"${resumen['monto_recuperado_total']:,.2f}")

    st.markdown("**Últimas acciones actualizadas**")
    for item in registros[:5]:
        prioridad = _safe_text(item.get("prioridad")) or "Sin prioridad"
        rol = _safe_text(item.get("rol")) or "Sin rol"
        estado = _safe_text(item.get("estado")) or "sugerida"
        hallazgo = _safe_text(item.get("hallazgo")) or "No disponible"
        with st.container(border=True):
            st.markdown(f"**{rol} · Prioridad {prioridad} · Estado {estado}**")
            st.markdown(hallazgo)
            comentario = _safe_text(item.get("comentario"))
            resultado = _safe_text(item.get("resultado"))
            monto_recuperado = _safe_float(item.get("monto_recuperado", 0))
            proxima_fecha = _safe_text(item.get("proxima_fecha"))
            if comentario:
                st.caption(f"Comentario: {comentario}")
            if resultado:
                st.caption(f"Resultado: {resultado}")
            if monto_recuperado > 0:
                st.caption(f"Monto recuperado: ${monto_recuperado:,.2f}")
            if proxima_fecha:
                st.caption(f"Próxima fecha: {proxima_fecha}")
            render_formulario_resultado_accion(item)

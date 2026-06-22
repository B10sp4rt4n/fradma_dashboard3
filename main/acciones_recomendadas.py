"""
Motor prescriptivo inicial (sin IA) para sugerir la siguiente mejor accion.

Este modulo concentra reglas de negocio simples para transformar hallazgos
de CxC, ventas y CFDI en acciones recomendadas por rol.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from main.acciones_tracking import registrar_accion_en_memoria, render_tracking_acciones


def _pick_col(df: Optional[pd.DataFrame], candidates: List[str]) -> Optional[str]:
    if df is None or df.empty:
        return None
    cols_l = {str(c).strip().lower(): c for c in df.columns}
    for c in candidates:
        found = cols_l.get(c.lower())
        if found is not None:
            return found
    return None


def _to_num(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series(dtype="float64")
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False).str.replace("$", "", regex=False),
        errors="coerce",
    ).fillna(0)


def _new_action(
    prioridad: str,
    rol: str,
    tipo: str,
    hallazgo: str,
    accion_sugerida: str,
    impacto_estimado: Any,
    fuente: str,
    regla_id: str,
) -> Dict[str, Any]:
    return {
        "prioridad": prioridad,
        "rol": rol,
        "tipo": tipo,
        "hallazgo": hallazgo,
        "accion_sugerida": accion_sugerida,
        "impacto_estimado": impacto_estimado,
        "fuente": fuente,
        # Campo listo para siguiente fase de trazabilidad:
        # recomendacion -> accion tomada -> resultado.
        "tracking": {
            "regla_id": regla_id,
            "estado": "pendiente",
            "fecha_generada": datetime.now().isoformat(timespec="seconds"),
        },
    }


def _acciones_cxc(df_cxc: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    acciones: List[Dict[str, Any]] = []
    if df_cxc is None or df_cxc.empty:
        return acciones

    c_saldo = _pick_col(df_cxc, ["saldo_adeudado", "saldo", "importe", "monto", "valor_mxn"])
    c_dias = _pick_col(df_cxc, ["dias_overdue", "dias_vencido", "dias_vencidos", "dias_restante", "dias_de_credito"])
    c_cliente = _pick_col(df_cxc, ["cliente", "receptor_nombre", "razon_social"])
    if c_saldo is None or c_dias is None:
        return acciones

    work = df_cxc.copy()
    work["_saldo"] = _to_num(work[c_saldo])
    work["_dias"] = pd.to_numeric(work[c_dias], errors="coerce").fillna(0)

    # Regla: CxC con mas de 90 dias vencidos -> prioridad Alta para Cobranza.
    m_90 = work[work["_dias"] > 90]
    if not m_90.empty:
        monto_90 = float(m_90["_saldo"].sum())
        clientes_90 = int(m_90[c_cliente].nunique()) if c_cliente else len(m_90)
        acciones.append(
            _new_action(
                prioridad="Alta",
                rol="Cobranza",
                tipo="Cartera vencida",
                hallazgo=f"{clientes_90} clientes con vencimiento mayor a 90 dias.",
                accion_sugerida="Activar plan de cobranza intensiva hoy y escalar top deudores con seguimiento diario.",
                impacto_estimado=f"${monto_90:,.2f}",
                fuente="CxC",
                regla_id="CXC_90_PLUS",
            )
        )

    # Regla: CxC entre 60 y 90 dias -> prioridad Media para Cobranza.
    m_60_90 = work[(work["_dias"] >= 60) & (work["_dias"] <= 90)]
    if not m_60_90.empty:
        monto_60_90 = float(m_60_90["_saldo"].sum())
        clientes_60_90 = int(m_60_90[c_cliente].nunique()) if c_cliente else len(m_60_90)
        acciones.append(
            _new_action(
                prioridad="Media",
                rol="Cobranza",
                tipo="Cartera vencida",
                hallazgo=f"{clientes_60_90} clientes en ventana de riesgo de 60 a 90 dias.",
                accion_sugerida="Programar recordatorios de pago y acuerdos de regularizacion antes de que pasen a >90 dias.",
                impacto_estimado=f"${monto_60_90:,.2f}",
                fuente="CxC",
                regla_id="CXC_60_90",
            )
        )

    return acciones


def _acciones_ventas(df_ventas: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    acciones: List[Dict[str, Any]] = []
    if df_ventas is None or df_ventas.empty:
        return acciones

    c_fecha = _pick_col(df_ventas, ["fecha", "fecha_emision", "fecha_factura"])
    c_cliente = _pick_col(df_ventas, ["cliente", "receptor_nombre", "razon_social"])
    c_ventas = _pick_col(df_ventas, ["valor_mxn", "ventas_usd", "ventas_usd_con_iva", "importe", "monto", "valor", "venta"])
    if c_fecha is None or c_cliente is None or c_ventas is None:
        return acciones

    work = df_ventas.copy()
    work["_fecha"] = pd.to_datetime(work[c_fecha], errors="coerce")
    work["_ventas"] = _to_num(work[c_ventas])
    work = work.dropna(subset=["_fecha"])
    if work.empty:
        return acciones

    work["_periodo"] = work["_fecha"].dt.to_period("M")
    periodos = sorted(work["_periodo"].dropna().unique())
    if len(periodos) < 2:
        return acciones

    actual = periodos[-1]
    anterior = periodos[-2]

    cur = work[work["_periodo"] == actual].groupby(c_cliente)["_ventas"].sum()
    prev = work[work["_periodo"] == anterior].groupby(c_cliente)["_ventas"].sum()
    comp = pd.concat([prev.rename("prev"), cur.rename("cur")], axis=1).fillna(0)
    comp = comp[comp["prev"] > 0]
    if comp.empty:
        return acciones

    comp["caida_abs"] = comp["prev"] - comp["cur"]
    caidas = comp[comp["caida_abs"] > 0].sort_values("caida_abs", ascending=False)
    if caidas.empty:
        return acciones

    top = caidas.head(3)
    impacto = float(top["caida_abs"].sum())
    clientes_txt = ", ".join([str(x) for x in top.index.tolist()])

    # Regla: Clientes con caida de ventas vs periodo anterior -> prioridad Media para Ventas.
    acciones.append(
        _new_action(
            prioridad="Media",
            rol="Ventas",
            tipo="Riesgo comercial",
            hallazgo=(
                f"Caida de ventas en clientes clave entre {anterior} y {actual}: {clientes_txt}."
            ),
            accion_sugerida="Ejecutar plan de reactivacion comercial con visita y propuesta en las proximas 48 horas.",
            impacto_estimado=f"${impacto:,.2f}",
            fuente="Comercial",
            regla_id="VENTAS_CAIDA_CLIENTE",
        )
    )

    return acciones


def _acciones_cfdi(df_cfdi: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    acciones: List[Dict[str, Any]] = []
    if df_cfdi is None or df_cfdi.empty:
        return acciones

    c_metodo = _pick_col(df_cfdi, ["metodo_pago", "metodo_de_pago", "forma_pago"])
    c_moneda = _pick_col(df_cfdi, ["moneda"])
    c_estatus = _pick_col(df_cfdi, ["estatus", "status", "estado"])
    c_monto = _pick_col(df_cfdi, ["total", "monto", "importe", "valor_mxn", "subtotal"])

    if c_metodo is None and c_moneda is None and c_estatus is None:
        return acciones

    work = df_cfdi.copy()
    inconsistencias = pd.Series(False, index=work.index)

    # Regla: CFDI con metodo de pago inconsistente o vacio.
    if c_metodo is not None:
        m = work[c_metodo].astype(str).str.strip().str.upper()
        inconsistencias = inconsistencias | m.isin(["", "NAN", "NONE", "NULL", "POR DEFINIR", "99"])

    # Regla: CFDI con moneda inconsistente o vacia.
    if c_moneda is not None:
        mo = work[c_moneda].astype(str).str.strip().str.upper()
        inconsistencias = inconsistencias | mo.isin(["", "NAN", "NONE", "NULL"])

    # Regla: CFDI con estatus inconsistente o vacio.
    if c_estatus is not None:
        es = work[c_estatus].astype(str).str.strip().str.upper()
        validos = {"VIGENTE", "CANCELADO", "PAGADO", "POR PAGAR"}
        inconsistencias = inconsistencias | es.isin(["", "NAN", "NONE", "NULL"]) | (~es.isin(validos))

    bad = work[inconsistencias]
    if bad.empty:
        return acciones

    impacto = f"{len(bad)} CFDI con potencial riesgo de cumplimiento"
    if c_monto is not None:
        impacto = f"${_to_num(bad[c_monto]).sum():,.2f} en CFDI inconsistentes"

    acciones.append(
        _new_action(
            prioridad="Alta",
            rol="Fiscal",
            tipo="Inconsistencia fiscal",
            hallazgo="Se detectaron CFDI con metodo de pago, moneda o estatus incompletos/inconsistentes.",
            accion_sugerida="Validar catalogos SAT y corregir CFDI observados antes del siguiente cierre fiscal.",
            impacto_estimado=impacto,
            fuente="CFDI",
            regla_id="CFDI_INCONSISTENCIAS",
        )
    )

    return acciones


def _acciones_direccion(df_cxc: Optional[pd.DataFrame], df_ventas: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    acciones: List[Dict[str, Any]] = []
    if df_cxc is None or df_cxc.empty or df_ventas is None or df_ventas.empty:
        return acciones

    c_vend_v = _pick_col(df_ventas, ["agente", "vendedor"])
    c_cli_v = _pick_col(df_ventas, ["cliente", "receptor_nombre", "razon_social"])
    c_ventas = _pick_col(df_ventas, ["valor_mxn", "ventas_usd", "ventas_usd_con_iva", "importe", "monto", "valor", "venta"])
    c_saldo = _pick_col(df_cxc, ["saldo_adeudado", "saldo", "importe", "monto", "valor_mxn"])
    c_dias = _pick_col(df_cxc, ["dias_overdue", "dias_vencido", "dias_vencidos"])
    c_vend_c = _pick_col(df_cxc, ["agente", "vendedor"])
    c_cli_c = _pick_col(df_cxc, ["cliente", "receptor_nombre", "razon_social"])

    if c_vend_v is None or c_ventas is None or c_saldo is None or c_dias is None:
        return acciones

    v = df_ventas.copy()
    v["_ventas"] = _to_num(v[c_ventas])
    ventas_por_vendedor = v.groupby(c_vend_v)["_ventas"].sum().rename("ventas")
    if ventas_por_vendedor.empty:
        return acciones

    c = df_cxc.copy()
    c["_saldo"] = _to_num(c[c_saldo])
    c["_dias"] = pd.to_numeric(c[c_dias], errors="coerce").fillna(0)
    c = c[c["_dias"] > 60]
    if c.empty:
        return acciones

    if c_vend_c is None and c_cli_c is not None and c_cli_v is not None:
        # Si CxC no trae vendedor, se aproxima por el vendedor principal por cliente.
        mapa = (
            v.groupby([c_cli_v, c_vend_v])["_ventas"]
            .sum()
            .reset_index()
            .sort_values([c_cli_v, "_ventas"], ascending=[True, False])
            .drop_duplicates(subset=[c_cli_v])
            [[c_cli_v, c_vend_v]]
        )
        c = c.merge(mapa, left_on=c_cli_c, right_on=c_cli_v, how="left")
        c_vend_c = c_vend_v

    if c_vend_c is None or c_vend_c not in c.columns:
        return acciones

    cartera_por_vendedor = c.groupby(c_vend_c)["_saldo"].sum().rename("cartera_vencida")
    comp = pd.concat([ventas_por_vendedor, cartera_por_vendedor], axis=1).fillna(0)
    if comp.empty:
        return acciones

    p75_ventas = comp["ventas"].quantile(0.75)
    p75_cartera = comp["cartera_vencida"].quantile(0.75)
    crit = comp[(comp["ventas"] >= p75_ventas) & (comp["cartera_vencida"] >= p75_cartera)]
    if crit.empty:
        return acciones

    vendedor = str(crit.sort_values("cartera_vencida", ascending=False).index[0])
    impacto = float(crit["cartera_vencida"].sum())

    # Regla: Vendedores con ventas altas pero cartera vencida alta -> prioridad Alta para Direccion.
    acciones.append(
        _new_action(
            prioridad="Alta",
            rol="Direccion",
            tipo="Riesgo comercial",
            hallazgo="Se detectaron vendedores de alto volumen con cartera vencida alta.",
            accion_sugerida=(
                f"Revisar esquema comercial/cobranza del vendedor {vendedor} y activar objetivo quincenal de recuperacion."
            ),
            impacto_estimado=f"${impacto:,.2f}",
            fuente="Comercial",
            regla_id="DIR_VENDEDOR_ALTO_RIESGO",
        )
    )

    return acciones


def generar_acciones_recomendadas(
    df_cxc: Optional[pd.DataFrame] = None,
    df_ventas: Optional[pd.DataFrame] = None,
    df_cfdi: Optional[pd.DataFrame] = None,
    rol: str = "direccion",
) -> List[Dict[str, Any]]:
    """
    Genera recomendaciones prescriptivas iniciales basadas en reglas.

    Soporta ejecucion parcial: puede recibir uno o varios DataFrames y solo
    aplicara las reglas para las fuentes disponibles.
    """
    acciones: List[Dict[str, Any]] = []
    acciones.extend(_acciones_cxc(df_cxc))
    acciones.extend(_acciones_ventas(df_ventas))
    acciones.extend(_acciones_cfdi(df_cfdi))
    acciones.extend(_acciones_direccion(df_cxc, df_ventas))

    rol_map = {
        "direccion": "Direccion",
        "cobranza": "Cobranza",
        "ventas": "Ventas",
        "fiscal": "Fiscal",
    }
    rol_norm = rol_map.get(str(rol).strip().lower())
    if rol_norm:
        return [a for a in acciones if a.get("rol") == rol_norm]
    return acciones


def render_acciones_recomendadas(acciones: Optional[List[Dict[str, Any]]]) -> None:
    """Render ejecutivo en Streamlit para la lista de acciones recomendadas."""
    st.subheader("Acciones recomendadas de hoy")

    if not acciones:
        st.info("No hay acciones recomendadas con los datos actuales")
        render_tracking_acciones()
        return

    if not isinstance(acciones, list):
        st.info("No hay acciones recomendadas con los datos actuales")
        render_tracking_acciones()
        return

    acciones_validas: List[Dict[str, Any]] = [a for a in acciones if isinstance(a, dict)]
    if not acciones_validas:
        st.info("No hay acciones recomendadas con los datos actuales")
        render_tracking_acciones()
        return

    prioridad_orden = {"Alta": 0, "Media": 1, "Baja": 2}

    def _prioridad_valor(item: Dict[str, Any]) -> int:
        p = str(item.get("prioridad", "")).strip().title()
        return prioridad_orden.get(p, 99)

    acciones_ordenadas = sorted(
        acciones_validas,
        key=lambda a: (_prioridad_valor(a), str(a.get("rol", ""))),
    )

    # KPIs ejecutivos por prioridad.
    c1, c2, c3 = st.columns(3)
    c1.metric("Alta", sum(1 for a in acciones_ordenadas if str(a.get("prioridad", "")).strip().title() == "Alta"))
    c2.metric("Media", sum(1 for a in acciones_ordenadas if str(a.get("prioridad", "")).strip().title() == "Media"))
    c3.metric("Baja", sum(1 for a in acciones_ordenadas if str(a.get("prioridad", "")).strip().title() == "Baja"))

    def _texto(item: Dict[str, Any], key: str) -> str:
        val = item.get(key)
        if val is None:
            return ""
        if isinstance(val, float) and pd.isna(val):
            return ""
        txt = str(val).strip()
        return txt

    def _emoji_prioridad(prioridad: str) -> str:
        p = prioridad.title()
        if p == "Alta":
            return "🔴"
        if p == "Media":
            return "🟡"
        if p == "Baja":
            return "🟢"
        return "⚪"

    def _render_card(item: Dict[str, Any]) -> None:
        registro = registrar_accion_en_memoria(item, estado="sugerida")
        prioridad = _texto(item, "prioridad").title() or "Sin prioridad"
        rol = _texto(item, "rol") or "Sin rol"
        hallazgo = _texto(item, "hallazgo") or "No disponible"
        accion = _texto(item, "accion_sugerida") or "No disponible"
        impacto = _texto(item, "impacto_estimado")
        fuente = _texto(item, "fuente")
        estado_actual = _texto(registro, "estado") or "sugerida"
        id_rec = _texto(registro, "id_recomendacion") or f"tmp_{hash(hallazgo)}"

        with st.container(border=True):
            st.markdown(f"**{_emoji_prioridad(prioridad)} {rol} · Prioridad {prioridad}**")
            st.caption(f"Estado: {estado_actual}")
            st.markdown("**Hallazgo:**")
            st.markdown(hallazgo)
            st.markdown("**Acción sugerida:**")
            st.markdown(accion)
            if impacto:
                st.markdown("**Impacto estimado:**")
                st.markdown(impacto)
            if fuente:
                st.markdown("**Fuente:**")
                st.markdown(fuente)

            c1, c2, c3 = st.columns(3)
            if c1.button("Marcar en proceso", key=f"act_proc_{id_rec}"):
                registrar_accion_en_memoria(item, estado="en_proceso")
                st.rerun()
            if c2.button("Marcar ejecutada", key=f"act_exec_{id_rec}"):
                registrar_accion_en_memoria(item, estado="ejecutada")
                st.rerun()
            if c3.button("Descartar", key=f"act_desc_{id_rec}"):
                registrar_accion_en_memoria(item, estado="descartada")
                st.rerun()

    visibles = acciones_ordenadas[:5]
    resto = acciones_ordenadas[5:]

    for item in visibles:
        _render_card(item)

    if resto:
        with st.expander("Ver más acciones recomendadas"):
            for item in resto:
                _render_card(item)

    render_tracking_acciones()

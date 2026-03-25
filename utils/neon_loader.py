"""
Carga de datos CFDI desde Neon hacia session_state["df"].

Garantiza aislamiento de tenant: solo se cargan CFDIs cuyo empresa_id
coincide con el empresa_id del usuario autenticado.

El DataFrame resultante usa el esquema estándar del dashboard:
    fecha, valor_usd, cliente, receptor_rfc, linea_producto, agente,
    año, mes, uuid_sat, serie, folio, moneda, tipo_cambio,
    tipo_comprobante, metodo_pago, emisor_rfc, emisor_nombre
"""

import os
import pandas as pd
from utils.logger import configurar_logger

logger = configurar_logger("neon_loader", nivel="INFO")

# Columnas de cfdi_ventas → nombre en el df del dashboard
_COLUMN_MAP = {
    "fecha_emision": "fecha",
    "receptor_nombre": "cliente",
    "receptor_rfc": "receptor_rfc",
    "linea_negocio": "linea_producto",
    "vendedor_asignado": "agente",
    "total": "valor_usd",       # normalizado a MXN con tipo_cambio abajo
    "uuid_sat": "uuid_sat",
    "serie": "serie",
    "folio": "folio",
    "moneda": "moneda",
    "tipo_cambio": "tipo_cambio",
    "tipo_comprobante": "tipo_comprobante",
    "metodo_pago": "metodo_pago",
    "emisor_rfc": "emisor_rfc",
    "emisor_nombre": "emisor_nombre",
    "subtotal": "subtotal",
    "impuestos": "impuestos",
}


def cargar_cfdi_como_df(empresa_id: str, neon_url: str | None = None) -> pd.DataFrame:
    """
    Lee cfdi_ventas de Neon filtrado por empresa_id y devuelve un DataFrame
    con el esquema esperado por los módulos de reporte.

    Args:
        empresa_id: UUID de la empresa (tenant).
        neon_url: URL de conexión a Neon. Si es None usa NEON_DATABASE_URL.

    Returns:
        DataFrame con columnas normalizadas, o DataFrame vacío si no hay datos.

    Raises:
        RuntimeError: si no hay URL de conexión configurada.
    """
    url = neon_url or os.environ.get("NEON_DATABASE_URL") or _streamlit_neon_url()
    if not url:
        raise RuntimeError(
            "No hay URL de base de datos configurada (NEON_DATABASE_URL)"
        )

    try:
        import psycopg2
    except ImportError:
        raise RuntimeError("psycopg2 no está instalado")

    query = """
        SELECT
            cv.fecha_emision,
            cv.receptor_nombre,
            cv.receptor_rfc,
            cv.linea_negocio,
            cv.vendedor_asignado,
            cv.total * COALESCE(cv.tipo_cambio, 1)  AS total,
            cv.uuid_sat,
            cv.serie,
            cv.folio,
            cv.moneda,
            cv.tipo_cambio,
            cv.tipo_comprobante,
            cv.metodo_pago,
            cv.emisor_rfc,
            cv.emisor_nombre,
            cv.subtotal,
            cv.impuestos
        FROM cfdi_ventas cv
        WHERE cv.empresa_id = %s
          AND cv.tipo_comprobante = 'I'
        ORDER BY cv.fecha_emision DESC
        LIMIT 50000
    """

    conn = None
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute(query, (empresa_id,))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        logger.info(
            f"CFDI cargados desde Neon: {len(df)} registros para empresa_id={empresa_id}"
        )
    except Exception as e:
        logger.error(f"Error cargando CFDIs desde Neon: {e}")
        raise RuntimeError(f"Error al leer CFDI: {e}")
    finally:
        if conn:
            conn.close()

    if df.empty:
        logger.warning(f"No hay CFDIs para empresa_id={empresa_id}")
        return df

    # Renombrar columnas al esquema del dashboard
    df = df.rename(columns=_COLUMN_MAP)

    # Columnas derivadas
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["año"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month

    # Asegurar tipos numéricos
    for col in ("valor_usd", "tipo_cambio", "subtotal", "impuestos"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Rellenar nulos en columnas de texto
    for col in ("cliente", "linea_producto", "agente"):
        if col in df.columns:
            df[col] = df[col].fillna("Sin dato")

    return df


def _streamlit_neon_url() -> str | None:
    """Intenta obtener la URL desde Streamlit secrets (cuando corre en Cloud)."""
    try:
        import streamlit as st
        return st.secrets.get("NEON_DATABASE_URL") or st.secrets.get(
            "connections", {}
        ).get("neon", {}).get("url")
    except Exception:
        return None

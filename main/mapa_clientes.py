"""
Módulo: Mapa de Clientes
Distribución geográfica de las ventas por Código Postal receptor.
Muestra burbujas en el mapa de México proporcionales al monto facturado.
"""

import os
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import requests
import streamlit as st

from utils.logger import configurar_logger

logger = configurar_logger("mapa_clientes", nivel="INFO")

_COORDS_PATH = Path(__file__).parent.parent / "data" / "cp_coords.csv"

# ---------------------------------------------------------------------------
# Mapa de CPs → Estado (rangos aproximados según SEPOMEX)
# ---------------------------------------------------------------------------
_ESTADOS_CP = [
    (1000, 16999, "Ciudad de México"),
    (17000, 17999, "Morelos"),
    (18000, 18999, "Nayarit"),
    (20000, 20999, "Aguascalientes"),
    (21000, 22999, "Baja California"),
    (23000, 23999, "Baja California Sur"),
    (24000, 24999, "Campeche"),
    (25000, 27999, "Coahuila"),
    (28000, 28999, "Colima"),
    (29000, 31999, "Chiapas"),
    (32000, 33999, "Chihuahua"),
    (34000, 35999, "Durango"),
    (36000, 39999, "Guanajuato"),
    (40000, 41999, "Guerrero"),
    (42000, 43999, "Hidalgo"),
    (44000, 49999, "Jalisco"),
    (50000, 57999, "Estado de México"),
    (58000, 61999, "Michoacán"),
    (62000, 62999, "Morelos"),
    (63000, 63999, "Nayarit"),
    (64000, 67999, "Nuevo León"),
    (68000, 71999, "Oaxaca"),
    (72000, 75999, "Puebla"),
    (76000, 76999, "Querétaro"),
    (77000, 77999, "Quintana Roo"),
    (78000, 79999, "San Luis Potosí"),
    (80000, 82999, "Sinaloa"),
    (83000, 85999, "Sonora"),
    (86000, 86999, "Tabasco"),
    (87000, 89999, "Tamaulipas"),
    (90000, 90999, "Tlaxcala"),
    (91000, 96999, "Veracruz"),
    (97000, 97999, "Yucatán"),
    (98000, 99999, "Zacatecas"),
]


def _cp_a_estado(cp: str) -> str:
    try:
        n = int(cp)
        for lo, hi, estado in _ESTADOS_CP:
            if lo <= n <= hi:
                return estado
    except Exception:
        pass
    return "Otro"


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------
def _get_neon_url() -> str | None:
    url = os.environ.get("NEON_DATABASE_URL")
    if not url:
        try:
            url = st.secrets.get("NEON_DATABASE_URL")
        except Exception:
            pass
    return url


def _cargar_datos(empresa_id: str, neon_url: str, anio: int | None = None) -> pd.DataFrame:
    """Carga ventas vigentes agrupadas por CP."""
    filtro_anio = "AND EXTRACT(YEAR FROM fecha_emision) = %(anio)s" if anio else ""
    query = f"""
        SELECT
            receptor_domicilio_fiscal                              AS cp,
            COUNT(DISTINCT receptor_rfc)                          AS clientes,
            COUNT(*)                                               AS facturas,
            ROUND(SUM(total * COALESCE(tipo_cambio, 1))::numeric, 2)  AS total_mxn,
            ROUND(AVG(total * COALESCE(tipo_cambio, 1))::numeric, 2)  AS ticket_promedio,
            (
                SELECT receptor_nombre
                FROM cfdi_ventas cv2
                WHERE cv2.receptor_domicilio_fiscal = cv.receptor_domicilio_fiscal
                  AND cv2.empresa_id = cv.empresa_id
                  AND cv2.tipo_comprobante = 'I'
                  AND cv2.estatus = 'vigente'
                  AND cv2.receptor_rfc != 'XAXX010101000'
                GROUP BY receptor_nombre
                ORDER BY SUM(total * COALESCE(tipo_cambio, 1)) DESC
                LIMIT 1
            )                                                      AS cliente_principal,
            STRING_AGG(DISTINCT receptor_nombre, ' · ' ORDER BY receptor_nombre)
                FILTER (WHERE receptor_rfc != 'XAXX010101000')    AS clientes_lista
        FROM cfdi_ventas cv
        WHERE tipo_comprobante = 'I'
          AND estatus = 'vigente'
          AND empresa_id = %(empresa_id)s
          AND receptor_domicilio_fiscal IS NOT NULL
          AND receptor_domicilio_fiscal != ''
          {filtro_anio}
        GROUP BY receptor_domicilio_fiscal, empresa_id
        ORDER BY total_mxn DESC
    """
    conn = None
    try:
        conn = psycopg2.connect(neon_url)
        cur = conn.cursor()
        cur.execute(query, {"empresa_id": empresa_id, "anio": anio})
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        logger.error(f"Error cargando datos del mapa: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Geocodificación
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600 * 24 * 30, show_spinner=False)
def _geocodificar_cp_online(cp: str) -> tuple[float | None, float | None]:
    """Geocodifica un CP vía Nominatim (resultado cacheado 30 días)."""
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"country": "mx", "postalcode": cp, "format": "json", "limit": 1},
            headers={"User-Agent": "fradma-dashboard/1.0"},
            timeout=6,
        )
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None, None


def _cargar_coords(cps: list[str]) -> pd.DataFrame:
    """
    Retorna DataFrame (cp, lat, lon).
    Lee primero del CSV pre-geocodificado; los CPs faltantes se geocodifican
    online con Nominatim (respetando 1 req/s).
    """
    known: dict[str, tuple[float, float]] = {}

    if _COORDS_PATH.exists():
        try:
            df_csv = pd.read_csv(_COORDS_PATH, dtype={"cp": str})
            df_csv = df_csv.dropna(subset=["lat", "lon"])
            known = {row["cp"]: (row["lat"], row["lon"]) for _, row in df_csv.iterrows()}
        except Exception as e:
            logger.warning(f"Error leyendo cp_coords.csv: {e}")

    missing = [cp for cp in cps if cp not in known]

    if missing:
        msg = st.empty()
        msg.info(f"Geocodificando {len(missing)} CP(s) nuevos, un momento...")
        for cp in missing:
            lat, lon = _geocodificar_cp_online(cp)
            if lat is not None:
                known[cp] = (lat, lon)
            time.sleep(1.1)
        msg.empty()

    rows = [
        {"cp": cp, "lat": known[cp][0], "lon": known[cp][1]}
        if cp in known
        else {"cp": cp, "lat": None, "lon": None}
        for cp in cps
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------
def run():
    neon_url = _get_neon_url()
    if not neon_url:
        st.error("No se encontró NEON_DATABASE_URL.")
        return

    empresa_id = st.session_state.get("empresa_id")
    empresa_nombre = st.session_state.get("empresa_nombre", "")

    st.title("📍 Mapa de Clientes")
    st.caption(f"Distribución geográfica de ventas · {empresa_nombre}")

    # ---- Filtros ----
    col_f1, col_f2, _ = st.columns([1, 1, 4])
    with col_f1:
        anio_opts = [None, 2024, 2025, 2026]
        anio_labels = ["Todos los años", "2024", "2025", "2026"]
        anio_sel = st.selectbox("Año", options=anio_opts, format_func=lambda x: anio_labels[anio_opts.index(x)])
    with col_f2:
        metrica_opts = {"total_mxn": "Monto facturado", "facturas": "N° facturas", "clientes": "N° clientes"}
        metrica = st.selectbox("Tamaño de burbuja", options=list(metrica_opts.keys()), format_func=lambda k: metrica_opts[k])

    # ---- Carga de datos ----
    with st.spinner("Cargando datos..."):
        df = _cargar_datos(empresa_id, neon_url, anio=anio_sel)

    if df.empty:
        st.warning("No se encontraron ventas con código postal registrado.")
        return

    df["estado"] = df["cp"].apply(_cp_a_estado)

    # ---- Coordenadas ----
    df_coords = _cargar_coords(df["cp"].tolist())
    df = df.merge(df_coords, on="cp", how="left")
    df_map = df.dropna(subset=["lat", "lon"]).copy()
    sin_coords = len(df) - len(df_map)

    # ---- KPIs ----
    cps_activos = df["cp"].nunique()
    estados_activos = df["estado"].nunique()
    clientes_unicos = df["clientes"].sum()
    total_general = df["total_mxn"].sum()
    top_cp_row = df.iloc[0]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("CPs con actividad", f"{cps_activos}")
    k2.metric("Estados / regiones", f"{estados_activos}")
    k3.metric("Clientes únicos", f"{int(clientes_unicos)}")
    k4.metric("CP principal", f"{top_cp_row['cp']} · ${top_cp_row['total_mxn']:,.0f}")

    st.divider()

    # ---- Mapa ----
    if df_map.empty:
        st.warning("No se pudieron geocodificar los CPs. Revisa la conexión a internet.")
    else:
        df_map["total_mxn_fmt"] = df_map["total_mxn"].apply(lambda x: f"${x:,.2f}")
        df_map["cliente_hover"] = df_map["cliente_principal"].fillna("Mostrador")

        # Tamaño de burbuja normalizado (mínimo 8, máximo 55 px)
        valores = df_map[metrica].astype(float)
        v_min, v_max = valores.min(), valores.max()
        if v_max > v_min:
            sizes = 8 + (valores - v_min) / (v_max - v_min) * 47
        else:
            sizes = valores * 0 + 20

        hover_text = [
            f"<b>CP {row['cp']}</b> · {row['estado']}<br>"
            f"Cliente principal: {row['cliente_hover']}<br>"
            f"Clientes: {int(row['clientes'])} · Facturas: {int(row['facturas'])}<br>"
            f"Total: {row['total_mxn_fmt']}"
            for _, row in df_map.iterrows()
        ]

        fig_map = go.Figure(go.Scattermap(
            lat=df_map["lat"],
            lon=df_map["lon"],
            mode="markers",
            marker=go.scattermap.Marker(
                size=sizes,
                color=df_map["total_mxn"].astype(float),
                colorscale="Plasma",
                showscale=True,
                colorbar=dict(title="MXN", tickformat="$,.0f"),
                sizemode="diameter",
                opacity=0.8,
            ),
            text=hover_text,
            hoverinfo="text",
        ))
        fig_map.update_layout(
            map=dict(
                style="open-street-map",
                center=dict(lat=22.5, lon=-100.5),
                zoom=4.2,
            ),
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            height=540,
        )
        st.plotly_chart(fig_map, use_container_width=True)

        if sin_coords > 0:
            st.caption(f"ℹ️ {sin_coords} CP(s) sin coordenadas disponibles no se muestran en el mapa.")

    st.divider()

    # ---- Análisis por Estado ----
    col_a, col_b = st.columns([3, 2])

    with col_a:
        st.subheader("Por estado")
        df_estado = (
            df.groupby("estado")
            .agg(total_mxn=("total_mxn", "sum"), facturas=("facturas", "sum"), clientes=("clientes", "sum"))
            .reset_index()
            .sort_values("total_mxn", ascending=True)
        )
        fig_bar = px.bar(
            df_estado,
            x="total_mxn",
            y="estado",
            orientation="h",
            color="total_mxn",
            color_continuous_scale=px.colors.sequential.Plasma,
            text="total_mxn",
            labels={"total_mxn": "Monto (MXN)", "estado": ""},
            height=max(300, len(df_estado) * 30),
        )
        fig_bar.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig_bar.update_layout(showlegend=False, coloraxis_showscale=False, margin={"l": 0, "r": 60, "t": 10, "b": 0})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_b:
        st.subheader("Top CPs")
        disp = df[["cp", "estado", "clientes", "facturas", "total_mxn", "cliente_principal"]].head(20).copy()
        disp.columns = ["CP", "Estado", "Clientes", "Facturas", "Total MXN", "Cliente principal"]
        st.dataframe(
            disp.style.format({"Total MXN": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True,
            height=480,
        )

    st.divider()

    # ---- Detalle descargable ----
    with st.expander("📋 Detalle completo por CP"):
        df_det = df[["cp", "estado", "clientes", "facturas", "total_mxn", "ticket_promedio", "cliente_principal"]].copy()
        df_det.columns = ["CP", "Estado", "Clientes", "Facturas", "Total MXN", "Ticket promedio", "Cliente principal"]
        st.dataframe(
            df_det.style.format({"Total MXN": "${:,.2f}", "Ticket promedio": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )
        csv = df_det.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar CSV",
            data=csv,
            file_name=f"mapa_clientes_{empresa_nombre}.csv",
            mime="text/csv",
        )

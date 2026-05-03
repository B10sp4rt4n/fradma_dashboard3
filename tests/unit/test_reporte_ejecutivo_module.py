import pandas as pd

from main import reporte_ejecutivo


def test_obtener_paleta_colores_monocromatica():
    paleta = reporte_ejecutivo._obtener_paleta_colores(modo_monocromatico=True)

    assert paleta["primario"] == "#1a1a1a"
    assert isinstance(paleta["scale"], list)
    assert len(paleta["scale"]) >= 6


def test_obtener_paleta_colores_vibrante():
    paleta = reporte_ejecutivo._obtener_paleta_colores(modo_monocromatico=False)

    assert paleta["primario"] == "#1F4E79"
    assert paleta["scale"] == "Viridis"


def test_mostrar_reporte_ejecutivo_normaliza_columna_importe(monkeypatch):
    # Validamos rama temprana: si no hay columna de ventas, emite warning y degrada.
    # Interrumpimos de forma controlada en st.tabs para no entrar a toda la UI.
    df_ventas = pd.DataFrame(
        {
            "fecha": ["2026-01-01"],
            "receptor_nombre": ["Cliente A"],
        }
    )
    df_cxc = pd.DataFrame()
    calls = {"warning": []}

    class DummyCol:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def metric(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(reporte_ejecutivo.st, "session_state", {}, raising=False)
    monkeypatch.setattr(reporte_ejecutivo.st, "toast", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reporte_ejecutivo.st, "warning", lambda msg, **_kwargs: calls["warning"].append(msg))
    monkeypatch.setattr(reporte_ejecutivo.st, "info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reporte_ejecutivo.st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reporte_ejecutivo.st, "subheader", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reporte_ejecutivo.st, "columns", lambda spec, **_kwargs: [DummyCol() for _ in range(len(spec))])
    monkeypatch.setattr(reporte_ejecutivo.st, "selectbox", lambda _label, options, **_kwargs: options[0])
    monkeypatch.setattr(reporte_ejecutivo.st, "expander", lambda *_args, **_kwargs: DummyCol())
    monkeypatch.setattr(reporte_ejecutivo.st, "dataframe", lambda *_args, **_kwargs: None)

    class StopHere(Exception):
        pass

    monkeypatch.setattr(reporte_ejecutivo.st, "tabs", lambda *_args, **_kwargs: (_ for _ in ()).throw(StopHere()))

    try:
        reporte_ejecutivo.mostrar_reporte_ejecutivo(df_ventas, df_cxc)
    except StopHere:
        pass

    assert any("no se encontró columna de ventas" in m.lower() for m in calls["warning"])

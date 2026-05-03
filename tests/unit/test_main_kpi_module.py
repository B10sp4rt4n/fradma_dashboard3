import pandas as pd

from main import main_kpi


def test_detectar_columna_es_case_insensitive():
    df = pd.DataFrame({"AgEnTe": ["Ana"], "fecha": ["2026-01-01"]})
    col = main_kpi._detectar_columna(df, {"agente", "vendedor"})
    assert col == "AgEnTe"


def test_detectar_columna_existente_respeta_lista_candidatos():
    df = pd.DataFrame({"linea_producto": ["A"], "linea_de_negocio": ["B"]})
    col = main_kpi._detectar_columna_existente(df, ["linea_de_negocio", "linea_producto"])
    assert col == "linea_de_negocio"


def test_dataframe_to_excel_bytes_regresa_binario_valido():
    df = pd.DataFrame({"agente": ["Ana"], "valor_mxn": [1000]})
    blob = main_kpi._dataframe_to_excel_bytes(df)
    assert isinstance(blob, bytes)
    # XLSX es un contenedor ZIP, firma PK
    assert blob[:2] == b"PK"


def test_run_sale_con_warning_si_no_hay_df_en_session_state(monkeypatch):
    calls = {"warning": []}

    monkeypatch.setattr(main_kpi.st, "session_state", {}, raising=False)
    monkeypatch.setattr(main_kpi.st, "title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_kpi.st, "warning", lambda msg, **_kwargs: calls["warning"].append(msg))

    main_kpi.run()

    assert len(calls["warning"]) == 1
    assert "cargar" in calls["warning"][0].lower()


def test_run_muestra_error_si_falta_columna_ventas(monkeypatch):
    calls = {"error": []}
    df = pd.DataFrame({"fecha": ["2026-01-01"], "agente": ["Ana"]})

    monkeypatch.setattr(main_kpi.st, "session_state", {"df": df}, raising=False)
    monkeypatch.setattr(main_kpi.st, "title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_kpi.st, "subheader", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_kpi.st, "warning", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_kpi.st, "error", lambda msg, **_kwargs: calls["error"].append(msg))

    main_kpi.run()

    assert len(calls["error"]) == 1
    assert "valor_mxn" in calls["error"][0]

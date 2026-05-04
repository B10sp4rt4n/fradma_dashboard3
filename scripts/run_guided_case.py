#!/usr/bin/env python3
"""Runner CLI para ejecutar casos del framework guiado sin usar NL."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import psycopg2

from utils.guided_catalog_store import load_runtime_catalog
from utils.guided_query_framework import GuidedQueryFramework


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run guided case against PostgreSQL")
    parser.add_argument("--case-id", required=True, help="ID del caso en el catalogo")
    parser.add_argument("--period-mode", default="ultimos_12_meses", help="todo|este_ano|ultimos_12_meses|ultimos_6_meses|rango_personalizado")
    parser.add_argument("--start-date", default="", help="YYYY-MM-DD")
    parser.add_argument("--end-date", default="", help="YYYY-MM-DD")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--metodo-pago", default="todos")
    parser.add_argument("--tipo-comprobante", default="todos")
    parser.add_argument("--cliente", default="")
    parser.add_argument("--producto", default="")
    parser.add_argument("--grouping", default="mensual")
    parser.add_argument("--empresa-id", default="", help="Tenant opcional para inyeccion de filtro")
    parser.add_argument("--connection-string", default=os.getenv("NEON_DATABASE_URL", ""))
    parser.add_argument("--prefer-db-catalog", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if not args.connection_string:
        print("ERROR: falta connection string. Usa --connection-string o NEON_DATABASE_URL", file=sys.stderr)
        return 2

    params = {
        "period_mode": args.period_mode,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "top_n": args.top_n,
        "metodo_pago": args.metodo_pago,
        "tipo_comprobante": args.tipo_comprobante,
        "cliente": args.cliente,
        "producto": args.producto,
        "grouping": args.grouping,
    }

    catalog = load_runtime_catalog(
        connection_string=args.connection_string,
        prefer_db=args.prefer_db_catalog,
    )
    framework = GuidedQueryFramework(catalog)
    sql, chart, case = framework.build_query(args.case_id, params)

    if args.empresa_id:
        tenant_filter = f"empresa_id = '{args.empresa_id}'"
        if " where " in sql.lower():
            sql = sql.replace("WHERE ", f"WHERE {tenant_filter} AND ", 1)
        else:
            sql = sql.rstrip(";") + f" WHERE {tenant_filter};"

    with psycopg2.connect(args.connection_string) as conn:
        df = pd.read_sql_query(sql, conn)

    print(f"case={case.get('id')} label={case.get('label')}")
    print(f"chart={chart} rows={len(df)}")
    print("sql=")
    print(sql)
    print("preview=")
    print(df.head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Sincroniza config/guided_query_catalog.json hacia BD (Neon)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.guided_catalog_store import load_catalog_from_json, upsert_catalog_to_db, catalog_stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync guided query catalog JSON -> DB")
    parser.add_argument("--catalog", default="config/guided_query_catalog.json", help="Ruta al JSON de catálogo")
    parser.add_argument(
        "--connection-string",
        default=os.getenv("NEON_DATABASE_URL", ""),
        help="Connection string PostgreSQL (default: NEON_DATABASE_URL)",
    )
    parser.add_argument("--source", default="json", help="Etiqueta de fuente para auditoría")
    args = parser.parse_args()

    if not args.connection_string:
        print("ERROR: Falta connection string. Usa --connection-string o NEON_DATABASE_URL", file=sys.stderr)
        return 2

    catalog = load_catalog_from_json(args.catalog)
    stats = catalog_stats(catalog)
    version = upsert_catalog_to_db(args.connection_string, catalog, source=args.source)

    print(f"sync_ok=true version={version}")
    print(f"domains={stats['domains']} cases={stats['cases']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

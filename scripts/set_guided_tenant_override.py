#!/usr/bin/env python3
"""Administra overrides de rollout por tenant para el catalogo guiado."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.guided_catalog_store import upsert_tenant_override, list_tenant_overrides


def _parse_bool(value: str) -> bool:
    text = value.strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError("enabled debe ser true/false")


def main() -> int:
    parser = argparse.ArgumentParser(description="Set/list guided catalog tenant overrides")
    parser.add_argument("--connection-string", default=os.getenv("NEON_DATABASE_URL", ""))
    parser.add_argument("--empresa-id", required=True, help="UUID del tenant")
    parser.add_argument("--domain-id", default="*", help="Dominio o '*' para todos")
    parser.add_argument("--case-id", default="*", help="Caso o '*' para dominio completo")
    parser.add_argument("--enabled", type=_parse_bool, help="true/false para upsert")
    parser.add_argument("--list", action="store_true", help="Listar overrides del tenant")
    args = parser.parse_args()

    if not args.connection_string:
        print("ERROR: falta connection string", file=sys.stderr)
        return 2

    if args.list:
        rows = list_tenant_overrides(args.connection_string, args.empresa_id)
        print(f"overrides={len(rows)}")
        for row in rows:
            print(f"domain={row['domain_key']} case={row['case_key']} enabled={row['enabled']}")
        return 0

    if args.enabled is None:
        print("ERROR: usa --enabled true|false o --list", file=sys.stderr)
        return 2

    upsert_tenant_override(
        args.connection_string,
        empresa_id=args.empresa_id,
        domain_key=args.domain_id,
        case_key=args.case_id,
        enabled=args.enabled,
    )
    print("override_upserted=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

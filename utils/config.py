"""
utils/config.py — Validación centralizada de variables de entorno.

Ejecutar validate_environment() al arrancar la app para detectar
configuración faltante antes de que ocurra un error en runtime.

No imprime secretos completos en logs (solo los primeros 6 caracteres).
"""

import os
import streamlit as st
from utils.logger import configurar_logger

logger = configurar_logger("config", nivel="INFO")

# Variables que deben estar presentes para que la app funcione
REQUIRED_ENV_VARS: list[str] = [
    "NEON_DATABASE_URL",
]

# Variables opcionales — la app funciona sin ellas pero con funcionalidad reducida
OPTIONAL_ENV_VARS: list[str] = [
    "OPENAI_API_KEY",
    "PASSKEY_PREMIUM",
    "GUIDED_CATALOG_SOURCE",
    "LOG_LEVEL",
]


def _mask(value: str) -> str:
    """Muestra solo los primeros 6 caracteres de un secreto."""
    if not value:
        return "(vacío)"
    return value[:6] + "***"


def validate_environment() -> dict:
    """
    Valida variables de entorno al arranque.

    - Detiene la app con st.stop() si falta alguna variable obligatoria.
    - Registra en log el estado de cada variable (sin exponer valores).
    - Soporta lectura desde st.secrets como fallback (Streamlit Cloud).

    Returns:
        dict con las variables resueltas.
    """
    resolved: dict[str, str | None] = {}

    # ── Resolver variables: env → st.secrets → None ──────────────────
    all_vars = REQUIRED_ENV_VARS + OPTIONAL_ENV_VARS
    for var in all_vars:
        value = os.environ.get(var)
        if not value and hasattr(st, "secrets"):
            try:
                value = st.secrets.get(var)
            except Exception:
                pass
        resolved[var] = value or None

    # ── Verificar obligatorias ────────────────────────────────────────
    missing = [v for v in REQUIRED_ENV_VARS if not resolved.get(v)]
    if missing:
        msg = (
            "⚠️ **Configuración incompleta.** "
            "Faltan las siguientes variables de entorno requeridas:\n\n"
            + "\n".join(f"- `{v}`" for v in missing)
            + "\n\nConfigúralas en Railway → Settings → Variables "
            "o en tu archivo `.env` local."
        )
        logger.error(f"Variables faltantes al arranque: {missing}")
        st.error(msg)
        st.stop()

    # ── Log de estado sin exponer secretos ───────────────────────────
    app_env = os.environ.get("APP_ENV", "development")
    logger.info(f"APP_ENV={app_env}")
    for var in REQUIRED_ENV_VARS:
        logger.info(f"  [OK] {var}={_mask(resolved[var] or '')}")
    for var in OPTIONAL_ENV_VARS:
        estado = "OK" if resolved.get(var) else "ausente (opcional)"
        logger.info(f"  [{estado}] {var}")

    return {
        "database_url": resolved["NEON_DATABASE_URL"],
        "openai_api_key": resolved.get("OPENAI_API_KEY"),
        "passkey_premium": resolved.get("PASSKEY_PREMIUM", "fradma2026"),
        "guided_catalog_source": resolved.get("GUIDED_CATALOG_SOURCE", "json"),
        "log_level": resolved.get("LOG_LEVEL", "INFO"),
        "app_env": app_env,
    }

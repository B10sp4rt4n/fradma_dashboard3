"""
CIMA Schema Engine by FixCel
Motor transversal de esquemas, validacion y activacion de modulos analiticos.
"""

__version__ = "1.0.0"
__author__ = "FixCel / CIMA Analytics"

from .schema_registry import get_schema, list_schemas, list_schemas_by_source
from .column_mapper import map_columns, normalize_column_name, get_canonical_field
from .schema_validator import validate_dataframe_against_schema
from .context_score import calculate_context_score
from .module_requirements import get_activable_modules

__all__ = [
    "get_schema",
    "list_schemas",
    "list_schemas_by_source",
    "map_columns",
    "normalize_column_name",
    "get_canonical_field",
    "validate_dataframe_against_schema",
    "calculate_context_score",
    "get_activable_modules",
]

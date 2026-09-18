"""JSON Schema validation utilities.

Uses jsonschema (draft 2020-12) for schema validation.
"""

from __future__ import annotations

__all__ = ["validate_draft202012"]

import json
import logging
from pathlib import Path
from typing import Any

from sense_ai.errors import SchemaValidationError, SerializationError

logger = logging.getLogger(__name__)

try:
    import jsonschema

    _HAS_JSN = True
except ImportError:
    _HAS_JSN = False


def validate_draft202012(
    instance: Any,
    schema_uri: str | Path,
) -> list[SchemaValidationError]:
    """
    Validate *instance* against the JSON Schema found at *schema_uri*.

    Returns
    -------
    list[SchemaValidationError]
        Empty list on success; otherwise one ``SchemaValidationError`` per
        validation failure, each carrying ``schema_version``, ``json_path``,
        ``message``, and the failing ``value``.

    Raises
    ------
    ImportError
        If the ``jsonschema`` package is not installed.
    SerializationError
        When the schema file cannot be read or is not valid JSON.
    """
    if not _HAS_JSN:
        raise ImportError(
            "jsonschema is required for schema validation. "
            "Install it with: pip install jsonschema"
        )

    schema_path = Path(schema_uri)
    try:
        with open(schema_path) as fh:
            schema = json.load(fh)
    except OSError as exc:
        raise SerializationError(
            f"Failed to read schema file {schema_path!s}: {exc}",
            schema_version=None,
        ) from exc
    except json.JSONDecodeError as exc:
        raise SerializationError(
            f"Schema file {schema_path!s} is not valid JSON: {exc}",
            schema_version=None,
        ) from exc

    schema_version: str | None = schema.get("$schema", "unknown")
    logger.debug("Validating against schema %s (%s)", schema_path.name, schema_version)

    validator = jsonschema.Draft202012Validator(schema)
    errors = [
        SchemaValidationError(
            message=f"{e.json_path}: {e.message}",
            schema_version=schema_version,
            json_path=e.json_path,
            value=getattr(e, "instance", None),
        )
        for e in validator.iter_errors(instance)
    ]
    return errors

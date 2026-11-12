"""Config editing glue for the stlite app.

``select_schema_edit`` wraps ``snakelit.editor.config.schema_config`` with the
schema selector and error reporting the browser app needs.
"""

from __future__ import annotations

from typing import Callable

import streamlit as st

from snakelit.utils.yaml import load

from .deploy import Schemas


def select_schema_edit(
    language: str, schema_edit: Callable, schemas: Schemas | bytes | None, **options
):
    """Wrap ``schema_edit`` with a workflow schema.

    ``schemas`` is either a :class:`Schemas` registry (infer a default and
    render a selector), the raw bytes of a fixed schema (no selector), or
    ``None`` (edit without a schema, also without a selector).
    """

    def config_edit(path: str, data: bytes, key: str):
        errors: list[str] = []
        header = f"Editing `{path}`"
        schema = None
        content = (
            _choose_schema(schemas, path, key)
            if isinstance(schemas, Schemas)
            else schemas
        )
        if content:
            schema, error = _parse_schema(content)
            if error is not None:
                errors.append(error)
        header += " with schema" if schema else " without schema"
        updated = schema_edit(
            data,
            errors,
            schema,
            header=header,
            key=key,
            format=language,
            **options,
        )
        for message in errors:
            st.error(message)
        return data if updated is None else updated

    return config_edit


def _parse_schema(content: bytes):
    """Parse a schema file, returning ``(schema, error)``."""
    errors: list[str] = []
    schema = load(content.decode("utf-8"), errors)
    if errors:
        return None, f"Invalid schema: {errors[0]}"
    if schema is None:
        return {}, None
    if not isinstance(schema, dict):
        return None, "The schema must be a YAML mapping."
    return schema, None


def _choose_schema(schemas: Schemas, file: str, key: str):
    """Render the read-only schema selector; return the raw schema content."""
    paths = sorted(schemas.schemas)
    if not paths:  # noqa
        return

    default_schema = schemas.infer(file)
    index = 1 + paths.index(default_schema) if default_schema in paths else 0

    choice = st.selectbox(
        "Schema",
        ["(none)", *paths],
        index=index,
        key=f"{key}-schema",
        help=(
            "Read-only upstream schema. Pick another file when the workflow "
            "keeps its schema elsewhere, or none for raw YAML."
        ),
    )
    if choice == "(none)":
        return
    return schemas.get(choice)

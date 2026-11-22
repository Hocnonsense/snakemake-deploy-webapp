"""File editor dispatch and host schema selection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Mapping

import streamlit as st
from snakelit.filetypes import BINARY_SUFFIXES, IMAGE_SUFFIXES, suffix
from snakelit.utils import yaml

if TYPE_CHECKING:
    from .deploy import Schemas
    from .fs import DeploymentFS


def select_schema_edit(
    language: str, schema_edit: Callable, schemas: Schemas | bytes | None, **options
):
    """Wrap ``schema_edit`` with a workflow schema.

    ``schemas`` is either a :class:`Schemas` registry (infer a default and
    render a selector), the raw bytes of a fixed schema (no selector), or
    ``None`` (edit without a schema, also without a selector).
    """

    from .deploy import Schemas

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
        return None if errors else updated

    return config_edit


def _parse_schema(content: bytes):
    """Parse a schema file, returning ``(schema, error)``."""
    errors: list[str] = []
    schema = yaml.load(content.decode("utf-8"), errors)
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


Editor = Callable[[str, bytes, str], bytes | None]


def edit_for(
    path: str,
    store: DeploymentFS,
    key: str,
    *,
    editors: Mapping[str, Editor] | None = None,
):
    """Render ``path``'s editor and write the result back to ``store``.

    The editor is chosen by suffix: a host-provided one from ``editors`` when
    available, a plain text area for other text, nothing for images and
    binaries.  A host editor returns changed bytes or None to skip the write.  Missing files start empty, so the
    same call creates them; a successful change writes and reruns.
    """
    stored = store.read(path)
    content = stored or b""
    ext = suffix(path)
    if editors and ext in editors:
        edited = editors[ext](path, content, key)
    elif ext in IMAGE_SUFFIXES or ext in BINARY_SUFFIXES:
        return
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return
        widget_key = f"{key}-text"

        def save_text():
            current = store.read(path)
            if current != stored:
                st.warning(
                    "The file changed while you were editing. Its latest contents are shown."
                )
                return
            data = st.session_state[widget_key].encode("utf-8")
            if data != (current or b""):
                store.write(path, data)

        # Uploads and merges can replace an open file between renders.
        if st.session_state.get(widget_key) != text:
            st.session_state[widget_key] = text
        st.text_area("Content", key=widget_key, height=420, on_change=save_text)
        return
    if edited is not None:
        store.write(path, edited)
        st.rerun()

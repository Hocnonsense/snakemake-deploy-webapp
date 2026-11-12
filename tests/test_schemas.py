"""Upstream schema lookup rules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalog_webapp.deploy import Schemas  # noqa: E402


def test_find_prefers_the_workflow_layout():
    schemas = Schemas(
        {
            "config/schemas/config.schema.yaml": b"config: true\n",
            "workflow/schemas/config.schema.yaml": b"workflow: true\n",
        }
    )

    assert schemas.find("config") == "workflow/schemas/config.schema.yaml"
    assert "config/schemas/config.schema.yaml" in schemas.schemas
    assert schemas.get("workflow/schemas/config.schema.yaml") == b"workflow: true\n"


def test_find_returns_none_without_a_match():
    assert Schemas({}).find("missing") is None


def test_infer_uses_the_file_stem_except_for_profiles():
    schemas = Schemas(
        {
            "workflow/schemas/config.schema.yaml": b"config: true\n",
            "workflow/schemas/samples.schema.yaml": b"samples: true\n",
        }
    )

    assert schemas.infer("config/config.yaml") == "workflow/schemas/config.schema.yaml"
    assert schemas.infer("config/samples.tsv") == "workflow/schemas/samples.schema.yaml"
    assert schemas.infer("profiles/default/config.yaml") is None
    assert schemas.infer("config/unknown.yaml") is None

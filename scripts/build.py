"""Build the static stlite site into ``dist/``.

The page fetches ``files.json`` and mounts every listed Python file into the
stlite virtual filesystem.  ``catalog_webapp`` comes from this repository;
``snakelit`` comes from the installed package, so the deployed app uses the
same version as the locked dependency.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import snakelit

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
PACKAGE = Path(snakelit.__file__).resolve().parent


def python_files():
    """Yield ``(source, relative)`` for every Python file in the bundle."""
    yield ROOT / "app.py", "app.py"
    for source in sorted((ROOT / "catalog_webapp").rglob("*.py")):
        yield source, source.relative_to(ROOT).as_posix()
    for source in sorted(PACKAGE.rglob("*.py")):
        yield source, (Path("snakelit") / source.relative_to(PACKAGE)).as_posix()


def build():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copy2(ROOT / "index.html", DIST / "index.html")
    shutil.copy2(ROOT / "oauth-component.html", DIST / "oauth-component.html")

    entries = sorted(python_files(), key=lambda entry: entry[1])
    for source, relative in entries:
        destination = DIST / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    paths = [relative for _, relative in entries]
    (DIST / "files.json").write_text(
        json.dumps(paths, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    build()

"""File tree rendering, folder toggles, preview and editing."""

import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalog_webapp.deploy import Schemas  # noqa: E402
from catalog_webapp.fs import DeploymentFS  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

APP_IMPORTS = """
import streamlit as st
from catalog_webapp.deploy import Schemas
from catalog_webapp.file_explorer import FileExplorer
from catalog_webapp.fs import DeploymentFS
"""


SCRIPT = (
    APP_IMPORTS
    + """

if "state" not in st.session_state:
    st.session_state["state"] = FileExplorer(
        key="files",
        store=DeploymentFS(
            {
                "config/params.yaml": b"x: 1\\n",
                "config/README.md": b"# readme\\n",
                "LICENSE": b"MIT\\n",
            },
            Schemas({}),
        ),
    )
st.session_state["state"].render()
"""
)


def _button(at, key):
    return next(item for item in at.button if item.key == key)


def _labels(at):
    return [item.label for item in at.button]


def _app(script=SCRIPT):
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    _button(at, "files-header-files").click()
    at.run()
    return at


def test_tree_lists_folders_and_files():
    at = _app()

    assert not at.exception
    labels = _labels(at)
    assert "▸ config/" in labels
    assert "LICENSE" in labels
    assert "params.yaml" not in labels


def test_styles_target_documented_key_hook():
    at = _app()

    assert not at.exception
    css = "\n".join(item.value for item in getattr(at, "html"))
    assert ".st-key-files-tree" in css
    assert "max-height: 650px" in css
    assert "data-testid" not in css


def test_folder_toggles_open():
    at = _app()
    _button(at, "files-dir-config").click()
    at.run()

    assert not at.exception
    labels = _labels(at)
    assert "▾ config/" in labels
    assert "params.yaml" in labels
    assert "README.md" in labels


def test_file_preview_shows_content():
    at = _app()
    _button(at, "files-dir-config").click()
    at.run()
    _button(at, "files-file-config/params.yaml").click()
    at.run()

    assert not at.exception
    assert "x: 1" in at.code[0].value


BINARY_SCRIPT = (
    APP_IMPORTS
    + """

if "state" not in st.session_state:
    st.session_state["state"] = FileExplorer(
        key="files", store=DeploymentFS({"data.gz": b"\\x1f\\x8b\\x08"}, Schemas({}))
    )
st.session_state["state"].render()
"""
)


def test_binary_preview_does_not_decode():
    at = _app(BINARY_SCRIPT)
    _button(at, "files-file-data.gz").click()
    at.run()

    assert not at.exception
    assert any("Binary file" in item.value for item in at.caption)


TABLE_SCRIPT = (
    APP_IMPORTS
    + """

if "state" not in st.session_state:
    st.session_state["state"] = FileExplorer(
        key="files", store=DeploymentFS({"data.csv": b"a,b\\n1,2\\n"}, Schemas({}))
    )
st.session_state["state"].render()
"""
)


def test_table_preview_reads_csv():
    at = _app(TABLE_SCRIPT)
    _button(at, "files-file-data.csv").click()
    at.run()

    assert not at.exception
    assert len(at.dataframe) == 1


def test_tree_reflects_deployment_edits():
    store = DeploymentFS({"a/b.txt": b"old", "c.txt": b"C"}, Schemas({}))
    assert store.tree() == {"a": {"b.txt": "a/b.txt"}, "c.txt": "c.txt"}

    store.write("a/b.txt", b"updated")
    store.write("new/deep.txt", b"")
    store.rm("c.txt")
    assert store.tree() == {"a": {"b.txt": "a/b.txt"}, "new": {"deep.txt": "new/deep.txt"}}
    assert store.read("c.txt") is None
    assert store.collect() == {"a/b.txt": b"updated", "new/deep.txt": b""}


EDIT_SCRIPT = """
import streamlit as st
from catalog_webapp.deploy import Schemas
from catalog_webapp.fs import DeploymentFS

if "fs" not in st.session_state:
    st.session_state.fs = DeploymentFS({"a.txt": b"old", "b.txt": b"other"}, Schemas({}))
fs = st.session_state.fs
path = st.selectbox("File", ["a.txt", "b.txt"])
if st.button("Replace a.txt"):
    fs.write("a.txt", b"replacement")
fs.show(path, "Edit")()
"""


def test_plain_text_editor_tracks_file_contents_across_reruns():
    at = AppTest.from_string(EDIT_SCRIPT, default_timeout=60).run()
    assert at.text_area[0].value == "old"
    assert not at.session_state["fs"].overrides

    at.text_area[0].set_value("new").run()
    assert at.session_state["fs"].read("a.txt") == b"new"
    at.selectbox[0].set_value("b.txt").run()
    assert at.text_area[0].value == "other"
    at.selectbox[0].set_value("a.txt").run()
    assert at.text_area[0].value == "new"
    at.text_area[0].set_value("").run()
    assert at.session_state["fs"].read("a.txt") == b""

    at.button[0].click().run()
    assert not at.exception
    assert at.text_area[0].value == "replacement"
    assert at.session_state["fs"].read("a.txt") == b"replacement"


def test_plain_text_editor_reloads_external_changes_before_saving_a_stale_edit():
    at = AppTest.from_string(EDIT_SCRIPT, default_timeout=60).run()
    fs = at.session_state["fs"]
    fs.write("a.txt", b"external")
    at.text_area[0].set_value("stale edit").run()
    assert fs.read("a.txt") == b"external"
    assert at.text_area[0].value == "external"
    assert not at.exception


UPLOAD_SCRIPT = (
    APP_IMPORTS
    + """

if "state" not in st.session_state:
    st.session_state["state"] = FileExplorer(
        key="files",
        store=DeploymentFS({"config/config.yaml": b"x: 1\\n"}, Schemas({})),
        on_zip=lambda name, data: st.session_state.__setitem__(
            "zip", (name, data)
        ),
    )
st.session_state["state"].render()
"""
)


def test_upload_places_files_according_to_the_target():
    at = _app(UPLOAD_SCRIPT)

    def upload(target: str, *files: tuple[str, bytes]):
        at.text_input(key="files-upload-path").set_value(target)
        uploader = at.file_uploader(key="files-upload-files")
        uploader.clear()
        for name, data in files:
            uploader.upload(name, data)
        at.run()
        _button(at, "files-upload-button").click()
        at.run()

    upload("/new/named.txt", ("content.txt", b"named"))
    upload("more/", ("a.txt", b"A"))
    upload("many", ("b.txt", b"B"), ("c.txt", b"C"))
    upload("config", ("x.txt", b"X"))

    assert not at.exception, [str(error.value) for error in at.exception]
    files = at.session_state["state"].store.collect()
    assert files["new/named.txt"] == b"named"
    assert files["more/a.txt"] == b"A"
    assert files["many/b.txt"] == b"B"
    assert files["many/c.txt"] == b"C"
    assert files["config/x.txt"] == b"X"


def test_upload_reports_an_invalid_target_path():
    at = _app(UPLOAD_SCRIPT)
    at.text_input(key="files-upload-path").set_value("../x/")
    at.file_uploader(key="files-upload-files").upload("a.txt", b"A")
    at.run()

    assert [item.value for item in at.error] == ["Invalid target path: '../x/'"]
    assert not [item for item in at.button if item.key == "files-upload-button"]


def test_upload_warns_before_overwriting_an_existing_file():
    at = _app(UPLOAD_SCRIPT)
    at.text_input(key="files-upload-path").set_value("config/")
    at.file_uploader(key="files-upload-files").upload("config.yaml", b"new")
    at.run()

    assert [item.value for item in at.warning] == [
        "These files will be overwritten: config/config.yaml"
    ]


def test_upload_warns_before_overwriting_a_named_file():
    at = _app(UPLOAD_SCRIPT)
    at.text_input(key="files-upload-path").set_value("config/config.yaml")
    at.file_uploader(key="files-upload-files").upload("local.yaml", b"new")
    at.run()

    assert [item.value for item in at.warning] == [
        "This file will be overwritten: config/config.yaml"
    ]

    _button(at, "files-upload-button").click()
    at.run()

    assert not at.exception, [str(error.value) for error in at.exception]
    assert at.session_state["state"].store.read("config/config.yaml") == b"new"


def test_upload_refuses_several_files_at_a_file_path():
    at = _app(UPLOAD_SCRIPT)
    at.text_input(key="files-upload-path").set_value("config/config.yaml")
    uploader = at.file_uploader(key="files-upload-files")
    uploader.upload("a.txt", b"A")
    uploader.upload("b.txt", b"B")
    at.run()

    assert [item.value for item in at.error] == [
        "'config/config.yaml' is a file; choose a folder path."
    ]


def _zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def test_upload_zip_can_start_a_merge_instead_of_writing():
    at = _app(UPLOAD_SCRIPT)
    data = _zip({"Snakefile": b"rule all:\n"})
    at.file_uploader(key="files-upload-files").upload("workflow.zip", data)
    at.run()

    merge = _button(at, "files-upload-zip-merge")
    assert merge.label == "Unzip and trigger merge"
    merge.click()
    at.run()

    assert not at.exception, [str(error.value) for error in at.exception]
    assert "workflow.zip" not in at.session_state["state"].store.collect()
    assert at.session_state["zip"] == ("workflow.zip", data)


def _open_params_in_edit(at):
    _button(at, "files-dir-config").click()
    at.run()
    _button(at, "files-file-config/params.yaml").click()
    at.run()
    _button(at, "files-edit-toggle").click()
    at.run()
    return at.session_state["state"].store


def test_delete_opens_a_confirmation_dialog():
    at = _app()
    store = _open_params_in_edit(at)

    _button(at, "files-delete").click()
    at.run()

    assert not at.exception
    assert store.read("config/params.yaml") is not None
    assert _button(at, "files-cancel-delete").label == "Cancel"
    assert len(at.get("dialog")) == 1

    # cannot close the dialog in the test, use the api directly
    explorer = at.session_state["state"]
    explorer.delete("config/params.yaml")
    at.run()

    assert not at.exception
    assert store.read("config/params.yaml") is None
    assert explorer.preview is None

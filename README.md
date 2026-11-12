# Snakemake deploy webapp

A static [stlite](https://github.com/whitphx/stlite) app that deploys a Snakemake workflow from the catalog into a new GitHub repository, lets the user edit its configuration, and pushes the result.
Streamlit runs in the browser via WebAssembly. GitHub can be accessed either
through GitHub OAuth (recommended) or, as a fallback, with a personal access
token that stays in `st.session_state`.

The catalog links here with:

```text
https://<host>/<repo>/?repo=<owner>/<name>&ref=<tag-or-branch>
```

## Architecture

- `index.html` mounts stlite and builds `bootstrap.json` from the query string;
- `app.py` is the Streamlit entrypoint;
- `catalog_webapp/` contains the GitHub client, deployment, editing and publishing logic;
- `snakelit` is consumed from PyPI and copied into the static bundle at build time, so the deployed code uses the same version as the lockfile.

`scripts/build.py` writes `dist/` with `index.html`, all Python sources and the
`files.json` manifest that tells stlite what to mount.

## Local development

```bash
pixi run build
pixi run serve
# open http://localhost:8000/?repo=owner/name&ref=v1
```

The app can also run with normal Streamlit from the repository root:

```bash
echo '{"repo":"owner/name","ref":"v1"}' > bootstrap.json
pixi run streamlit run app.py
```

## Tests

```bash
pixi run test
```

This runs the pure logic tests in `tests/` and the `AppTest` UI tests in `tests_ui/`.

## Compatibility contract

`snakedeploy` deploys by shelling out to `git`, which is unavailable in the browser. The app therefore cannot call it at runtime. `catalog_webapp/deploy.py` is an independent implementation that must produce the same files as snakedeploy 0.11.x:

- the generated `workflow/Snakefile` (module declaration, `configfile`,
  `use rule *`);
- copied `config/`, `profiles/`, and the root license;
- an empty `config/config.yaml` when the source has no `config/`.

If snakedeploy gains a pure-Python/API git layer later, this module can be replaced by a direct dependency.

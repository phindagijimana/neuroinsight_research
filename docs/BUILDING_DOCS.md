# Building the documentation site

The docs are published as a static site with **[MkDocs Material](https://squidfunk.github.io/mkdocs-material/)**
(QSIPrep uses Sphinx on Read the Docs; NeuroInsight uses MkDocs because guides are already Markdown in `docs/`).

## Local preview

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

Open **http://127.0.0.1:8000**.

## Production build

```bash
mkdocs build
# output in site/
```

## Host on Read the Docs (recommended, QSIPrep-style)

1. Sign in at [readthedocs.org](https://readthedocs.org) with GitHub.
2. **Import** `phindagijimana/neuroinsight_research`.
3. RTD reads [`.readthedocs.yaml`](https://github.com/phindagijimana/neuroinsight_research/blob/main/.readthedocs.yaml) and `mkdocs.yml`.
4. Set **default branch** `main`; optional custom domain.

Badge for README (after project slug is `neuroinsight`):

```markdown
[![Documentation](https://readthedocs.org/projects/neuroinsight/badge/?version=latest)](https://neuroinsight.readthedocs.io/en/latest/)
```

## GitHub Pages (alternative)

```bash
mkdocs gh-deploy
```

Requires `gh-pages` branch permission.

## What to edit

| Change | File |
|--------|------|
| Navigation / site title | `mkdocs.yml` |
| Landing page | [index.md](index.md) |
| “How it works” narrative | [HOW_IT_WORKS.md](HOW_IT_WORKS.md) |
| Guides | Existing `docs/*.md` |

After changing plugin `references:`, run `python3 scripts/generate_references_doc.py` before release — not required for mkdocs build.

## CI (optional)

Add a workflow step: `pip install -r requirements-docs.txt && mkdocs build --strict` to fail on broken links or missing nav targets.

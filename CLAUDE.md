# CLAUDE.md

Guidance for AI agents (and humans) working in this repository.

## What this is

A Flask app that turns a JSON array of "content blocks" into a right-to-left
(Hebrew) PDF. The interesting code is the PDF engine in
`app/services/pdf_service.py`; everything else is a thin CRUD shell around it.

## Run / test

```bash
pip install -r requirements.txt
python run.py                 # dev server on :5000
python -m pytest              # full suite (in-memory SQLite, no external deps)

pip install -r requirements-dev.txt
pyinstaller DocGenerator.spec  # -> dist/DocGenerator/
```

There is no build step for the front-end (vanilla JS/CSS served from
`app/static/`).

## Architecture & decisions

- **App factory + single blueprint.** `create_app(config_class)` in
  `app/__init__.py`; the `/api` blueprint is in `app/api/routes.py`; `/` and
  `/history` are plain routes on the app. Tests pass a `TestConfig` to the
  factory.
- **Content is schemaless JSON.** `Document.content` / `Template.content` store a
  JSON array of blocks. The DB does not model blocks; `schemas.BlockSchema` is
  the only contract. Keep the block `type` list in sync across `schemas.py`,
  `pdf_service.py`, and `app/static/js/app.js`.
- **Block shape:** `{type, text, level?, image_name?}`. `text` is overloaded: for
  `image` blocks it is a filesystem path; for `table` blocks it is a JSON string
  of rows.
- **Revisions, not edits.** Regenerating from `parent_document_id` inserts a new
  `Document` row sharing the parent's `unique_identifier`, with
  `revision_number + 1`. `diff_service.calculate_diff` adds `_highlight: true` to
  changed blocks; `pdf_service` renders those with a yellow background. The diff
  is deliberately positional/simple. A revision inherits the parent's
  `signature_path` / `logo_left_path` / `logo_right_path` unless overridden.
- **Header logos.** `logo_left_path` / `logo_right_path` are optional per-document
  `Document` columns (uploaded via `/api/upload` like the signature). When a side
  has no image, that header corner is left empty — no fallback. Right = the
  RTL-leading corner. `app/static/assets/logo{,2}.png` are only example images.
- **Performance.** Two things dominate: (1) always reach the server on
  `127.0.0.1`, never `localhost` — on some machines `localhost` → IPv6 `::1`
  stalls ~2 s per request (run.py binds 127.0.0.1, the templates redirect
  `localhost`→`127.0.0.1`, all docs use the literal). (2) Images: uploads are
  capped to 2200 px on the longest edge (`_shrink_oversized` in routes.py) and
  `pdf_service._fit_image` downsizes each image again to the actual draw box
  before embedding — an image-heavy PDF is ~10x faster and ~15x smaller than
  embedding raw photos. Keep both layers.
- **Watermark.** `Document.watermark` (string, ≤60 chars) — a faint diagonal
  watermark drawn on every page via the `onFirstPage`/`onLaterPages` hooks
  (so it sits *behind* content), light grey rather than alpha (ReportLab does
  not reliably emit fill alpha). Editor default is `טיוטה`.
- **Contact block.** `Document.contact_details` is a JSON array of
  `{"label", "value"}` rows. Rendered by `NumberedCanvas.draw_page_number` only
  on `self._pageNumber == 1`, left-aligned below the left logo. Blank rows are
  dropped server-side; both fields go through the `<`/`>` reject check.
- **Optional settings in the editor.** `OPTIONAL_SETTINGS` in `app.js` is the
  single registry — each entry wires a toggle to a revealed control and clears
  its value when switched off. Add new optional document settings there.
- **Lightweight migrations.** `db.create_all()` never alters existing tables, so
  columns added later go in `_apply_lightweight_migrations()` in
  `app/__init__.py` (idempotent `ALTER TABLE ADD COLUMN` for nullable columns).
  Add new post-v1 columns there too.
- **Document numbers** come from the single-row `DocCounter` table via an atomic
  `UPDATE ... SET counter = counter + 1`. Format: `IT-<seq:03d>-<DDMMYYYY>`.
- **Two-pass PDF build.** `MyDocTemplate.multiBuild` runs layout twice so the TOC
  can resolve page numbers. `NumberedCanvas` buffers page state and stamps
  headers/footers/`page X of N` only in `save()`, when the total is known. Do not
  try to collapse this to one pass.
- **Deferred bookmarks.** Because `NumberedCanvas.showPage()` is deferred,
  calling `canv.bookmarkPage()` during layout would bind every TOC/TOF
  destination to page 1 (`_doc.thisPageRef()` never advances). Instead
  `afterFlowable` records `(key, y)` per page in `canv._deferred_bookmarks`, and
  `save()` calls `bookmarkPage()` one page at a time, just before emitting that
  page. Keep these in sync if you touch either method.
- **RTL rendering.** ReportLab has no BiDi support. Every user string for a
  `Paragraph` goes through `pdf_service.rtl_markup()`: split on hard newlines →
  greedy word-wrap each line to the available width (real font metrics) →
  `get_display(line, base_dir='R')` per resulting line → `html.escape` → join
  with `<br/>`. Do **not** call `get_display` on a whole multi-line/wrapping
  string (it reverses line order and mangles mixed Hebrew/English) and do not
  set `wordWrap='RTL'` on top of `rtl_markup` output (double reorder).
  `drawString` calls still use `get_display` directly (single short strings).
  `RTLTableOfContents` /
  `RTLTableOfFigures` re-implement row drawing (page number left, dot leaders,
  right-aligned title, full-width `linkRect`) because the stock TOC is LTR-only.
- **Fonts.** `_resolve_font()` tries `HEBREW_FONT_PATH`, then common Windows /
  Linux / macOS paths, then falls back to `Helvetica` (which cannot render
  Hebrew). Never hardcode a single OS path again.
- **Config via env.** `config.py` reads `SECRET_KEY`, `DATABASE_URL`,
  `MAX_CONTENT_LENGTH`, `UPLOAD_FOLDER`. `run.py` loads `.env` if `python-dotenv`
  is present. Document every new env var in `.env.example`.
- **Source vs frozen (.exe).** `paths.py` is the single source of truth:
  `resource_path(*parts)` for read-only bundled files (it honours
  `sys._MEIPASS`), `data_dir()` / `uploads_dir()` for writable per-user data. In
  a PyInstaller build the DB and uploads live under the OS app-data dir, never
  next to the executable. Rules: never open a bundled path for writing; never
  hardcode `app/static/...` — go through `paths.py`; add new bundled data files
  to `DocGenerator.spec`'s `datas`. `run.py` detects `sys.frozen` and switches to
  a no-reloader server (`waitress` if importable) plus auto-opens the browser.
- **Fonts.** `pdf_service._resolve_font()` registers a (regular, bold) TTF pair,
  trying `HEBREW_FONT_PATH` → system fonts → the bundled
  `app/static/assets/fonts/DejaVuSans*.ttf` (which ships so the .exe renders
  Hebrew anywhere) → Helvetica (no Hebrew). Result is cached in module globals
  `FONT_REGULAR` / `FONT_BOLD`.
- **PDF theme.** `pdf_service` has a palette block near the top (INK, MUTED,
  ACCENT, …). Keep colours referenced by name, not inline hex, so the look stays
  consistent. Headings: level 0 = filled dark band, level 1 = filled indigo-50
  band, level 2 = accent underline. Tables: dark header row + zebra body.

## Coding standards

- Python: PEP 8, 4-space indent, module-level docstring on every file, docstrings
  on non-trivial functions/classes. Prefer explicit names; the one sanctioned
  abbreviation is `b_type` for a block's type inside tight loops.
- Keep user input on the escape path: schema validation → `html.escape` →
  `get_display`. Do not add a code path that renders user text without all three.
- New API endpoints: validate the body with a marshmallow schema, return
  `(jsonify(...), status)` tuples, and rely on the app-level 400/404/500 error
  handlers for uncaught cases.
- New block types: update `BlockSchema.type`'s `OneOf`, the render loop in
  `generate_pdf`, and the editor in `app.js` (`typeLabels` + `addBlock`).
- Add a pytest test for every bug fix and new endpoint. Tests must not require
  network or a real database.

## Security / data hygiene

- **Never commit** `app.db`, `app/static/uploads/*`, or `.env`. They are
  git-ignored; keep it that way — real deployments hold sensitive content.
- Uploads are restricted to image extensions and run through
  `werkzeug.secure_filename` with a UUID prefix.
- There is **no auth/CSRF** — this is known and documented in the README. If you
  add auth, add it as blueprint-level `before_request`, not per-route.

## Files that should stay deleted

`temp.js`, `fix.py`, root-level `test_pdf.py`, `test_bm*.pdf` were scratch
artifacts removed during the public-release cleanup. `migrate.py` is a historical
one-shot script kept for reference — do not run it against a live DB.

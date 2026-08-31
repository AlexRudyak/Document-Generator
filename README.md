<div align="center">

<img src="docs/logo.png" alt="Document Generator" width="120">

# מחולל מסמכים · Document Generator

**Author structured, right‑to‑left (Hebrew) documents in a drag‑and‑drop block editor —
render them to polished, paginated PDFs with a linked table of contents and
figure list, revision tracking, per‑document header logos, an optional contact
block and watermark, templates you can share, and a one‑file Windows build.**

[![Release](https://img.shields.io/github/v/release/AlexRudyak/Document-Generator?color=4F46E5&label=release)](https://github.com/AlexRudyak/Document-Generator/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.0-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)

[![PDF engine](https://img.shields.io/badge/PDF-ReportLab-CC0000)](https://www.reportlab.com/)
[![RTL](https://img.shields.io/badge/RTL-Hebrew-4F46E5)](#)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#-tests)
[![Built with Claude Code](https://img.shields.io/badge/built%20with-Claude%20Code-D97757?logo=anthropic&logoColor=white)](https://claude.com/claude-code)

<img src="docs/sample.png" alt="Sample generated PDF: cover, numbered content, and a captioned figure" width="92%">

</div>

> [!WARNING]
> **Before forking or deploying:** the local `app.db` and `app/static/uploads/`
> can hold real, sensitive document content — they are git‑ignored, keep it that
> way. There is **no built‑in authentication** (see [Known limitations](#-known-limitations)).

---

## Contents

- [Features](#-features)
- [Quick start](#-quick-start)
- [Standalone executable](#-standalone-executable)
- [Usage](#-usage)
- [Architecture](#-architecture)
- [Tests](#-tests)
- [Known limitations](#-known-limitations)
- [Contributing](#-contributing)
- [License & acknowledgements](#-license)

---

## ✨ Features

| | |
|---|---|
| **Block editor** | Headings (6 indent levels), paragraphs, ordered / unordered lists, JSON tables, and captioned images. Drag‑and‑drop reordering, keyboard‑free indent controls. |
| **Automatic structure** | Hierarchical heading numbers (`1.` → `1.1` → `1.1.1`), a linked **Table of Contents** and **Table of Figures**, figure captions — all generated at render time. |
| **RTL‑correct PDFs** | Text is word‑wrapped and BiDi‑reordered **per line**, so hard newlines and mixed Hebrew ↔ English come out in the right order. Custom right‑to‑left TOC/TOF renderer with dot leaders and working internal links; bundled Hebrew‑capable font. |
| **Modern layout** | Cover page, banded headings, zebra tables, hairline figure frames, per‑page furniture (document number, revision, date, `page X of N`). |
| **Revisions** | Regenerate from any previous version — changed blocks are highlighted, the revision counter bumps, and the document's stable identifier is preserved. |
| **Templates** | Save any layout as a reusable template, and **export / import** all templates as a JSON file to move them between installs. |
| **Custom logos** | Upload a left / right header logo per document (each optional, with a live placement preview); a blank side leaves that corner empty. |
| **Contact block** | Optional user‑defined `label: value` rows (phone, e‑mail, address, …) rendered left‑aligned in the **first‑page** header, beneath the left logo. |
| **Watermark** | Optional faint diagonal watermark on every page (defaults to `טיוטה`, editable). |
| **Fast with photos** | Uploads are capped and each image is downsized to what the page needs, so an image‑heavy PDF renders in a fraction of a second and stays small. |
| **History & search** | Every generated document is kept and searchable by title, ID or content. |

<sub>Tech: **Flask 3** (app‑factory + blueprint) · **Flask‑SQLAlchemy** (SQLite by default) · **marshmallow** · **ReportLab** + **python‑bidi** · **Pillow** · vanilla‑JS front end, no build step · **pytest** · **PyInstaller** for the executable.</sub>

---

## 🚀 Quick start

**Prerequisites:** Python 3.10+ and a TTF font covering Hebrew. Windows uses
`arial.ttf` automatically; elsewhere install e.g. `fonts-dejavu` or set
`HEBREW_FONT_PATH`. A copy of DejaVu Sans is bundled as a last‑resort fallback.

```bash
git clone https://github.com/AlexRudyak/Document-Generator.git
cd Document-Generator

python -m venv .venv
# Windows:  .venv\Scripts\activate
# Unix:     source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # then set SECRET_KEY

python run.py                 # opens http://127.0.0.1:5000
```

The SQLite schema is created on first run. Use `127.0.0.1`, not `localhost` —
on some systems `localhost` resolves to IPv6 first and every request stalls
~2 s before falling back.

<details>
<summary>Running in production</summary>

```bash
export SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"
export DATABASE_URL="postgresql+psycopg://user:pass@host/docgen"
gunicorn "app:create_app()"
```

Put it behind an authenticating reverse proxy — there is no built‑in auth.
</details>

---

## 📦 Standalone executable

Package everything into a self‑contained folder with **PyInstaller** — no Python
required on the target machine. Pre‑built Windows binaries are attached to each
[release](https://github.com/AlexRudyak/Document-Generator/releases).

```bash
pip install -r requirements-dev.txt
pyinstaller DocGenerator.spec        # → dist/DocGenerator/
```

Running `DocGenerator[.exe]` starts a local server and opens the browser; closing
the console window quits. User data lives **outside the bundle**, per user:

| Platform | Location |
|----------|----------|
| Windows  | `%LOCALAPPDATA%\DocGenerator\` |
| macOS    | `~/Library/Application Support/DocGenerator/` |
| Linux    | `${XDG_DATA_HOME:-~/.local/share}/DocGenerator/` |

Override paths with `DOCGEN_DATA_DIR`, `DOCGEN_UPLOAD_DIR`, or `HEBREW_FONT_PATH`.

---

## 🧩 Usage

### Web UI

1. Give the document a **title** and (optionally) a custom ID.
2. Add blocks, drag the `☰` handle to reorder, indent with `<` / `>`.
3. In **document settings**, optionally enable header logos, a signature, a
   watermark, and a first-page contact block (add as many `label: value` rows as
   you need). Each is a toggle; turning it off clears it.
4. **צור מסמך PDF** downloads the rendered PDF.
5. **שמור כתבנית** saves the current layout as a template; **⬇ ייצא תבניות** / **⬆ ייבא תבניות** move templates between installs as a JSON file.
6. **היסטוריית מסמכים** lists past documents — open one to start a new **revision**.

### API

```bash
curl -X POST http://127.0.0.1:5000/api/documents/generate \
  -H 'Content-Type: application/json' \
  -d '{
        "content": [
          {"type": "title",     "text": "דוח שנתי"},
          {"type": "header",    "text": "מבוא", "level": 0},
          {"type": "paragraph", "text": "תוכן הפסקה כאן."}
        ]
      }' \
  --output report.pdf
```

| Method & path | Purpose |
|---|---|
| `GET  /api/templates` | List templates |
| `POST /api/templates` | Create a template (`{name, content}`) |
| `GET  /api/templates/export` | Download all templates as JSON (`?id=` for one) |
| `POST /api/templates/import` | Create templates from an uploaded JSON file |
| `GET  /api/documents?q=` | List / search documents |
| `GET  /api/documents/<id>` | Fetch one document's blocks |
| `POST /api/documents/generate` | Validate, persist, and render a PDF |
| `POST /api/upload` | Upload an image (multipart `file`) → returns a path |

**Block shape:** `{"type": title|header|paragraph|table|image|list_ordered|list_unordered, "text": str, "level"?: int, "image_name"?: str}`.
For `table`, `text` is a JSON string of rows (`[["a","b"],["c","d"]]`); for `image`
it is the path returned by `/api/upload`.

**Optional `generate` fields:** `parent_document_id` (create a revision),
`watermark` (str), `contact_details` (`[{label, value}]`), `signature_path`,
`logo_left_path`, `logo_right_path`.

---

## 🏗 Architecture

```
run.py               entry point (dev server, or frozen‑app launcher)
config.py             env‑driven configuration
paths.py              source‑vs‑frozen path resolution (resources, user data, version)
VERSION               single‑line version string, bundled into the build
DocGenerator.spec     PyInstaller build recipe
requirements.txt      runtime deps  ·  requirements-dev.txt  build + test deps
app/
├── __init__.py       app factory: config, db, blueprint, error handlers, migrations
├── models.py         Template · Document (revision + settings metadata) · DocCounter
├── schemas.py        marshmallow BlockSchema / ContactRowSchema / TemplateSchema / DocumentSchema
├── api/routes.py     /api blueprint (templates, import/export, documents, upload)
├── services/
│   ├── pdf_service.py   ⭐ the PDF engine — see the module docstring
│   └── diff_service.py  positional block diff → _highlight flags
├── templates/        index.html (editor), history.html
└── static/           app.js, style.css, assets/ (bundled DejaVu Sans + example logos)
tests/                pytest suite
```

**PDF generation flow**

1. `app.js` serializes the editor blocks and `POST`s them to `/api/documents/generate`.
2. `DocumentSchema` validates every block (rejecting `<` / `>`).
3. With `parent_document_id`, `diff_service.calculate_diff` marks changed blocks and
   the revision number increments; otherwise a new number is minted from `DocCounter`.
4. The document is persisted as a JSON block array.
5. `pdf_service.generate_pdf` builds the ReportLab story (cover → TOC → TOF → one
   flowable per block), reordering every string for RTL **per line** and
   downsizing images to the draw box first. A **two‑pass** `multiBuild` resolves
   TOC page numbers; `NumberedCanvas` stamps page furniture, the watermark and
   the bookmark destinations once the page count is known.
6. The PDF is streamed back as a download.

See [CLAUDE.md](CLAUDE.md) for architectural decisions and coding standards.

---

## 🧪 Tests

```bash
python -m pytest
```

In‑memory SQLite, no network or external services required. A few tests that
inspect the generated PDF's links need PyMuPDF (`pip install -r requirements-dev.txt`);
they're skipped automatically if it isn't installed.

---

## ⚠️ Known limitations

- **No authentication / CSRF protection** — deploy behind an authenticating proxy or VPN.
- The revision diff is **positional**: inserting a block near the top marks everything below it as changed.
- SQLite by default; the document‑number counter relies on a single‑row atomic `UPDATE`.
- Text is greedily wrapped and BiDi‑reordered per line, so hard newlines and mixed Hebrew/English render in the right order. A single long word or a very wide table cell can still overflow, since cell widths aren't known before layout.

---

## 🤝 Contributing

Issues and PRs welcome. Please keep the test suite green (`python -m pytest`) and
follow the conventions in [CLAUDE.md](CLAUDE.md) — module docstrings, marshmallow
validation on new endpoints, and a test for every fix.

---

## 📄 License

[MIT](LICENSE) © Document Generator contributors.

<sub>Bundled font: **DejaVu Sans** (see `app/static/assets/fonts/LICENSE-DejaVu.txt`).</sub>

---

<div align="center">
<sub>Cleaned up, documented, packaged and released with
<a href="https://claude.com/claude-code"><b>Claude Code</b></a>.</sub>
</div>

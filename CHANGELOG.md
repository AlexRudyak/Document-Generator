# Changelog

Notable changes to this project. Earlier releases (v0.2.6 and before) are
documented on the [GitHub Releases](https://github.com/AlexRudyak/Document-Generator/releases)
page.

## [Unreleased]

## [0.5.0] - 2026-11-23

### Added

- **Code blocks.** A new "+ הוסף קוד" button, next to "add image", inserts a code
  block with a language dropdown (22 languages: Python, JavaScript, TypeScript,
  Java, C#, C++, C, Go, Rust, PHP, Ruby, Kotlin, Swift, SQL, HTML, XML, CSS,
  JSON, YAML, Bash, PowerShell, or plain text). The PDF shows the code in a boxed,
  left-to-right monospace block with syntax highlighting and a language label;
  long code wraps and flows across pages. Code may contain `<` and `>`.
- **Visual table editor.** Adding a table now opens a popup asking for the number of
  rows and columns (with a live preview), then creates an editable grid instead of a
  raw JSON box. Rows and columns can be added or deleted afterwards; Enter moves down
  a column. Tables are still stored as the same JSON rows, so existing documents and
  templates open in the grid unchanged.
- **Table captions and list of tables.** Each table can have an optional caption
  (shown below it as "טבלה N - caption"), and a new "רשימת טבלאות" document setting adds a
  linked list of tables after the contents page. Tables are now centred, both in the
  editor and in the PDF.
- **Insert anywhere.** Hovering the gap between two blocks (or above the first /
  below the last) reveals a "+ כותרת / פסקה / טבלה / תמונה / קוד" strip that inserts a new
  block at that exact spot.

### Changed

- **Document sheet.** The content blocks now sit inside a framed, highlighted "תוכן המסמך"
  sheet, separate from the title/ID fields and the settings. The bottom "add" buttons
  hide once the document has a block, since the hover strip covers every position.

### Fixed

- **Indent of new blocks.** A paragraph, image or code block added under a sub-header
  (1.1, 1.2 …) now sits at that sub-header's level instead of jumping back to the top
  level; a block inserted via the hover strip takes the level of the block above it.

## [0.4.2] - 2026-11-23

### Fixed

- **Windows .exe failed to start.** The packaged app could crash on launch with
  `ModuleNotFoundError: sqlalchemy.util._collection_cy` (SQLAlchemy 2.1's
  compiled helper modules were not bundled). The build now collects
  SQLAlchemy, Flask-SQLAlchemy, marshmallow and Pillow in full. The packaged
  build was verified end to end (all block types, images, logos, signature,
  watermark, revisions, templates) without Python installed.

## [0.4.1] - 2026-10-14

### Fixed

- **Duplicate revision numbers.** Re-editing an older revision from the history
  page (e.g. Rev 1 when Rev 2 already exists) no longer creates a second Rev 2.
  The new revision takes the next free number in the document's lineage, and
  "highlight changes" compares against that newest revision.

## [0.4.0] - 2026-10-06

### Added

- **App icon.** A new indigo document-with-sparkle icon: browser favicon on both
  pages and the embedded icon of the Windows `.exe`. Regenerate it with
  `python tools/make_icon.py`.

### Fixed

- **Stored XSS.** Closed a gap where `custom_doc_id` and template names were not
  rejected for `<` / `>`; also includes a QA/DRY audit cleanup.
- **Dev server shutdown.** Closing the console window now also kills the
  reloader's child process, so it no longer lingers holding the port.

### Changed

- **License.** Switched from MIT to PolyForm Noncommercial 1.0.0.

## [0.3.0]

### Added

- **Dark mode.** A toggle in the editor and history page switches the whole UI
  between light and dark themes, remembered per browser.
- **Template export/import panel.** Pick exactly which templates to export or
  import from a side panel instead of an all-or-nothing download.
- **Collapsible sections.** Each top-level numbered header can be collapsed to
  hide its content while editing a long document.
- **Draw a signature.** Draw a signature with the mouse/touch instead of only
  uploading an image, with an optional caption that overlays the (faded)
  signature like a watermark.
- **Document setting previews.** Classification, watermark, and signature
  settings show a small live preview of where they'll appear on the page.
- **Revision history actions.** Bulk-select and delete documents from the
  history page; redownload any past revision's PDF as-is, or a clean copy
  with the yellow diff highlighting stripped out.
- **Optional diff highlighting.** Choose whether a new revision's changed
  blocks get the yellow highlight, instead of it always being on.
- **Inline text/list blocks.** A paragraph block gets "+ הוסף טקסט / תבליטים /
  רשימה ממוספרת" buttons attached beneath it — items added this way merge into
  the same box, and list items render with a slight indent from body text, in
  both the editor and the PDF.

### Fixed

- **Table of contents.** Dot leaders and heading numbers no longer disappear
  or scramble for headings long enough to wrap onto multiple lines.
- **Signature caption.** Long captions now wrap (including a single unbroken
  run with no spaces) instead of running off the page, and show up even when
  no image was uploaded or drawn.
- **Signature persistence.** Toggling the signature off and back on no longer
  discards the uploaded/drawn file.
- **Block alignment.** Every block type's input field lines up at the same
  edge now, regardless of type.

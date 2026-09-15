# Changelog

Notable changes to this project. Earlier releases (v0.2.6 and before) are
documented on the [GitHub Releases](https://github.com/AlexRudyak/Document-Generator/releases)
page.

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

document.addEventListener('DOMContentLoaded', () => {
    loadTemplates();

    const urlParams = new URLSearchParams(window.location.search);
    const docId = urlParams.get('doc_id');
    if (docId) {
        loadDocument(docId);
    }

    document.getElementById('add-header-btn').addEventListener('click', () => addBlock('header'));
    document.getElementById('add-paragraph-btn').addEventListener('click', () => addBlock('paragraph'));
    document.getElementById('add-table-btn').addEventListener('click', () => addTableViaPrompt(null));
    document.getElementById('add-image-btn').addEventListener('click', () => addBlock('image'));
    document.getElementById('add-code-btn').addEventListener('click', () => addBlock('code'));
    initHoverInserter();
    
    document.getElementById('save-template-btn').addEventListener('click', saveTemplate);
    document.getElementById('generate-btn').addEventListener('click', generateDocument);
    document.getElementById('template-select').addEventListener('change', (e) => loadTemplate(e.target.value));
    document.getElementById('open-templates-panel-btn').addEventListener('click', openTemplatesPanel);
    document.getElementById('close-templates-panel-btn').addEventListener('click', closeTemplatesPanel);
    document.getElementById('templates-panel-overlay').addEventListener('click', closeTemplatesPanel);
    document.getElementById('export-select-all').addEventListener('change', (e) => {
        document.querySelectorAll('#export-templates-list input[type="checkbox"]').forEach(cb => cb.checked = e.target.checked);
    });
    document.getElementById('export-selected-btn').addEventListener('click', exportSelectedTemplates);
    document.getElementById('import-templates-input').addEventListener('change', handleImportFileSelect);
    document.getElementById('import-selected-btn').addEventListener('click', importSelectedTemplates);

    initThemeToggle();

    wireImageUpload('doc-signature', 'signature-path', 'signature-status');
    wireImageUpload('doc-logo-right', 'logo-right-path', 'logo-right-status', 'logo-right-thumb');
    wireImageUpload('doc-logo-left', 'logo-left-path', 'logo-left-status', 'logo-left-thumb');
    initSignaturePad();

    // Each option's control (dropdown / file picker / rows) is revealed only
    // when its toggle is on; turning a toggle off clears whatever it held.
    OPTIONAL_SETTINGS.forEach(s => {
        document.getElementById(s.toggle).addEventListener('change', () => {
            syncSetting(s);
            // Ticking "contact details" with no rows yet: start with one.
            if (s.rows && document.getElementById(s.toggle).checked
                && !document.getElementById(s.rows).children.length) {
                addContactRow();
            }
        });
        syncSetting(s);
    });

    document.getElementById('contact-add').addEventListener('click', () => addContactRow());

    document.getElementById('wm-text').addEventListener('input', (e) => {
        document.getElementById('wm-preview-text').innerText = e.target.value.trim() || WATERMARK_DEFAULT;
    });

    const container = document.getElementById('blocks-container');
    container.addEventListener('dragover', (e) => {
        e.preventDefault();
        const draggingBlock = document.querySelector('.dragging');
        if (!draggingBlock) return;
        const afterElement = getDragAfterElement(container, e.clientY);
        if (afterElement == null) {
            container.appendChild(draggingBlock);
        } else {
            container.insertBefore(draggingBlock, afterElement);
        }
    });
});

// Applies immediately on load (see the inline <script> in <head>); this just
// wires the toggle button and keeps localStorage/icon in sync with it.
function initThemeToggle() {
    const btn = document.getElementById('theme-toggle-btn');
    if (!btn) return;
    const sync = () => {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        btn.innerText = isDark ? '☀️ מצב בהיר' : '🌙 מצב כהה';
    };
    sync();
    btn.addEventListener('click', () => {
        const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        sync();
    });
}

// The optional document settings. Each has a toggle checkbox, a revealed
// control container, and (for file settings) the hidden input that carries the
// uploaded server path plus its status label.
const WATERMARK_DEFAULT = 'טיוטה';

const OPTIONAL_SETTINGS = [
    { key: 'classification', toggle: 'classify-toggle',   control: 'classify-control' },
    { key: 'watermark',      toggle: 'wm-toggle',         control: 'wm-control',         text: 'wm-text', default: WATERMARK_DEFAULT },
    // persistOnOff: switching this off only hides/excludes it from the
    // document — it doesn't discard the uploaded/drawn file. The dedicated
    // "remove" button (or a full reset) is what actually clears it.
    { key: 'signature',      toggle: 'sig-toggle',        control: 'sig-control',        hidden: 'signature-path',   status: 'signature-status', caption: 'signature-text', persistOnOff: true },
    { key: 'logo_right',     toggle: 'logo-right-toggle', control: 'logo-right-control', hidden: 'logo-right-path',  status: 'logo-right-status', thumb: 'logo-right-thumb' },
    { key: 'logo_left',      toggle: 'logo-left-toggle',  control: 'logo-left-control',  hidden: 'logo-left-path',   status: 'logo-left-status',  thumb: 'logo-left-thumb'  },
    { key: 'contact',        toggle: 'contact-toggle',    control: 'contact-control',    rows: 'contact-rows' },
    // A plain on/off flag: no revealed control.
    { key: 'table_list',     toggle: 'tl-toggle' },
];

// Paint (or clear) the mini page-preview corner for a logo setting.
function setThumb(thumbId, url) {
    const el = document.getElementById(thumbId);
    if (!el) return;
    el.style.backgroundImage = url ? `url("${url}")` : '';
    el.classList.toggle('has-img', !!url);
}

// Show/hide a setting's control to match its toggle; clear its value when off
// (unless the setting is marked persistOnOff — then only `hardReset`, used
// for an actual full reset, clears it). The visual on/off state is driven by
// an `is-on` class (rather than a CSS `:checked` sibling selector) so it
// updates reliably when set from script.
function syncSetting(s, hardReset = false) {
    const cb = document.getElementById(s.toggle);
    const on = cb.checked;
    cb.closest('.setting').classList.toggle('is-on', on);
    if (s.control) document.getElementById(s.control).hidden = !on;
    if (!on && s.hidden && (hardReset || !s.persistOnOff)) {
        document.getElementById(s.hidden).value = '';
        const st = document.getElementById(s.status);
        if (st) { st.textContent = ''; st.className = 'file-name'; }
        if (s.thumb) setThumb(s.thumb, null);
        if (s.caption) document.getElementById(s.caption).value = '';
    }
    if (!on && s.key === 'signature') {
        const panel = document.getElementById('sig-draw-panel');
        if (panel) panel.hidden = true;
    }
    if (!on && s.rows) {
        document.getElementById(s.rows).innerHTML = '';
    }
    if (!on && s.text) {
        document.getElementById(s.text).value = s.default || '';
    }
}

// Turn a setting on with a stored value, or off when it is empty:
//   classification / watermark -> string   signature/logo -> path (+ previewUrl)
//   contact                    -> [{label, value}, ...]
function applySetting(key, value, previewUrl, caption) {
    const s = OPTIONAL_SETTINGS.find(x => x.key === key);
    document.getElementById(s.toggle).checked = !!value;
    if (value) {
        if (s.key === 'classification') {
            document.getElementById('doc-classification').value = value;
        } else if (s.text) {
            document.getElementById(s.text).value = value;
        } else if (s.rows) {
            const box = document.getElementById(s.rows);
            box.innerHTML = '';
            value.forEach(r => addContactRow(r.label || '', r.value || ''));
        } else {
            document.getElementById(s.hidden).value = value;
            const st = document.getElementById(s.status);
            st.textContent = '✓ קובץ קיים';
            st.className = 'file-name ok';
            if (s.thumb) setThumb(s.thumb, previewUrl || null);
            if (s.caption) document.getElementById(s.caption).value = caption || '';
        }
    }
    // Explicit state for a specific document/template: always applies fully
    // (clearing stale values from whatever was previously loaded), unlike a
    // plain user toggle-flip, which respects persistOnOff.
    syncSetting(s, /* hardReset */ true);
}

// --- Contact-detail rows -------------------------------------------------
function addContactRow(label = '', value = '') {
    const row = document.createElement('div');
    row.className = 'contact-row';

    const l = document.createElement('input');
    l.className = 'contact-label';
    l.placeholder = 'תווית (למשל: טלפון)';
    l.value = label;

    const v = document.createElement('input');
    v.className = 'contact-value';
    v.placeholder = 'ערך (למשל: 050-1234567)';
    v.value = value;

    const del = document.createElement('button');
    del.type = 'button';
    del.className = 'contact-del';
    del.textContent = '✕';
    del.onclick = () => row.remove();

    row.append(l, v, del);
    document.getElementById('contact-rows').appendChild(row);
}

function getContactDetails() {
    return [...document.querySelectorAll('#contact-rows .contact-row')]
        .map(r => ({
            label: r.querySelector('.contact-label').value.trim(),
            value: r.querySelector('.contact-value').value.trim(),
        }))
        .filter(r => r.label || r.value);
}

function resetOptionalSettings() {
    OPTIONAL_SETTINGS.forEach(s => {
        document.getElementById(s.toggle).checked = false;
        syncSetting(s, /* hardReset */ true);
    });
}

// Upload an image file to /api/upload, stash the returned server path in the
// hidden input, show its name, and (for logos) preview it in its corner.
async function uploadImageFile(file, hiddenId, statusId, thumbId) {
    const status = statusId ? document.getElementById(statusId) : null;
    if (status) { status.textContent = 'מעלה…'; status.className = 'file-name uploading'; }
    if (thumbId) setThumb(thumbId, URL.createObjectURL(file));   // instant local preview
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (!data.filepath) throw new Error(data.error || 'upload failed');
        document.getElementById(hiddenId).value = data.filepath;
        if (status) { status.textContent = '✓ ' + file.name; status.className = 'file-name ok'; }
        if (thumbId && data.url) setThumb(thumbId, data.url);
        return true;
    } catch (err) {
        if (status) { status.textContent = ''; status.className = 'file-name'; }
        if (thumbId) setThumb(thumbId, null);
        alert('העלאה נכשלה: ' + err.message);
        return false;
    }
}

function wireImageUpload(inputId, hiddenId, statusId, thumbId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.addEventListener('change', (e) => {
        if (e.target.files.length === 0) return;
        uploadImageFile(e.target.files[0], hiddenId, statusId, thumbId);
    });
}

// Lets the user draw a signature with the mouse (or touch/pen) instead of
// uploading a file. Strokes are drawn in a fixed dark ink color regardless of
// the app's theme, since the canvas always represents a white printed page.
function initSignaturePad() {
    const toggleBtn = document.getElementById('sig-draw-toggle-btn');
    const panel = document.getElementById('sig-draw-panel');
    const canvas = document.getElementById('sig-canvas');
    if (!toggleBtn || !panel || !canvas) return;

    const ctx = canvas.getContext('2d');
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#1e293b';
    let drawing = false;
    let hasStrokes = false;

    const posFromEvent = (e) => {
        const rect = canvas.getBoundingClientRect();
        return {
            x: (e.clientX - rect.left) * (canvas.width / rect.width),
            y: (e.clientY - rect.top) * (canvas.height / rect.height),
        };
    };

    canvas.addEventListener('pointerdown', (e) => {
        drawing = true;
        hasStrokes = true;
        const p = posFromEvent(e);
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener('pointermove', (e) => {
        if (!drawing) return;
        const p = posFromEvent(e);
        ctx.lineTo(p.x, p.y);
        ctx.stroke();
    });
    const stopDrawing = () => { drawing = false; };
    canvas.addEventListener('pointerup', stopDrawing);
    canvas.addEventListener('pointercancel', stopDrawing);
    canvas.addEventListener('pointerleave', stopDrawing);

    const clearCanvas = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        hasStrokes = false;
    };

    toggleBtn.addEventListener('click', () => {
        panel.hidden = !panel.hidden;
        if (!panel.hidden) clearCanvas();
    });
    document.getElementById('sig-clear-btn').addEventListener('click', clearCanvas);
    document.getElementById('sig-cancel-btn').addEventListener('click', () => {
        panel.hidden = true;
        clearCanvas();
    });
    document.getElementById('sig-save-btn').addEventListener('click', () => {
        if (!hasStrokes) { alert('צייר חתימה לפני השמירה.'); return; }
        canvas.toBlob(async (blob) => {
            if (!blob) return;
            const file = new File([blob], 'signature.png', { type: 'image/png' });
            const ok = await uploadImageFile(file, 'signature-path', 'signature-status');
            if (ok) panel.hidden = true;
        }, 'image/png');
    });
    document.getElementById('sig-remove-btn').addEventListener('click', () => {
        document.getElementById('signature-path').value = '';
        document.getElementById('signature-text').value = '';
        const st = document.getElementById('signature-status');
        st.textContent = '';
        st.className = 'file-name';
        panel.hidden = true;
        clearCanvas();
    });
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.block:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

let templates = [];
let currentParentDocId = null;
let blockIdSeq = 0;   // unique per-block DOM-id suffix (see addBlock's image branch)

const typeLabels = {
    'header': 'כותרת',
    'paragraph': 'טקסט',
    'table': 'טבלה',
    'list_unordered': 'תבליטים',
    'list_ordered': 'רשימה ממוספרת',
    'image': 'תמונה',
    'code': 'קוד'
};

function updateNumbering() {
    const blocks = document.querySelectorAll('.block');
    let counters = [0, 0, 0, 0, 0, 0];
    let orderedListCount = 0;
    let unorderedListCount = 0;
    let lastType = null;
    // Sections run from one top-level (level 0) header up to the next; a
    // collapsed one hides everything in between except that anchor header.
    let sectionCollapsed = false;

    blocks.forEach(block => {
        const type = block.dataset.type;
        const level = parseInt(block.dataset.level) || 0;
        const labelElement = block.querySelector('.block-type');
        const collapseBtn = block.querySelector('.collapse-toggle');

        if (type === 'header') {
            counters[level]++;
            for (let i = level + 1; i < 6; i++) counters[i] = 0;
            let numStr = counters.slice(0, level + 1).join('.');
            if (level === 0) numStr += '.';
            labelElement.innerText = numStr + ' כותרת';

            if (level === 0) {
                // Anchor header: always visible, only place the toggle is active.
                const collapsed = block.dataset.collapsed === 'true';
                if (collapseBtn) {
                    collapseBtn.hidden = false;
                    collapseBtn.innerText = collapsed ? '▶' : '▼';
                }
                block.classList.toggle('section-collapsed', collapsed);
                block.style.display = '';
                sectionCollapsed = collapsed;
            } else {
                if (collapseBtn) collapseBtn.hidden = true;
                block.classList.remove('section-collapsed');
                block.style.display = sectionCollapsed ? 'none' : '';
            }
        } else {
            if (type === 'list_ordered') {
                if (lastType !== 'list_ordered') orderedListCount = 1;
                else orderedListCount++;
                labelElement.innerText = typeLabels[type] + ' ' + orderedListCount;
            } else if (type === 'list_unordered') {
                if (lastType !== 'list_unordered') unorderedListCount = 1;
                else unorderedListCount++;
                labelElement.innerText = typeLabels[type] + ' ' + unorderedListCount;
            } else {
                labelElement.innerText = typeLabels[type] || type.toUpperCase();
            }
            block.style.display = sectionCollapsed ? 'none' : '';
        }
        lastType = type;
    });

    // Merge a paragraph with any list items added under it via its
    // quick-add buttons into one visual box (see .block-grouped /
    // .block-group-has-next): recomputed from live DOM order every time, so
    // dragging things around keeps the merged box honest.
    const blockList = Array.from(blocks);
    blockList.forEach((block, i) => {
        const grouped = block.dataset.groupWithPrev === 'true';
        block.classList.toggle('block-grouped', grouped);
        const next = blockList[i + 1];
        const hasNext = !!next && next.dataset.groupWithPrev === 'true';
        block.classList.toggle('block-group-has-next', hasNext);

        // A paragraph's quick-add row always sits at the bottom of its
        // current group, not fixed under the paragraph itself, so it moves
        // down as items are added and up again as they're removed.
        if (block.quickAddEl) {
            let tail = block;
            while (tail.nextElementSibling && tail.nextElementSibling.dataset.groupWithPrev === 'true') {
                tail = tail.nextElementSibling;
            }
            tail.append(block.quickAddEl);
        }
    });
}

function addBlock(type, text = '', level = -1, imageName = '', language = '', caption = '') {
    const container = document.getElementById('blocks-container');
    const blockUid = `block-${++blockIdSeq}`;

    if (level === -1) {
        // Content added under a sub-header (1.1, 1.2 …) sits at that header's
        // level, not back at the top level. A new header keeps level 0.
        if (type !== 'header') {
            const blocks = container.querySelectorAll('.block');
            if (blocks.length > 0) {
                const lastBlock = blocks[blocks.length - 1];
                level = parseInt(lastBlock.dataset.level) || 0;
            } else {
                level = 0;
            }
        } else {
            level = 0;
        }
    }

    const block = document.createElement('div');
    block.className = 'block';
    block.dataset.type = type;
    block.dataset.level = level;
    block.dataset.imageName = imageName;
    block.style.marginRight = (level * 30) + 'px';
    
    const dragHandle = document.createElement('div');
    dragHandle.innerText = '☰';
    dragHandle.className = 'drag-handle';

    dragHandle.onmousedown = () => block.draggable = true;
    dragHandle.onmouseup = () => block.draggable = false;
    dragHandle.onmouseleave = () => block.draggable = false;

    block.addEventListener('dragstart', (e) => {
        block.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
    });
    block.addEventListener('dragend', () => {
        block.classList.remove('dragging');
        block.draggable = false;
        // A manually-moved block no longer belongs to wherever it used to be
        // grouped; it can be regrouped with a fresh quick-add click if needed.
        delete block.dataset.groupWithPrev;
        updateNumbering();
    });

    // Always created (not just for headers) and reserved via visibility —
    // not display — when inactive, so every block type's input starts at
    // the same x regardless of whether it actually has a collapse toggle.
    const collapseBtn = document.createElement('button');
    collapseBtn.type = 'button';
    collapseBtn.className = 'collapse-toggle';
    collapseBtn.title = 'כווץ / הרחב סעיף';
    collapseBtn.innerText = '▼';
    collapseBtn.hidden = !(type === 'header' && level === 0);
    if (type === 'header') {
        collapseBtn.onclick = () => {
            block.dataset.collapsed = block.dataset.collapsed === 'true' ? 'false' : 'true';
            updateNumbering();
        };
    }

    const label = document.createElement('span');
    label.className = 'block-type';
    label.innerText = typeLabels[type] || type.toUpperCase();

    let input;
    if (type === 'image') {
        input = document.createElement('div');
        input.className = 'image-input-wrapper';

        const fileIn = document.createElement('input');
        fileIn.type = 'file';
        fileIn.accept = 'image/*';

        const nameIn = document.createElement('input');
        nameIn.type = 'text';
        nameIn.placeholder = 'שם תמונה (אופציונלי)';
        nameIn.className = 'image-name-input';
        nameIn.value = block.dataset.imageName || '';

        const hiddenPath = document.createElement('input');
        hiddenPath.type = 'hidden';
        hiddenPath.className = 'block-input image-path-input';
        hiddenPath.id = `${blockUid}-path`;
        hiddenPath.value = text;

        const statusSpan = document.createElement('span');
        statusSpan.id = `${blockUid}-status`;
        if (text) {
            statusSpan.textContent = '✓ קובץ קיים';
            statusSpan.className = 'file-name ok';
        } else {
            statusSpan.className = 'file-name';
        }

        // Same upload flow as the logo/signature pickers (status text,
        // error handling) instead of a separate copy of the fetch/response
        // handling here.
        fileIn.onchange = (e) => {
            if (e.target.files.length > 0) {
                uploadImageFile(e.target.files[0], hiddenPath.id, statusSpan.id);
            }
        };
        input.append(fileIn, statusSpan, nameIn, hiddenPath);
    } else if (type === 'table') {
        input = createTableEditor(parseTableText(text), caption);
    } else if (type === 'code') {
        // Language dropdown above a monospace, LTR textarea. The language
        // list comes from the server (window.CODE_LANGUAGES, see index.html).
        input = document.createElement('div');
        input.className = 'code-input-wrapper';

        const langSelect = document.createElement('select');
        langSelect.className = 'code-lang-select';
        langSelect.title = 'שפת תכנות';
        (window.CODE_LANGUAGES || []).forEach(([key, name]) => {
            const opt = document.createElement('option');
            opt.value = key;
            opt.textContent = name;
            langSelect.append(opt);
        });
        langSelect.value = language || window.DEFAULT_CODE_LANGUAGE || 'text';
        if (!langSelect.value) langSelect.selectedIndex = 0;

        const codeArea = document.createElement('textarea');
        codeArea.className = 'block-input code-textarea';
        codeArea.dir = 'ltr';
        codeArea.spellcheck = false;
        codeArea.placeholder = 'הדבק או הקלד קוד כאן…';
        codeArea.value = text;
        // Tab inserts indentation instead of leaving the field.
        codeArea.addEventListener('keydown', (e) => {
            if (e.key === 'Tab' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
                e.preventDefault();
                const { selectionStart: a, selectionEnd: b } = codeArea;
                codeArea.setRangeText('    ', a, b, 'end');
            }
        });
        input.append(langSelect, codeArea);
    } else {
        input = document.createElement(type === 'header' ? 'input' : 'textarea');
        input.className = 'block-input';
        input.value = text;
        if (type === 'header') input.type = 'text';
    }
    
    const deleteBtn = document.createElement('button');
    deleteBtn.innerText = 'X';
    deleteBtn.className = 'delete-btn';
    deleteBtn.onclick = () => {
        // Deleting a group's head shouldn't leave its followers merging
        // into whatever unrelated block now precedes them — promote the
        // next one to be the new (ungrouped) head instead.
        const next = block.nextElementSibling;
        if (block.dataset.groupWithPrev !== 'true' && next && next.dataset.groupWithPrev === 'true') {
            delete next.dataset.groupWithPrev;
        }
        // Deleting the paragraph that owns the quick-add row removes the
        // row too — there's no paragraph left for it to add lists under —
        // rather than leaving it stranded wherever it last was pinned.
        if (block.quickAddEl) block.quickAddEl.remove();
        block.remove();
        updateNumbering();
    };
    
    const indentLeftBtn = document.createElement('button');
    indentLeftBtn.innerText = '>';
    indentLeftBtn.className = 'move-btn';
    indentLeftBtn.onclick = () => {
        let lvl = parseInt(block.dataset.level);
        if(lvl < 5) {
            lvl++;
            block.dataset.level = lvl;
            block.style.marginRight = (lvl * 30) + 'px';
            updateNumbering();
        }
    };

    const indentRightBtn = document.createElement('button');
    indentRightBtn.innerText = '<';
    indentRightBtn.className = 'move-btn';
    indentRightBtn.onclick = () => {
        let lvl = parseInt(block.dataset.level);
        if(lvl > 0) {
            lvl--;
            block.dataset.level = lvl;
            block.style.marginRight = (lvl * 30) + 'px';
            updateNumbering();
        }
    };

    const controls = document.createElement('div');
    controls.className = 'block-controls';
    controls.append(indentRightBtn, indentLeftBtn, deleteBtn);

    // A paragraph gets its own "add more content right after this" shortcuts,
    // attached under the block instead of living in the general toolbar.
    // Each addition lands at the end of the paragraph's existing group (not
    // always right after the paragraph itself), so repeated clicks stack in
    // the order they were added, and is flagged groupWithPrev so it renders
    // merged into the paragraph's box (see updateNumbering).
    let quickAdd = null;
    if (type === 'paragraph') {
        const insertBlockAfter = (newType) => {
            let anchor = block;
            while (anchor.nextElementSibling && anchor.nextElementSibling.dataset.groupWithPrev === 'true') {
                anchor = anchor.nextElementSibling;
            }
            addBlock(newType, '', parseInt(block.dataset.level) || 0);
            const newBlock = container.lastElementChild;
            newBlock.dataset.groupWithPrev = 'true';
            container.insertBefore(newBlock, anchor.nextSibling);
            if (newType === 'paragraph') {
                // The new paragraph creates its own quick-add row and
                // becomes the group's sole owner going forward — drop this
                // one entirely (not just untrack it) or it's left orphaned
                // in the DOM, no longer repositioned by updateNumbering().
                if (block.quickAddEl) block.quickAddEl.remove();
                delete block.quickAddEl;
            }
            updateNumbering();
        };
        const addTextBtn = document.createElement('button');
        addTextBtn.type = 'button';
        addTextBtn.className = 'quick-add-btn';
        addTextBtn.innerText = '+ הוסף טקסט';
        addTextBtn.onclick = () => insertBlockAfter('paragraph');

        const addBulletBtn = document.createElement('button');
        addBulletBtn.type = 'button';
        addBulletBtn.className = 'quick-add-btn';
        addBulletBtn.innerText = '+ הוסף תבליטים';
        addBulletBtn.onclick = () => insertBlockAfter('list_unordered');

        const addOrderedBtn = document.createElement('button');
        addOrderedBtn.type = 'button';
        addOrderedBtn.className = 'quick-add-btn';
        addOrderedBtn.innerText = '+ הוסף רשימה ממוספרת';
        addOrderedBtn.onclick = () => insertBlockAfter('list_ordered');

        quickAdd = document.createElement('div');
        quickAdd.className = 'paragraph-quick-add';
        quickAdd.append(addTextBtn, addBulletBtn, addOrderedBtn);
        // Referenced by updateNumbering() to keep this pinned to the
        // bottom of the group, wherever that currently is.
        block.quickAddEl = quickAdd;
    }

    block.append(dragHandle, collapseBtn, label, input, controls,
                ...(quickAdd ? [quickAdd] : []));
    container.append(block);
    updateNumbering();
}

// --- Tables ---------------------------------------------------------------
// A table block is edited as a grid of inputs but still stored as the same JSON
// string of rows (`[["a","b"],["c","d"]]`) the PDF engine and old documents use.
// Column 0 is the right-most column (the page is RTL), matching the PDF.
const TABLE_MAX_ROWS = 100;
const TABLE_MAX_COLS = 10;
const TABLE_CELL_MIN = 100;   // px; keep in sync with .table-grid td in style.css
const TABLE_CTL_W = 28;       // px; width of the row-delete / spacer columns

function emptyTableJson(rows, cols) {
    return JSON.stringify(Array.from({ length: rows }, () => Array(cols).fill('')));
}

function parseTableText(text) {
    try {
        const v = JSON.parse(text);
        if (Array.isArray(v) && v.length && v.every(Array.isArray) && v.some(r => r.length)) {
            const width = Math.max(...v.map(r => r.length));
            return v.map(r => Array.from({ length: width }, (_, i) => (r[i] == null ? '' : String(r[i]))));
        }
    } catch (e) { /* not JSON: fall through to a small blank grid */ }
    return [['', ''], ['', '']];
}

function el(tag, className, text) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (text) e.textContent = text;
    return e;
}

// The grid editor inside a table block. `wrap.readRows()` returns the cells.
function createTableEditor(initialRows, caption = '') {
    const wrap = el('div', 'table-editor');
    const capIn = el('input', 'table-caption-input');
    capIn.type = 'text';
    capIn.placeholder = 'כיתוב לטבלה (אופציונלי)';
    capIn.value = caption;
    capIn.dir = 'auto';
    const scroll = el('div', 'table-scroll');
    const table = el('table', 'table-grid');
    scroll.append(table);
    let data = initialRows;

    const readRows = () => Array.from(table.querySelectorAll('tr.t-row'))
        .map(tr => Array.from(tr.querySelectorAll('input.table-cell')).map(i => i.value));
    wrap.readRows = readRows;

    const bar = el('div', 'table-toolbar');
    const addRowBtn = el('button', 'quick-add-btn', '+ שורה');
    const addColBtn = el('button', 'quick-add-btn', '+ עמודה');
    addRowBtn.type = addColBtn.type = 'button';
    bar.append(addRowBtn, addColBtn);

    function render(focusAt) {
        table.innerHTML = '';
        const cols = data[0].length;
        // Fixed layout: the two side columns stay 28px, cells share the rest
        // evenly; many columns scroll sideways instead of squashing.
        table.style.minWidth = (cols * TABLE_CELL_MIN + 2 * TABLE_CTL_W) + 'px';
        data.forEach((row, r) => {
            const tr = el('tr', 't-row');
            // Empty leading cell mirrors the delete column so the grid itself is centred.
            tr.append(el('td', 't-ctl t-spacer'));
            row.forEach((val, c) => {
                const td = el('td', r === 0 ? 't-head' : '');
                const inp = el('input', 'table-cell');
                inp.type = 'text';
                inp.value = val;
                inp.dir = 'auto';
                inp.setAttribute('aria-label', `שורה ${r + 1}, עמודה ${c + 1}`);
                // Enter moves down the column, like a spreadsheet.
                inp.addEventListener('keydown', (e) => {
                    if (e.key !== 'Enter') return;
                    e.preventDefault();
                    const next = table.querySelectorAll('tr.t-row')[r + 1];
                    if (next) next.querySelectorAll('input.table-cell')[c].focus();
                    else addRow();
                });
                td.append(inp);
                tr.append(td);
            });
            const ctl = el('td', 't-ctl');
            const del = el('button', 't-del', '✕');
            del.type = 'button';
            del.title = 'מחק שורה';
            del.disabled = data.length === 1;
            del.onclick = () => { data = readRows(); data.splice(r, 1); render(); };
            ctl.append(del);
            tr.append(ctl);
            table.append(tr);
        });
        const foot = el('tr', 't-foot');
        foot.append(el('td', 't-ctl t-spacer'));
        for (let c = 0; c < cols; c++) {
            const td = el('td', 't-ctl');
            const del = el('button', 't-del', '✕');
            del.type = 'button';
            del.title = 'מחק עמודה';
            del.disabled = cols === 1;
            del.onclick = () => { data = readRows(); data.forEach(row => row.splice(c, 1)); render(); };
            td.append(del);
            foot.append(td);
        }
        foot.append(el('td'));
        table.append(foot);
        if (focusAt) {
            const cell = table.querySelectorAll('tr.t-row')[focusAt[0]]
                .querySelectorAll('input.table-cell')[focusAt[1]];
            if (cell) cell.focus();
        }
        addRowBtn.disabled = data.length >= TABLE_MAX_ROWS;
        addColBtn.disabled = cols >= TABLE_MAX_COLS;
    }

    function addRow() {
        if (data.length >= TABLE_MAX_ROWS) return;
        data = readRows();
        data.push(Array(data[0].length).fill(''));
        render([data.length - 1, 0]);
    }
    function addCol() {
        if (data[0].length >= TABLE_MAX_COLS) return;
        data = readRows();
        data.forEach(row => row.push(''));
        render([0, data[0].length - 1]);
    }
    addRowBtn.onclick = addRow;
    addColBtn.onclick = addCol;

    wrap.append(scroll, capIn, bar);     // caption sits below the table
    render();
    return wrap;
}

// Popup asking for the table size, with a live preview of the grid it will
// create. Resolves to {rows, cols}, or null when cancelled.
function promptTableSize() {
    return new Promise((resolve) => {
        const backdrop = el('div', 'modal-backdrop');
        const dlg = el('form', 'modal');
        dlg.setAttribute('role', 'dialog');
        dlg.setAttribute('aria-modal', 'true');
        dlg.append(el('h3', 'modal-title', 'הוספת טבלה'));

        const field = (label, max, value) => {
            const wrapper = el('label', 'modal-field');
            wrapper.append(el('span', '', label));
            const inp = el('input');
            inp.type = 'number';
            inp.min = 1;
            inp.max = max;
            inp.value = value;
            inp.required = true;
            wrapper.append(inp);
            return { wrapper, inp };
        };
        const rowsF = field('שורות', TABLE_MAX_ROWS, 3);
        const colsF = field('עמודות', TABLE_MAX_COLS, 3);
        const fields = el('div', 'modal-fields');
        fields.append(rowsF.wrapper, colsF.wrapper);

        const preview = el('div', 'table-preview');
        const clamp = (inp, max) => Math.min(max, Math.max(1, parseInt(inp.value, 10) || 1));
        const redraw = () => {
            const r = clamp(rowsF.inp, TABLE_MAX_ROWS), c = clamp(colsF.inp, TABLE_MAX_COLS);
            const t = el('table', 'table-grid preview-grid');
            for (let i = 0; i < Math.min(r, 8); i++) {
                const tr = el('tr');
                for (let j = 0; j < c; j++) tr.append(el('td', i === 0 ? 't-head' : ''));
                t.append(tr);
            }
            preview.replaceChildren(t);
            if (r > 8) preview.append(el('div', 'preview-more', `… ועוד ${r - 8} שורות`));
        };
        rowsF.inp.oninput = colsF.inp.oninput = redraw;
        redraw();

        const actions = el('div', 'modal-actions');
        const ok = el('button', 'btn-primary', 'צור טבלה');
        ok.type = 'submit';
        const cancel = el('button', 'btn-secondary', 'ביטול');
        cancel.type = 'button';
        actions.append(ok, cancel);
        dlg.append(fields, preview, actions);
        backdrop.append(dlg);
        document.body.append(backdrop);

        const onKey = (e) => { if (e.key === 'Escape') { e.preventDefault(); close(null); } };
        const close = (result) => {
            document.removeEventListener('keydown', onKey, true);
            backdrop.remove();
            resolve(result);
        };
        document.addEventListener('keydown', onKey, true);
        cancel.onclick = () => close(null);
        backdrop.addEventListener('mousedown', (e) => { if (e.target === backdrop) close(null); });
        dlg.onsubmit = (e) => {
            e.preventDefault();
            close({ rows: clamp(rowsF.inp, TABLE_MAX_ROWS), cols: clamp(colsF.inp, TABLE_MAX_COLS) });
        };
        rowsF.inp.focus();
        rowsF.inp.select();
    });
}

// Toolbar / hover entry point for a new table: ask for the size, then insert.
function addTableViaPrompt(beforeBlock) {
    return promptTableSize().then((size) => {
        if (size) insertBlockBefore('table', beforeBlock || null, emptyTableJson(size.rows, size.cols));
    });
}

// --- Hover inserter -----------------------------------------------------------
// Hovering the gap between two blocks (or above the first one) reveals a small
// "+ כותרת / פסקה / תמונה / קוד" strip that inserts a new block right there,
// instead of only at the end of the document. One floating element, positioned
// from live DOM geometry, so it never touches the block list itself.
const HOVER_INSERT_TYPES = [
    ['header', '+ כותרת'],
    ['paragraph', '+ פסקה'],
    ['table', '+ טבלה'],
    ['image', '+ תמונה'],
    ['code', '+ קוד'],
];
const HOVER_INSERT_REACH = 18;   // px from a gap's centre line that still triggers it

function insertBlockBefore(type, beforeBlock, text = '') {
    const container = document.getElementById('blocks-container');
    // Take the level of the block it lands under, so something inserted below
    // a sub-header (or a new sibling sub-header) stays at that depth.
    const above = beforeBlock ? beforeBlock.previousElementSibling : container.lastElementChild;
    const level = above ? (parseInt(above.dataset.level) || 0) : 0;
    addBlock(type, text, level);
    const newBlock = container.lastElementChild;     // addBlock appends
    if (beforeBlock && beforeBlock !== newBlock) container.insertBefore(newBlock, beforeBlock);
    updateNumbering();
    newBlock.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    const field = newBlock.querySelector('.table-cell, .block-input:not([type="hidden"]), input[type="file"]');
    if (field) field.focus({ preventScroll: true });
}

function initHoverInserter() {
    const container = document.getElementById('blocks-container');

    // The bottom "add" toolbar only bootstraps an empty document; once any
    // block exists the hover inserter covers every position, so hide it.
    const toolbar = document.getElementById('add-toolbar');
    const syncToolbar = () => {
        toolbar.hidden = !!container.querySelector(':scope > .block');
    };
    new MutationObserver(syncToolbar).observe(container, { childList: true });
    syncToolbar();
    const bar = document.createElement('div');
    bar.id = 'block-inserter';
    bar.hidden = true;
    let target = null;      // block the new one goes before; null = at the end

    HOVER_INSERT_TYPES.forEach(([type, label]) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'inserter-btn';
        btn.textContent = label;
        btn.onclick = () => {
            const before = target;
            bar.hidden = true;
            if (type === 'table') addTableViaPrompt(before);
            else insertBlockBefore(type, before);
        };
        bar.append(btn);
    });
    document.body.append(bar);

    // Gaps: before each top-level visible block (grouped paragraph+list boxes
    // count as one), plus after the last visible block.
    function gaps() {
        const visible = Array.from(container.querySelectorAll(':scope > .block'))
            .filter(b => b.offsetParent !== null);
        const out = [];
        visible.forEach((b, i) => {
            if (b.dataset.groupWithPrev === 'true') return;
            const r = b.getBoundingClientRect();
            const prev = visible[i - 1];
            const y = prev ? (prev.getBoundingClientRect().bottom + r.top) / 2 : r.top - 8;
            out.push({ y, before: b });
        });
        const last = visible[visible.length - 1];
        if (last) out.push({ y: last.getBoundingClientRect().bottom + 8, before: null });
        return out;
    }

    function hide() { bar.hidden = true; }

    document.addEventListener('mousemove', (e) => {
        if (bar.contains(e.target)) return;                 // keep it while using it
        if (document.querySelector('.block.dragging')) return hide();
        const box = container.getBoundingClientRect();
        if (e.clientX < box.left || e.clientX > box.right ||
            e.clientY < box.top - 20 || e.clientY > box.bottom + 20) return hide();
        let best = null;
        for (const g of gaps()) {
            const d = Math.abs(e.clientY - g.y);
            if (d <= HOVER_INSERT_REACH && (!best || d < best.d)) best = { d, g };
        }
        if (!best) return hide();
        target = best.g.before;
        bar.hidden = false;
        bar.style.top = best.g.y + 'px';
        bar.style.left = (box.left + box.width / 2) + 'px';
    });
    document.addEventListener('scroll', hide, true);
    document.addEventListener('mouseleave', hide);
}

function getBlocksData() {
    const data = [];
    const titleText = document.getElementById('doc-title').value.trim();
    if(titleText) {
        data.push({ type: 'title', text: titleText });
    }
    
    const blocks = document.querySelectorAll('.block');
    blocks.forEach(b => {
        const type = b.dataset.type;
        const level = parseInt(b.dataset.level) || 0;
        
        if (type === 'image') {
            const pathElem = b.querySelector('.image-path-input');
            const nameElem = b.querySelector('.image-name-input');
            const text = pathElem ? pathElem.value.trim() : '';
            const imgName = nameElem ? nameElem.value.trim() : '';
            if (text) {
                data.push({ type, text, image_name: imgName, level });
            }
        } else if (type === 'table') {
            const editor = b.querySelector('.table-editor');
            const rows = editor ? editor.readRows().map(r => r.map(c => c.trim())) : [];
            if (rows.some(r => r.some(c => c))) {
                const capElem = b.querySelector('.table-caption-input');
                const caption = capElem ? capElem.value.trim() : '';
                data.push(caption ? { type, text: JSON.stringify(rows), caption, level }
                                  : { type, text: JSON.stringify(rows), level });
            }
        } else if (type === 'code') {
            const codeElem = b.querySelector('.code-textarea');
            const langElem = b.querySelector('.code-lang-select');
            // Keep leading indentation: only trim blank lines around the code.
            const code = codeElem ? codeElem.value.replace(/^(?:[ \t]*\r?\n)+|\s+$/g, '') : '';
            if (code) {
                data.push({ type, text: code, language: langElem ? langElem.value : 'text', level });
            }
        } else {
            const textElem = b.querySelector('.block-input');
            const text = textElem ? textElem.value.trim() : '';
            if(text) {
                data.push({ type, text, level });
            }
        }
    });
    return data;
}

function loadTemplates() {
    fetch('/api/templates')
        .then(r => r.json())
        .then(data => {
            templates = data;
            const select = document.getElementById('template-select');
            select.innerHTML = '<option value="">-- טען תבנית --</option>';
            data.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.innerText = t.name;
                select.append(opt);
            });
        });
}

// The revision banner and its "highlight changes" toggle always change
// together; hiding it also resets the toggle back to its checked default so
// it doesn't leak a previous document's choice into the next one.
function hideRevisionAlert() {
    document.getElementById('revision-alert').style.display = 'none';
    document.getElementById('highlight-changes-toggle').checked = true;
}

function showRevisionAlert() {
    document.getElementById('revision-alert').style.display = 'flex';
    document.getElementById('highlight-changes-toggle').checked = true;
}

// Common state to clear when leaving "editing a specific document's
// revision" context: used both to start fresh (no template/document
// selected) and as the first step before loading a different template.
function resetRevisionState() {
    currentParentDocId = null;
    hideRevisionAlert();
    document.getElementById('custom-doc-id').value = '';
    document.getElementById('custom-doc-id').disabled = false;
    resetOptionalSettings();
}

function loadTemplate(id) {
    if(!id) return;
    const t = templates.find(x => x.id == id);
    if(t) {
        resetRevisionState();
        document.getElementById('blocks-container').innerHTML = '';
        document.getElementById('doc-title').value = '';
        t.content.forEach(b => {
            if (b.type === 'title') {
                document.getElementById('doc-title').value = b.text;
            } else {
                addBlock(b.type, b.text, b.level || 0, b.image_name || '', b.language || '', b.caption || '');
            }
        });
    }
}

function loadDocument(id) {
    if(!id) {
        resetRevisionState();
        return;
    }
    fetch(`/api/documents/${id}`)
        .then(r => r.json())
        .then(d => {
            currentParentDocId = d.id;
            showRevisionAlert();
            applySetting('classification', d.classification);
            applySetting('watermark', d.watermark);
            applySetting('signature', d.signature_path, null, d.signature_text);
            applySetting('logo_right', d.logo_right_path, d.logo_right_url);
            applySetting('logo_left', d.logo_left_path, d.logo_left_url);
            applySetting('contact', d.contact_details);
            applySetting('table_list', d.table_list);
            document.getElementById('blocks-container').innerHTML = '';
            document.getElementById('doc-title').value = '';
            document.getElementById('custom-doc-id').value = d.document_number;
            document.getElementById('custom-doc-id').disabled = true;
            d.content.forEach(b => {
                if (b.type === 'title') {
                    document.getElementById('doc-title').value = b.text;
                } else {
                    addBlock(b.type, b.text, b.level || 0, b.image_name || '', b.language || '', b.caption || '');
                }
            });
        });
}

function saveTemplate() {
    const name = prompt("אנא הזן שם לתבנית:");
    if(!name) return;
    
    const content = getBlocksData();
    if(content.length === 0) {
        alert("לא ניתן לשמור תבנית ריקה.");
        return;
    }
    
    fetch('/api/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, content })
    })
    .then(r => r.json())
    .then(res => {
        if(res.error || res.name) alert(JSON.stringify(res));
        else {
            alert("התבנית נשמרה בהצלחה!");
            loadTemplates();
        }
    });
}

let pendingImportItems = [];

function openTemplatesPanel() {
    renderExportList();
    document.getElementById('templates-panel-overlay').hidden = false;
    const panel = document.getElementById('templates-panel');
    panel.hidden = false;
    panel.setAttribute('aria-hidden', 'false');
}

function closeTemplatesPanel() {
    document.getElementById('templates-panel-overlay').hidden = true;
    const panel = document.getElementById('templates-panel');
    panel.hidden = true;
    panel.setAttribute('aria-hidden', 'true');
}

function renderExportList() {
    const list = document.getElementById('export-templates-list');
    document.getElementById('export-select-all').checked = false;
    if (templates.length === 0) {
        list.innerHTML = '<p class="panel-empty">אין תבניות שמורות.</p>';
        return;
    }
    list.innerHTML = '';
    templates.forEach(t => {
        const label = document.createElement('label');
        label.className = 'panel-item';
        label.innerHTML = `<input type="checkbox" value="${t.id}"><span>${escapeHtml(t.name)}</span>`;
        list.append(label);
    });
}

function exportSelectedTemplates() {
    const ids = Array.from(document.querySelectorAll('#export-templates-list input[type="checkbox"]:checked'))
        .map(cb => cb.value);
    if (templates.length === 0) { alert("אין תבניות לייצוא."); return; }
    if (ids.length === 0) { alert("בחר לפחות תבנית אחת לייצוא."); return; }
    // A plain navigation triggers the download (Content-Disposition: attachment).
    const params = ids.map(id => `id=${encodeURIComponent(id)}`).join('&');
    window.location.href = `/api/templates/export?${params}`;
}

async function handleImportFileSelect(e) {
    const file = e.target.files[0];
    e.target.value = '';           // allow re-selecting the same file
    const list = document.getElementById('import-templates-list');
    const importBtn = document.getElementById('import-selected-btn');
    pendingImportItems = [];
    importBtn.disabled = true;
    if (!file) return;

    try {
        const text = await file.text();
        const data = JSON.parse(text);
        const items = (data && Array.isArray(data.templates)) ? data.templates
            : Array.isArray(data) ? data
            : (data && data.name && data.content) ? [data]
            : null;
        if (!items) throw new Error('מבנה קובץ התבניות לא מזוהה');
        pendingImportItems = items;
    } catch (err) {
        list.innerHTML = `<p class="panel-empty">שגיאה בקריאת הקובץ: ${escapeHtml(err.message)}</p>`;
        return;
    }

    if (pendingImportItems.length === 0) {
        list.innerHTML = '<p class="panel-empty">הקובץ לא מכיל תבניות.</p>';
        return;
    }

    const existingNames = new Set(templates.map(t => t.name));
    list.innerHTML = '';
    pendingImportItems.forEach((item, i) => {
        const name = (item && item.name) ? item.name : '(ללא שם)';
        const label = document.createElement('label');
        label.className = 'panel-item';
        const note = existingNames.has(name) ? '<span class="panel-item-note">שם קיים</span>' : '';
        label.innerHTML = `<input type="checkbox" value="${i}" checked><span>${escapeHtml(name)}</span>${note}`;
        list.append(label);
    });
    importBtn.disabled = false;
}

async function importSelectedTemplates() {
    const indices = Array.from(document.querySelectorAll('#import-templates-list input[type="checkbox"]:checked'))
        .map(cb => parseInt(cb.value, 10));
    if (indices.length === 0) { alert("בחר לפחות תבנית אחת לייבוא."); return; }
    const selected = indices.map(i => pendingImportItems[i]);
    try {
        const res = await fetch('/api/templates/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(selected)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'ייבוא נכשל');
        let msg = `יובאו ${data.created.length} תבניות`;
        if (data.skipped.length) msg += `, ${data.skipped.length} דולגו (לא תקינות)`;
        alert(msg);
        loadTemplates();
        closeTemplatesPanel();
    } catch (err) {
        alert('ייבוא נכשל: ' + err.message);
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
}

function generateDocument() {
    const content = getBlocksData();
    if(content.length === 0) {
        alert("לא ניתן לייצר מסמך ריק.");
        return;
    }
    
    // Off toggles clear their hidden value (syncSetting), so empty ⇒ not sent.
    const classified = document.getElementById('classify-toggle').checked;
    const payload = {
        content: content,
        classification: classified ? document.getElementById('doc-classification').value : null,
        watermark: document.getElementById('wm-toggle').checked
            ? (document.getElementById('wm-text').value.trim() || WATERMARK_DEFAULT) : null,
        signature_path: document.getElementById('sig-toggle').checked
            ? (document.getElementById('signature-path').value || null) : null,
        signature_text: document.getElementById('sig-toggle').checked
            ? (document.getElementById('signature-text').value.trim() || null) : null,
        logo_right_path: document.getElementById('logo-right-path').value || null,
        logo_left_path: document.getElementById('logo-left-path').value || null,
        contact_details: document.getElementById('contact-toggle').checked ? getContactDetails() : null,
        table_list: document.getElementById('tl-toggle').checked,
        custom_doc_id: document.getElementById('custom-doc-id').value.trim()
    };
    if (currentParentDocId) {
        payload.parent_document_id = currentParentDocId;
        payload.highlight_changes = document.getElementById('highlight-changes-toggle').checked;
    }
    
    fetch('/api/documents/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(res => {
        if(res.ok) {
            const disposition = res.headers.get('Content-Disposition');
            let filename = 'document.pdf';
            if (disposition && disposition.includes('attachment')) {
                const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                const matches = filenameRegex.exec(disposition);
                if (matches != null && matches[1]) {
                    filename = matches[1].replace(/['"]/g, '');
                }
            }
            return res.blob().then(blob => ({blob, filename}));
        } else {
            res.json().then(err => alert(JSON.stringify(err)));
            throw new Error("Server Error");
        }
    })
    .then(({blob, filename}) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        
        currentParentDocId = null;
        hideRevisionAlert();
    })
    .catch(err => console.error(err));
}

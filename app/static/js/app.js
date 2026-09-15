document.addEventListener('DOMContentLoaded', () => {
    loadTemplates();

    const urlParams = new URLSearchParams(window.location.search);
    const docId = urlParams.get('doc_id');
    if (docId) {
        loadDocument(docId);
    }

    document.getElementById('add-header-btn').addEventListener('click', () => addBlock('header'));
    document.getElementById('add-paragraph-btn').addEventListener('click', () => addBlock('paragraph'));
    document.getElementById('add-table-btn').addEventListener('click', () => addBlock('table'));
    document.getElementById('add-list-btn').addEventListener('click', () => addBlock('list_unordered'));
    document.getElementById('add-ordered-list-btn').addEventListener('click', () => addBlock('list_ordered'));
    document.getElementById('add-image-btn').addEventListener('click', () => addBlock('image'));
    
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
    { key: 'signature',      toggle: 'sig-toggle',        control: 'sig-control',        hidden: 'signature-path',   status: 'signature-status' },
    { key: 'logo_right',     toggle: 'logo-right-toggle', control: 'logo-right-control', hidden: 'logo-right-path',  status: 'logo-right-status', thumb: 'logo-right-thumb' },
    { key: 'logo_left',      toggle: 'logo-left-toggle',  control: 'logo-left-control',  hidden: 'logo-left-path',   status: 'logo-left-status',  thumb: 'logo-left-thumb'  },
    { key: 'contact',        toggle: 'contact-toggle',    control: 'contact-control',    rows: 'contact-rows' },
];

// Paint (or clear) the mini page-preview corner for a logo setting.
function setThumb(thumbId, url) {
    const el = document.getElementById(thumbId);
    if (!el) return;
    el.style.backgroundImage = url ? `url("${url}")` : '';
    el.classList.toggle('has-img', !!url);
}

// Show/hide a setting's control to match its toggle; clear its value when off.
// The visual on/off state is driven by an `is-on` class (rather than a CSS
// `:checked` sibling selector) so it updates reliably when set from script.
function syncSetting(s) {
    const cb = document.getElementById(s.toggle);
    const on = cb.checked;
    cb.closest('.setting').classList.toggle('is-on', on);
    document.getElementById(s.control).hidden = !on;
    if (!on && s.hidden) {
        document.getElementById(s.hidden).value = '';
        const st = document.getElementById(s.status);
        if (st) { st.textContent = ''; st.className = 'file-name'; }
        if (s.thumb) setThumb(s.thumb, null);
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
function applySetting(key, value, previewUrl) {
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
        }
    }
    syncSetting(s);
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
    OPTIONAL_SETTINGS.forEach(s => applySetting(s.key, null));
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

const typeLabels = {
    'header': 'כותרת',
    'paragraph': 'פסקה',
    'table': 'טבלה (JSON)',
    'list_unordered': 'תבליטים',
    'list_ordered': 'רשימה ממוספרת',
    'image': 'תמונה'
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
}

function addBlock(type, text = '', level = -1, imageName = '') {
    const container = document.getElementById('blocks-container');
    
    if (level === -1) {
        if (type.startsWith('list')) {
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
    dragHandle.style.cursor = 'grab';
    dragHandle.style.fontSize = '24px';
    dragHandle.style.color = 'var(--text-faint)';
    dragHandle.style.padding = '0 10px';
    dragHandle.style.userSelect = 'none';
    
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
        updateNumbering();
    });

    let collapseBtn = null;
    if (type === 'header') {
        collapseBtn = document.createElement('button');
        collapseBtn.type = 'button';
        collapseBtn.className = 'collapse-toggle';
        collapseBtn.title = 'כווץ / הרחב סעיף';
        collapseBtn.innerText = '▼';
        collapseBtn.hidden = level !== 0;
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
        input.style.flexGrow = '1';
        input.style.display = 'flex';
        input.style.alignItems = 'center';
        input.style.padding = '10px 0';
        
        const fileIn = document.createElement('input');
        fileIn.type = 'file';
        fileIn.accept = 'image/*';
        
        const nameIn = document.createElement('input');
        nameIn.type = 'text';
        nameIn.placeholder = 'שם תמונה (אופציונלי)';
        nameIn.className = 'image-name-input';
        nameIn.style.marginRight = '15px';
        nameIn.style.padding = '8px';
        nameIn.style.border = '2px solid var(--border)';
        nameIn.style.borderRadius = '8px';
        nameIn.style.flexGrow = '1';
        nameIn.style.background = 'var(--surface-alt)';
        nameIn.style.color = 'var(--text-strong)';
        nameIn.value = block.dataset.imageName || '';

        const hiddenPath = document.createElement('input');
        hiddenPath.type = 'hidden';
        hiddenPath.className = 'block-input image-path-input';
        hiddenPath.value = text;
        
        const statusSpan = document.createElement('span');
        statusSpan.style.marginRight = '10px';
        statusSpan.style.fontSize = '13px';
        statusSpan.style.fontWeight = 'bold';
        statusSpan.style.color = 'var(--success)';
        if (text) {
            statusSpan.innerText = '✓ קובץ קיים';
        }

        fileIn.onchange = async (e) => {
            if(e.target.files.length > 0) {
                statusSpan.innerText = 'מעלה...';
                statusSpan.style.color = 'var(--accent)';
                const formData = new FormData();
                formData.append('file', e.target.files[0]);
                const res = await fetch('/api/upload', { method: 'POST', body: formData });
                const data = await res.json();
                if(data.filepath) {
                    hiddenPath.value = data.filepath;
                    statusSpan.innerText = '✓ הועלה';
                    statusSpan.style.color = 'var(--success)';
                }
            }
        };
        input.append(fileIn, statusSpan, nameIn, hiddenPath);
    } else {
        input = document.createElement(type === 'header' ? 'input' : 'textarea');
        input.className = 'block-input';
        input.value = text;
        if (type === 'header') input.type = 'text';
    }
    
    const deleteBtn = document.createElement('button');
    deleteBtn.innerText = 'X';
    deleteBtn.className = 'delete-btn';
    deleteBtn.onclick = () => { block.remove(); updateNumbering(); };
    
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
    
    block.append(dragHandle, ...(collapseBtn ? [collapseBtn] : []), label, input, controls);
    container.append(block);
    updateNumbering();
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

function loadTemplate(id) {
    if(!id) return;
    const t = templates.find(x => x.id == id);
    if(t) {
        currentParentDocId = null;
        document.getElementById('revision-alert').style.display = 'none';
        document.getElementById('blocks-container').innerHTML = '';
        document.getElementById('doc-title').value = '';
        document.getElementById('custom-doc-id').value = '';
        document.getElementById('custom-doc-id').disabled = false;
        resetOptionalSettings();
        t.content.forEach(b => {
            if (b.type === 'title') {
                document.getElementById('doc-title').value = b.text;
            } else {
                addBlock(b.type, b.text, b.level || 0, b.image_name || '');
            }
        });
    }
}

function loadDocument(id) {
    if(!id) {
        currentParentDocId = null;
        document.getElementById('revision-alert').style.display = 'none';
        document.getElementById('custom-doc-id').value = '';
        document.getElementById('custom-doc-id').disabled = false;
        resetOptionalSettings();
        return;
    }
    fetch(`/api/documents/${id}`)
        .then(r => r.json())
        .then(d => {
            currentParentDocId = d.id;
            document.getElementById('revision-alert').style.display = 'block';
            applySetting('classification', d.classification);
            applySetting('watermark', d.watermark);
            applySetting('signature', d.signature_path);
            applySetting('logo_right', d.logo_right_path, d.logo_right_url);
            applySetting('logo_left', d.logo_left_path, d.logo_left_url);
            applySetting('contact', d.contact_details);
            document.getElementById('blocks-container').innerHTML = '';
            document.getElementById('doc-title').value = '';
            document.getElementById('custom-doc-id').value = d.document_number;
            document.getElementById('custom-doc-id').disabled = true;
            d.content.forEach(b => {
                if (b.type === 'title') {
                    document.getElementById('doc-title').value = b.text;
                } else {
                    addBlock(b.type, b.text, b.level || 0, b.image_name || '');
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
        signature_path: document.getElementById('signature-path').value || null,
        logo_right_path: document.getElementById('logo-right-path').value || null,
        logo_left_path: document.getElementById('logo-left-path').value || null,
        contact_details: document.getElementById('contact-toggle').checked ? getContactDetails() : null,
        custom_doc_id: document.getElementById('custom-doc-id').value.trim()
    };
    if (currentParentDocId) {
        payload.parent_document_id = currentParentDocId;
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
        document.getElementById('revision-alert').style.display = 'none';
        
    })
    .catch(err => console.error(err));
}

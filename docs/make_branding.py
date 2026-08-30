"""Generate the project logo and the GitHub/social ("WhatsApp") preview card.

    python docs/make_branding.py

Outputs (committed):
    docs/logo.png            512x512  - app / README icon
    docs/social-preview.png  1280x640 - repo Settings -> Social preview

Palette matches the generated-PDF theme (slate + indigo accent).
"""

import os

from PIL import Image, ImageDraw, ImageFont

try:
    from bidi.algorithm import get_display
except Exception:  # pragma: no cover
    def get_display(s):
        return s


def rtl(s):
    """Reorder a Hebrew string for a renderer (PIL) that has no BiDi support."""
    return get_display(s)

HERE = os.path.dirname(os.path.abspath(__file__))

INK = (15, 23, 42)          # #0F172A  slate-900
SLATE = (30, 41, 59)        # #1E293B
ACCENT = (99, 102, 241)     # #6366F1  indigo-500
ACCENT_DK = (67, 56, 202)   # #4338CA
INDIGO_100 = (224, 231, 255)
MUTED = (148, 163, 184)     # slate-400
WHITE = (255, 255, 255)

WIN = r"C:\Windows\Fonts"
DEJAVU_BOLD = os.path.join(HERE, os.pardir, "app", "static", "assets", "fonts", "DejaVuSans-Bold.ttf")


def _font(*names, size=48):
    for n in names:
        p = n if os.path.isabs(n) else os.path.join(WIN, n)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.truetype(DEJAVU_BOLD, size)


def _rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def draw_mark(img, size):
    """Draw the logo mark (indigo card + white document) covering the image."""
    d = ImageDraw.Draw(img)
    pad = int(size * 0.06)
    _rounded(d, (pad, pad, size - pad, size - pad), radius=int(size * 0.23), fill=ACCENT_DK)
    # very subtle top sheen
    sheen = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sheen).rounded_rectangle(
        (pad, pad, size - pad, int(size * 0.5)), radius=int(size * 0.23),
        fill=ACCENT + (60,))
    img.alpha_composite(sheen)
    d = ImageDraw.Draw(img)

    # white document sheet with a folded top-left corner
    m = int(size * 0.26)
    x0, y0, x1, y1 = m, int(size * 0.20), size - m, size - int(size * 0.16)
    fold = int((x1 - x0) * 0.28)
    d.polygon(
        [(x0 + fold, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0 + fold)],
        fill=WHITE,
    )
    d.polygon([(x0 + fold, y0), (x0 + fold, y0 + fold), (x0, y0 + fold)], fill=INDIGO_100)

    # sheet content: an accent header bar + right-aligned text lines (RTL hint),
    # evenly distributed down the sheet body.
    inset = int((x1 - x0) * 0.16)
    lx0, lx1 = x0 + inset, x1 - inset
    lh = int((y1 - y0) * 0.085)
    rows = [("accent", 0.72), ("line", 0.95), ("line", 0.62), ("line", 0.88), ("line", 0.45)]
    top = y0 + fold + int(lh * 1.4)
    step = (y1 - int((y1 - y0) * 0.12) - top) / (len(rows) - 1)
    for i, (kind, frac) in enumerate(rows):
        y = int(top + i * step)
        w = int((lx1 - lx0) * frac)
        color = ACCENT if kind == "accent" else (203, 213, 225)
        d.rounded_rectangle((lx1 - w, y, lx1, y + lh), radius=lh // 2, fill=color)


def make_logo():
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_mark(img, size)
    out = os.path.join(HERE, "logo.png")
    img.save(out)
    print("wrote", out)


def make_social():
    W, H = 1280, 640
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)

    # faint diagonal panel + accent hairlines top & bottom
    d.polygon([(0, 0), (W, 0), (W, 120), (0, 320)], fill=SLATE)
    d.rectangle((0, 0, W, 8), fill=ACCENT)
    d.rectangle((0, H - 8, W, H), fill=ACCENT)

    # logo mark on the left
    mark = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    draw_mark(mark, 300)
    img.paste(mark, (90, (H - 300) // 2), mark)

    tx = 440
    title_f = _font("segoeuib.ttf", "arialbd.ttf", size=74)
    he_f = _font("arialbd.ttf", DEJAVU_BOLD, size=46)
    sub_f = _font("segoeui.ttf", "arial.ttf", size=30)
    url_f = _font("segoeui.ttf", "arial.ttf", size=26)

    d.text((tx, 196), "Document Generator", font=title_f, fill=WHITE)
    d.text((tx, 292), rtl("מחולל מסמכים"), font=he_f, fill=INDIGO_100)
    d.rectangle((tx + 2, 372, tx + 74, 378), fill=ACCENT)
    d.text((tx, 398), "Block editor  →  paginated RTL PDF", font=sub_f, fill=MUTED)
    d.text((tx, 438), "auto TOC  ·  revisions  ·  classification", font=sub_f, fill=MUTED)
    d.text((tx, 512), "github.com/AlexRudyak/Document-Generator", font=url_f, fill=(120, 134, 156))

    out = os.path.join(HERE, "social-preview.png")
    img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    make_logo()
    make_social()

"""Render the Document Generator app icon.

    python tools/make_icon.py

Draws the icon procedurally with Pillow (no external art needed) and writes:

* ``app/static/assets/icon.png``     - 256 px master, used by the web UI
* ``app/static/assets/favicon.ico``  - 16-64 px, served as the browser favicon
* ``assets/icon.ico``                - 16-256 px, embedded into the .exe by
                                       ``DocGenerator.spec``

Design: an indigo gradient rounded square (the PDF theme's accent colour)
holding a white page with a dog-eared top-left corner. The text lines are
right-aligned to reflect the app's right-to-left (Hebrew) output, the first
one is a heading band, and an amber sparkle marks the "generator" idea.
"""

import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE = 1024          # drawn large, then downsampled for smooth edges

INDIGO_TOP = (99, 102, 241)
INDIGO_BOTTOM = (49, 46, 129)
PAGE = (255, 255, 255)
PAGE_FOLD = (199, 210, 254)
HEADING = (67, 56, 202)
TEXT_LINE = (165, 180, 252)
AMBER = (251, 191, 36)


def _gradient_square(size):
    """Vertical indigo gradient clipped to a rounded square."""
    base = Image.new('RGB', (size, size))
    px = base.load()
    for y in range(size):
        t = y / (size - 1)
        colour = tuple(round(a + (b - a) * t) for a, b in zip(INDIGO_TOP, INDIGO_BOTTOM))
        for x in range(size):
            px[x, y] = colour
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), size * 0.22, fill=255)
    base.putalpha(mask)
    return base


def _sparkle(draw, cx, cy, r, fill):
    """Four-pointed star centred on (cx, cy) with outer radius r."""
    k = r * 0.28
    draw.polygon([(cx, cy - r), (cx + k, cy - k), (cx + r, cy), (cx + k, cy + k),
                  (cx, cy + r), (cx - k, cy + k), (cx - r, cy), (cx - k, cy - k)], fill=fill)


def render(size=SIZE):
    """Return the icon as an RGBA image of ``size`` x ``size`` pixels."""
    s = size / 1024
    img = _gradient_square(size)
    d = ImageDraw.Draw(img)

    # Page with a folded top-left corner.
    left, top, right, bottom, fold = 250 * s, 170 * s, 774 * s, 854 * s, 170 * s
    d.polygon([(left + fold, top), (right, top), (right, bottom), (left, bottom),
               (left, top + fold)], fill=PAGE)
    d.polygon([(left + fold, top), (left + fold, top + fold), (left, top + fold)],
              fill=PAGE_FOLD)

    # Right-aligned lines: heading band first, then body text of varying length.
    edge = right - 70 * s
    d.rounded_rectangle((edge - 290 * s, 330 * s, edge, 400 * s), 18 * s, fill=HEADING)
    for i, width in enumerate((380, 330, 380, 240)):
        y = 470 * s + i * 78 * s
        d.rounded_rectangle((edge - width * s, y, edge, y + 34 * s), 17 * s, fill=TEXT_LINE)

    # Generator sparkles, overlapping the page's bottom-left corner.
    _sparkle(d, 300 * s, 800 * s, 150 * s, AMBER)
    _sparkle(d, 440 * s, 690 * s, 60 * s, AMBER)
    return img


def main():
    master = render()
    web = os.path.join(ROOT, 'app', 'static', 'assets')
    master.resize((256, 256), Image.LANCZOS).save(os.path.join(web, 'icon.png'))
    master.save(os.path.join(web, 'favicon.ico'), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    os.makedirs(os.path.join(ROOT, 'assets'), exist_ok=True)
    master.save(os.path.join(ROOT, 'assets', 'icon.ico'),
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == '__main__':
    main()

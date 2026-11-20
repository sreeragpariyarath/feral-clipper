"""Image assets for the 'overlay' layout: rounded facecam card, shadow, white title card.

Needs Pillow (pip install pillow). Windows fonts are found automatically;
set "title_font" in config.json to a .ttf path to use another font.
"""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = ["Anton-Regular.ttf", "BebasNeue-Regular.ttf", "impact.ttf", "Impact.ttf",
                   "ariblk.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]

# emoji and symbols can't be drawn by normal fonts -> remove them from the title
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0000FE0F\U0000200D]")


def _font(size, custom=None):
    for name in ([custom] if custom else []) + FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if cur and draw.textlength(t, font=font) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def title_card(text, out_png, width=800, font_path=None, size=66):
    """White rounded card, big bold black text (1 or 2 lines). Returns (w, h)."""
    text = _EMOJI.sub("", text or "").strip().upper()
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    pad_x, pad_y = 28, 14
    while True:
        font = _font(size, font_path)
        lines = _wrap(probe, text, font, width - 2 * pad_x)
        if len(lines) <= 2 or size <= 40:
            break
        size -= 6
    line_h = int(size * 1.12)
    h = pad_y * 2 + line_h * len(lines)
    img = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, width - 1, h - 1), radius=24, fill=(255, 255, 255, 255))
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=font)
        d.text(((width - tw) / 2, pad_y + i * line_h), line, font=font, fill=(10, 10, 10, 255))
    img.save(out_png)
    return width, h


def cam_assets(w, h, out_dir, radius=36, shadow=22):
    """Writes cam_mask.png (gray, for alphamerge) and shadow.png (RGBA, w+2*shadow)."""
    out_dir = Path(out_dir)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    mask.save(out_dir / "cam_mask.png")
    sh = Image.new("RGBA", (w + 2 * shadow * 2, h + 2 * shadow * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        (shadow * 2, shadow * 2 + 10, shadow * 2 + w, shadow * 2 + h + 10),
        radius=radius, fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(shadow))
    sh.save(out_dir / "shadow.png")
    return shadow * 2


def round_mask(w, h, out_png, radius=28):
    """Gray rounded-rectangle mask (for alphamerge)."""
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    mask.save(out_png)

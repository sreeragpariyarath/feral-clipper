"""Five clip layouts for 9:16 shorts (1080x1920). Choose one with config "layout".

  bubble     full-height gameplay, round facecam bubble bottom-right, title on top
  cinematic  blurred background, wide gameplay panel in the middle, small facecam card below it
  stack      facecam strip on top, gameplay below, title on the seam (default)
  minimal    full-bleed gameplay, title on top, no facecam needed
  punch      big facecam, bold title + subtitle pill on the seam, arrow, boxed captions

Each builder returns (filter_graph, extra_images, caption_y, used_title).
Input 0 is the video; extra_images become inputs 1..n in the order they were added.
Every graph ends with ass=captions.ass[v] so the caption and logo code keeps working.
"""
import math

from clipper.render.overlay import cam_assets, round_mask, title_card

W, H = 1080, 1920
NAMES = ("bubble", "cinematic", "stack", "minimal", "punch")


def _crop(box):
    return f"crop=iw*{box['w']}:ih*{box['h']}:iw*{box['x']}:ih*{box['y']}"


def _cover(w, h):
    """Scale to fill w x h, then crop the middle."""
    return f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},setsar=1"


def _split(labels):
    if len(labels) == 1:
        return f"[0:v]null[{labels[0]}];"
    return f"[0:v]split={len(labels)}" + "".join(f"[{x}]" for x in labels) + ";"


def _add(extra, name):
    """Register an extra image input; returns its ffmpeg input index."""
    extra.append(name)
    return len(extra)


def _title(hook, out_dir, cfg, width=880):
    tw, th = title_card(hook, out_dir / "title.png", width=width,
                        font_path=cfg.get("title_font"), size=cfg.get("title_size", 52))
    return tw, th


def minimal(game, cam, hook, out_dir, cfg):
    extra, used = [], False
    graph = f"[0:v]{_crop(game)},{_cover(W, H)},unsharp=5:5:0.6:5:5:0.0[bg];"
    last = "[bg]"
    if hook:
        tw, _ = _title(hook, out_dir, cfg)
        t = _add(extra, "title.png")
        graph += f"{last}[{t}:v]overlay={(W - tw) // 2}:170:format=auto[t1];"
        last, used = "[t1]", True
    graph += f"{last}ass=captions.ass[v]"
    return graph, extra, 960, used


def bubble(game, cam, hook, out_dir, cfg):
    d = 360                                    # bubble diameter
    extra, used = [], False
    graph = _split(["a", "b"] if cam else ["a"])
    graph += f"[a]{_crop(game)},{_cover(W, H)},unsharp=5:5:0.6:5:5:0.0[bg];"
    last = "[bg]"
    if hook:
        tw, _ = _title(hook, out_dir, cfg)
        t = _add(extra, "title.png")
        graph += f"{last}[{t}:v]overlay={(W - tw) // 2}:110:format=auto[t0];"
        last, used = "[t0]", True
    if cam:
        round_mask(d, d, out_dir / "bubble_mask.png", radius=d // 2)   # square + full radius = circle
        m = _add(extra, "bubble_mask.png")
        graph += (f"[b]{_crop(cam)},{_cover(d, d)},format=rgba[c0];"
                  f"[{m}:v]format=gray[mk];[c0][mk]alphamerge[cam];"
                  f"{last}[cam]overlay={W - d - 60}:1150:format=auto[t1];")
        last = "[t1]"
    graph += f"{last}ass=captions.ass[v]"
    return graph, extra, 1480, used


def cinematic(game, cam, hook, out_dir, cfg):
    gh, gy = 608, 700                          # 16:9 game panel, its top edge
    cw, ch = 340, 192                          # facecam card
    extra, used = [], False
    graph = _split(["a", "b", "c"] if cam else ["a", "b"])
    graph += f"[a]{_crop(game)},{_cover(W, H)},boxblur=24:3,eq=brightness=-0.15[bg];"
    graph += f"[b]{_crop(game)},{_cover(W, gh)},unsharp=5:5:0.6:5:5:0.0,format=rgba[g0];"
    round_mask(W, gh, out_dir / "game_mask.png", radius=28)
    gm = _add(extra, "game_mask.png")
    graph += f"[{gm}:v]format=gray[gmk];[g0][gmk]alphamerge[gm];[bg][gm]overlay=0:{gy}:format=auto[t0];"
    last = "[t0]"
    if hook:
        tw, th = _title(hook, out_dir, cfg)
        t = _add(extra, "title.png")
        graph += f"{last}[{t}:v]overlay={(W - tw) // 2}:{gy - th - 36}:format=auto[t1];"
        last, used = "[t1]", True
    if cam:
        pad = cam_assets(cw, ch, out_dir)
        cm = _add(extra, "cam_mask.png")
        sh = _add(extra, "shadow.png")
        cx, cy = W - cw - 60, gy + gh + 50
        graph += (f"[c]{_crop(cam)},{_cover(cw, ch)},format=rgba[c0];"
                  f"[{cm}:v]format=gray[cmk];[c0][cmk]alphamerge[cam];"
                  f"{last}[{sh}:v]overlay={cx - pad}:{cy - pad}:format=auto[t2];"
                  f"[t2][cam]overlay={cx}:{cy}:format=auto[t3];")
        last = "[t3]"
    graph += f"{last}ass=captions.ass[v]"
    return graph, extra, 1600 if cam else 1400, used


def stack(game, cam, hook, out_dir, cfg):
    extra, used = [], False
    graph = _split(["a", "b"])
    graph += f"[a]{_crop(cam)},{_cover(W, 560)}[top];"       # facecam panel: a compact strip
    graph += f"[b]{_crop(game)},{_cover(W, 1360)}[bot];"     # gameplay gets the rest of the height
    graph += "[top][bot]vstack=inputs=2[stk];"
    last = "[stk]"
    if hook:
        # centred on the seam between the panels: it covers sky and road, never the face
        tw, th = _title(hook, out_dir, cfg)
        t = _add(extra, "title.png")
        graph += f"{last}[{t}:v]overlay={(W - tw) // 2}:{560 - th // 2}:format=auto[t1];"
        last, used = "[t1]", True
    graph += f"{last}ass=captions.ass[v]"
    return graph, extra, 1480, used


# ---------------------------------------------------------------- punch (bold design)
RED = (220, 30, 30, 255)
YELLOW = (255, 215, 0, 255)
BLACK = (10, 10, 10, 255)
WHITE = (255, 255, 255, 255)


def _split_hook(hook):
    """Title = first part of the hook, subtitle = the rest. Short hooks stay one title."""
    words = (hook or "").split()
    if len(words) < 6:
        return hook, ""
    k = max(3, round(len(words) * 0.45))
    return " ".join(words[:k]), " ".join(words[k:])


def _fit_lines(draw, text, cfg, max_w, size, lines_max=2, min_size=40, step=4):
    from clipper.render.overlay import _font, _wrap
    while True:
        font = _font(size, cfg.get("title_font"))
        lines = _wrap(draw, text, font, max_w)
        if len(lines) <= lines_max or size <= min_size:
            return font, lines, size
        size -= step


def _draw_words(d, line, font, x0, y, yellow_last):
    """Draw one line of words, the last word yellow when yellow_last is set."""
    words = line.split()
    x = x0
    for i, w in enumerate(words):
        color = YELLOW if (yellow_last and i == len(words) - 1) else BLACK
        d.text((x, y), w, font=font, fill=color)
        x += d.textlength(w + " ", font=font)


def _visible(path):
    """Bounding box (left, top, right, bottom) of the non-transparent part of a PNG."""
    from PIL import Image
    with Image.open(path) as im:
        return im.getchannel("A").getbbox()


def _bottom_at(path, x):
    """Lowest opaque row in column x of a PNG (the card's bottom edge at that point)."""
    from PIL import Image
    with Image.open(path) as im:
        alpha = im.getchannel("A")
        x = min(max(x, 0), alpha.size[0] - 1)
        rows = [y for y in range(alpha.size[1]) if alpha.getpixel((x, y)) > 128]
    return rows[-1] if rows else alpha.size[1]


def _tilt(img, deg=3, shear=0.16):
    """Italic slant and a small counter-clockwise tilt, like the reference cards."""
    from PIL import Image
    # work at 2x, then scale back down: smooth edges instead of jagged ones
    img = img.resize((img.size[0] * 2, img.size[1] * 2), Image.LANCZOS)
    w, h = img.size
    m = int(h * shear) + 20                    # transparent margin so the slant never clips the edges
    padded = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
    padded.paste(img, (m, m))
    img = padded
    w, h = img.size
    img = img.transform(img.size, Image.AFFINE, (1, shear, -shear * h / 2, 0, 1, 0), resample=Image.BICUBIC)
    img = img.rotate(deg, resample=Image.BICUBIC, expand=True)
    return img.resize((img.size[0] // 2, img.size[1] // 2), Image.LANCZOS)


def _title_card(text, out_png, cfg, width=960):
    """Bold white card with a thick red border, black uppercase text. Returns (w, h)."""
    from PIL import Image, ImageDraw
    from clipper.render.overlay import _EMOJI
    text = _EMOJI.sub("", text or "").strip().upper().replace("GTA 6", "GTA_6")   # keep "GTA 6" together
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    border, pad_x, pad_y = 10, 34, 18
    # narrower text column so the lines break like the reference (short first line, bigger text)
    if len(text.replace("GTA_6", "GTA 6").split()) <= 4:
        # short title: one big line, no awkward orphan word
        font, lines, size = _fit_lines(probe, text, cfg, width - 2 * (pad_x + border) - 20, 92,
                                       lines_max=1, min_size=56)
    else:
        # narrower text column so longer titles break like the reference
        font, lines, size = _fit_lines(probe, text, cfg, min(width - 2 * (pad_x + border), 800),
                                       cfg.get("punch_title_size", 80))
    line_h = int(size * 1.08)
    h = pad_y * 2 + line_h * len(lines) + 2 * border
    img = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, width - 1, h - 1), radius=30, fill=RED)
    d.rounded_rectangle((border, border, width - 1 - border, h - 1 - border), radius=22, fill=WHITE)
    space = d.textlength(" ", font=font)
    for i, line in enumerate(lines):
        words = line.split()
        shown = [w.replace("GTA_6", "GTA 6") for w in words]          # the game name goes red, as in the reference
        widths = [d.textlength(s, font=font) for s in shown]
        x = (width - (sum(widths) + space * (len(words) - 1))) / 2
        y = border + pad_y + i * line_h
        for w, s, ww in zip(words, shown, widths):
            d.text((x, y), s, font=font, fill=RED if w == "GTA_6" else BLACK)
            x += ww + space
    img = _tilt(img)
    img.save(out_png)
    return img.size


def _subtitle_pill(text, out_png, cfg, width=900):
    """Dark rounded pill with white text; the last word in yellow. Returns (w, h)."""
    from PIL import Image, ImageDraw
    from clipper.render.overlay import _EMOJI, _font, _wrap
    text = _EMOJI.sub("", text or "").strip().upper()
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    pad_x, pad_y = 30, 14
    size = cfg.get("punch_sub_size", 46)
    font = _font(size, cfg.get("title_font"))
    lines = _wrap(probe, text, font, width - 2 * pad_x)
    while len(lines) > 2 and size > 30:
        size -= 3
        font = _font(size, cfg.get("title_font"))
        lines = _wrap(probe, text, font, width - 2 * pad_x)
    line_h = int(size * 1.15)
    h = pad_y * 2 + line_h * len(lines)
    img = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, width - 1, h - 1), radius=26, fill=(12, 12, 12, 235))
    for i, line in enumerate(lines):
        lw = d.textlength(line, font=font)
        x0 = (width - lw) / 2
        last_line = i == len(lines) - 1
        _draw_words_white(d, line, font, x0, pad_y + i * line_h, yellow_last=last_line)
    img = _tilt(img, deg=3)                    # same tilt as the title, so the two edges run parallel
    img.save(out_png)
    return img.size


def _draw_words_white(d, line, font, x0, y, yellow_last):
    words = line.split()
    x = x0
    for i, w in enumerate(words):
        color = YELLOW if (yellow_last and i == len(words) - 1) else WHITE
        d.text((x, y), w, font=font, fill=color)
        x += d.textlength(w + " ", font=font)


def _arrow(out_png):
    """Red curved arrow with a head, pointing down-right."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (90, 100), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    p0, p1, p2 = (14, 10), (14, 70), (68, 84)          # short hook: down, then right into the title's left edge
    pts = []
    for i in range(41):
        t = i / 40
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    d.line(pts, fill=RED, width=11, joint="curve")
    ang = math.atan2(p2[1] - pts[-2][1], p2[0] - pts[-2][0])
    tip = p2
    left = (tip[0] - 24 * math.cos(ang - 0.5), tip[1] - 24 * math.sin(ang - 0.5))
    right = (tip[0] - 24 * math.cos(ang + 0.5), tip[1] - 24 * math.sin(ang + 0.5))
    d.polygon([tip, left, right], fill=RED)
    img.save(out_png)


def punch(game, cam, hook, out_dir, cfg):
    """Big webcam, red-bordered title on the seam with an arrow, a dark subtitle pill, gameplay below."""
    extra, used = [], False
    title_text, sub_text = hook, ""            # no subtitle pill: the whole hook goes in the title card
    graph = _split(["a", "b"])
    graph += f"[a]{_crop(cam)},{_cover(W, 640)}[top];"       # big facecam panel
    graph += f"[b]{_crop(game)},{_cover(W, 1280)}[bot];"     # gameplay below
    graph += "[top][bot]vstack=inputs=2[stk];"
    last = "[stk]"
    if hook:
        tw, th = _title_card(title_text, out_dir / "punch_title.png", cfg)
        t = _add(extra, "punch_title.png")
        ty = 500
        tl, tt, tr, tb = _visible(out_dir / "punch_title.png")   # place by the visible card, not the padded image
        title_x, title_y = (W - (tr - tl)) // 2 - tl, ty - tt
        graph += f"{last}[{t}:v]overlay={title_x}:{title_y}:format=auto[t1];"
        last, used = "[t1]", True
        if sub_text:
            sw, sh = _subtitle_pill(sub_text, out_dir / "punch_sub.png", cfg)
            s = _add(extra, "punch_sub.png")
            sl, st, sr, sb = _visible(out_dir / "punch_sub.png")
            # the title's bottom edge is tilted: measure it under the frame centre, then tuck the pill in 14 px
            bottom_here = _bottom_at(out_dir / "punch_title.png", W // 2 - title_x)
            pill_top = title_y + bottom_here - 14
            graph += f"{last}[{s}:v]overlay={(W - (sr - sl)) // 2 - sl}:{pill_top - st}:format=auto[t3];"
            last = "[t3]"
    graph += f"{last}ass=captions.ass[v]"
    return graph, extra, 1760, used


_BUILDERS = {"bubble": bubble, "cinematic": cinematic, "stack": stack, "minimal": minimal,
             "punch": punch}


def build(name, game, cam, hook, out_dir, cfg):
    """Build the named layout. Layouts that need a facecam fall back to minimal when there is none."""
    if name != "minimal" and cam is None:
        name = "minimal"
    return _BUILDERS[name](game, cam, hook, out_dir, cfg)

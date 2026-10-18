#!/usr/bin/env python3
# Polar CNC — turns the frames that record.py wrote into the help animations, the way WikiTips
# makes its own (sharp, light, 1248 x 750): the 3D view framed on what moves, the toolbar button
# in a card at the top left (shown pressed when the step presses it) and a numbered badge for
# the step. No words in the picture: the popup writes the steps beside it in the reader's
# language and lights the step that is playing (from <name>.json, frame -> step), so one
# animation serves every language.
#
#   python3 tools/help_gifs/compose.py /tmp/frames            # every scene found there
#   python3 tools/help_gifs/compose.py /tmp/frames chuck      # one scene
#
# Writes freecad/help/img/<name>.gif and <name>.json. Needs Pillow (only this tool, not the addon).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import json
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMG = os.path.join(REPO, "freecad", "help", "img")
W, H = 1248, 750             # 3x the 416 x 250 the popup shows at least: sharp up to 300 % screens
K = W / 640.0                # the sizes below are given for 640 wide
BG = (244, 245, 242)
SLATE = (38, 50, 64)
AMBER = (240, 160, 32)
FRAME_MS = 120
HOLD_MS = 1600               # the last frame, before it starts again
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
# scene -> animation file (a toolbar command's, or a field's)
SCENES = {"machine": "machine", "chuck": "chuck", "clamp": "clamp", "polarface": "polarface",
          "polarwrap": "polarwrap", "simulate": "simulate", "pf_clearing": "pf_clearing",
          "pf_ramp": "pf_ramp", "wrap_strategy": "wrap_strategy"}


def px(v):
    return int(round(v * K))


def content_box(images):
    """The part of the view where anything is drawn, over all these frames, with a margin, in
    the shape of the picture."""
    box = None
    for im in images[::3] + images[-1:]:
        bg = im.getpixel((4, 4))
        diff = ImageChops.difference(im, Image.new("RGB", im.size, bg)).convert("L")
        b = diff.point(lambda v: 255 if v > 12 else 0).getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]),
                                         max(box[2], b[2]), max(box[3], b[3]))
    if box is None:
        return (0, 0) + images[0].size
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    w, h = (box[2] - box[0]) * 1.16, (box[3] - box[1]) * 1.16
    if w / h < W / float(H):
        w = h * W / float(H)
    else:
        h = w * H / float(W)
    return (int(cx - w / 2), int(cy - h / 2), int(cx + w / 2), int(cy + h / 2))


def badge(img, step):
    """The step number (a tick for the result) in an amber disc, bottom left."""
    d = ImageDraw.Draw(img)
    r = px(17)
    cx, cy = px(14) + r, H - px(14) - r
    d.ellipse((cx - r - px(3), cy - r - px(3), cx + r + px(3), cy + r + px(3)), fill=(255, 255, 255))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=AMBER)
    if step:
        d.text((cx, cy), str(step), font=ImageFont.truetype(FONT_BOLD, px(20)), fill=SLATE, anchor="mm")
    else:
        d.line((cx - px(8), cy, cx - px(2), cy + px(7), cx + px(9), cy - px(7)), fill=SLATE, width=px(4))


def button_card(img, icon, pressed):
    """The toolbar button, top left; pressed: amber ring, pushed in, and the pointer on it."""
    d = ImageDraw.Draw(img)
    x, y, s = px(12), px(12), px(58)
    off = px(2) if pressed else 0
    d.rounded_rectangle((x + px(3), y + px(4), x + s + px(3), y + s + px(4)), radius=px(10), fill=(214, 217, 212))
    d.rounded_rectangle((x + off, y + off, x + s + off, y + s + off), radius=px(10),
                        fill=(255, 255, 255) if not pressed else (255, 243, 214),
                        outline=AMBER if pressed else (180, 186, 192), width=px(3) if pressed else px(1))
    ic = icon.resize((px(40), px(40)), Image.LANCZOS)
    img.paste(ic, (x + px(9) + off, y + px(9) + off), ic)
    if pressed:
        cx, cy = x + s - px(12), y + s - px(10)
        arrow = [(0, 0), (0, 22), (6, 16), (11, 26), (15, 24), (10, 14), (18, 14)]
        d.polygon([(cx + px(a), cy + px(b)) for a, b in arrow], fill=(255, 255, 255), outline=(20, 20, 20))


def save_gif(frames, durations, path):
    """One palette for the whole animation (from a sample of its frames), no dither: the colours
    stay still from frame to frame and flat CAD shading needs no more."""
    sample = frames[::max(1, len(frames) // 12)] + frames[-1:]
    sheet = Image.new("RGB", (W, H * len(sample)))
    for i, im in enumerate(sample):
        sheet.paste(im, (0, H * i))
    pal = sheet.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=durations, loop=0,
              optimize=True, disposal=1)


def compose(frames_dir, scene):
    src = os.path.join(frames_dir, scene)
    with open(os.path.join(src, "frames.json")) as f:
        meta = json.load(f)["frames"]
    icon_path = os.path.join(src, "icon.png")
    icon = Image.open(icon_path).convert("RGBA") if os.path.isfile(icon_path) else None
    raw = [Image.open(os.path.join(src, "%03d.png" % i)).convert("RGB") for i in range(len(meta))]
    boxes = {}
    for shot in sorted({m.get("shot", 0) for m in meta}):
        boxes[shot] = content_box([im for im, m in zip(raw, meta) if m.get("shot", 0) == shot])
    out, steps = [], []
    for im, m in zip(raw, meta):
        box = boxes[m.get("shot", 0)]
        bg = im.getpixel((4, 4))
        canvas = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), bg)
        canvas.paste(im, (-box[0], -box[1]))
        frame = canvas.resize((W, H), Image.LANCZOS)
        if icon is not None:
            button_card(frame, icon, m["pressed"])
        badge(frame, m["step"])
        out.append(frame)
        steps.append(m["step"])
    # identical frames in a row become one longer frame
    frames, durations, kept = [], [], []
    for frame, step in zip(out, steps):
        if frames and step == kept[-1] and not ImageChops.difference(frame, frames[-1]).getbbox():
            durations[-1] += FRAME_MS
            continue
        frames.append(frame)
        durations.append(FRAME_MS)
        kept.append(step)
    durations[-1] = max(durations[-1], HOLD_MS)
    os.makedirs(IMG, exist_ok=True)
    name = SCENES.get(scene, scene)
    path = os.path.join(IMG, name + ".gif")
    save_gif(frames, durations, path)
    with open(os.path.join(IMG, name + ".json"), "w") as f:
        json.dump({"steps": kept, "ms": durations}, f)
    print("%s  %d frames  %d kB" % (path, len(frames), os.path.getsize(path) // 1024))


def main():
    frames_dir = sys.argv[1]
    scenes = sys.argv[2:] or [s for s in SCENES if os.path.isfile(os.path.join(frames_dir, s, "frames.json"))]
    for scene in scenes:
        compose(frames_dir, scene)


if __name__ == "__main__":
    main()

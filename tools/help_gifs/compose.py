#!/usr/bin/env python3
# Polar CNC — turns the frames that record.py wrote into the help animations, one per language:
# the 3D view framed on what moves, the toolbar button in a card at the top left (shown pressed
# when the step presses it) and a caption with the numbered step from help.json.
#
#   python3 tools/help_gifs/compose.py /tmp/frames            # every scene found there
#   python3 tools/help_gifs/compose.py /tmp/frames chuck      # one scene
#
# Writes freecad/help/img/<lang>/<scene>.gif. Needs Pillow (not the addon: only this tool).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import json
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HELP = os.path.join(REPO, "freecad", "help")
W, H = 576, 360              # shown at 480 x 300 in the popup: still sharp on high-DPI screens
CAPTION_H = 64
BG = (244, 245, 242)
SLATE = (38, 50, 64)
AMBER = (240, 160, 32)
FRAME_MS = 110
COLOURS = 64            # flat shaded CAD: enough, and the files stay small
COMMANDS = {"machine": "PolarCNC_MachineSettings", "chuck": "PolarCNC_Chuck",
            "clamp": "PolarCNC_Clamp", "polarface": "PolarCNC_PolarFace",
            "polarwrap": "PolarCNC_PolarWrap", "simulate": "PolarCNC_Simulate"}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def content_box(paths):
    """The part of the view where anything is drawn, over all frames, with a margin."""
    box = None
    for p in paths[::3] + paths[-1:]:
        im = Image.open(p).convert("RGB")
        diff = ImageChops.difference(im, Image.new("RGB", im.size, BG)).convert("L")
        b = diff.point(lambda v: 255 if v > 12 else 0).getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]),
                                         max(box[2], b[2]), max(box[3], b[3]))
    im = Image.open(paths[0])
    if box is None:
        return (0, 0) + im.size
    # the shape of the space it is shown in, with room round it
    area_w, area_h = W, H - CAPTION_H
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    w, h = (box[2] - box[0]) * 1.18, (box[3] - box[1]) * 1.18
    if w / h < area_w / float(area_h):
        w = h * area_w / float(area_h)
    else:
        h = w * area_h / float(area_w)
    return (int(cx - w / 2), int(cy - h / 2), int(cx + w / 2), int(cy + h / 2))


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        test = (line + " " + word).strip()
        if draw.textlength(test, font=fnt) <= width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def caption(img, number, text):
    """The dark caption at the bottom: an amber badge with the step number (a tick for the
    result) and the text, one or two lines."""
    d = ImageDraw.Draw(img)
    top = H - CAPTION_H + 6
    d.rounded_rectangle((10, top, W - 10, H - 8), radius=14, fill=SLATE)
    cx, cy = 40, (top + H - 8) // 2
    d.ellipse((cx - 15, cy - 15, cx + 15, cy + 15), fill=AMBER)
    if number:
        d.text((cx, cy), str(number), font=font(18, True), fill=SLATE, anchor="mm")
    else:
        d.line((cx - 7, cy, cx - 2, cy + 6, cx + 8, cy - 6), fill=SLATE, width=4)
    fnt = font(16)
    lines = wrap(d, text, fnt, W - 90)
    if len(lines) > 2:
        fnt = font(14)
        lines = wrap(d, text, fnt, W - 90)[:2]
    y = cy - (len(lines) * 20) // 2 + 1
    for line in lines:
        d.text((66, y), line, font=fnt, fill=(255, 255, 255))
        y += 20


def button_card(img, icon, pressed):
    """The toolbar button, top left; pressed: amber ring, pushed in, and the pointer on it."""
    d = ImageDraw.Draw(img)
    x, y, s = 12, 12, 58
    off = 2 if pressed else 0
    d.rounded_rectangle((x + 3, y + 4, x + s + 3, y + s + 4), radius=10, fill=(214, 217, 212))
    d.rounded_rectangle((x + off, y + off, x + s + off, y + s + off), radius=10,
                        fill=(255, 255, 255) if not pressed else (255, 243, 214),
                        outline=AMBER if pressed else (180, 186, 192), width=3 if pressed else 1)
    ic = icon.resize((40, 40), Image.LANCZOS)
    img.paste(ic, (x + 9 + off, y + 9 + off), ic)
    if pressed:
        px, py = x + s - 12, y + s - 10
        arrow = [(px, py), (px, py + 22), (px + 6, py + 16), (px + 11, py + 26), (px + 15, py + 24),
                 (px + 10, py + 14), (px + 18, py + 14)]
        d.polygon(arrow, fill=(255, 255, 255), outline=(20, 20, 20))


def compose(frames_dir, scene):
    with open(os.path.join(frames_dir, scene, "frames.json")) as f:
        frames = json.load(f)["frames"]
    paths = [os.path.join(frames_dir, scene, "%03d.png" % i) for i in range(len(frames))]
    boxes = {}
    for shot in sorted({m.get("shot", 0) for m in frames}):
        boxes[shot] = content_box([p for p, m in zip(paths, frames) if m.get("shot", 0) == shot])
    icon = Image.open(os.path.join(frames_dir, scene, "icon.png")).convert("RGBA")
    with open(os.path.join(HELP, "help.json"), encoding="utf-8") as f:
        entry = json.load(f)["commands"][COMMANDS[scene]]
    views = []
    for p, meta in zip(paths, frames):
        box = boxes[meta.get("shot", 0)]
        im = Image.open(p).convert("RGB")
        canvas = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), im.getpixel((4, 4)))
        canvas.paste(im, (-box[0], -box[1]))
        views.append(canvas.resize((W, H - CAPTION_H), Image.LANCZOS))
    for lang in ("el", "en"):
        text = entry[lang]
        out = []
        for view, meta in zip(views, frames):
            img = Image.new("RGB", (W, H), view.getpixel((2, 2)))
            img.paste(view, (0, 0))
            button_card(img, icon, meta["pressed"])
            step = meta["step"]
            caption(img, step, text["steps"][step - 1] if step else text.get("r", ""))
            out.append(img.quantize(colors=COLOURS, method=Image.MEDIANCUT, dither=Image.NONE))
        os.makedirs(os.path.join(HELP, "img", lang), exist_ok=True)
        path = os.path.join(HELP, "img", lang, entry["i"])
        durations = [FRAME_MS] * len(out)
        durations[-1] = 1800                     # a pause on the result before it starts again
        out[0].save(path, save_all=True, append_images=out[1:], duration=durations, loop=0,
                    optimize=True, disposal=1)
        print("%s  %d frames  %d kB" % (path, len(out), os.path.getsize(path) // 1024))


def main():
    frames_dir = sys.argv[1]
    scenes = sys.argv[2:] or [s for s in COMMANDS if os.path.isfile(os.path.join(frames_dir, s, "frames.json"))]
    for scene in scenes:
        compose(frames_dir, scene)


if __name__ == "__main__":
    main()

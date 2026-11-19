"""Render the profile artwork with Pillow. Optional arguments give the display and mono font paths."""

from math import dist, pi, sin
from pathlib import Path
from random import Random
import os
import sys

from PIL import Image, ImageColor, ImageDraw, ImageFont


ASSETS = Path(__file__).resolve().parents[1] / "assets"
FONTS = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
DISPLAY, MONO = sys.argv[1:] or (FONTS / "bahnschrift.ttf", FONTS / "consola.ttf")
INK = "#060d18"
WHITE = "#e8f7ff"
MUTED = "#a0b6cc"
CYAN = "#66f5ec"
BLUE = "#84a7ff"


def font(size, family=MONO):
    face = ImageFont.truetype(family, size)
    if family == DISPLAY:
        try:
            axes = face.get_variation_axes()
        except OSError:
            return face
        face.set_variation_by_axes([
            axis["maximum"] if axis["name"] == b"Weight" else axis["default"] for axis in axes
        ])
    return face


def label(draw, xy, value, size=22, color=MUTED, family=MONO, anchor="lt"):
    draw.text(xy, value, fill=color, font=font(size, family), anchor=anchor)


def background(size, center, color=(8, 28, 50)):
    width, height = size
    base = ImageColor.getrgb(INK)
    image = Image.new("RGB", size)
    image.putdata([
        tuple(round(a + (b - a) * max(0, 1 - ((x - center) / width * 1.6) ** 2 - ((y - height / 2) / height) ** 2)) for a, b in zip(base, color))
        for y in range(height) for x in range(width)
    ])
    return image


def node(draw, xy, radius, color, open_center=False):
    x, y = xy
    bounds = (x - radius, y - radius, x + radius, y + radius)
    draw.ellipse(bounds, outline=color, width=1, fill=INK if open_center else color)


def route_point(route, progress):
    lengths = [dist(a, b) for a, b in zip(route, route[1:])]
    remaining = sum(lengths) * (progress % 1)
    for (x, y), (nx, ny), length in zip(route, route[1:], lengths):
        if remaining < length:
            step = remaining / length
            return round(x + (nx - x) * step), round(y + (ny - y) * step)
        remaining -= length
    return route[-1]


def pulse(draw, route, progress, color=CYAN):
    if not 0.035 < progress % 1 < 0.965:
        return
    tail = [route_point(route, progress - offset * 0.004) for offset in range(8, -1, -1)]
    draw.line(tail, fill="#21798b", width=3)
    draw.line(tail[-5:], fill=color, width=2)
    node(draw, tail[-1], 3, color)
    node(draw, tail[-1], 1, WHITE)


def save_loop(path, frames, duration):
    # One palette keeps fixed elements from shifting color between frames.
    sample = Image.new("RGB", (frames[0].width, frames[0].height * 4))
    for row in range(4):
        sample.paste(frames[row * len(frames) // 4], (0, row * frames[0].height))
    palette = sample.quantize(colors=128)
    indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    indexed[0].save(path, save_all=True, append_images=indexed[1:], duration=duration, loop=0, optimize=True)
    with Image.open(path) as output:
        assert output.is_animated and output.size == frames[0].size, path


def hero():
    base = background((1200, 400), 911)
    draw = ImageDraw.Draw(base)
    rng = Random(41)
    for _ in range(180):
        x, y = rng.randrange(24, 1176), rng.randrange(22, 377)
        draw.point((x, y), fill=rng.choice(("#1b344b", "#274256", "#183347")))

    center = (900, 196)
    cx, cy = center
    for radius in (49, 78, 116, 162, 205):
        ring = (cx - radius, cy - radius, cx + radius, cy + radius)
        draw.arc(ring, 0, 360, fill="#173346")
        draw.arc(ring, 205, 272, fill="#27576a")
        draw.arc(ring, 14, 87, fill="#244762")
    for x in range(612, 1137, 16):
        draw.point((x, cy), fill="#2a4b66")
    for y in range(28, 373, 16):
        draw.point((cx, y), fill="#2a4b66")
    net = [
        [(557, 85), (653, 85), (731, 163), (811, 163), (850, 202), (900, 202), (970, 132), (1150, 132)],
        [(642, 321), (740, 321), (820, 241), (869, 241), (914, 196), (994, 196), (1063, 265), (1161, 265)],
        [(724, 36), (793, 105), (899, 105), (931, 137), (931, 173), (1008, 250), (1008, 283), (1081, 356)],
        [(601, 270), (700, 270), (773, 197), (853, 197), (910, 254), (967, 254), (1013, 300), (1125, 300)],
        [(690, 128), (743, 128), (793, 78), (982, 78), (1023, 119), (1023, 185), (1106, 268)],
        [(762, 369), (821, 308), (910, 308), (941, 277), (941, 230), (992, 179), (1117, 179)],
        [(866, 37), (925, 37), (956, 68), (1033, 68), (1092, 127), (1092, 193), (1143, 244)],
        [(626, 208), (702, 208), (742, 248), (780, 248), (850, 318), (967, 318), (1021, 372)],
    ]
    for index, path in enumerate(net):
        draw.line(path, fill=("#225066", "#244569", "#2c6473")[index % 3], width=2, joint="curve")
        for j, xy in enumerate(path):
            if j % 2 == 0 or j == len(path) - 1:
                node(draw, xy, 4 if j in (0, len(path) - 1) else 2, "#46879b", open_center=True)
    draw.regular_polygon((cx, cy, 29), 6, rotation=30, fill="#0a2639", outline="#508eaa")
    draw.regular_polygon((cx, cy, 18), 6, rotation=30, outline=CYAN)
    draw.line((cx - 7, cy, cx + 7, cy), fill=CYAN, width=2)
    draw.line((cx, cy - 7, cx, cy + 7), fill=CYAN, width=2)

    # Recess the routes behind the wordmark without cutting them off abruptly.
    veil = Image.new("RGB", base.size, INK)
    ramp = Image.linear_gradient("L").rotate(270, expand=True).resize(base.size)
    veil_mask = ramp.point(lambda value: max(0, min(235, (value - 97) * 4)))
    base = Image.composite(veil, base, veil_mask)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((8, 8, 1191, 391), radius=18, outline="#234053", width=1)
    draw.line(((61, 103), (61, 78), (96, 78)), fill="#36818b", width=2)
    draw.line(((1098, 326), (1139, 326), (1139, 300)), fill="#36818b", width=2)
    draw.line((72, 314, 530, 314), fill="#233f51", width=1)
    draw.line((72, 314, 131, 314), fill=CYAN, width=2)
    label(draw, (73, 102), "Network engineering", 26, CYAN)
    label(draw, (75, 271), "VPN protocols / Open source", 29, MUTED)

    frames = []
    for frame_index in range(64):
        phase = frame_index / 64
        frame = base.copy()
        draw = ImageDraw.Draw(frame)
        for index, route in enumerate(net):
            pulse(draw, route, phase + index * 0.173, BLUE if index % 3 == 2 else CYAN)
        intensity = sin(pi * phase) ** 2
        label(draw, (62, 144), "FLOXU1", 150, (190 + int(42 * intensity), 218 + int(29 * intensity), 231 + int(24 * intensity)), DISPLAY)
        frames.append(frame)
    frames[32].save(ASSETS / "banner-static.png", optimize=True)
    save_loop(ASSETS / "banner.gif", frames, 80)


def terminal():
    base = Image.new("RGB", (704, 68), INK)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((0, 0, 703, 67), radius=10, outline="#274358")
    label(draw, (21, 18), "$", 37, CYAN)
    route = [(405, 37), (472, 37), (491, 24), (575, 24), (594, 37), (676, 37)]
    draw.line(route, fill="#2c5369", width=2)
    for point in (route[0], route[3], route[-1]):
        node(draw, point, 4, "#56899d", open_center=True)
    command = "trace route"
    clear = ImageColor.getrgb(INK)
    ink = ImageColor.getrgb(WHITE)
    face = font(37)
    frames = []
    for i in range(56):
        frame = base.copy()
        draw = ImageDraw.Draw(frame)
        typed = command[:max(0, i - 3)]
        opacity = sin(pi / 2 * min(1, (55 - i) / 6)) ** 2
        if typed:
            color = tuple(round(a + (b - a) * opacity) for a, b in zip(clear, ink))
            draw.text((55, 18), typed, fill=color, font=face, anchor="lt")
        cursor_x = 58 + round(face.getlength(typed) * opacity)
        draw.rectangle((cursor_x, 19, cursor_x + 3, 49), fill=CYAN)
        if 14 < i < 46:
            pulse(draw, route, (i - 14) / 32)
        frames.append(frame)
    frames[36].save(ASSETS / "terminal-static.png", optimize=True)
    save_loop(ASSETS / "terminal.gif", frames, 90)


def projects():
    directory = ASSETS / "projects"
    directory.mkdir(parents=True, exist_ok=True)
    diagrams = {
        "android": ("Android", "Device tunnel", CYAN, ("VpnService", "TUN", "Xray / Tor")),
        "windows": ("Windows", "Desktop routing", BLUE, ("Desktop", "Rules", "Proxy / TUN")),
        "gateway": ("Gateway", "VPN sharing", CYAN, ("VPN", "Windows", "LAN")),
        "android-tv": ("Android TV", "Remote-first client", BLUE, ("Phone", "QR / Web", "TV")),
    }
    for index, (slug, (title, subtitle, accent, ports)) in enumerate(diagrams.items()):
        height = 156 if index < 2 else 112
        middle = height // 2
        base = background((936, height), 641)
        draw = ImageDraw.Draw(base)
        draw.rounded_rectangle((0, 0, 935, height - 1), radius=12, outline="#244054", width=2)
        draw.line((28, 24, 28, height - 24), fill=accent, width=3)
        label(draw, (54, 25 if index < 2 else 19), title, 63 if index < 2 else 50, WHITE, DISPLAY)
        label(draw, (57, 98 if index < 2 else 75), subtitle, 32 if index < 2 else 26, accent)
        left, hub, right = 442, 608, 792
        for x in range(370, 912, 17):
            for y in range(19, height - 11, 17):
                draw.point((x, y), fill="#204859")
        path = [(left, middle), (left + 80, middle), (left + 103, middle - 21),
                (hub + 30, middle - 21), (hub + 53, middle), (right, middle)]
        draw.line(path, fill="#397181", width=2)
        if index == 0:
            draw.rounded_rectangle((390, 34, 426, 92), radius=7, outline=accent, width=2)
            draw.line((402, 84, 415, 84), fill=accent, width=2)
            draw.arc((563, 40, 654, 133), 15, 340, fill="#376e80", width=2)
        elif index == 1:
            draw.rectangle((373, 42, 423, 77), outline=accent, width=2)
            draw.line((398, 77, 398, 89), fill=accent, width=2)
            draw.line((389, 89, 408, 89), fill=accent, width=2)
            draw.line(((hub, middle - 21), (hub, 33), (799, 33)), fill="#3a5884", width=2)
            draw.line(((hub + 30, middle - 21), (hub + 57, middle + 3), (hub + 57, 133), (769, 133)),
                      fill="#3a5884", width=2)
        elif index == 2:
            for y in (24, height - 10):
                draw.line(((680, middle), (713, y), (858, y)), fill="#3a6275", width=2)
                node(draw, (858, y), 4, accent, open_center=True)
        else:
            for offset in (0, 12, 24):
                draw.arc((565 + offset, 13 + offset, 651 - offset, 72 - offset), 206, 334, fill="#668ac0", width=2)
            draw.rectangle((812, 27, 858, 59), outline=accent, width=2)
            draw.line((822, 66, 847, 66), fill=accent, width=2)
        for x, y, port in zip((left, hub, right), (middle, middle - 21, middle), ports):
            node(draw, (x, y), 6, accent, open_center=True)
            label(draw, (x, middle + 20), port, 35 if index < 2 else 31, "#c2d5e9", anchor="mt")
        base.quantize().save(directory / f"{slug}.png", optimize=True)
        if index < 2:
            frames = []
            for step in range(40):
                frame = base.copy()
                pulse(ImageDraw.Draw(frame), path, step / 40, accent)
                frames.append(frame)
            save_loop(directory / f"{slug}.gif", frames, 110)


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    hero()
    terminal()
    projects()

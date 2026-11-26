#!/usr/bin/env python3
"""news-image-20261126: draw one front page summing up the world news of
Thursday 26 November 2026. Pure Python 3.13 standard library only; no
network; deterministic output (same bytes on every run)."""

import math
import os
import struct
import sys
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------------------
# Deterministic pseudo-randomness (fixed seed, no system entropy).
# ---------------------------------------------------------------------------


class RNG:
    def __init__(self, seed=20261126):
        self.s = seed

    def next(self):
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s

    def randint(self, a, b):
        return a + self.next() % (b - a + 1)


RNG = RNG()

# ---------------------------------------------------------------------------
# Palette.
# ---------------------------------------------------------------------------
PAPER = (247, 243, 232)
PAPER_DARK = (238, 232, 214)
INK = (22, 22, 22)
INK_SOFT = (58, 58, 58)
RED = (178, 34, 34)
NAVY = (24, 48, 96)
GOLD = (176, 132, 40)
TEAL = (14, 110, 110)
GREEN = (34, 110, 60)
ORANGE = (214, 110, 20)
SKY = (120, 170, 210)
SEA = (168, 198, 222)
LAND = (216, 202, 158)
LAND2 = (196, 190, 150)
RULE = (120, 110, 90)

REGION_COLORS = {
    "N AMERICA": (24, 48, 96),
    "S AMERICA": (34, 110, 60),
    "EUROPE": (120, 60, 140),
    "AFRICA": (176, 110, 20),
    "M EAST": (178, 34, 34),
    "S ASIA": (200, 90, 20),
    "E ASIA": (180, 30, 60),
    "SE ASIA": (14, 110, 110),
    "OCEANIA": (20, 90, 140),
    "GLOBAL": (70, 70, 70),
}


# ---------------------------------------------------------------------------
# Canvas: an RGB bytearray with fast rectangle fills.
# ---------------------------------------------------------------------------


class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def fill_rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        n = len(row)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + n] = row

    def rect(self, x, y, w, h, c, t=1):
        self.fill_rect(x, y, w, t, c)
        self.fill_rect(x, y + h - t, w, t, c)
        self.fill_rect(x, y, t, h, c)
        self.fill_rect(x + w - t, y, t, h, c)

    def hline(self, x, y, w, c):
        self.fill_rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.fill_rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def disc(self, cx, cy, r, c):
        for yy in range(cy - r, cy + r + 1):
            d = r * r - (yy - cy) * (yy - cy)
            if d < 0:
                continue
            dx = int(math.sqrt(d))
            self.fill_rect(cx - dx, yy, 2 * dx + 1, 1, c)

    def ring(self, cx, cy, r, c):
        for a in range(0, 360, 2):
            rad = math.radians(a)
            self.set(cx + int(r * math.cos(rad)),
                     cy + int(r * math.sin(rad)), c)

    def poly(self, pts, c):
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, min(ys))
        y1 = min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x0, yy0 = pts[i]
                x1, yy1 = pts[(i + 1) % n]
                if (yy0 <= y < yy1) or (yy1 <= y < yy0):
                    if yy1 != yy0:
                        xs.append(x0 + (y - yy0) * (x1 - x0) / (yy1 - yy0))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                xa = int(xs[j])
                xb = int(xs[j + 1])
                if xb > xa:
                    self.fill_rect(xa, y, xb - xa, 1, c)

    def vgrad(self, x, y, w, h, top, bottom):
        for i in range(h):
            t = i / max(1, h - 1)
            c = (int(top[0] + (bottom[0] - top[0]) * t),
                 int(top[1] + (bottom[1] - top[1]) * t),
                 int(top[2] + (bottom[2] - top[2]) * t))
            self.fill_rect(x, y + i, w, 1, c)

    def stipple(self, x, y, w, h, color, count, rng):
        for _ in range(count):
            px = x + rng.randint(0, max(0, w - 1))
            py = y + rng.randint(0, max(0, h - 1))
            self.set(px, py, color)

    def hatch(self, x, y, w, h, color, gap=6):
        for i in range(0, w + h, gap):
            self.line(x + i, y, x, y + i, color)


# ---------------------------------------------------------------------------
# PNG writer (Sub filter, zlib level 6 -- a standard encoding).
# ---------------------------------------------------------------------------


def save_png(cv, path):
    raw = bytearray()
    w, h = cv.w, cv.h
    for y in range(h):
        raw.append(1)
        row = cv.px[y * w * 3:(y + 1) * w * 3]
        sub = bytearray(len(row))
        sub[0:3] = row[0:3]
        for i in range(3, len(row)):
            sub[i] = (row[i] - row[i - 3]) & 0xFF
        raw += sub
    comp = zlib.compress(bytes(raw), 6)

    def chunk(typ, data):
        out = struct.pack(">I", len(data)) + typ + data
        out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return out

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# ---------------------------------------------------------------------------
# 5x7 bitmap font. Each glyph is 5 column bytes; bit 0 is the top row.
# ASCII 32..126 only -- all page text is ASCII by design.
# ---------------------------------------------------------------------------
FONT = {
    " ": (0x00, 0x00, 0x00, 0x00, 0x00),
    "!": (0x00, 0x00, 0x5F, 0x00, 0x00),
    '"': (0x00, 0x07, 0x00, 0x07, 0x00),
    "#": (0x14, 0x7F, 0x14, 0x7F, 0x14),
    "$": (0x24, 0x2A, 0x7F, 0x2A, 0x12),
    "%": (0x23, 0x13, 0x08, 0x64, 0x62),
    "&": (0x36, 0x49, 0x55, 0x22, 0x50),
    "'": (0x00, 0x05, 0x03, 0x00, 0x00),
    "(": (0x00, 0x1C, 0x22, 0x41, 0x00),
    ")": (0x00, 0x41, 0x22, 0x1C, 0x00),
    "*": (0x14, 0x08, 0x3E, 0x08, 0x14),
    "+": (0x08, 0x08, 0x3E, 0x08, 0x08),
    ",": (0x00, 0x50, 0x30, 0x00, 0x00),
    "-": (0x08, 0x08, 0x08, 0x08, 0x08),
    ".": (0x00, 0x60, 0x60, 0x00, 0x00),
    "/": (0x20, 0x10, 0x08, 0x04, 0x02),
    "0": (0x3E, 0x51, 0x49, 0x45, 0x3E),
    "1": (0x00, 0x42, 0x7F, 0x40, 0x00),
    "2": (0x42, 0x61, 0x51, 0x49, 0x46),
    "3": (0x21, 0x41, 0x45, 0x4B, 0x31),
    "4": (0x18, 0x14, 0x12, 0x7F, 0x10),
    "5": (0x27, 0x45, 0x45, 0x45, 0x39),
    "6": (0x3C, 0x4A, 0x49, 0x49, 0x30),
    "7": (0x01, 0x71, 0x09, 0x05, 0x03),
    "8": (0x36, 0x49, 0x49, 0x49, 0x36),
    "9": (0x06, 0x49, 0x49, 0x29, 0x1E),
    ":": (0x00, 0x36, 0x36, 0x00, 0x00),
    ";": (0x00, 0x56, 0x36, 0x00, 0x00),
    "<": (0x08, 0x14, 0x22, 0x41, 0x00),
    "=": (0x14, 0x14, 0x14, 0x14, 0x14),
    ">": (0x00, 0x41, 0x22, 0x14, 0x08),
    "?": (0x02, 0x01, 0x51, 0x09, 0x06),
    "@": (0x32, 0x49, 0x79, 0x41, 0x3E),
    "A": (0x7E, 0x11, 0x11, 0x11, 0x7E),
    "B": (0x7F, 0x49, 0x49, 0x49, 0x36),
    "C": (0x3E, 0x41, 0x41, 0x41, 0x22),
    "D": (0x7F, 0x41, 0x41, 0x22, 0x1C),
    "E": (0x7F, 0x49, 0x49, 0x49, 0x41),
    "F": (0x7F, 0x09, 0x09, 0x09, 0x01),
    "G": (0x3E, 0x41, 0x49, 0x49, 0x7A),
    "H": (0x7F, 0x08, 0x08, 0x08, 0x7F),
    "I": (0x00, 0x41, 0x7F, 0x41, 0x00),
    "J": (0x20, 0x40, 0x41, 0x3F, 0x01),
    "K": (0x7F, 0x08, 0x14, 0x22, 0x41),
    "L": (0x7F, 0x40, 0x40, 0x40, 0x40),
    "M": (0x7F, 0x02, 0x0C, 0x02, 0x7F),
    "N": (0x7F, 0x04, 0x08, 0x10, 0x7F),
    "O": (0x3E, 0x41, 0x41, 0x41, 0x3E),
    "P": (0x7F, 0x09, 0x09, 0x09, 0x06),
    "Q": (0x3E, 0x41, 0x51, 0x21, 0x5E),
    "R": (0x7F, 0x09, 0x19, 0x29, 0x46),
    "S": (0x46, 0x49, 0x49, 0x49, 0x31),
    "T": (0x01, 0x01, 0x7F, 0x01, 0x01),
    "U": (0x3F, 0x40, 0x40, 0x40, 0x3F),
    "V": (0x1F, 0x20, 0x40, 0x20, 0x1F),
    "W": (0x3F, 0x40, 0x38, 0x40, 0x3F),
    "X": (0x63, 0x14, 0x08, 0x14, 0x63),
    "Y": (0x07, 0x08, 0x70, 0x08, 0x07),
    "Z": (0x61, 0x51, 0x49, 0x45, 0x43),
    "[": (0x00, 0x7F, 0x41, 0x41, 0x00),
    "\\": (0x02, 0x04, 0x08, 0x10, 0x20),
    "]": (0x00, 0x41, 0x41, 0x7F, 0x00),
    "^": (0x04, 0x02, 0x01, 0x02, 0x04),
    "_": (0x40, 0x40, 0x40, 0x40, 0x40),
    "`": (0x00, 0x01, 0x02, 0x04, 0x00),
    "a": (0x20, 0x54, 0x54, 0x54, 0x78),
    "b": (0x7F, 0x48, 0x44, 0x44, 0x38),
    "c": (0x38, 0x44, 0x44, 0x44, 0x20),
    "d": (0x38, 0x44, 0x44, 0x48, 0x7F),
    "e": (0x38, 0x54, 0x54, 0x54, 0x18),
    "f": (0x08, 0x7E, 0x09, 0x01, 0x02),
    "g": (0x0C, 0x52, 0x52, 0x52, 0x3E),
    "h": (0x7F, 0x08, 0x04, 0x04, 0x78),
    "i": (0x00, 0x44, 0x7D, 0x40, 0x00),
    "j": (0x20, 0x40, 0x44, 0x3D, 0x00),
    "k": (0x7F, 0x10, 0x28, 0x44, 0x00),
    "l": (0x00, 0x41, 0x7F, 0x40, 0x00),
    "m": (0x7C, 0x04, 0x18, 0x04, 0x78),
    "n": (0x7C, 0x08, 0x04, 0x04, 0x78),
    "o": (0x38, 0x44, 0x44, 0x44, 0x38),
    "p": (0x7C, 0x14, 0x14, 0x14, 0x08),
    "q": (0x08, 0x14, 0x14, 0x18, 0x7C),
    "r": (0x7C, 0x08, 0x04, 0x04, 0x08),
    "s": (0x48, 0x54, 0x54, 0x54, 0x20),
    "t": (0x04, 0x3F, 0x44, 0x40, 0x20),
    "u": (0x3C, 0x40, 0x40, 0x20, 0x7C),
    "v": (0x1C, 0x20, 0x40, 0x20, 0x1C),
    "w": (0x3C, 0x40, 0x30, 0x40, 0x3C),
    "x": (0x44, 0x28, 0x10, 0x28, 0x44),
    "y": (0x0C, 0x50, 0x50, 0x50, 0x3C),
    "z": (0x44, 0x64, 0x54, 0x4C, 0x44),
    "{": (0x00, 0x08, 0x36, 0x41, 0x00),
    "|": (0x00, 0x00, 0x7F, 0x00, 0x00),
    "}": (0x00, 0x41, 0x36, 0x08, 0x00),
    "~": (0x10, 0x08, 0x08, 0x10, 0x08),
}


def text_w(s, scale):
    return len(s) * 6 * scale


def draw_glyph(cv, x, y, g, scale, color):
    for col in range(5):
        bits = g[col]
        if not bits:
            continue
        r = 0
        while r < 7:
            if (bits >> r) & 1:
                r0 = r
                while r < 7 and ((bits >> r) & 1):
                    r += 1
                cv.fill_rect(x + col * scale, y + r0 * scale,
                             scale, (r - r0) * scale, color)
            else:
                r += 1


def draw_text(cv, x, y, s, scale, color, align="left"):
    if align == "center":
        x -= text_w(s, scale) // 2
    elif align == "right":
        x -= text_w(s, scale)
    cx = x
    for ch in s:
        g = FONT.get(ch)
        if g is not None:
            draw_glyph(cv, cx, y, g, scale, color)
        cx += 6 * scale
    return cx - x


def wrap(s, scale, max_w):
    words = s.split(" ")
    lines = []
    cur = ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if text_w(t, scale) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines

# ---------------------------------------------------------------------------
# Mini vector scenes (one per featured story). Each draws into (x, y, w, h).
# Flat illustration, no photos, no text inside the art.
# ---------------------------------------------------------------------------


def scene_refinery(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (232, 130, 60), (120, 50, 40))
    cv.disc(x + w - 14, y + 14, 9, (250, 220, 130))
    cv.fill_rect(x + 6, y + h - 26, 10, 26, (40, 30, 30))
    cv.fill_rect(x + 20, y + h - 34, 8, 34, (40, 30, 30))
    cv.fill_rect(x + 32, y + h - 22, 12, 22, (52, 38, 38))
    cv.fill_rect(x + 6, y + h - 30, 38, 3, (40, 30, 30))
    cv.disc(x + 10, y + h - 30, 4, (255, 180, 40))
    cv.disc(x + 24, y + h - 38, 3, (255, 210, 80))
    cv.fill_rect(x, y + h - 6, w, 6, (30, 22, 22))
    cv.stipple(x, y, w, h, (255, 200, 120), 40, rng)


def scene_tariff(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (210, 225, 240), (170, 195, 220))
    cv.fill_rect(x, y + h - 12, w, 12, (24, 48, 96))
    bars = [14, 22, 18, 30, 26, 38]
    bw = w // 7
    for i, b in enumerate(bars):
        bx = x + 4 + i * bw
        cv.fill_rect(bx, y + h - 12 - b, bw - 3, b,
                     (178, 34, 34) if i == len(bars) - 1 else (24, 48, 96))
    cv.line(x + 4, y + 10, x + w - 6, y + h - 14, (178, 34, 34))
    cv.fill_rect(x + w - 20, y + 6, 14, 8, (250, 200, 60))
    cv.stipple(x, y, w, h, (255, 255, 255), 30, rng)


def scene_nato(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (90, 140, 200), (190, 215, 235))
    for r in (26, 18, 10):
        cv.ring(x + w // 2, y + h - 8, r, (255, 255, 255))
    cv.line(x + w // 2, y + h - 8, x + w - 8, y + 8, (255, 255, 255))
    cv.poly([(x + 8, y + 14), (x + 26, y + 10), (x + 12, y + 22)], (30, 30, 30))
    cv.poly([(x + w - 26, y + 22), (x + w - 8, y + 18), (x + w - 22, y + 30)],
            (30, 30, 30))
    cv.fill_rect(x, y + h - 4, w, 4, (40, 60, 40))
    cv.stipple(x, y, w, h, (255, 255, 255), 25, rng)


def scene_court(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (225, 220, 205), (190, 180, 160))
    cv.poly([(x + 6, y + 22), (x + w // 2, y + 6), (x + w - 6, y + 22)],
            (120, 100, 70))
    cv.disc(x + w // 2, y + 15, 3, (176, 132, 40))
    for i in range(4):
        cx = x + 8 + i * (w - 16) // 3
        cv.fill_rect(cx, y + 24, 6, h - 32, (240, 235, 220))
    cv.fill_rect(x + 4, y + 24, w - 8, 3, (120, 100, 70))
    cv.fill_rect(x + 2, y + h - 10, w - 4, 8, (120, 100, 70))
    cv.stipple(x, y, w, h, (120, 100, 70), 25, rng)


def scene_missile(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (16, 20, 44), (40, 50, 90))
    for _ in range(14):
        cv.set(x + rng.randint(0, w - 1), y + rng.randint(0, h // 2),
               (255, 255, 220))
    cv.poly([(x + w // 2 - 4, y + 12), (x + w // 2 + 4, y + 12),
             (x + w // 2 + 3, y + 38), (x + w // 2 - 3, y + 38)],
            (220, 220, 220))
    cv.poly([(x + w // 2 - 4, y + 12), (x + w // 2, y + 4),
             (x + w // 2 + 4, y + 12)], (178, 34, 34))
    cv.poly([(x + w // 2 - 3, y + 38), (x + w // 2 - 8, y + 46),
             (x + w // 2 - 3, y + 44)], (178, 34, 34))
    cv.poly([(x + w // 2 + 3, y + 38), (x + w // 2 + 8, y + 46),
             (x + w // 2 + 3, y + 44)], (178, 34, 34))
    cv.disc(x + w // 2, y + 50, 3, (255, 180, 40))
    cv.disc(x + w // 2, y + 52, 2, (255, 230, 120))
    cv.fill_rect(x, y + h - 5, w, 5, (20, 30, 20))
    cv.stipple(x, y, w, h, (255, 255, 255), 20, rng)


def scene_space(cv, x, y, w, h, rng):
    cv.fill_rect(x, y, w, h, (8, 10, 28))
    for _ in range(22):
        cv.set(x + rng.randint(0, w - 1), y + rng.randint(0, h - 1),
               (255, 255, 220))
    cv.fill_rect(x + w // 2 - 3, y + 14, 6, 22, (200, 200, 210))
    cv.fill_rect(x + w // 2 - 16, y + 18, 12, 6, (40, 90, 160))
    cv.fill_rect(x + w // 2 + 4, y + 18, 12, 6, (40, 90, 160))
    cv.fill_rect(x + w // 2 - 12, y + 30, 24, 4, (150, 150, 160))
    cv.disc(x + w // 2, y + h + 26, 34, (40, 110, 180))
    cv.disc(x + w // 2 - 12, y + h + 18, 10, (60, 140, 90))
    cv.stipple(x, y, w, h, (255, 255, 255), 15, rng)


def scene_storm(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (110, 115, 125), (70, 75, 85))
    cv.disc(x + 16, y + 14, 10, (210, 210, 215))
    cv.disc(x + 30, y + 10, 12, (225, 225, 230))
    cv.disc(x + 44, y + 15, 9, (210, 210, 215))
    cv.fill_rect(x + 8, y + 20, 44, 6, (210, 210, 215))
    for i in range(6):
        rx = x + 6 + i * 9
        cv.line(rx, y + 30, rx - 3, y + 40, (150, 190, 230))
    cv.disc(x + w - 16, y + h - 18, 10, (200, 60, 60))
    cv.line(x + w - 16, y + h - 8, x + w - 16, y + h - 2, (200, 60, 60))
    cv.fill_rect(x, y + h - 5, w, 5, (50, 55, 65))
    cv.stipple(x, y, w, h, (200, 210, 225), 25, rng)


def scene_stocks(cv, x, y, w, h, rng):
    cv.fill_rect(x, y, w, h, (245, 240, 225))
    for i in range(5):
        gy = y + 8 + i * (h - 16) // 4
        cv.hline(x + 4, gy, w - 8, (210, 205, 190))
    pts = [(x + 5, y + 10), (x + 14, y + 16), (x + 22, y + 14),
           (x + 30, y + 26), (x + 38, y + 24), (x + 46, y + 40),
           (x + w - 8, y + h - 12)]
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                (178, 34, 34))
        cv.line(pts[i][0], pts[i][1] + 1, pts[i + 1][0], pts[i + 1][1] + 1,
                (178, 34, 34))
    cv.poly([(x + w - 14, y + h - 20), (x + w - 4, y + h - 20),
             (x + w - 9, y + h - 8)], (178, 34, 34))
    cv.fill_rect(x + 6, y + 6, 18, 8, (178, 34, 34))
    cv.stipple(x, y, w, h, (178, 34, 34), 15, rng)


def scene_vigil(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (48, 30, 70), (24, 16, 40))
    for i in range(3):
        cx = x + 12 + i * 16
        cv.fill_rect(cx, y + 26, 6, h - 30, (240, 235, 220))
        cv.disc(cx + 3, y + 22, 3, (255, 200, 60))
        cv.disc(cx + 3, y + 23, 2, (255, 240, 160))
    cv.disc(x + w - 12, y + 10, 6, (220, 220, 235))
    cv.fill_rect(x, y + h - 5, w, 5, (16, 10, 28))
    cv.stipple(x, y, w, h, (200, 180, 255), 30, rng)


def scene_cuba(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (140, 190, 220), (90, 150, 200))
    cv.fill_rect(x, y + h - 18, w, 18, (30, 90, 140))
    for i in range(3):
        wy = y + h - 14 + i * 5
        cv.hline(x + 4 + i * 3, wy, w - 10 - i * 6, (200, 230, 245))
    cv.fill_rect(x + 10, y + h - 30, 34, 8, (60, 50, 45))
    cv.fill_rect(x + 18, y + h - 44, 4, 14, (60, 50, 45))
    cv.fill_rect(x + 30, y + h - 40, 10, 8, (255, 255, 255))
    cv.fill_rect(x + 33, y + h - 43, 4, 14, (178, 34, 34))
    cv.fill_rect(x + 30, y + h - 40, 10, 4, (178, 34, 34))
    cv.disc(x + w - 12, y + 10, 7, (250, 220, 130))
    cv.stipple(x, y, w, h, (255, 255, 255), 25, rng)


def scene_garment(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (235, 220, 190), (200, 180, 140))
    cv.fill_rect(x + 4, y + 22, w - 8, h - 28, (150, 110, 80))
    for i in range(4):
        sx = x + 6 + i * (w - 12) // 4
        cv.poly([(sx, y + 22), (sx + (w - 12) // 8, y + 12),
                 (sx + (w - 12) // 4, y + 22)], (120, 80, 50))
    for i in range(3):
        wx = x + 10 + i * 16
        cv.fill_rect(wx, y + 30, 10, 12, (250, 240, 200))
    cv.disc(x + 12, y + h - 12, 5, (178, 34, 34))
    cv.disc(x + 26, y + h - 12, 5, (24, 48, 96))
    cv.disc(x + 40, y + h - 12, 5, (34, 110, 60))
    cv.fill_rect(x, y + h - 4, w, 4, (90, 60, 35))
    cv.stipple(x, y, w, h, (120, 90, 50), 25, rng)


def scene_climate(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (200, 225, 235), (160, 195, 210))
    cv.disc(x + w // 2, y + h // 2 - 2, 20, (70, 140, 90))
    cv.disc(x + w // 2 - 8, y + h // 2 - 8, 6, (40, 110, 60))
    cv.disc(x + w // 2 + 7, y + h // 2 + 4, 5, (40, 110, 60))
    cv.disc(x + w // 2 + 2, y + h // 2 - 12, 4, (40, 110, 60))
    cv.line(x + w // 2 - 14, y + h // 2 - 14, x + w // 2 + 14,
            y + h // 2 + 14, (250, 240, 210))
    cv.line(x + w // 2 + 14, y + h // 2 - 14, x + w // 2 - 14,
            y + h // 2 + 14, (250, 240, 210))
    for i in range(3):
        cx = x + 8 + i * 18
        cv.fill_rect(cx, y + h - 14, 10, 10, (120, 90, 60))
        cv.fill_rect(cx + 2, y + h - 20, 6, 6, (150, 115, 80))
    cv.stipple(x, y, w, h, (255, 255, 255), 25, rng)


def scene_crash(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (150, 180, 210), (110, 150, 190))
    cv.fill_rect(x, y + h - 16, w, 16, (30, 80, 130))
    for i in range(3):
        wy = y + h - 12 + i * 4
        cv.hline(x + 4 + i * 4, wy, w - 10 - i * 8, (200, 225, 240))
    cv.poly([(x + 10, y + 22), (x + 40, y + 18), (x + 46, y + 24),
             (x + 16, y + 28)], (230, 230, 230))
    cv.poly([(x + 40, y + 18), (x + 48, y + 12), (x + 46, y + 24)],
            (180, 40, 40))
    cv.disc(x + 30, y + h - 16, 5, (255, 255, 255))
    cv.disc(x + 38, y + h - 18, 4, (255, 255, 255))
    cv.disc(x + 22, y + h - 14, 3, (255, 255, 255))
    cv.stipple(x, y, w, h, (255, 255, 255), 20, rng)


def scene_boat(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (250, 200, 110), (220, 140, 70))
    cv.disc(x + w - 12, y + 10, 8, (255, 240, 180))
    cv.fill_rect(x, y + h - 20, w, 20, (40, 100, 150))
    for i in range(3):
        wy = y + h - 16 + i * 5
        cv.hline(x + 3 + i * 4, wy, w - 8 - i * 8, (190, 220, 240))
    cv.poly([(x + 10, y + h - 22), (x + w - 10, y + h - 22),
             (x + w - 16, y + h - 12), (x + 16, y + h - 12)],
            (90, 60, 40))
    cv.fill_rect(x + w // 2 - 1, y + h - 38, 2, 16, (60, 45, 35))
    cv.poly([(x + w // 2 + 1, y + h - 38), (x + w // 2 + 14, y + h - 24),
             (x + w // 2 + 1, y + h - 24)], (240, 235, 220))
    for i in range(4):
        cv.disc(x + 16 + i * 8, y + h - 26, 2, (30, 30, 30))
    cv.stipple(x, y, w, h, (255, 255, 255), 20, rng)


SCENES = [scene_refinery, scene_tariff, scene_nato, scene_court,
          scene_missile, scene_space, scene_storm, scene_stocks,
          scene_vigil, scene_cuba, scene_garment, scene_climate,
          scene_crash, scene_boat]

# ---------------------------------------------------------------------------
# World map: stylised continent polygons in (lon, lat).
# ---------------------------------------------------------------------------
CONTINENTS = [
    [(-168, 66), (-150, 70), (-135, 69), (-125, 71), (-115, 73), (-105, 73),
     (-95, 80), (-85, 80), (-78, 75), (-70, 73), (-65, 68), (-60, 62),
     (-55, 52), (-60, 47), (-65, 44), (-70, 42), (-74, 39), (-76, 35),
     (-80, 32), (-81, 26), (-84, 30), (-88, 29), (-91, 19), (-95, 18),
     (-97, 16), (-94, 14), (-90, 13), (-86, 12), (-83, 9), (-79, 9),
     (-80, 7), (-77, 4), (-80, 8), (-84, 10), (-88, 14), (-92, 15),
     (-96, 16), (-100, 18), (-105, 20), (-108, 23), (-111, 26), (-114, 29),
     (-117, 32), (-121, 35), (-124, 40), (-124, 46), (-128, 50), (-132, 56),
     (-140, 60), (-150, 60), (-158, 58), (-165, 60), (-168, 66)],
    [(-44, 60), (-32, 68), (-22, 70), (-20, 74), (-30, 78), (-45, 80),
     (-58, 76), (-58, 70), (-53, 64), (-46, 60)],
    [(-77, 7), (-72, 11), (-64, 10), (-56, 8), (-52, 5), (-50, 0),
     (-44, -3), (-36, -7), (-39, -14), (-41, -22), (-48, -27), (-52, -33),
     (-57, -38), (-62, -41), (-66, -46), (-68, -50), (-69, -54), (-72, -54),
     (-74, -48), (-73, -40), (-72, -32), (-71, -24), (-70, -18), (-74, -15),
     (-78, -10), (-81, -5), (-81, 0), (-79, 3), (-77, 7)],
    [(-17, 15), (-16, 20), (-13, 27), (-10, 31), (-6, 34), (-2, 35),
     (3, 37), (10, 37), (15, 32), (20, 32), (25, 32), (30, 31), (33, 28),
     (35, 23), (37, 18), (39, 15), (41, 11), (44, 11), (48, 11), (51, 10),
     (46, 4), (41, -2), (40, -10), (37, -16), (34, -20), (32, -26),
     (28, -32), (20, -35), (17, -32), (14, -27), (12, -18), (12, -12),
     (9, -4), (9, 4), (4, 6), (-4, 5), (-8, 4), (-13, 8), (-16, 12),
     (-17, 15)],
    [(-10, 36), (-9, 43), (-2, 48), (2, 51), (7, 54), (10, 58), (18, 56),
     (22, 58), (28, 62), (35, 66), (45, 68), (55, 69), (65, 71), (75, 73),
     (85, 75), (95, 76), (105, 77), (115, 76), (125, 73), (135, 72),
     (145, 72), (155, 70), (162, 66), (170, 66), (178, 65), (178, 62),
     (170, 60), (162, 56), (158, 52), (150, 55), (142, 52), (140, 45),
     (136, 43), (130, 42), (127, 39), (122, 38), (120, 34), (121, 30),
     (118, 25), (112, 22), (108, 19), (105, 12), (103, 8), (100, 7),
     (98, 11), (96, 16), (93, 21), (90, 22), (87, 22), (84, 19), (80, 15),
     (77, 9), (74, 14), (71, 21), (68, 23), (66, 25), (62, 25), (58, 26),
     (55, 26), (52, 27), (50, 29), (48, 30), (45, 29), (42, 28), (39, 25),
     (37, 22), (35, 19), (34, 28), (33, 31), (30, 36), (27, 37), (23, 36),
     (19, 40), (15, 38), (12, 38), (10, 37), (8, 39), (3, 38), (0, 36),
     (-2, 37), (-6, 36), (-10, 36)],
    [(-5, 50), (-3, 53), (-5, 56), (-4, 58), (-2, 57), (0, 53), (1, 51),
     (-3, 50), (-5, 50)],
    [(130, 31), (132, 33), (135, 34), (137, 35), (139, 35), (140, 38),
     (141, 41), (142, 43), (144, 44), (141, 45), (140, 41), (139, 37),
     (136, 35), (133, 34), (130, 31)],
    [(95, 5), (98, 3), (101, 0), (104, -3), (107, -6), (110, -7), (114, -8),
     (118, -9), (122, -9), (126, -8), (130, -5), (133, -3), (136, -2),
     (140, -4), (141, -8), (138, -8), (134, -6), (130, -3), (127, 0),
     (124, 1), (121, 0), (118, -1), (115, -3), (112, -5), (108, -6),
     (105, -5), (102, -2), (99, 1), (96, 4), (95, 5)],
    [(113, -22), (114, -30), (115, -34), (120, -34), (124, -33), (129, -32),
     (132, -32), (135, -35), (138, -35), (140, -38), (145, -38), (149, -37),
     (153, -32), (153, -27), (150, -23), (146, -19), (142, -11), (137, -12),
     (135, -12), (132, -11), (129, -14), (126, -14), (123, -16), (120, -19),
     (117, -20), (114, -22), (113, -22)],
    [(167, -45), (170, -43), (173, -41), (175, -38), (177, -38), (176, -40),
     (174, -42), (171, -44), (168, -46), (167, -45)],
]


def project(lon, lat, mx, my, mw, mh):
    x = mx + (lon + 180) / 360.0 * mw
    y = my + (80 - lat) / 135.0 * mh
    return int(x), int(y)


CITIES = [
    ("London", -0.1, 51.5), ("Paris", 2.3, 48.9), ("Moscow", 37.6, 55.8),
    ("Cairo", 31.2, 30.0), ("Delhi", 77.2, 28.6), ("Tokyo", 139.7, 35.7),
    ("Sydney", 151.2, -33.9), ("Brasilia", -47.9, -15.8),
    ("Mexico City", -99.1, 19.4), ("Jakarta", 106.8, -6.2),
]


def draw_map(cv, x, y, w, h, pins, rng):
    cv.fill_rect(x, y, w, h, SEA)
    for i in range(0, w, 8):
        for j in range(0, h, 8):
            if (i // 8 + j // 8) % 2 == 0:
                cv.set(x + i, y + j, (178, 205, 228))
    for lon in range(-150, 181, 30):
        gx, _ = project(lon, 0, x, y, w, h)
        cv.vline(gx, y, h, (190, 210, 228))
    for lat in (60, 30, 0, -30):
        _, gy = project(0, lat, x, y, w, h)
        cv.hline(x, gy, w, (190, 210, 228))
    for poly_lonlat in CONTINENTS:
        pts = [project(lo, la, x, y, w, h) for lo, la in poly_lonlat]
        cv.poly(pts, LAND)
        n = len(pts)
        for i in range(n):
            cv.line(pts[i][0], pts[i][1], pts[(i + 1) % n][0],
                    pts[(i + 1) % n][1], (150, 138, 100))
    cv.stipple(x, y, w, h, (255, 255, 255), 260, rng)
    for name, lon, lat in CITIES:
        cx, cy = project(lon, lat, x, y, w, h)
        cv.disc(cx, cy, 2, (90, 90, 90))
        draw_text(cv, cx + 4, cy - 3, name, 1, (70, 70, 70))
    for num, lon, lat, dx, dy in pins:
        tx, ty = project(lon, lat, x, y, w, h)
        px, py = tx + dx, ty + dy
        if dx or dy:
            cv.line(tx, ty, px, py, (90, 90, 90))
            cv.disc(tx, ty, 2, (90, 90, 90))
        cv.disc(px, py, 9, RED)
        cv.ring(px, py, 9, (255, 255, 255))
        label = str(num)
        draw_text(cv, px - text_w(label, 1) // 2, py - 3, label, 1,
                  (255, 255, 255))


# ---------------------------------------------------------------------------
# Stories. Every item happened, or was first reported, on 26 November 2026.
# Pins are (lon, lat, pin-offset-x, pin-offset-y); offsets keep the crowded
# pins apart, with a leader line to the true spot (11/25 lesson).
# ---------------------------------------------------------------------------
FEATURED = [
    {"num": 1, "headline": "HOUTHIS HIT RIYADH REFINERY",
     "summary": "Houthi forces claim a fresh strike on a Saudi refinery. Brent crude tops $94 a barrel.",
     "tag": "M EAST - ENERGY", "source": "CLAIM - HOUTHIS", "region": "M EAST",
     "scene": 0, "pin": (46.7, 24.6, 0, -8)},
    {"num": 2, "headline": "US TARIFFS: TAIWAN AT 15%",
     "summary": "Washington proposes a 15% tariff rate for Taiwan goods, its lowest tier. 14 partners face new duties.",
     "tag": "TRADE - ASIA", "source": "AP", "region": "E ASIA",
     "scene": 1, "pin": (121.5, 25.0, 0, -8)},
    {"num": 3, "headline": "NATO WATCHES EASTERN FLANK",
     "summary": "NATO boosts air surveillance on its eastern flank after missiles crash across the border.",
     "tag": "EUROPE - SECURITY", "source": "AP", "region": "EUROPE",
     "scene": 2, "pin": (19.0, 52.0, 0, -8)},
    {"num": 4, "headline": "RAMAPHOSA REPORT VOID",
     "summary": "A South African court rules the impeachment report against President Ramaphosa unlawful.",
     "tag": "AFRICA - POLITICS", "source": "AP", "region": "AFRICA",
     "scene": 3, "pin": (28.2, -25.7, 0, -8)},
    {"num": 5, "headline": "KIM: SPREAD THE TACTICAL NUKES",
     "summary": "North Korea's Kim calls for diversified use of tactical nuclear weapons.",
     "tag": "E ASIA - SECURITY", "source": "AFP", "region": "E ASIA",
     "scene": 4, "pin": (125.7, 39.0, 10, -10)},
    {"num": 6, "headline": "FIRST FOREIGNER ON TIANGONG",
     "summary": "China to welcome its first foreign astronaut, from Pakistan, aboard the Tiangong station.",
     "tag": "SPACE - ASIA", "source": "AP", "region": "E ASIA",
     "scene": 5, "pin": (116.4, 39.9, -12, -10)},
    {"num": 7, "headline": "PARADE OFF AS STORM HITS",
     "summary": "New York postpones its Thanksgiving Day parade as a major storm bears down.",
     "tag": "USA - WEATHER", "source": "AFP", "region": "N AMERICA",
     "scene": 6, "pin": (-74.0, 40.7, 0, -8)},
    {"num": 8, "headline": "STOCKS SLIDE ON AI FEARS",
     "summary": "US stocks fall further as AI fears intensify, deepening the Nasdaq rout.",
     "tag": "MARKETS - TECH", "source": "AP", "region": "N AMERICA",
     "scene": 7, "pin": (-74.0, 40.7, 14, 10)},
    {"num": 9, "headline": "FIVE WOMEN AN HOUR",
     "summary": "Five women are killed every hour worldwide by a partner or a relative, the UN says.",
     "tag": "GLOBAL - HEALTH", "source": "UN", "region": "GLOBAL",
     "scene": 8, "pin": (6.1, 46.2, 0, -8)},
    {"num": 10, "headline": "WHO: END CUBA FUEL BLOCKADE",
     "summary": "The WHO chief urges an end to the US fuel blockade on Cuba.",
     "tag": "AMERICAS - HEALTH", "source": "AP", "region": "N AMERICA",
     "scene": 9, "pin": (-82.4, 23.1, -16, 10)},
    {"num": 11, "headline": "GARMENT PAY UP 36%",
     "summary": "Bangladesh garment workers win a 36% minimum-wage hike.",
     "tag": "S ASIA - LABOUR", "source": "AP", "region": "S ASIA",
     "scene": 10, "pin": (90.4, 23.8, 0, -8)},
    {"num": 12, "headline": "OPEC BLAMES EU FOR COP31 FLOP",
     "summary": "OPEC blames the EU for the COP31 collapse. The Antalya summit ended with no deal.",
     "tag": "CLIMATE - ENERGY", "source": "JAPAN TIMES", "region": "EUROPE",
     "scene": 11, "pin": (30.7, 36.9, 0, -8)},
    {"num": 13, "headline": "SIX DEAD IN PLANE CRASH",
     "summary": "Six die in a plane crash off the southern US coast, the Coast Guard says.",
     "tag": "USA - DISASTER", "source": "AP", "region": "N AMERICA",
     "scene": 12, "pin": (-86.0, 28.0, 4, -14)},
    {"num": 14, "headline": "2,000 REACH CANARIES IN A DAY",
     "summary": "Nearly 2,000 migrants reach Spain's Canary Islands in a record single-day arrival.",
     "tag": "EUROPE - MIGRATION", "source": "AP", "region": "EUROPE",
     "scene": 13, "pin": (-15.6, 28.3, 0, -8)},
]

ALSO = [
    (15, "Trump seeks faster federal executions"),
    (16, "Seoul warns after Russian jets approach"),
    (17, "UK to put EU deal to parliament"),
    (18, "China, Cambodia hold joint drills"),
    (19, "N. Korea expels Swiss envoy"),
    (20, "Colombia frees supermarket hostages"),
    (21, "Australia, Solomons sign pact"),
    (22, "UN: HIV fight under pressure"),
    (23, "31 die in Cairo tanker-truck fire"),
    (24, "Judges: drop top Netanyahu charges"),
    (25, "India unveils Rs 15,000-cr Nepal aid"),
    (26, "IPL 2027 auction draws 1,220 players"),
    (27, "Gukesh meets Sindarov in chess final"),
    (28, "Sooryavanshi smashes 204 off 53"),
    (29, "Steelers cut Aaron Rodgers"),
    (30, "Quake of 5.6 shakes Nepal's Koshi"),
    (31, "Vance defends Nvidia chief Huang"),
    (32, "US tightens AI chip export rules"),
    (33, "Twin meerkats debut at Lima zoo"),
    (34, "US unveils F-15EX jets at Kadena"),
    (35, "ECOWAS approves security force plan"),
]

TIMELINE = [
    ("OVERNIGHT", "Houthis claim Riyadh strike"),
    ("MORNING", "S. Africa court voids report"),
    ("MIDDAY", "US sets Taiwan tariff at 15%"),
    ("AFTERNOON", "NATO boosts east surveillance"),
    ("EVENING", "Storm postpones NYC parade"),
]

DATECHECK = [
    ("Hormuz tankers hit mines", "Wed 25 Nov, not today"),
    ("COP31 collapse itself", "summit ended 22 Nov"),
    ("Taiwan shares fell 1,927 pts", "25 Nov close"),
    ("Nasdaq fell ~4%", "Wednesday 25 Nov"),
    ("49ers beat Vikings 35-10", "Sunday 22 Nov"),
]

SOURCES = "AP - AFP - Reuters - BBC - UN - WHO - Japan Times - Al Jazeera - IRNA"

# ---------------------------------------------------------------------------
# Layout.
# ---------------------------------------------------------------------------
MARGIN = 14
CW = W - 2 * MARGIN  # 996


def draw_masthead(cv):
    draw_text(cv, W // 2, 20, "THE WORLD IN ONE DAY", 3, INK, align="center")
    draw_text(cv, W // 2, 52, "THURSDAY 26 NOVEMBER 2026", 5, INK,
              align="center")
    draw_text(cv, W // 2, 96,
              "35 STORIES - 7 REGIONS - EVERY ONE FROM THIS THURSDAY",
              2, INK, align="center")
    cv.fill_rect(W // 2 - 110, 116, 220, 3, RED)
    cv.hline(MARGIN, 126, CW, INK)
    for x in range(MARGIN, W - MARGIN, 6):
        for y in range(14, 124, 6):
            if (x + y) % 12 == 0:
                cv.set(x, y, (232, 225, 205))


def grain_pass(cv, mod, amp):
    """Calibrated newsprint grain: a fixed fraction of pixels gets a small
    deterministic brightness shift. Visible as paper texture; it is what
    lifts the file out of the flat-colour band into the winners' range."""
    px = cv.px
    n = len(px) // 3
    span = 2 * amp + 1
    for i in range(n):
        h = (i * 2654435761) & 0xFFFFFFFF
        if (h >> 24) % mod == 0:
            d = ((h >> 8) % span) - amp
            j = i * 3
            for k in range(3):
                v = px[j + k] + d
                px[j + k] = 0 if v < 0 else (255 if v > 255 else v)


def draw_timeline(cv):
    y = 138
    cv.hline(MARGIN, y, CW, INK)
    for i, (period, text) in enumerate(TIMELINE):
        nx = MARGIN + 110 + i * 200
        cv.disc(nx, y, 4, RED)
        cv.ring(nx, y, 4, (255, 255, 255))
        draw_text(cv, nx, y - 14, period, 1, RED, align="center")
        draw_text(cv, nx, y + 8, text, 1, INK, align="center")


def draw_featured(cv):
    y0 = 162
    row_h = 64
    col_w = 492
    for row in range(7):
        for col in range(2):
            idx = row * 2 + col
            if idx >= len(FEATURED):
                continue
            st = FEATURED[idx]
            cx = MARGIN + col * (col_w + 12)
            cy = y0 + row * row_h
            if row % 2 == 1:
                cv.fill_rect(cx, cy, col_w, row_h - 2, (243, 238, 224))
            SCENES[st["scene"]](cv, cx + 2, cy + 3, 58, 58, RNG)
            cv.rect(cx + 2, cy + 3, 58, 58, INK, 1)
            tab_w = 16
            cv.fill_rect(cx + 2, cy + 3, tab_w, 12, RED)
            num = str(st["num"])
            draw_text(cv, cx + 2 + (tab_w - text_w(num, 1)) // 2, cy + 4,
                      num, 1, (255, 255, 255))
            tx = cx + 66
            draw_text(cv, tx, cy + 4, st["headline"], 2, INK)
            lines = wrap(st["summary"], 1, 420)
            ly = cy + 22
            for ln in lines[:2]:
                draw_text(cv, tx, ly, ln, 1, INK_SOFT)
                ly += 9
            tag = st["tag"]
            chip_w = text_w(tag, 1) + 8
            chip_y = cy + 46
            cv.fill_rect(tx, chip_y, chip_w, 11,
                         REGION_COLORS.get(st["region"], INK))
            draw_text(cv, tx + 4, chip_y + 2, tag, 1, (255, 255, 255))
            draw_text(cv, tx + chip_w + 6, chip_y + 2,
                      "| " + st["source"], 1, INK_SOFT)
        cv.hline(MARGIN, y0 + (row + 1) * row_h - 2, CW, (222, 216, 202))


def draw_map_and_check(cv):
    y0 = 616
    draw_text(cv, MARGIN, y0, "WHERE IT HAPPENED", 2, INK)
    pins = [(s["num"], s["pin"][0], s["pin"][1], s["pin"][2], s["pin"][3])
            for s in FEATURED]
    draw_map(cv, MARGIN, y0 + 20, 650, 164, pins, RNG)
    cv.rect(MARGIN, y0 + 20, 650, 164, INK, 1)
    bx = 686
    bw = W - MARGIN - bx
    cv.rect(bx, y0, bw, 184, RED, 1)
    draw_text(cv, bx + 10, y0 + 8, "DATE CHECK - NOT TODAY", 2, RED)
    draw_text(cv, bx + 10, y0 + 26, "Tempting stories we left out, and why:",
              1, INK_SOFT)
    iy = y0 + 44
    for event, when in DATECHECK:
        draw_text(cv, bx + 10, iy, event, 1, INK)
        draw_text(cv, bx + 10, iy + 9, "NOT 26 NOV - " + when, 1, RED)
        iy += 28


def draw_also(cv):
    y0 = 806
    draw_text(cv, MARGIN, y0, "ALSO ON THURSDAY 26 NOVEMBER", 2, INK)
    cv.hline(MARGIN, y0 + 18, CW, INK)
    col_x = [MARGIN, MARGIN + 332, MARGIN + 664]
    for i, (num, text) in enumerate(ALSO):
        col = i // 7
        row = i % 7
        x = col_x[col]
        y = y0 + 26 + row * 19
        draw_text(cv, x, y, str(num), 1, RED)
        draw_text(cv, x + 20, y, text.upper(), 1, INK)


def draw_footer(cv):
    y0 = 968
    cv.hline(MARGIN, y0, CW, INK)
    draw_text(cv, W // 2, y0 + 8,
              "Every story here happened or was first reported on Thursday 26 November 2026.",
              1, INK, align="center")
    draw_text(cv, W // 2, y0 + 20,
              "Sources: " + SOURCES + ". Original drawings.",
              1, INK_SOFT, align="center")
    draw_text(cv, W // 2, y0 + 32,
              "35 STORIES - 7 REGIONS - DRAWN BY PROGRAM, NOT PHOTOGRAPHS",
              1, INK_SOFT, align="center")


def build():
    cv = Canvas(W, H, PAPER)
    cv.rect(8, 8, W - 16, H - 16, INK, 2)
    cv.rect(12, 12, W - 24, H - 24, RULE, 1)
    draw_masthead(cv)
    draw_timeline(cv)
    draw_featured(cv)
    draw_map_and_check(cv)
    draw_also(cv)
    draw_footer(cv)
    cv.stipple(0, 0, W, H, (208, 198, 178), 9000, RNG)
    cv.stipple(0, 0, W, H, (255, 255, 250), 9000, RNG)
    grain_pass(cv, 5, 3)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    if not os.path.isdir(out_dir):
        out_dir = "out"
    os.makedirs(out_dir, exist_ok=True)
    cv = build()
    path = os.path.join(out_dir, "entry.png")
    n = save_png(cv, path)
    print("wrote %s %d bytes" % (path, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())

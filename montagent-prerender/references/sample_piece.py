#!/usr/bin/env python3
"""A sample code-drawn piece: bars turning inside a soft-edged diamond, on a transparent
background. Writes raw RGBA frames to stdout, size and frame count from the environment,
in integer arithmetic only so every machine draws the same bytes.

    PRERENDER_WIDTH=160 PRERENDER_HEIGHT=120 PRERENDER_FRAMES=48 python3 sample_piece.py > frames.rgba
"""

import os
import sys

W = int(os.environ["PRERENDER_WIDTH"])
H = int(os.environ["PRERENDER_HEIGHT"])
N = int(os.environ["PRERENDER_FRAMES"])
CX, CY = W // 2, H // 2
R = min(W, H) // 2 - 2


def pixel(x, y, f):
    dx, dy = x - CX, y - CY
    d = abs(dx) + abs(dy)  # the diamond's distance
    if d >= R:
        return (0, 0, 0, 0)  # outside: transparent
    a = min(255, (R - d) * 255 // 12)  # soft edge, 12 px wide
    phase = (dx * 3 + dy * 5 + f * 16) % 64
    if phase < 8:  # the turning bars
        return (255, 90 + f * 3 % 120, 40, a)
    return (20 + d * 2 % 200, 60, 200 - d % 100, a // 2)  # translucent body


out = sys.stdout.buffer
for f in range(N):
    out.write(bytes(c for y in range(H) for x in range(W) for c in pixel(x, y, f)))

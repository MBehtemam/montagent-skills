#!/usr/bin/env python3
"""One frame of a Lottie, from a fresh ThorVG player, as raw RGBA. The sample player for the
Lottie route: `prerender.py` runs it once per frame, so no frame is ever a seek from another.

    python3 lottie_frame.py <lottie.json> <width> <height> <frame> <out.rgba> [<font.ttf> ...]

Needs `pip install thorvg-python==1.1.3` (ThorVG 1.0.4 inside). Writes width x height x 4 bytes,
straight (non-premultiplied) RGBA, transparent where nothing is drawn, to <out.rgba>; exits 1
on any ThorVG error. Any font file after the output is loaded into ThorVG first, for text set in
a vendored font. Any other player that writes RGBA frames will do: this one is only a sample.
"""

import sys

import thorvg_python as tvg


def main(argv):
    path, width, height, frame, out, *fonts = argv
    width, height, frame = int(width), int(height), float(frame)
    engine = tvg.Engine()
    engine.init(0)
    for font in fonts:
        if tvg.Text(engine).font_load(font) != tvg.Result.SUCCESS:
            sys.exit(f"lottie_frame: ThorVG could not load the font {font}")
    canvas = tvg.SwCanvas(engine)
    canvas.set_target(width, height, cs=tvg.Colorspace.ABGR8888S)  # straight RGBA bytes
    animation = tvg.LottieAnimation(engine)
    picture = animation.get_picture()
    steps = (
        ("load", picture.load(path)), ("set_size", picture.set_size(width, height)),
        ("add", canvas.add(picture)), ("set_frame", animation.set_frame(frame)),
        ("update", canvas.update()), ("draw", canvas.draw(True)), ("sync", canvas.sync()),
    )  # fmt: skip
    for name, result in steps:
        # ThorVG ignores a frame change under 0.001, and says so with INSUFFICIENT_CONDITION: a
        # fresh player starts at frame 0, so frame 0 is already set and is not an error.
        if name == "set_frame" and result == tvg.Result.INSUFFICIENT_CONDITION and frame < 0.001:
            continue
        if result != tvg.Result.SUCCESS:
            sys.exit(f"lottie_frame: ThorVG {name} returned {result.name} for frame {frame}")
    with open(out, "wb") as f:
        f.write(bytes(canvas.buffer_arr))
    engine.term()


if __name__ == "__main__":
    main(sys.argv[1:])

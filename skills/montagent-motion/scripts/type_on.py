#!/usr/bin/env python3
"""Set a line of text on one unit at a time: letters typed on, or words landing on beats.

    python3 type_on.py <project> <spec>

Requires Python >= 3.9
Standard library only.
drift-guard: type_on.montagent.json type_on.spec.json

Prints <project> with one text element per unit (each letter, or each word), placed where
the font's own advances put it, kerning included, so the line reads as if set whole. Each
says `caption: false`, since a typed or kinetic line is not a caption. An
optional cursor rect blinks while idle and steps ahead of each unit. Each element gets its
own track, named for its id (`<track>-01`, ..., `<track>-cursor`), on consecutive layers
from `layer`; running the script again replaces the tracks it wrote before.

Positions come from `montagent measure` on <project>, so the project must already declare
the spec's font in `fonts`, and `montagent` must be on PATH. Every time is moved to the
frame the project draws it on. `tracking` adds pixels after every unit: that is how a
tracked title is set.

<spec> is a JSON file:

    {
      "track": "name",            required: the prefix of every id and track name
      "layer": 20,                required
      "text": "Montagent",        required: one line
      "by": "letter",             "letter" (typing, tracking) or "word" (kinetic lines)
      "font": "title",            required: a key of the project's `fonts`
      "size": 120,                required
      "color": "#101418",
      "x": 337, "y": 540,         required: the line's left edge (or centre) and vertical centre
      "align": "left",            "left" or "center": what `x` places
      "start": 3000,              first unit; with "every", or give "times" instead
      "every": 150,               ms between units
      "times": [3000, 3150],      one time per unit, instead of start/every
      "end": 5500,                required: when the line leaves
      "tracking": 0,              extra px after each unit
      "enter": "cut",             "cut" (typing) or "pop" (each unit pops in)
      "pop": {"from": 0.5, "ms": 400, "rise": 40},  optional: the pop's start scale,
                                  length and upward travel
      "highlights": [{"unit": 5, "start": 2000, "color": "#FF5A36"}],
                                  optional: recolour unit n (1-based) from `start`
      "exit": {"at": 5000, "ms": 300},              optional fade-out of every unit
      "cursor": {"from": 2500, "to": 5000, "blink": 500, "width": 10,
                 "color": "#101418", "height": 96, "gap": 8}   optional
    }

"""

import json
import math
import re
import subprocess
import sys

POP = [0.34, 1.56, 0.64, 1]


def main(argv):
    if "--help" in argv or "-h" in argv or len(argv) != 2:
        print(__doc__)
        return 0 if "--help" in argv or "-h" in argv else 2
    project_path, spec_path = argv
    with open(project_path) as f:
        project = json.load(f)
    with open(spec_path) as f:
        spec = json.load(f)
    fps = project["fps"]

    def on_frame(t):
        """The drawn instant nearest to t: frame n is drawn at floor(n * 1000 / fps)."""
        return math.floor(round(t * fps / 1000) * 1000 / fps)

    text = spec["text"]
    pattern = r"\S+" if spec.get("by", "letter") == "word" else r"\S"
    units = [(m.start(), m.end()) for m in re.finditer(pattern, text)]
    if "times" in spec:
        times = spec["times"]
        if len(times) != len(units):
            sys.exit(f"`times` has {len(times)} entries; {text!r} has {len(units)} units")
    else:
        times = [spec["start"] + k * spec["every"] for k in range(len(units))]
    times = [on_frame(t) for t in times]
    end = on_frame(spec["end"])

    # Advance of the text up to each unit's end, and of each unit alone: the unit's left
    # edge is the first less the second, so the kern before it counts.
    font, size = spec["font"], spec["size"]
    asks = [text[:b] for _, b in units] + [text[a:b] for a, b in units]
    batch = [{"font": font, "size": size, "runs": [{"text": s}]} for s in asks]
    out = subprocess.run(
        ["montagent", "measure", project_path, "--json", "--elements", json.dumps(batch)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        sys.exit(f"montagent measure failed:\n{out.stdout}{out.stderr}")
    results = json.loads(out.stdout)["measure"]["results"]
    for r in results:
        if r["error"]:
            sys.exit(f"montagent measure: {r['error']}")
    prefix = [r["ok"]["advance_width"] for r in results[: len(units)]]
    alone = [r["ok"]["advance_width"] for r in results[len(units):]]
    height = math.ceil(results[0]["ok"]["block_height"])

    track, tracking = spec["track"], spec.get("tracking", 0)
    x0, y = spec["x"], spec["y"]
    if spec.get("align", "left") == "center":
        x0 -= (prefix[-1] + tracking * (len(units) - 1)) / 2
    exit_, pop = spec.get("exit"), {"from": 0.5, "ms": 400, "rise": 0, **spec.get("pop", {})}
    highlights = {h["unit"]: h for h in spec.get("highlights", [])}
    elements, right_edges = [], []
    for k, ((a, b), w) in enumerate(zip(units, alone)):
        left = x0 + prefix[k] - w + k * tracking
        right_edges.append(x0 + prefix[k] + k * tracking)
        start = times[k]
        el = {
            "id": f"{track}-{k + 1:02d}", "type": "text", "start": start, "end": end,
            "x": round(left + w / 2), "y": y, "origin": "center",
            "width": math.ceil(w) + 2, "height": height,
            "font": font, "size": size,
        }
        if "color" in spec:
            el["color"] = spec["color"]
        el["align"] = "center"
        run = {"text": text[a:b]}
        if k + 1 in highlights:
            h = highlights[k + 1]
            run["highlight"] = {"start": on_frame(h["start"]), "end": h.get("end", end), "color": h["color"]}
        el["runs"] = [run]
        if spec.get("enter", "cut") == "pop":
            landed = on_frame(start + pop["ms"])
            if pop["rise"]:
                el["y"] = [{"t": start, "v": y + pop["rise"]}, {"t": landed, "v": y, "ease": POP}]
            s = pop["from"]
            el["scale"] = [{"t": start, "v": [s, s]}, {"t": landed, "v": [1.0, 1.0], "ease": POP}]
        if exit_:
            at = on_frame(exit_["at"])
            el["opacity"] = [{"t": at, "v": 1.0}, {"t": on_frame(at + exit_["ms"]), "v": 0.0, "ease": "ease-in"}]
        # A typed or kinetic line is not a caption: keep it out of the caption checks.
        el["caption"] = False
        elements.append(el)

    cursor = spec.get("cursor")
    if cursor:
        gap = cursor.get("gap", 8)
        # Where the cursor stands at each instant it moves: before the first letter, then
        # just past each letter as it appears.
        moves = [(on_frame(cursor["from"]), x0 + gap)] + [
            (t, right_edges[k] + tracking + gap) for k, t in enumerate(times)
        ]
        xs = [{"t": moves[0][0], "v": round(moves[0][1])}]
        for t, x in moves[1:]:
            if t > xs[-1]["t"] and round(x) != xs[-1]["v"]:
                xs.append({"t": t, "v": round(x), "ease": "step"})
        # Solid while typing, a hard on/off blink while idle before and after.
        half = cursor.get("blink", 500) // 2
        start, stop = on_frame(cursor["from"]), on_frame(cursor["to"])
        typing = (times[0], times[-1] + half)

        def lit(t):
            if typing[0] <= t < typing[1]:
                return True
            since = t - (typing[1] if t >= typing[1] else start)
            return (since // half) % 2 == 0

        instants = sorted({*range(start, stop, half), *range(typing[1], stop, half), *typing})
        ops = [{"t": start, "v": 1.0}]
        for t in instants:
            v = 1.0 if lit(t) else 0.0
            if start < t < stop and on_frame(t) > ops[-1]["t"] and v != ops[-1]["v"]:
                ops.append({"t": on_frame(t), "v": v, "ease": "step"})
        # A blink that would come on for less than half a cycle before the cursor goes
        # reads as a flicker: stay off instead.
        if len(ops) > 1 and ops[-1]["v"] == 1.0 and stop - ops[-1]["t"] < half:
            ops.pop()
        elements.append({
            "id": f"{track}-cursor", "type": "rect", "start": start, "end": stop,
            "x": xs if len(xs) > 1 else xs[0]["v"], "y": y, "origin": "center-left",
            "width": cursor.get("width", 10), "height": cursor.get("height", round(size * 0.8)),
            "fill": cursor.get("color", spec.get("color", "#000000")), "opacity": ops,
        })

    # Letters overlap in time, and a track holds no overlap: one track per element, each
    # named for its element, on consecutive layers from the spec's.
    project["tracks"] = [
        t for t in project.get("tracks", []) if not t["name"].startswith(f"{track}-")
    ]
    for k, el in enumerate(elements):
        project["tracks"].append({"name": el["id"], "layer": spec["layer"] + k, "elements": [el]})
    json.dump(project, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

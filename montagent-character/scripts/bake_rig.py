#!/usr/bin/env python3
"""Bake a cut-out character rig's poses, lip sync and blinks into flat Montagent elements.

    python3 bake_rig.py <project> <rig> <spec>

Requires Python >= 3.9
Standard library only.
# workaround: #499 · replaced by: parenting or a group transform
# workaround: #518 · replaced by: an image that changes over time
drift-guard: rig.montagent.json rig/rig.json rig.spec.json

Montagent has no parenting, so every part's on-screen transform is computed here, from
its parents, at every drawn frame, and written as `x`, `y` and `rotation` keyframes. An
element cannot change its image, so each mouth shape is its own element, shown for its
own span with the head's transform. Prints <project> with one track per part added, and
a report on stderr. Running it again replaces the tracks it wrote (those named
"<prefix>-...").

<rig> is the rig's JSON: `drawing`, `draw_order` (back to front), and `parts`, each with
`file` (relative to the rig), `width`, `height`, `pivot` (where the part's canvas centre
sits in the drawing) and `parent`; and `visemes`, mapping Azure viseme ids to a mouth
name, or to null for the mouth at rest. Mouth "open" is the part "mouth_open".

<spec> is a JSON file (times are milliseconds on the project's timeline; angles are
degrees, positive turns clockwise on screen, as Montagent's `rotation` does; eases are
Montagent's names or a cubic bezier `[x1, y1, x2, y2]`, sampled here, so `step` is not
one):

    {
      "prefix": "owl",             required: track and element id prefix
      "layer": 10,                 required: the first part's layer; each part in
                                   `draw_order` takes the next one up
      "start": 0, "end": 8000,     required: the character's span
      "scale": 0.5,                required: frame px per drawing px
      "place": [                   required: where the root part's pivot sits on the frame.
        {"t": 0, "x": -300, "y": 1000},             The first key sets `x` and `y`. A
        {"t": 700, "x": 600, "ease": "ease-out"}    later key sets any of `x`, `y`,
      ],                                            `scale`, keeping the others
      "hops": [{"from": 0, "to": 350, "height": 80}],     optional: a parabola lifted
                                   off `place` (frame px at its peak)
      "poses": {"wave": {"upper_arm_right": -100, "forearm_right": -30}},
                                   named poses: joint angles from the drawn rest pose,
                                   each relative to its parent. "rest" is every joint at 0.
      "moves": [                   each sets the joints its pose names, arriving at `t`
        {"t": 0, "pose": "rest"},  along `ease` (default "ease-in-out"); a joint it doesn't
        {"t": 1100, "pose": "wave", "ease": [0.34, 1.56, 0.64, 1]},    name keeps going
        {"t": 1166, "pose": {"forearm_right": -60}}                    as it was.
      ],                           A move with "in": 300 holds until 300 ms before `t`;
                                   without it, it sets off from the joint's previous key.
      "swings": [{"joint": "forearm_right", "from": 1300, "to": 2600,
                  "degrees": 25, "period": 500}],    optional: a sine added to a joint,
                                   easing in and out over a quarter period
      "voice": {"id": "voice", "visemes": "voice/line-1.json", "lead": 0},
                                   optional: the audio element that speaks, and its
                                   viseme file ({"visemes": [[ms, id], ...]}, relative to
                                   the spec). A mouth shows `lead` ms early.
      "min_mouth": 2,              the fewest frames a mouth shape stays; a shorter one is
                                   merged into the shape before it
      "blinks": {"part": "eyes_closed", "at": [2000, 4500], "frames": 3}    optional
    }

The report gives the elements and keyframes written, every mouth span merged or dropped,
the largest gap at any joint over every drawn frame (it should be well under 1 px), and
the instants to look at: each move's arrival and each joint's extremes.
"""

import json
import math
import os
import sys

NAMED = {
    "linear": (0.0, 0.0, 1.0, 1.0),
    "ease": (0.25, 0.1, 0.25, 1.0),
    "ease-in": (0.42, 0.0, 1.0, 1.0),
    "ease-out": (0.0, 0.0, 0.58, 1.0),
    "ease-in-out": (0.42, 0.0, 0.58, 1.0),
}
# How far a simplified keyframe line may miss the exact pose before a key is kept.
TOLERANCE = {"x": 0.25, "y": 0.25, "rotation": 0.05, "scale": 0.0005}


def main(argv):
    if "--help" in argv or "-h" in argv or len(argv) != 3:
        print(__doc__)
        return 0 if "--help" in argv or "-h" in argv else 2
    project_path, rig_path, spec_path = argv
    with open(project_path) as f:
        project = json.load(f)
    with open(rig_path) as f:
        rig = json.load(f)
    with open(spec_path) as f:
        spec = json.load(f)
    fps = project["fps"]
    parts = rig["parts"]
    prefix = spec["prefix"]

    def report(line):
        print(line, file=sys.stderr)

    def on_frame(t):
        """The drawn instant nearest to t: frame n is drawn at floor(n * 1000 / fps)."""
        return math.floor(round(t * fps / 1000) * 1000 / fps)

    start, end = spec["start"], spec["end"]
    first = math.ceil(start * fps / 1000)
    frames = []
    n = first
    while math.floor(n * 1000 / fps) < end:
        frames.append(math.floor(n * 1000 / fps))
        n += 1
    if not frames:
        sys.exit("start and end hold no drawn frame")

    for name in parts:
        if parts[name]["parent"] is not None and parts[name]["parent"] not in parts:
            sys.exit(f"part {name!r}: parent {parts[name]['parent']!r} is not a part")
    roots = [p for p in parts if parts[p]["parent"] is None]
    if len(roots) != 1:
        sys.exit(f"the rig needs exactly one part with no parent, not {roots}")
    root = roots[0]

    # Which parts are swapped in for a span (mouths, the blink) and which are always drawn.
    mouths = {}
    for shape in set(v for v in rig.get("visemes", {}).values() if v is not None):
        part = f"mouth_{shape}"
        if part not in parts:
            sys.exit(f"the viseme table names mouth {shape!r}, but there is no part {part!r}")
        mouths[shape] = part
    blinks = spec.get("blinks")
    overlays = set(mouths.values()) | ({blinks["part"]} if blinks else set())
    for p in overlays:
        if p not in parts:
            sys.exit(f"no part {p!r} in the rig")

    # ---- curves -------------------------------------------------------------------

    poses = dict(spec.get("poses", {}))
    joints = [p for p in parts if p not in overlays]
    poses.setdefault("rest", {j: 0 for j in joints})
    keys = {j: [] for j in joints}
    for move in sorted(spec.get("moves", []), key=lambda m: m["t"]):
        pose = move["pose"]
        if isinstance(pose, str):
            if pose not in poses:
                sys.exit(f"move at {move['t']}: no pose named {pose!r}")
            pose = poses[pose]
        for j, v in pose.items():
            if j not in keys:
                sys.exit(f"move at {move['t']}: {j!r} is not a joint of the rig")
            if "in" in move:
                # Hold where the joint was until the move sets off.
                setoff = move["t"] - move["in"]
                keys[j].append((setoff, curve(keys[j], setoff, 0.0), bezier("linear")))
            keys[j].append((move["t"], v, bezier(move.get("ease", "ease-in-out"))))

    place = spec["place"]
    if "x" not in place[0] or "y" not in place[0]:
        sys.exit("the first place key needs both x and y")
    place_keys = {"x": [], "y": [], "scale": [(place[0]["t"], spec["scale"], None)]}
    for k in sorted(place, key=lambda k: k["t"]):
        for prop in ("x", "y", "scale"):
            if prop in k:
                place_keys[prop].append((k["t"], k[prop], bezier(k.get("ease", "ease-in-out"))))

    def angle(j, t):
        a = curve(keys[j], t, 0.0)
        for s in spec.get("swings", []):
            if s["joint"] == j and s["from"] <= t <= s["to"]:
                ramp = s["period"] / 4
                env = smooth((t - s["from"]) / ramp) * smooth((s["to"] - t) / ramp)
                a += s["degrees"] * env * math.sin(2 * math.pi * (t - s["from"]) / s["period"])
        return a

    def pose_at(t):
        """{part: (x, y, rotation, scale)} on the frame at t, every parent applied."""
        x = curve(place_keys["x"], t, 0.0)
        y = curve(place_keys["y"], t, 0.0)
        for h in spec.get("hops", []):
            if h["from"] <= t <= h["to"]:
                u = (t - h["from"]) / (h["to"] - h["from"])
                y -= 4 * h["height"] * u * (1 - u)
        k = curve(place_keys["scale"], t, spec["scale"])
        out = {}

        def world(name):
            if name in out:
                return out[name]
            part = parts[name]
            own = 0.0 if name in overlays else angle(name, t)
            if part["parent"] is None:
                out[name] = (x, y, own, k)
            else:
                px, py, pr, pk = world(part["parent"])
                pp = parts[part["parent"]]["pivot"]
                dx, dy = rotate(part["pivot"][0] - pp[0], part["pivot"][1] - pp[1], pr)
                out[name] = (px + pk * dx, py + pk * dy, pr + own, pk)
            return out[name]

        for name in parts:
            world(name)
        return out

    samples = [pose_at(t) for t in frames]

    # ---- elements -----------------------------------------------------------------

    base = spec["scale"]
    rig_dir = os.path.dirname(os.path.abspath(rig_path))
    project_dir = os.path.dirname(os.path.abspath(project_path))

    def source(name):
        path = os.path.join(rig_dir, parts[name]["file"])
        return os.path.relpath(path, project_dir).replace(os.sep, "/")

    def lists(name):
        """Simplified keyframe lists for one part over the whole span."""
        got = {}
        for i, prop in enumerate(("x", "y", "rotation", "scale")):
            values = [s[name][i] for s in samples]
            if prop == "scale":
                values = [v / base for v in values]
            got[prop] = simplify(list(zip(frames, values)), TOLERANCE[prop])
        return got

    def element(eid, name, s, e, transform):
        el = {"id": eid, "type": "image", "start": s, "end": e, "source": source(name)}
        for prop in ("x", "y"):
            el[prop] = written(transform[prop], None)
        el["origin"] = "center"
        el["fit"] = "literal"
        el["width"] = round(parts[name]["width"] * base)
        el["height"] = round(parts[name]["height"] * base)
        rot = written(transform["rotation"], 2)
        if rot != 0:
            el["rotation"] = rot
        sc = written(transform["scale"], 4)
        if isinstance(sc, list):
            el["scale"] = [{**k, "v": [k["v"], k["v"]]} for k in sc]
        elif sc != 1:
            el["scale"] = [sc, sc]
        return el

    layer_of = {name: spec["layer"] + i for i, name in enumerate(rig["draw_order"])}
    for name in parts:
        if name not in layer_of:
            sys.exit(f"part {name!r} is missing from draw_order")
    tracks = []
    written_lists = {}
    for name in rig["draw_order"]:
        if name in overlays:
            continue
        written_lists[name] = lists(name)
        tracks.append({"name": f"{prefix}-{name}", "layer": layer_of[name], "elements": [
            element(f"{prefix}-{name}", name, frames[0], end, written_lists[name])]})

    def overlay_track(label, spans):
        """One track of swapped-in parts, each with its parent's keys over its span."""
        els = []
        for i, (s, e, name) in enumerate(spans):
            parent = parts[name]["parent"]
            if parts[name]["pivot"] != parts[parent]["pivot"]:
                sys.exit(f"overlay {name!r} must share its parent's pivot")
            src = written_lists[parent]
            last = max(t for t in frames if s <= t < e)
            clipped = {prop: clip(ks, s, last) for prop, ks in src.items()}
            els.append(element(f"{prefix}-{label}-{i}", name, s, e, clipped))
        if els:
            layer = min(layer_of[n] for _, _, n in spans)
            tracks.append({"name": f"{prefix}-{label}", "layer": layer, "elements": els})
            return els
        return []

    # ---- the mouth ----------------------------------------------------------------

    mouth_els = []
    voice_spec = spec.get("voice")
    if voice_spec:
        elements = {e["id"]: e for t in project.get("tracks", []) for e in t["elements"]}
        voice = elements.get(voice_spec["id"])
        if voice is None:
            sys.exit(f"no element with id {voice_spec['id']!r} in {project_path}")
        vis_path = os.path.join(os.path.dirname(os.path.abspath(spec_path)), voice_spec["visemes"])
        with open(vis_path) as f:
            vis = json.load(f)["visemes"]
        speed = voice.get("speed", 1)
        src0, src1 = voice["source_start"], voice["source_end"]
        lead = voice_spec.get("lead", 0)

        def to_timeline(t):
            return voice["start"] + (t - src0) / speed - lead

        raw = []
        for (t0, vid), nxt in zip(vis, vis[1:] + [[src1, 0]]):
            a, b = max(t0, src0), min(nxt[0], src1)
            if b <= a:
                continue
            shape = rig["visemes"].get(str(vid))
            raw.append([to_timeline(a), to_timeline(b), shape])
        spans = []
        for a, b, shape in raw:
            if spans and spans[-1][2] == shape and abs(spans[-1][1] - a) < 1:
                spans[-1][1] = b
            else:
                spans.append([a, b, shape])
        min_mouth = spec.get("min_mouth", 2)
        snapped = []
        for a, b, shape in spans:
            a, b = max(on_frame(a), frames[0]), min(on_frame(b), end)
            if snapped and a < snapped[-1][1]:
                a = snapped[-1][1]
            drawn = sum(1 for t in frames if a <= t < b)
            if drawn == 0:
                continue
            if drawn < min_mouth and snapped and snapped[-1][1] == a:
                report(f"mouth {shape or 'rest'} at {a}-{b} is {drawn} frame(s): "
                       f"merged into the {snapped[-1][2] or 'rest'} before it")
                snapped[-1][1] = b
                continue
            if snapped and snapped[-1][2] == shape:
                snapped[-1][1] = b
                continue
            snapped.append([a, b, shape])
        shown = [(a, b, mouths[shape]) for a, b, shape in snapped if shape is not None]
        mouth_els = overlay_track("mouth", shown)
        if shown:
            shortest = min(sum(1 for t in frames if a <= t < b) for a, b, _ in shown)
            report(f"mouth: {len(shown)} spans from {len(vis)} visemes, the shortest "
                   f"{shortest} frames; at rest outside them")

    if blinks:
        n_frames = blinks.get("frames", 3)
        spans = []
        for at in sorted(blinks["at"]):
            a = on_frame(at)
            b = on_frame(a + n_frames * 1000 / fps)
            spans.append((a, min(b, end), blinks["part"]))
        overlay_track("blink", spans)

    # ---- check and report -----------------------------------------------------------

    # Read back what was written, at every drawn frame: does each child still meet its parent?
    drawn = {tr["elements"][0]["id"][len(prefix) + 1:]: tr["elements"][0] for tr in tracks
             if tr["elements"][0]["id"][len(prefix) + 1:] in written_lists}
    worst = (-1.0, None, None)
    for t in frames:
        got = {name: tuple(read_back(drawn[name], p, t) for p in ("x", "y", "rotation", "scale"))
               for name in written_lists}
        for name in written_lists:
            parent = parts[name]["parent"]
            if parent is None:
                continue
            px, py, pr, pk = got[parent]
            pp = parts[parent]["pivot"]
            dx, dy = rotate(parts[name]["pivot"][0] - pp[0], parts[name]["pivot"][1] - pp[1], pr)
            gap = math.hypot(px + pk * base * dx - got[name][0], py + pk * base * dy - got[name][1])
            if gap > worst[0]:
                worst = (gap, name, t)
    count = sum(len(v) if isinstance(v, list) else 0
                for tr in tracks for el in tr["elements"] for v in el.values())
    report(f"{sum(len(tr['elements']) for tr in tracks)} elements on {len(tracks)} tracks, "
           f"{count} keyframes over {len(frames)} drawn frames")
    if worst[1]:
        report(f"largest joint gap: {worst[0]:.2f} px, {worst[1]} at {worst[2]}")
    look = sorted(set(on_frame(m["t"]) for m in spec.get("moves", []) if start <= m["t"] < end))
    report(f"look at each move's arrival: {', '.join(map(str, look))}")
    for j in joints:
        values = [angle(j, t) for t in frames]
        if max(values) - min(values) > 1:
            lo, hi = values.index(min(values)), values.index(max(values))
            report(f"  {j}: {min(values):.0f}° at {frames[lo]}, {max(values):.0f}° at {frames[hi]}")

    project["tracks"] = [t for t in project.get("tracks", []) if not t["name"].startswith(f"{prefix}-")]
    project["tracks"] += tracks
    print(json.dumps(project, indent=1))
    return 0


# ---- helpers ------------------------------------------------------------------------


def bezier(ease):
    if isinstance(ease, str):
        if ease not in NAMED:
            sys.exit(f"ease {ease!r}: use one of {sorted(NAMED)} or a cubic bezier")
        ease = NAMED[ease]
    x1, y1, x2, y2 = ease

    def f(u):
        if u <= 0 or u >= 1:
            return min(max(u, 0.0), 1.0)
        lo, hi = 0.0, 1.0
        for _ in range(60):
            s = (lo + hi) / 2
            x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3
            lo, hi = (s, hi) if x < u else (lo, s)
        s = (lo + hi) / 2
        return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s ** 3

    return f


def curve(keys, t, default):
    """keys: [(t, value, ease)], eased into each key, held before the first and after the last."""
    if not keys:
        return default
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0, _), (t1, v1, ease) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * ease((t - t0) / (t1 - t0)) if t1 > t0 else v1
    return keys[-1][1]


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def rotate(x, y, degrees):
    r = math.radians(degrees)
    return x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)


def simplify(samples, tol):
    """Keep a sample only where a straight line from the last kept one would miss by more than tol."""
    kept = [samples[0]]
    i = 0
    while i < len(samples) - 1:
        j = i + 1
        while j + 1 < len(samples):
            (t0, v0), (t1, v1) = samples[i], samples[j + 1]
            if all(abs(v0 + (v1 - v0) * (t - t0) / (t1 - t0) - v) <= tol
                   for t, v in samples[i + 1:j + 1]):
                j += 1
            else:
                break
        kept.append(samples[j])
        i = j
    if len(kept) == 2 and abs(kept[0][1] - kept[1][1]) <= tol:
        return [kept[0]]
    return kept


def clip(keys, s, last):
    """The same line from the first drawn frame s to the last one: keys there and between."""
    if len(keys) == 1:
        return keys
    got = [(s, evaluate(keys, s))] + [k for k in keys if s < k[0] < last]
    if last > s:
        got.append((last, evaluate(keys, last)))
    if all(abs(v - got[0][1]) < 1e-9 for _, v in got):
        return [got[0]]
    return got


def evaluate(keys, t):
    if len(keys) == 1 or t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return keys[-1][1]


def read_back(el, prop, t):
    default = {"x": 0, "y": 0, "rotation": 0, "scale": [1, 1]}[prop]
    v = el.get(prop, default)
    if isinstance(v, list) and v and isinstance(v[0], dict):
        v = evaluate([(k["t"], k["v"][0] if prop == "scale" else k["v"]) for k in v], t)
    elif prop == "scale":
        v = v[0]
    return v


def written(keys, digits):
    """A plain value for one key, or Montagent keyframes, linear between baked frames."""
    if len(keys) == 1:
        return round(keys[0][1], digits)
    out = []
    for i, (t, v) in enumerate(keys):
        k = {"t": t, "v": round(v, digits)}
        if i:
            k["ease"] = "linear"
        out.append(k)
    return out


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

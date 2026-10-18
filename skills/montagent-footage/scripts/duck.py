#!/usr/bin/env python3
"""Duck a music bed under a voice: write the bed's `volume` as ordinary keyframes.

    python3 duck.py <project> --bed <id> --voice <id> (--words <file> | --spans "<s>-<e>,..." | --spans-file <file>)
                    [--under-db -15] [--over-db -6] [--end-db -1.5]
                    [--ramp-ms 200] [--lead-ms 100] [--join-ms 600] [--fade-ms N]
                    [--replace | --check]

Requires Python >= 3.9
Standard library only.
drift-guard: captions.montagent.json --bed bed --voice voice --words media/duck.words.json

Prints <project> with the bed's `volume` rewritten, and a report on stderr. <project> is not
touched on disk.

The voice's spans are milliseconds in the voice source's own time, and the script maps them
onto the timeline through the voice element's `start`, `source_start`, `speed` and `source_end`.
Give exactly one of:

  --words <file>        [{"word", "start", "end"}, ...]; the word is ignored
  --spans "<s>-<e>,..." or --spans-file <file> ([{"start", "end"}, ...])
                        for a voice with no aligner, such as per-sentence clips

It does not listen for silence and does not fall back to the voice element's own `start` and
`end`: with neither input it stops.

The bed goes `under` while the voice speaks, `over` in pauses of at least `join` ms, and `end`
after the last word (an end card). Ramps are `ramp` ms long and start `lead` ms ahead of the
voice. `--fade-ms N` adds a fade to 0 over the last N ms that lands on the bed's last drawn
frame. There is no fade-in argument: a hand-written one is re-added after `--replace`.
Levels are dB, the voice being 0; what is written is linear `volume`, rounded to four decimals,
and the script prints the dB to linear mapping it wrote.

The bed's `volume` is overwritten only if it is a single number. If it already has keyframes
the script stops and says so; pass `--replace` to own the whole curve (that includes its own
earlier output: it does not recognise its own shape).

`--check` writes nothing. It computes what these arguments would write, compares it with the
bed's current `volume`, and exits 0 when they are equal; otherwise it exits non-zero and names
the first instant that differs, with both values. Run it whenever the voice, its trim or speed,
or its words change.

The script ends by running `montagent validate` on the result and printing its findings. It
exits non-zero only on an error. Every review is printed and does not fail the run: a held
level is two equal keyframes, which `validate` reports as `R-EASE-INERT`, and that is expected.
It also prints each `transition` window the keyframes overlap, and changes nothing for it.
`montagent` must be on PATH.
"""

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

# The level defaults, in dB. `ci/test_duck.py` holds them equal to the ones
# docs/research/audio-effects/ducking/check_duck_levels.py checks.
DEFAULTS_DB = {"under_db": -15.0, "over_db": -6.0, "end_db": -1.5}
DEFAULTS_MS = {"ramp_ms": 200, "lead_ms": 100, "join_ms": 600}
DECIMALS = 4


def linear(db):
    """The linear level of a dB figure, as written to the file."""
    return round(10 ** (db / 20), DECIMALS)


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("project")
    ap.add_argument("--bed", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--words")
    ap.add_argument("--spans")
    ap.add_argument("--spans-file")
    for key, value in {**DEFAULTS_DB, **DEFAULTS_MS}.items():
        ap.add_argument("--" + key.replace("_", "-"), dest=key, type=float, default=value)
    ap.add_argument("--fade-ms", type=float, default=0)
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    given = [n for n in ("words", "spans", "spans_file") if getattr(args, n) is not None]
    if len(given) != 1:
        sys.exit("duck: give exactly one span source: --words <file> ([{\"word\", \"start\", \"end\"}], "
                 "ms in the voice's own time), --spans \"<start>-<end>,...\" (ms) or --spans-file <file> "
                 "([{\"start\", \"end\"}]). It does not detect silence or guess from the voice element.")
    if args.replace and args.check:
        sys.exit("duck: --replace writes and --check does not; give one")
    spans = read_spans(args)

    with open(args.project) as f:
        project = json.load(f)
    elements = {e["id"]: e for t in project.get("tracks", []) for e in t["elements"]}
    for label, ident in (("bed", args.bed), ("voice", args.voice)):
        if ident not in elements:
            sys.exit(f"duck: no element with id {ident!r} ({label}) in {args.project}")
    bed, voice = elements[args.bed], elements[args.voice]

    timeline = to_timeline_spans(voice, spans, report)
    if not timeline:
        sys.exit("duck: no span falls inside the voice's source range")
    levels = {k: linear(getattr(args, k)) for k in DEFAULTS_DB}
    keys = ducked(bed, timeline, {"under": levels["under_db"], "over": levels["over_db"],
                                  "end": levels["end_db"], "ramp": args.ramp_ms,
                                  "lead": args.lead_ms, "join": args.join_ms,
                                  "fade": args.fade_ms or None},
                  project["fps"], report)
    report("duck: " + ", ".join(f"{getattr(args, k):g} dB = {levels[k]}" for k in DEFAULTS_DB))

    current = bed.get("volume")
    if args.check:
        return check(current, keys)
    if isinstance(current, list) and not args.replace:
        sys.exit(f"duck: {args.bed!r} already has keyframes on `volume`. This script does not merge "
                 "into them or recognise its own output; pass --replace to have it own the whole curve")
    bed["volume"] = keys
    transitions(project, keys, report)
    json.dump(project, sys.stdout, indent=1, ensure_ascii=False)
    print()
    return validate(args.project, project)


def report(line):
    print(line, file=sys.stderr)


def read_spans(args):
    """[(start, end)] in ms of the voice's source, from whichever input was given."""
    if args.spans is not None:
        out = []
        for part in args.spans.split(","):
            try:
                a, b = part.split("-")
                out.append((float(a), float(b)))
            except ValueError:
                sys.exit(f"duck: --spans wants \"<start>-<end>,...\" in ms; got {part!r}")
        return out
    with open(args.words or args.spans_file) as f:
        return [(float(s["start"]), float(s["end"])) for s in json.load(f)]


def to_timeline_spans(voice, spans, report=report):
    """Spans in the voice source's time -> [{"start", "end"}] on the timeline. Spans that start
    outside the voice's source range are dropped; one that runs past it is cut at its end."""
    src0, src1 = voice["source_start"], voice["source_end"]
    speed = voice.get("speed", 1)
    out = []
    for a, b in sorted(spans):
        if not src0 <= a < src1 or b <= a:
            report(f"dropped span {a:g}-{b:g}: outside the voice's source range")
            continue
        out.append({"start": voice["start"] + (a - src0) / speed,
                    "end": voice["start"] + (min(b, src1) - src0) / speed})
    return out


def on_frame_fn(fps):
    def on_frame(t):
        """The drawn instant nearest to t: frame n is drawn at floor(n * 1000 / fps)."""
        return math.floor(round(t * fps / 1000) * 1000 / fps)
    return on_frame


def last_drawn_fn(fps):
    def last_drawn(end):
        """The last drawn instant before a half-open end."""
        return math.floor((math.ceil(end * fps / 1000) - 1) * 1000 / fps)
    return last_drawn


def ducked(bed, words, duck, fps, report):
    """`under` while the voice speaks, `over` in pauses of at least `join` ms, `end` after the
    last word, and, when `fade` is set, a fade to 0 that lands on the bed's last drawn frame.

    `words` are {"start", "end"} on the timeline; levels are linear; times are ms."""
    on_frame, last_drawn = on_frame_fn(fps), last_drawn_fn(fps)
    # Spans on the frame grid, as `captions.py` snaps its words before ducking.
    words = [{"start": on_frame(w["start"]), "end": on_frame(w["end"])} for w in words]
    under, over, end = duck["under"], duck["over"], duck["end"]
    ramp, lead, join = duck["ramp"], duck["lead"], duck["join"]
    fade = duck.get("fade")
    spans = []
    for w in words:
        if spans and w["start"] - spans[-1][1] < join:
            spans[-1][1] = w["end"]
        else:
            spans.append([w["start"], w["end"]])
    start, stop = bed["start"], last_drawn(bed["end"])
    points = [(start, over)]
    for n, (s, e) in enumerate(spans):
        after = end if n + 1 == len(spans) else over
        points += [(s - lead - ramp, over), (s - lead, under), (e + lead, under), (e + lead + ramp, after)]
        report(f"duck: voice {s}-{e}")
    points = [(on_frame(max(start, min(t, stop))), v) for t, v in points]
    if points[1][0] <= start:
        points[0] = (start, under)

    def level(t):
        for (a, va), (b, vb) in zip(points, points[1:]):
            if a <= t <= b:
                return va if b == a else va + (vb - va) * (t - a) / (b - a)
        return points[-1][1]

    if fade:
        fade_from = on_frame(stop - fade)
        fade_level = level(fade_from)
        if spans:
            up = points[-1][0]
            if up < fade_from:
                report(f"duck: {end} after the last word, from {up} until the fade at {fade_from}")
            else:
                report(f"duck: no end level, the fade at {fade_from} starts before the music is back up")
        points = [p for p in points if p[0] < fade_from] + [(fade_from, fade_level), (stop, 0.0)]
    elif spans:
        report(f"duck: {end} after the last word, from {points[-1][0]}")
    keys = []
    for t, v in points:
        v = round(v, DECIMALS)
        if keys and t <= keys[-1]["t"]:
            keys[-1]["v"] = v
            continue
        key = {"t": t, "v": v}
        if keys:
            key["ease"] = "linear" if v == keys[-1]["v"] else "ease-in-out"
        keys.append(key)
    return keys


def check(current, keys):
    """Exit 0 if the bed's `volume` is what `keys` would write, else name the first difference."""
    if not isinstance(current, list):
        print(f"duck: --check: the bed's volume is {current!r}, not keyframes; these arguments "
              f"would write {len(keys)} keys starting {keys[0]}", file=sys.stderr)
        return 1
    for a, b in zip(current, keys):
        if (a.get("t") != b["t"] or a.get("ease") != b.get("ease")
                or not isinstance(a.get("v"), (int, float)) or format(a["v"], ".4f") != format(b["v"], ".4f")):
            print(f"duck: --check: differs at t={b['t']}: the project has {a.get('t')}={a.get('v')} "
                  f"({a.get('ease')}), these arguments write {b['t']}={b['v']} ({b.get('ease')})", file=sys.stderr)
            return 1
    if len(current) != len(keys):
        longer, side = (current, "the project has") if len(current) > len(keys) else (keys, "these arguments write")
        extra = longer[min(len(current), len(keys))]
        print(f"duck: --check: differs at t={extra['t']}: only {side} a key there ({extra})", file=sys.stderr)
        return 1
    print("duck: --check: the bed's volume is what these arguments write", file=sys.stderr)
    return 0


def transitions(project, keys, report):
    """Name each transition window the keyframes overlap. Changes nothing."""
    t1, t2 = keys[0]["t"], keys[-1]["t"]
    for t in (e for tr in project.get("tracks", []) for e in tr["elements"] if e.get("type") == "transition"):
        if t["start"] < t2 and t["end"] > t1:
            report(f"duck: keyframes {t1}–{t2} overlap transition {t['id']} ({t['start']}–{t['end']})")


def validate(project_path, project):
    """Run `montagent validate` on the result, print its findings, and fail only on an error."""
    # Beside the project, so relative sources resolve the way they will in the real file.
    fd, scratch = tempfile.mkstemp(prefix=".duck-", suffix=".montagent.json",
                                   dir=os.path.dirname(os.path.abspath(project_path)))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(project, f)
        try:
            out = subprocess.run(["montagent", "validate", scratch, "--json"], capture_output=True, text=True)
            text = subprocess.run(["montagent", "validate", scratch], capture_output=True, text=True)
        except FileNotFoundError:
            print("duck: `montagent` is not on PATH, so the result was not validated", file=sys.stderr)
            return 1
    finally:
        os.unlink(scratch)
    print((text.stdout + text.stderr).replace(scratch, project_path).rstrip(), file=sys.stderr)
    try:
        errors = json.loads(out.stdout)["summary"]["error"]
    except (ValueError, KeyError):
        print("duck: could not read `montagent validate`'s verdict", file=sys.stderr)
        return 1
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

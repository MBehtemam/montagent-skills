#!/usr/bin/env python3
"""Turn a word-timings file into captions with the spoken word highlighted, and duck music under the voice.

    python3 captions.py <project> <words> <spec>

Requires Python >= 3.9
Standard library only.
drift-guard: captions.montagent.json media/bed.words.json captions.spec.json

<words> is a JSON list of {"word", "start", "end"}, in milliseconds from the start of the
voice's own source file. Prints <project> with one text element per caption page on the
spec's track, each word a run whose `highlight` is lit while the word is spoken, and a
report on stderr of every timing it repaired. Running it again replaces the tracks it wrote.

Before it sets anything it checks the timings:

  - It listens to the voice with ffmpeg's silencedetect. A word that starts a phrase
    more than 60 ms after the speech does is moved back to where the speech starts, and a
    word that sits wholly inside a silence is reported.
  - Overlapping or out-of-order words are pulled apart.
  - A word shorter than `min_word` is lengthened: first into the pause before it, then
    into the pause after it, then from the next word if that one can spare it.
  - Words outside the voice element's source range are dropped.

Then every time is moved to the frame the project draws it on. Line breaks come from
`montagent measure` on <project>, so the spec's font must already be in `fonts`, and
`montagent` and `ffmpeg` must be on PATH.

<spec> is a JSON file:

    {
      "track": "captions",        required: the caption track's name and id prefix
      "layer": 30,                required
      "voice": "presenter",       required: id of the video or audio element that speaks
      "font": "caption",          required: a key of the project's `fonts`
      "size": 64,                 required
      "color": "#F5F0E6",
      "highlight": "#FF5A36",     required: the spoken word's colour
      "x": 540, "y": 1380,        required: the centre of each page
      "width": 900,               required: the longest a line may be, in px
      "lines": 2,                 most lines on one page
      "gap": 400,                 a pause at least this long (ms) starts a new page
      "min_word": 150,            the shortest a word may be lit (ms)
      "hold": 1000,               the longest a page stays after its last word (ms); it
                                  never outstays the next page's start
      "listen": {"noise": -35, "min": 150},   silencedetect's threshold (dB) and shortest
                                  pause (ms); "listen": false skips the check
      "pill": {"color": "#101418CC", "pad": [28, 16], "radius": 24},   optional box
                                  behind each page, on track "<track>-bg" one layer below
      "duck": {"id": "bed", "under_db": -15, "over_db": -6, "end_db": -1.5, "ramp_ms": 200,
               "lead_ms": 100, "join_ms": 600, "fade_ms": 1000}      optional: rewrites that
                                  audio element's `volume` (the work is `duck.py`'s: see it):
                                  `under_db` while the voice speaks, `over_db` in pauses of at
                                  least `join_ms`, `end_db` after the last word (an end card),
                                  ramps of `ramp_ms` starting `lead_ms` ahead of the voice, and
                                  a fade to 0 over the last `fade_ms` that lands on the element's
                                  last drawn frame (default 1000; 0 for none). Deprecated, and
                                  accepted for one release: the linear `under`, `over`, `end`
                                  and ms `ramp`, `lead`, `join`, `fade`
    }

"""

import json
import math
import os
import re
import subprocess
import sys

from duck import DEFAULTS_DB, DEFAULTS_MS, DECIMALS, ducked, linear, on_frame_fn

# The linear and unsuffixed keys a `duck` entry took before ADR-0177, and the dB and ms keys that
# replace them. Accepted for one release.
OLD_KEYS = {"under": "under_db", "over": "over_db", "end": "end_db", "ramp": "ramp_ms",
            "lead": "lead_ms", "join": "join_ms", "fade": "fade_ms"}
# The one default this script keeps: a fade over the last second, as it always has.
FADE_MS = 1000


def duck_params(duck, report):
    """The `ducked` arguments for a `duck` entry: dB and ms keys, or the old linear ones, which
    pass through as written (to four decimals) and are not converted to dB and back."""
    old = sorted(k for k in OLD_KEYS if k in duck)
    if old:
        report("duck: " + ", ".join(f"`{k}`" for k in old) + " are deprecated and will be removed: "
               "use " + ", ".join(f"`{OLD_KEYS[k]}`" for k in old))
    params = {}
    for k, new in OLD_KEYS.items():
        if new in duck:
            params[k] = linear(duck[new]) if new in DEFAULTS_DB else duck[new]
        elif k in duck:
            params[k] = round(duck[k], DECIMALS) if new in DEFAULTS_DB else duck[k]
        elif new in DEFAULTS_DB:
            params[k] = linear(DEFAULTS_DB[new])
        elif new in DEFAULTS_MS:
            params[k] = DEFAULTS_MS[new]
        else:
            params[k] = FADE_MS
    params["fade"] = params["fade"] or None
    return params


def main(argv):
    if "--help" in argv or "-h" in argv or len(argv) != 3:
        print(__doc__)
        return 0 if "--help" in argv or "-h" in argv else 2
    project_path, words_path, spec_path = argv
    with open(project_path) as f:
        project = json.load(f)
    with open(words_path) as f:
        words = [dict(w) for w in json.load(f)]
    with open(spec_path) as f:
        spec = json.load(f)
    fps = project["fps"]

    on_frame = on_frame_fn(fps)

    def report(line):
        print(line, file=sys.stderr)

    elements = {e["id"]: e for t in project.get("tracks", []) for e in t["elements"]}
    voice = elements.get(spec["voice"])
    if voice is None:
        sys.exit(f"no element with id {spec['voice']!r} in {project_path}")
    speed = voice.get("speed", 1)
    src0, src1 = voice["source_start"], voice["source_end"]

    def to_timeline(t):
        return voice["start"] + (t - src0) / speed

    kept = [w for w in words if src0 <= w["start"] < src1]
    for w in words:
        if w not in kept:
            report(f"dropped {w['word']!r} {w['start']}-{w['end']}: outside the voice's source range")
    words = [{"word": w["word"], "start": to_timeline(w["start"]),
              "end": to_timeline(min(w["end"], src1))} for w in kept]
    first, last = to_timeline(src0), to_timeline(src1)

    # Listen: where does speech actually resume after each pause?
    listen = spec.get("listen", {})
    if listen is not False:
        source = os.path.join(os.path.dirname(os.path.abspath(project_path)), voice["source"])
        pauses = silences(source, listen.get("noise", -35), listen.get("min", 150))
        pauses = [(to_timeline(a), to_timeline(b)) for a, b in pauses]
        for k, w in enumerate(words):
            for a, b in pauses:
                if a <= w["start"] and w["end"] <= b:
                    report(f"{w['word']!r} {w['start']:.0f}-{w['end']:.0f} lies inside a silence "
                           f"({a:.0f}-{b:.0f}): check its timing by ear")
                # The first word after this pause: its start is where speech resumes.
                prev_end = words[k - 1]["end"] if k else first
                if prev_end <= b + 30 and a < w["start"] and b - 60 <= w["start"]:
                    if b + 60 < w["start"]:
                        report(f"{w['word']!r} starts at {w['start']:.0f}, but speech resumes at "
                               f"{b:.0f}: moved its start back")
                        w["start"] = max(b, prev_end)
                    w["heard"] = True

    # Order and overlap.
    for k in range(1, len(words)):
        prev, w = words[k - 1], words[k]
        if w["start"] < prev["end"]:
            report(f"{w['word']!r} starts at {w['start']:.0f}, inside {prev['word']!r}, "
                   f"which ends at {prev['end']:.0f}: moved its start to {prev['end']:.0f}")
            w["start"] = prev["end"]
        w["end"] = max(w["end"], w["start"])

    # Too short to see.
    min_word = spec.get("min_word", 150)
    for k, w in enumerate(words):
        need = min_word - (w["end"] - w["start"])
        if need <= 0:
            continue
        was = (w["start"], w["end"])
        # A start that was heard in the audio stays where it is.
        before = 0 if w.get("heard") else w["start"] - (words[k - 1]["end"] if k else first)
        take = max(0, min(need, before))
        w["start"] -= take
        need -= take
        after = (words[k + 1]["start"] if k + 1 < len(words) else last) - w["end"]
        take = max(0, min(need, after))
        w["end"] += take
        need -= take
        if need > 0 and k + 1 < len(words):
            nxt = words[k + 1]
            take = max(0, min(need, nxt["end"] - nxt["start"] - min_word))
            w["end"] += take
            nxt["start"] += take
            need -= take
        report(f"{w['word']!r} lasted {was[1] - was[0]:.0f} ms ({was[0]:.0f}-{was[1]:.0f}): "
               f"now {w['start']:.0f}-{w['end']:.0f}"
               + (f", still {need:.0f} ms short" if need > 0 else ""))

    # Onto the frame grid, with no sub-frame gap between words that touch.
    frame_ms = 1000 / fps
    for w in words:
        w["start"], w["end"] = on_frame(w["start"]), on_frame(w["end"])
    for k, w in enumerate(words):
        if k + 1 < len(words) and words[k + 1]["start"] - w["end"] < frame_ms:
            w["end"] = words[k + 1]["start"]
        if w["end"] <= w["start"]:
            w["end"] = on_frame(w["start"] + frame_ms)

    # Pages: break at a sentence end, at a long pause, or when the lines are full.
    font, size, width = spec["font"], spec["size"], spec["width"]
    widths = measure(project_path, font, size, [w["word"] for w in words] + ["a a", "a"])
    space = widths[-2] - 2 * widths[-1]
    widths = widths[:-2]
    pages, lines, line_w = [], None, 0.0
    for k, w in enumerate(words):
        new_page = lines is None
        if not new_page:
            prev = words[k - 1]
            new_page = (w["start"] - prev["end"] >= spec.get("gap", 400)
                        or re.search(r"[.!?]$", prev["word"]) is not None)
        if not new_page and line_w + space + widths[k] > width:
            if len(lines) >= spec.get("lines", 2):
                new_page = True
            else:
                lines.append([])
                line_w = 0.0
        if new_page:
            lines = [[]]
            pages.append(lines)
            line_w = 0.0
        if lines[-1]:
            line_w += space
        lines[-1].append(k)
        line_w += widths[k]

    texts = ["\n".join(" ".join(words[k]["word"] for k in line) for line in page) for page in pages]
    sizes = measure(project_path, font, size, texts, whole=True)
    track, layer, pill = spec["track"], spec["layer"], spec.get("pill")
    captions, boxes = [], []
    for n, (page, text, (w_px, h_px)) in enumerate(zip(pages, texts, sizes)):
        ids = [k for line in page for k in line]
        start = words[ids[0]]["start"]
        end = on_frame(words[ids[-1]]["end"] + spec.get("hold", 1000))
        if n + 1 < len(pages):
            end = min(end, words[pages[n + 1][0][0]]["start"])
        end = min(end, project["duration"])
        runs = []
        for i, line in enumerate(page):
            if i:
                runs.append({"text": "\n"})
            for j, k in enumerate(line):
                if j:
                    runs.append({"text": " "})
                runs.append({"text": words[k]["word"], "highlight": {
                    "start": words[k]["start"], "end": min(words[k]["end"], end),
                    "color": spec["highlight"]}})
        el = {"id": f"{track}-{n + 1:02d}", "type": "text", "start": start, "end": end,
              "x": spec["x"], "y": spec["y"], "origin": "center",
              "width": math.ceil(w_px) + 2, "height": math.ceil(h_px),
              "font": font, "size": size}
        if "color" in spec:
            el["color"] = spec["color"]
        el["align"] = "center"
        el["runs"] = runs
        captions.append(el)
        report(f"page {n + 1:02d} {start}-{end}: {text!r}")
        if pill:
            px, py = pill.get("pad", [28, 16])
            box = {"id": f"{track}-bg-{n + 1:02d}", "type": "rect", "start": start, "end": end,
                   "x": spec["x"], "y": spec["y"], "origin": "center",
                   "width": math.ceil(w_px) + 2 * px, "height": math.ceil(h_px) + 2 * py,
                   "fill": pill["color"]}
            if pill.get("radius"):
                box["radius"] = pill["radius"]
            boxes.append(box)

    project["tracks"] = [t for t in project.get("tracks", []) if t["name"] not in (track, f"{track}-bg")]
    if boxes:
        project["tracks"].append({"name": f"{track}-bg", "layer": layer - 1, "elements": boxes})
    project["tracks"].append({"name": track, "layer": layer, "elements": captions})

    duck = spec.get("duck")
    if duck:
        bed = elements.get(duck["id"])
        if bed is None:
            sys.exit(f"duck: no element with id {duck['id']!r}")
        bed["volume"] = ducked(bed, words, duck_params(duck, report), fps, report)

    json.dump(project, sys.stdout, indent=1, ensure_ascii=False)
    print()
    return 0


def silences(source, noise, min_ms):
    """Pauses in the source's audio, as (start, end) ms from the start of the file."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", source, "-map", "0:a:0", "-af",
         f"silencedetect=n={noise}dB:d={min_ms / 1000}", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        sys.exit(f"ffmpeg could not listen to {source}:\n{out.stderr[-2000:]}")
    starts = [float(x) * 1000 for x in re.findall(r"silence_start: (-?[\d.]+)", out.stderr)]
    ends = [float(x) * 1000 for x in re.findall(r"silence_end: ([\d.]+)", out.stderr)]
    return list(zip(starts, ends))


def measure(project_path, font, size, texts, whole=False):
    """Advance widths of each text, or (widest line, height) of each block when `whole`."""
    batch = [{"font": font, "size": size, "runs": [{"text": t}]} for t in texts]
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
    if not whole:
        return [r["ok"]["advance_width"] for r in results]
    return [(r["ok"]["advance_width"], r["ok"]["block_height"]) for r in results]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

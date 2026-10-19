---
name: montagent-footage
description: "Editing real video in Montagent: talking heads and interviews, green-screen keys, subtitles and word-by-word captions, lower-thirds and name bars, picture-in-picture, and music ducked under a voice. Use when a Montagent video starts from recorded footage."
---

# Editing recorded video

Recipes for pieces built on recorded footage. They slot into `montagent`'s loop at the build step; load `montagent` first if you haven't. For a talking head, a presenter clip or an interview cut, open [the talking-head structure](references/talking-head.md) before you plan.

## Start from the footage

Before you write an element, `probe` every clip: its size, frame rate, length and whether it has sound. Then plan the piece on the voice. Its word timings are the clock every caption, cue and duck hangs from, so the timings get checked first (see [Captions](#captions-with-the-spoken-word-highlighted)).

To choose a moment from a long clip (the stretch of a screen recording to show in an insert, say), put the clip alone in a scratch project and call `frame --from 0 --to <its length> --infill-ceiling <ms>`, with the ceiling at a twentieth of the length. One call gives a labelled tile every few seconds; `frame --at` any tile you want closer.

## Recipes

Every recipe gives starting ranges, not answers. Each ends in a **look step**: load `montagent-craft`, then look where the step says before you move on.

### Place the footage

```json
{
  "frame": {"width": 1080, "height": 1920}, "fps": 30, "background": "#FF5A36", "duration": 6000, "output": "out/presenter.mp4",
  "tracks": [
    {"name": "presenter", "layer": 10, "elements": [
      {"id": "presenter", "type": "video", "start": 0, "end": 6000, "source": "media/clip.mp4", "source_start": 0, "source_end": 6000, "x": 540, "y": 2160, "origin": "bottom-center", "width": 3413, "height": 1920, "fit": "cover", "effects": [{"name": "chroma", "color": "#00FF00", "tolerance": 0.2, "softness": 0.08, "spill": 0.9}]}
    ]}
  ]
}
```

- **Wide footage in a tall frame:** make the element as tall as the frame and as wide as the source's aspect gives (1920 tall is 3413 wide for 16:9), then slide it sideways to keep the speaker centred.
- **Eyes:** 25–35 % of the way down the frame. Lower the element's `bottom-center` past the frame's bottom edge to get there; cutting off the legs is normal.
- **Headroom:** 4–8 % of the frame height above the hair.
- **A take shorter than the piece:** `"overrun": "hold"` freezes its last frame. Keep the freeze under half a second, or end the piece earlier.
- **A freeze frame inside a clip, a speed ramp, or a reverse:** write `source_time` in place of `source_start` and `source_end`: a literal freezes one moment, and keys of source milliseconds against timeline `t` ramp (a flat pair freezes, a falling pair reverses). A clip with `source_time` is silent at `volume` 0, so put its sound on its own `audio` element.
- **The take's own sound:** the voice stays at `volume` 1.0. Everything else is mixed under it.
- **Look:** `frame` at the start, the middle and the last drawn frame, and check the eyes sit in the band and nothing important is cut at the frame's sides.

### Green-screen key

`chroma` on the footage element keys the screen out. Start here:

- **`color`:** the screen's pure colour, `#00FF00` for a green screen. A lit screen that has drifted a little towards blue or yellow keys the same at these tolerances, so you don't need to sample it.
- **`tolerance`:** 0.2 (range 0.18–0.25). Above about 0.3 the key eats black hair, white collars and dark clothes.
- **`softness`:** 0.08 (range 0.05–0.1).
- **`spill`:** 0.9 (range 0.9–1.0).

Check it before anything else goes on top:

1. **Three lossless crops.** `frame --crop <x,y,w,h> --png` at the hair, at a shoulder or sleeve edge, and at the hands, over the ground you will deliver on. A crop comes back at true scale, so a 200–400 px box is enough. <!-- workaround: #543 · replaced by: a fringe and hole count from measure on a keyed element -->
2. **Done already?** Hair, collar and hands solid, with at most a 1–2 px dark, olive or tan line along the edges: the key is done, so move on. That line is the **edge floor**: every setting from 0.12 to 0.3 leaves it, and `spill` has already turned it from green to tan, so a green-pixel count reads zero on it. <!-- workaround: #543 · replaced by: a fringe and hole count from measure on a keyed element -->
3. **Otherwise, one fix per defect.** The ground showing through hair, a collar or dark clothes: lower `tolerance` by 0.05. A pale or green halo wider than the edge floor: raise `tolerance` by 0.03, or `softness` by 0.03. Crop again and go back to 2. Three settings at most, all on the one keyed element: keyed copies split by region multiply render time and still leave a seam.
4. **Drift.** `measure` the keyed element. Its opaque share should stay within a point or two across the take. A step means the lighting changed there: key `tolerance` with a keyframe either side of the step, or cut the element at that frame and key each part on its own.

- **Look:** `frame` the whole picture at two moments where the speaker moves most, and check the outline holds.

### Captions with the spoken word highlighted

Captions come from the supplied word timings, through the bundled script, not by hand. `python3 scripts/captions.py <project> <words> <spec>` (run it with `--help` for the spec) checks the timings, breaks the words into pages of one or two lines with `measure`, gives each word a `highlight` window while it is spoken, and prints the project with the captions added. It reports every repair on stderr. **Read that report**: it is the timing check.

- **What it checks:** a word that starts a phrase after the speech has already resumed (a supplied "Now" 110 ms late and 20 ms long is the classic case), a word that sits inside a silence, overlapping words, and words too short to see. Short words are lengthened to `min_word` (150 ms): into the pause after, then from the next word. A reported word inside a silence means the file is misaligned there: fix the file, then run it again.
- **Size:** 56–72 px on a 1080-wide frame, bold, one light colour for the line and the brand's accent for the spoken word.
- **Lines:** at most two, `width` about 80 % of the frame width. A page breaks at a sentence end or a pause of 400 ms or more.
- **Ground:** a `pill` of the darkest brand colour at 80–85 % alpha (`CC`–`D9`) reads over any footage. `pad` 28–36 px across and 14–20 px down, `radius` 20–28. <!-- guard-ok: min_word pill pad -->
- **Placement:** below the chin and clear of the bottom 15–20 % of a tall frame, where players draw their controls. On 1080×1920 that is a centre at about `y` 1350–1450. On a wide frame, centre it 10–14 % up from the bottom.
- **Pages** stay up until the next page starts, or 1 s past their last word when a longer pause follows.

It writes real captions, so act on the caption findings `validate` raises on them.

- **Look:** `frame --from --to` over one page: each lit word is its own tile. Check each tile lights exactly one word, in speaking order, and the box stays clear of the face. Then `frame --at` the first frame after the longest pause, and check the new page is up and nothing is lit early.

### Name bar over footage

A lower-third wipes on and off. Footage isn't a flat colour, so the occluder wipe from `montagent-motion` can't reveal the bar itself. Instead the bar **grows from its edge**, and its text is revealed by an occluder in the **bar's own colour**, which is flat.

```json
{
  "frame": {"width": 1080, "height": 1920}, "fps": 30, "background": "#6E7B8B", "duration": 7000, "output": "out/namebar.mp4",
  "fonts": {"bold": [{"file": "fonts/Inter-Bold.ttf"}]},
  "fontVendor": {"fonts/Inter-Bold.ttf": {"licence": "OFL-1.1", "source": "https://github.com/rsms/inter", "sha256": "288316099b1e0a47a4716d159098005eef7c0066921f34e3200393dbdb01947f"}},
  "tracks": [
    {"name": "bar", "layer": 20, "elements": [
      {"id": "bar", "type": "rect", "start": 1000, "end": 6534, "x": 64, "y": 1160, "origin": "center-left", "width": 760, "height": 160, "fill": "#101418", "radius": 8, "scale": [{"t": 1000, "v": [0.0, 1.0]}, {"t": 1300, "v": [1.0, 1.0], "ease": [0.65, 0, 0.35, 1]}, {"t": 6266, "v": [1.0, 1.0], "ease": "linear"}, {"t": 6533, "v": [0.0, 1.0], "ease": [0.65, 0, 0.35, 1]}]}
    ]},
    {"name": "bar-edge", "layer": 21, "elements": [
      {"id": "bar-edge", "type": "rect", "start": 1000, "end": 6534, "x": 64, "y": 1160, "origin": "center-left", "width": 12, "height": 160, "fill": "#FF5A36"}
    ]},
    {"name": "bar-name", "layer": 22, "elements": [
      {"id": "bar-name", "type": "text", "start": 1300, "end": 6266, "x": 108, "y": 1128, "origin": "center-left", "width": 400, "height": 70, "font": "bold", "size": 58, "color": "#F5F0E6", "runs": [{"text": "Montagent"}], "caption": false}
    ]},
    {"name": "bar-line", "layer": 22, "elements": [
      {"id": "bar-line", "type": "text", "start": 1300, "end": 6266, "x": 108, "y": 1196, "origin": "center-left", "width": 560, "height": 44, "font": "bold", "size": 34, "color": "#F5F0E6", "runs": [{"text": "Video your agent can read"}], "caption": false}
    ]},
    {"name": "bar-cover", "layer": 23, "elements": [
      {"id": "bar-cover-on", "type": "rect", "start": 1300, "end": 1700, "x": 800, "y": 1160, "origin": "center-right", "width": 716, "height": 140, "fill": "#101418", "scale": [{"t": 1300, "v": [1.0, 1.0]}, {"t": 1666, "v": [0.0, 1.0], "ease": [0.65, 0, 0.35, 1]}]},
      {"id": "bar-cover-off", "type": "rect", "start": 6000, "end": 6266, "x": 84, "y": 1160, "origin": "center-left", "width": 716, "height": 140, "fill": "#101418", "scale": [{"t": 6000, "v": [0.0, 1.0]}, {"t": 6233, "v": [1.0, 1.0], "ease": [0.65, 0, 0.35, 1]}]}
    ]}
  ]
}
```

- **On:** the bar grows from its left edge over 250–350 ms, `[0.65, 0, 0.35, 1]`. The text and its cover start the frame the bar is fully grown (never earlier, or the cover shows over the footage). The cover shrinks about its far edge over 300–400 ms, uncovering the text in reading order.
- **Off,** starting on its cue: the cover grows back over the text in 200–300 ms, then the bar shrinks back to its edge over 250–300 ms. The whole bar is gone 450–600 ms after the cue.
- **Size:** bar 130–180 px tall on a 1080-wide frame, name 52–64 px, second line 30–38 px. An accent strip 8–16 px wide on the leading edge.
- **Cover:** exactly the bar's `fill`, 20 px inside the bar's ends and 10 px inside its top and bottom, above the text.
- **Place:** 48–80 px in from the frame's side, clear of the caption box and of the speaker's face, usually at 55–65 % of a tall frame's height.
- **Look:** `frame --from --to --keyframes` over 1 s from each cue, and check no cover shows beyond the bar on any tile. `frame --at` the bar at rest, and check its left edge lines up with the caption box's margin.

### Circular picture-in-picture

Show a second clip in a circle: a video element with a circle `mask`, a ring behind it, and a pop on the overshoot bezier.

```json
{
  "frame": {"width": 1080, "height": 1920}, "fps": 30, "background": "#6E7B8B", "duration": 6000, "output": "out/pip.mp4",
  "tracks": [
    {"name": "pip-ring", "layer": 30, "elements": [
      {"id": "pip-ring", "type": "ellipse", "start": 1000, "end": 5500, "x": 800, "y": 900, "origin": "center", "width": 384, "height": 384, "fill": "#F5F0E6", "scale": [{"t": 1000, "v": [0.0, 0.0]}, {"t": 1400, "v": [1.0, 1.0], "ease": [0.34, 1.56, 0.64, 1]}, {"t": 5233, "v": [1.0, 1.0], "ease": "linear"}, {"t": 5466, "v": [0.0, 0.0], "ease": "ease-in"}], "effects": [{"name": "shadow", "dx": 0, "dy": 16, "radius": 40, "color": "#101418", "opacity": 0.35}]}
    ]},
    {"name": "pip", "layer": 31, "elements": [
      {"id": "pip", "type": "video", "start": 1000, "end": 5500, "source": "media/clip.mp4", "source_start": 10000, "source_end": 14500, "volume": 0, "x": 800, "y": 900, "origin": "center", "width": 640, "height": 360, "fit": "contain", "scale": [{"t": 1000, "v": [0.0, 0.0]}, {"t": 1400, "v": [1.0, 1.0], "ease": [0.34, 1.56, 0.64, 1]}, {"t": 5233, "v": [1.0, 1.0], "ease": "linear"}, {"t": 5466, "v": [0.0, 0.0], "ease": "ease-in"}], "effects": [{"name": "mask", "shape": "circle", "x": 140, "y": 0, "width": 360, "height": 360}]}
    ]}
  ]
}
```

- **The circle's rect:** a square as tall as the element. Its `x` chooses which part of the picture shows. The centre is `(width - height) / 2`, and that is the one to use: the pop scales about the element's `origin`, so a circle moved off the centre drifts sideways as it grows. To show another part of the picture, pick a `source_start` where that part sits in the middle, or make the element larger and set its `x` so the part lands in the circle, then key `x` on the pop's curve so the circle's centre holds still.
- **Size:** 30–40 % of the frame's width across. The ring is 12–24 px wider than the circle, in the ground's lightest colour, with a soft `shadow`.
- **Pop:** 350–450 ms on `[0.34, 1.56, 0.64, 1]` for both, from scale 0, on the same keys. Exit in 200–300 ms, `ease-in`, back to 0.
- **Timing:** in when the speaker first names the thing it shows, out a beat before the end so the close is clean.
- **Place:** beside the speaker at chest height, clear of the face and the caption box, and 40 px or more from the frame's edge.
- **Sound:** `volume` 0 unless the clip's own sound is the point.
- **Look:** `frame` at the pop's peak (start plus 40 % of its length) and check the circle clears the face and the frame edge. `frame` at rest and check the part that matters is inside the circle.

### Music under a voice

The music ducks while the voice speaks and comes back up in the pauses. `scripts/duck.py` writes it as ordinary `volume` keyframes on the music element, from the voice's word timings (`--words`, a `[{word, start, end}]` file in the voice's own source time) or from spans you give it (`--spans "500-1500,2600-3900"` or `--spans-file`, for a voice with no aligner). It does not listen for silence and does not guess from the voice element: with neither input it stops.

```
python3 scripts/duck.py project.montagent.json --bed music --voice voice --words voice.words.json > out.json
```

One bed under one voice per call; several beds are several calls, and several voices are one merged span list. A project that has `captions.py` run on it can instead give the captions spec a `duck` entry naming the music element, and `captions.py` calls this script (its old linear keys are deprecated). <!-- guard-ok: duck -->

- **Loudness first:** give the voice `normalize_loudness` at `target_lufs` -23 and the music -38, 15 LU under the voice. The target is a number you write; nothing derives the bed's from the voice's. The duck's `volume` applies after it, so the music ends at -38 plus the duck's dB.
- **Levels,** in dB with the voice at 0, and the linear `volume` each writes: `--under-db` −15 (0.18) while the voice speaks, `--over-db` −6 (0.5) in pauses, `--end-db` −1.5 (0.84) after the last word. The script prints the dB to linear mapping it wrote.
- **Pauses:** only a pause of 600 ms or more (`--join-ms`) comes back up. Shorter ones stay down, or the music pumps.
- **Ramps:** 150–250 ms (`--ramp-ms`, 200), starting 100 ms before the voice (`--lead-ms`, 100), so the first syllable is already clear.
- **After the last word:** an end card or a closing hold has nothing left to duck for, so the music comes back up near full, not to the pause level. Left at −6 dB it plays 5 dB quieter than a mix that brings it back up.
- **End:** `--fade-ms 1000` adds a fade to 0 over the last 0.8–1.5 s, landing on the piece's last drawn frame. It is off by default. When the voice speaks almost to the end, the fade starts before the music is back up, and the script reports that there is no end level.
- **A music element that already has keyframes:** the script refuses and names `--replace`, which makes it own the whole `volume` curve, its own earlier output included; it never merges. A fade-in is not an argument: write one by hand after `--replace`.
- **Retime checklist.** The keyframes are not tied to the voice, so when the voice element, its trim or its speed, or its words file changes, run the same command with `--check`. It writes nothing, exits 0 if the music's `volume` is what the arguments would write, and otherwise names the first instant that differs. If it exits non-zero, run it again with `--replace`, and then add back any hand-written fade-in. If the words file is gone, regenerate it from the aligner first.
- The script ends by running `montagent validate` and printing the findings; it exits non-zero only on an error. It writes each held level as two equal keyframes, which `validate` reports as `R-EASE-INERT`, and that review is expected on a duck: [findings.md](../montagent/references/findings.md) covers it. It also prints each `transition` whose window overlaps the keyframes, and changes nothing for it.
- **Look:** `query --at` in the middle of a spoken phrase, in the longest pause and on the last drawn frame, and check the music's `volume` reads under, over and, with a fade, 0. With an end card, also check it reads the end level in the middle of the card.

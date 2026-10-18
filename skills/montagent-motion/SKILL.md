---
name: montagent-motion
description: "Motion graphics and titles in Montagent: launch spots, product and social ads, intros and outros, kinetic and typed text, logo reveals and loops, wipes, pops, colour changes, card flips and door swings in perspective, and trailer effects (slammed titles, glitch cuts, HUDs). Use when a Montagent video is built from graphics and text rather than footage or a character."
---

# Motion graphics and titles

Recipes for pieces built from shapes, stills and text. They slot into `montagent`'s loop at the build step; load `montagent` first if you haven't.

Open the reference file for the kind of piece before you plan it:

| The piece | Open |
|---|---|
| Launch spot, product or social ad, intro, outro | [the launch-spot structure](references/launch-spot.md) |
| Logo reveal, logo sting, anything that loops | [the logo loop](references/logo-loop.md) |
| Trailer, or any slammed, glitched, flashing or HUD effect | [trailer effects](references/trailer.md) |

For a new piece or a redesign, read [creative direction](references/creative-direction.md) before choosing the layout. It covers visual concepts, composition and choreography in native Montagent. For a specific edit, read only the relevant recipe and preserve the existing direction.

## Plan on a beat sheet

Before you write an element, write the **beat sheet**: every entrance, colour change, cut and exit in one table, each on a beat of the grid `montagent-craft` gives (its tempo, downbeat, frame snapping, and which events go on beats).

Build the project with a generator script from the beat sheet, so a retime is a one-line edit.

## Recipes

Every recipe gives starting ranges, not answers. Each ends in a **look step**: load `montagent-craft`, then look where the step says before you move on.

### Pop

An entrance with a small overshoot that settles. The overshoot is the curve: one keyframe pair with a bezier whose `y` goes above 1, not three keyframes.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 2000, "output": "out/pop.mp4",
  "tracks": [
    {"name": "badge", "layer": 10, "elements": [
      {"id": "badge", "type": "ellipse", "start": 500, "end": 2000, "x": 960, "y": [{"t": 500, "v": 580}, {"t": 900, "v": 540, "ease": [0.34, 1.56, 0.64, 1]}], "origin": "center", "width": 240, "height": 240, "fill": "#FF5A36", "scale": [{"t": 500, "v": [0.5, 0.5]}, {"t": 900, "v": [1.0, 1.0], "ease": [0.34, 1.56, 0.64, 1]}]}
    ]}
  ]
}
```

- **Length:** 300–450 ms. Shorter snaps, longer floats.
- **Start scale:** 0.5–0.7 for text and cards; 0 for small shapes and badges.
- **Overshoot:** `[0.34, 1.56, 0.64, 1]` peaks about 10 % over. Raise its second number to 1.8 for something playful, or lower it to 1.3 for something corporate. Keep one curve for every pop in a piece.
- **Rise:** 20–60 px of travel on `y` with the same curve adds weight. Skip it on pops that sit in a row.
- **Stagger:** one beat when each item lands on its own beat; 60–120 ms between items inside one beat.
- **Look:** `frame` at the start plus 40 % of the length, where the overshoot peaks, and check nothing clips the frame edge or a neighbour. Then `preview` a span from just before the first pop to just after the last.

### Hold, then clear

An entrance's last keyframe already holds, so a hold costs nothing. An exit starts with a keyframe at the held value, at the moment the exit begins. `validate` reports that keyframe as `R-EASE-INERT`, and the findings guide explains why that's expected.

- **Exit length:** 200–350 ms, `ease-in`. Exits run faster than entrances.
- **Exit move:** a fade plus 20–40 px of travel, or scale down to 0.9. For a hard cut, use a single `step` keyframe to the new value (see the starter project's title).
- **Hold length:** the reading time `montagent-craft` gives.
- **Group exits:** the whole group leaves together, or staggered 30–60 ms in reading order.
- **Look:** `frame` on the last drawn frame before the exit, and check the whole group is fully in and at rest.

### Colour change on a word

Recolour a word inside its line with a `highlight` on that word's run, starting on the beat. This keeps one element: there's no second copy to crossfade, and the element's own colour stays the line's colour.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 3000, "output": "out/accent.mp4",
  "fonts": {"title": [{"file": "fonts/Inter-Bold.ttf"}]},
  "fontVendor": {"fonts/Inter-Bold.ttf": {"licence": "OFL-1.1", "source": "https://github.com/rsms/inter", "sha256": "288316099b1e0a47a4716d159098005eef7c0066921f34e3200393dbdb01947f"}},
  "tracks": [
    {"name": "line", "layer": 20, "elements": [
      {"id": "line", "type": "text", "start": 0, "end": 3000, "x": 960, "y": 540, "origin": "center", "width": 1600, "height": 140, "font": "title", "size": 110, "color": "#F5F0E6", "align": "center", "runs": [{"text": "Video your agent can "}, {"text": "read.", "highlight": {"start": 2000, "end": 3000, "color": "#FF5A36"}}], "caption": false}
    ]}
  ]
}
```

- **Timing:** the change lands on a beat, never on the word's entrance. Give the eye at least half a beat to read the word first.
- **Emphasis:** when the word is its own element, a scale bump on the same beat (1.0 to 1.06–1.1 and back over 200–300 ms) makes the change land.
- **Look:** `frame` one frame before and one frame after the change, and check only the one word changed.

### Kinetic and typed text

When every letter, word or line shares one motion curve on a regular step (`every` ms), keep a single `text` element and stagger it with `units` (`by`: `letter`, `word` or `line`; `order`: `forward`, `reverse`, `center_out` or `edges_in`). Here a headline evaporates into focus from its centre outward:

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 2000, "output": "out/evaporate.mp4",
  "fonts": {"title": [{"file": "fonts/Inter-Bold.ttf"}]},
  "fontVendor": {"fonts/Inter-Bold.ttf": {"licence": "OFL-1.1", "source": "https://github.com/rsms/inter", "sha256": "288316099b1e0a47a4716d159098005eef7c0066921f34e3200393dbdb01947f"}},
  "tracks": [
    {"name": "title", "layer": 20, "elements": [
      {"id": "evaporate", "type": "text", "start": 0, "end": 2000, "x": 960, "y": 540, "origin": "center", "width": 1400, "height": 160, "font": "title", "size": 108, "color": "#F5F0E6", "align": "center", "runs": [{"text": "SHARP FOCUS"}], "units": {"by": "letter", "order": "center_out", "every": 45, "y": [{"t": 0, "v": 20}, {"t": 360, "v": 0, "ease": "ease-out"}], "opacity": [{"t": 0, "v": 0}, {"t": 360, "v": 1, "ease": "ease-out"}], "blur": [{"t": 0, "v": 24}, {"t": 360, "v": 0, "ease": "ease-out"}]}, "caption": false}
    ]}
  ]
}
```

- **Evaporate / optical focus-in (`blur`):** key `blur` inside `units` from `16`–`32` px down to `0` over 300–450 ms (`ease-out`), paired with `opacity` (`0 -> 1`) and a small `y` lift (`16`–`28` px `-> 0`) or `scale` (`[1.08, 1.08] -> [1.0, 1.0]`). Once `blur` reaches `0` and `opacity` reaches `1`, the renderer takes the fast path with zero extra layer cost.
- **Symmetric orders (`center_out`, `edges_in`):** `center_out` starts on the middle unit (or middle pair when the count is even) and steps outward to both ends; `edges_in` starts on the first and last units together and converges on the middle.
- **Travelling wave (`A -> peak -> A`):** instead of an After Effects Range Selector (`triangle`, `round` or `smooth`), write a three-keyframe return curve in `units` — for example `"y": [{"t": 0, "v": 0}, {"t": 180, "v": -28, "ease": "ease-out"}, {"t": 360, "v": 0, "ease": "ease-in-out"}]` (or a `scale` / `blur` pulse) — and let `every` ripple the peak across the line. To single out one word or letter with custom timing, split it into its own run with `unit`. <!-- guard-ok: triangle smooth -->
- **Keep glyphs as `text` (never convert glyphs to `path`):** `path` elements have one contour (`points` with no `holes`), so converting multi-contour glyphs (`O`, `A`, `B`, `8`, `i`, `?`, `%`) to `path` fills inner counters solid or drops islands (ADR-0224). Keep text as `text` and style or animate it with `stroke`, `units`, `path` and `effects`. <!-- guard-ok: holes i -->
- **Irregular beat times or typing cursor (`scripts/type_on.py`):** when words land on irregular beat timestamps or letters need a stepping `cursor`, run `python3 scripts/type_on.py <project> <spec>` (`--help` for the spec). It measures the line with `measure` and emits one `text` element per unit (`"by": "word"` with `"enter": "pop"` and `times` / `highlights`, or `"by": "letter"` at 60–150 ms with a blinking `cursor`), marking each `caption: false`. <!-- guard-ok: python3 times highlights cursor -->
- **Tracked titles:** do not split the title into letters. Write one `text` element with `letter_spacing`, in thousandths of an em (`size × letter_spacing / 1000` px after each letter; negative tightens). Key it to drift a title apart: `"letter_spacing": [{"t": 0, "v": 0}, {"t": 800, "v": 120, "ease": [0.65, 0, 0.35, 1]}]`. Any non-zero value switches the optional ligatures off, and a joining script such as Arabic takes no spacing.
- **Vertical columns and sideways spines:** Montagent has no `writing_mode` property (ADR-0224). For an **upright stacked column** (CJK vertical copy or a stacked marquee), join graphemes with `\n` (`"text": "東\n京\n都"`) inside a narrow `text` box with `"align": "center"` and `"line_height": 1.0` or `1.1`; keep 2–3 horizontal digits or Latin initials on one line (`"text": "第\n25\n回"`, Tate-chu-yoko) and stagger with `"by": "line"` so the horizontal number moves as one unit. For a **sideways Latin spine**, set a horizontal `text` element and rotate it with `"rotation": -90` (reads bottom-to-top) or `"rotation": 90` (reads top-to-bottom). <!-- guard-ok: writing_mode -->
- **Look:** `preview` the span of the line coming on. Then `frame` it at rest, and check the spacing reads as one line, with no gap wider at a word or letter boundary.

### Reveal by wipe

A wipe uncovers something by sliding an edge across it. Put an **occluder** above the thing: a rect filled with exactly what is behind the thing. Then shrink the occluder about its far edge, so its near edge sweeps across. An accent bar riding that edge makes the wipe read as deliberate.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 2000, "output": "out/wipe.mp4",
  "tracks": [
    {"name": "mark", "layer": 10, "elements": [
      {"id": "mark", "type": "image", "start": 0, "end": 2000, "source": "media/still.png", "x": 960, "y": 540, "origin": "center", "width": 360, "height": 360, "fit": "contain"}
    ]},
    {"name": "occluder", "layer": 11, "elements": [
      {"id": "occluder", "type": "rect", "start": 0, "end": 1000, "x": 1160, "y": 540, "origin": "center-right", "width": 400, "height": 400, "fill": "#101418", "scale": [{"t": 400, "v": [1.0, 1.0]}, {"t": 900, "v": [0.0, 1.0], "ease": [0.65, 0, 0.35, 1]}]}
    ]},
    {"name": "edge", "layer": 12, "elements": [
      {"id": "edge", "type": "rect", "start": 400, "end": 1000, "x": [{"t": 400, "v": 760}, {"t": 900, "v": 1160, "ease": [0.65, 0, 0.35, 1]}], "y": 540, "origin": "center", "width": 16, "height": 420, "fill": "#FF5A36", "opacity": [{"t": 900, "v": 1.0}, {"t": 1000, "v": 0.0, "ease": "ease-in"}]}
    ]}
  ]
}
```

- **Length:** 400–600 ms, `[0.65, 0, 0.35, 1]`: a sweep that starts and ends gently.
- **Occluder:** 20–40 px larger than the thing on every side, and the same fill as the ground behind it. The start keyframe sits where the wipe begins, so the thing stays covered until then.
- **Edge bar:** 8–24 px wide, 5–10 % taller than the occluder, moving on the same curve and time. It leaves over 100–200 ms once the sweep is done.
- **Direction:** wipe in the reading direction; to wipe off, grow the occluder back from the near edge.
- **Busy ground:** an occluder only works over a flat colour. Over a photo, a gradient or footage, key the element's own `mask` instead: `{"name": "mask", "shape": "rect", "x": 0, "y": 0, "width": [{"t": 400, "v": 0}, {"t": 900, "v": 400, "ease": [0.65, 0, 0.35, 1]}], "height": 400}` uncovers a 400 × 400 element from its left edge, with no occluder. The rect is element-local, from the element's top-left; a mask of zero `width` hides the element, so the reveal starts covered. Add `feather` for a soft edge.
- **Look:** `frame` at the middle of the sweep and check the edge bar covers the occluder's edge exactly; then `frame` just after the sweep and check nothing of the occluder is left.

### Hand over with a push, slide or wipe

To move from one card, still or scene to the next with motion, bridge the two with a `transition` of kind `push`, `slide` or `wipe`. Keyed `x` on both elements would drift apart at the join; the transition keeps the two halves joined to the pixel, and `validate` checks it.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 3000, "output": "out/handover.mp4",
  "tracks": [
    {"name": "first", "layer": 10, "elements": [
      {"id": "card-1", "type": "rect", "start": 0, "end": 1700, "x": 0, "y": 0, "origin": "top-left", "width": 1920, "height": 1080, "fill": "#FF5A36"}
    ]},
    {"name": "second", "layer": 11, "elements": [
      {"id": "card-2", "type": "rect", "start": 1200, "end": 3000, "x": 0, "y": 0, "origin": "top-left", "width": 1920, "height": 1080, "fill": "#2E86FF"}
    ]},
    {"name": "handover", "layer": 12, "elements": [
      {"id": "handover", "type": "transition", "start": 1200, "end": 1700, "kind": "push", "from": "card-1", "to": "card-2", "direction": "left", "ease": [0.65, 0, 0.35, 1]}
    ]}
  ]
}
```

- **Kind:** `push` when the two belong to one strip (pages, steps, a carousel); `slide` when the new one lands on top of a still one; `wipe` when the old one should stay put and be cut away.
- **Direction:** the way the motion travels. `left` brings the new one in from the right, which follows the reading direction.
- **Length:** 400–600 ms, `[0.65, 0, 0.35, 1]`. The transition's `start` and `end` are exactly the time the two share.
- **Slide stacking:** in a `slide`, the incoming element must sit on the higher `layer`.
- **Look:** `frame` at the middle of the window and check the join; then `preview` across it.

### Grow from an edge

Bars, underlines, dividers and progress lines grow out of the edge they stand on. Set `origin` to that edge (`bottom-center` for a bar on a baseline, `center-left` for an underline) and scale the one axis from 0 to 1.

- **Length:** 400–600 ms, `[0.16, 1, 0.3, 1]` (fast out, long settle).
- **A set of bars:** stagger by a quarter to half a beat, in reading order. The heights tell the story, so keep them honest to the data or the claim.
- **Labels:** each label arrives when its own bar settles (a 150–250 ms fade or a small pop), not with the whole set.
- **Baseline:** it draws first, growing from its centre over 200–300 ms, and the bars start as it lands.
- **Look:** `frame` halfway through the tallest bar's growth and check every bar is anchored to the baseline; then `frame` at rest.

### Push-in on a still

Screenshots and product stills get a slow push while on screen. A crossfade between two stills keeps the push going across the join.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#F5F0E6", "duration": 5000, "output": "out/push.mp4",
  "tracks": [
    {"name": "shot-1", "layer": 10, "elements": [
      {"id": "shot-1", "type": "image", "start": 0, "end": 3000, "source": "media/still.png", "x": 960, "y": 540, "origin": "center", "width": 720, "height": 720, "fit": "contain", "scale": [{"t": 0, "v": [1.0, 1.0]}, {"t": 3000, "v": [1.036, 1.036], "ease": "linear"}], "effects": [{"name": "mask", "shape": "rect", "radius": 28}, {"name": "shadow", "dx": 0, "dy": 24, "radius": 48, "color": "#101418", "opacity": 0.3}]}
    ]},
    {"name": "shot-2", "layer": 11, "elements": [
      {"id": "shot-2", "type": "image", "start": 2500, "end": 5000, "source": "media/still.png", "x": 960, "y": 540, "origin": "center", "width": 720, "height": 720, "fit": "contain", "scale": [{"t": 2500, "v": [1.03, 1.03]}, {"t": 5000, "v": [1.06, 1.06], "ease": "linear"}], "effects": [{"name": "mask", "shape": "rect", "radius": 28}, {"name": "shadow", "dx": 0, "dy": 24, "radius": 48, "color": "#101418", "opacity": 0.3}]}
    ]},
    {"name": "joins", "layer": 12, "elements": [
      {"id": "join", "type": "transition", "start": 2500, "end": 3000, "kind": "crossfade", "from": "shot-1", "to": "shot-2"}
    ]}
  ]
}
```

- **Push:** 4–8 % over the whole run of stills, `linear`. A push that eases in or out reads as a camera move, not a drift.
- **Across a crossfade:** plan one push from the first still's start to the last still's end. Each still's keyframes are that push's values at its own `start` and `end`, so both stills match through the crossfade.
- **Crossfade:** one beat (400–600 ms), ending on the beat the second still owns.
- **Frame:** a `mask` with a 20–32 px `radius`, plus a `shadow` with `dy` 16–32, `radius` 40–64 and `opacity` 0.25–0.4, in the ground's darkest colour.
- **Look:** `preview` across the crossfade and check the two stills hold the same size through the join, with no jump.

### Morph one shape into another

A morph, shape to shape, is one `path` whose `points` are keyed, and the tween runs number by number between the keyframe values. Those values must be matching vertex lists: the same vertex count, and each vertex the same handles. Nothing matches them for you, so write them to match. Here a square becomes a triangle: the triangle's apex is written twice, and the square's top edge closes into it.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 2000, "output": "out/morph.mp4",
  "tracks": [
    {"name": "shape", "layer": 10, "elements": [
      {"id": "shape", "type": "path", "start": 0, "end": 2000, "x": 960, "y": 540, "origin": "center", "width": 400, "height": 400, "closed": true, "fill": "#FF5A36", "points": [{"t": 500, "v": [{"at": [40, 40]}, {"at": [360, 40]}, {"at": [360, 360]}, {"at": [40, 360]}]}, {"t": 1300, "v": [{"at": [200, 40]}, {"at": [200, 40]}, {"at": [360, 360]}, {"at": [40, 360]}], "ease": [0.65, 0, 0.35, 1]}]}
    ]}
  ]
}
```

1. **Pad the shorter list** with coincident vertices (the same `at` twice), and write `[0, 0]` for a handle one side lacks. Neither changes the drawing: a coincident vertex adds a segment that draws nothing, and `[0, 0]` draws the same as a missing handle.
2. **Match the start vertex**, so each vertex travels to the nearest point of the other shape and not across it. Start both lists at the same place, the top for instance.
3. **Match the winding direction**: both lists clockwise on screen, or both counter-clockwise. Otherwise the outline turns inside out on the way.
4. **Split a segment for a smoother in-between.** Padding at a vertex starts several vertices from one point. Instead, add the extra vertex partway along a segment, near the vertex of the other shape it travels to. A straight segment splits exactly at any integer point on it. A curve splits to the nearest integers, which moves the drawing by under half a pixel.
5. **A rect is four corners**, and a circle of radius *r* is four cubics with handles of `0.5523 × r`, rounded to integers: its top vertex is `{"at": [cx, cy − r], "in": [−h, 0], "out": [h, 0]}` with *h* that handle length, and the other three turn the same way. It is not pixel-identical to an `ellipse`.
6. **A shape that will morph is a `path` from its first frame.** An element never changes its `type`. Where an `ellipse` must stay exact until the morph, keep it and cut to the `path` at the morph's start; the step at the cut is under half a pixel.
7. **Closed to open, stroke only:** write one open path throughout (`"closed": false`), the closed shape with its last `at` on its first. Its ends meet at a seam: use a `round` cap, or keep the seam smooth. The paths page of `montagent://format.md` has the rest, and `R-PATH-SEAM-CAP` names a seam that shows.
8. **A fill that opens is two elements**, the filled closed `path` and the open one, joined by a cut or a `crossfade`. `closed` never changes within an element.

- **Length:** 500–900 ms, `[0.65, 0, 0.35, 1]`. A morph reads as one change; give it the time a big move gets.
- **Look:** `frame` at the middle of the morph and check the in-between shape has no twist or fold; then `preview` across it.

### Bend a title along a curve

A title on an arc, a wave or a circle badge is one `text` with its own `path`: the `path` element's `points`, measured from the text's box. `path_offset` (a fraction of the curve's length, -1 to 2) places the point `align` names, and keying it slides the line along the curve. Here a title sits centred on an arc, then slides along it.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 3000, "output": "out/arc.mp4",
  "fonts": {"title": [{"file": "fonts/Inter-Bold.ttf"}]},
  "fontVendor": {"fonts/Inter-Bold.ttf": {"licence": "OFL-1.1", "source": "https://github.com/rsms/inter", "sha256": "288316099b1e0a47a4716d159098005eef7c0066921f34e3200393dbdb01947f"}},
  "tracks": [
    {"name": "title", "layer": 20, "elements": [
      {"id": "arc", "type": "text", "start": 0, "end": 3000, "x": 960, "y": 540, "origin": "center", "width": 1400, "height": 500, "font": "title", "size": 96, "color": "#F5F0E6", "align": "center", "runs": [{"text": "OVER THE TOP"}], "path": {"closed": false, "points": [{"at": [120, 380], "out": [380, -260]}, {"at": [1280, 380], "in": [-380, -260]}]}, "path_offset": [{"t": 0, "v": 0.5}, {"t": 1500, "v": 0.5, "ease": "linear"}, {"t": 2600, "v": 0.65, "ease": [0.65, 0, 0.35, 1]}], "caption": false}
    ]}
  ]
}
```

1. **Keep every point inside the box, inset by the largest run `size` plus the largest `stroke_width`**: here 96, so the points stay within `[96, 1304] × [96, 404]`. `validate` names a point outside it.
2. **`align` names an end of the curve**, not of the reading direction: `start` at offset 0 puts the line's left end on the curve's start, for Arabic too. Centre a title with `align: center` and `path_offset: 0.5`.
3. **Slide on and off:** `align: start`, `path_offset` keyed from -1 to 1 brings the line in from the curve's start and takes it out past the end, in one element. A line longer than its curve cannot fully enter or leave: use a stagger's `x`, or a cut.
4. **A circle badge** is four cubic vertices with handles of `0.5523 × r` (the morph recipe gives the vertex shape), clockwise on screen so the letters stand outside it. Write the list counter-clockwise to read along the bottom or from inside.
5. **A letter stagger reads along the curve:** a `units` `y` lifts each letter off the curve along its normal, and `x` slides it along.
6. **Fit:** `query --at` prints `hidden:` for the letters past an open end or beyond one loop of a circle; tighten the text or lengthen the curve until nothing is hidden. `measure` gives the bent line's ink, to size the box.

- **Size:** one line, 6–20 letters. A curve tighter than the line is tall makes wide letters lift off it.
- **Look:** `frame` at rest and check the letters sit evenly on the curve with no gap or overlap; then `preview` across the slide.

### Draw a line on

Underlines, arrows, signatures and outlines draw on along their own length. Key `trim_end` from 0 to 1: it is a fraction of the outline's length, so the stroke lands flush at 1 whatever the curve measures, and still does after you move a vertex. Nothing draws on the first frame, with no dot even under a round cap.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 2000, "output": "out/draw-on.mp4",
  "tracks": [
    {"name": "line", "layer": 10, "elements": [
      {"id": "underline", "type": "path", "start": 0, "end": 2000, "x": 960, "y": 600, "origin": "center", "width": 800, "height": 200, "closed": false, "stroke": "#FF5A36", "stroke_width": 12, "stroke_cap": "round", "trim_end": [{"t": 200, "v": 0}, {"t": 1100, "v": 1, "ease": [0.65, 0, 0.35, 1]}], "points": [{"at": [40, 150], "out": [260, -120]}, {"at": [760, 60], "in": [-240, 0]}]}
    ]}
  ]
}
```

- **Direction:** the line draws from `points[0]` to the last vertex. To draw it the other way, reverse the list. To draw it off, key `trim_start` from 0 to 1 after it lands.
- **Ends:** a `round` cap reads as a pen; `butt` (the default) as a wipe.
- **A closed outline** draws on the same way, from `points[0]` in points order on a path, from the top-left corner clockwise on a `rect` and from 3 o'clock clockwise on an `ellipse`. A trim on a closed path counts as an end, so a `stroke_cap` is fine there.
- **Dashes** stay where they are while the window reveals them; they do not slide along with it.
- **Length:** 600–1000 ms for a line, `[0.65, 0, 0.35, 1]`; scale with the length on screen.
- **Look:** `frame` at the first frame (nothing drawn) and half way through; then `preview` the draw.

### Spin a ring loader

A loader is an arc orbiting a ring: a window of the outline (`trim_start` 0, `trim_end` 0.25) rotated by `trim_offset`, which is in turns and keyed linearly from 0 to a whole number. The arc crosses the ring's start point as one stroke, with no seam, and a whole number of turns loops with no jump.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 3000, "loop": true, "output": "out/loader.mp4",
  "tracks": [
    {"name": "track", "layer": 10, "elements": [
      {"id": "ring-track", "type": "ellipse", "start": 0, "end": 3000, "x": 960, "y": 540, "origin": "center", "width": 160, "height": 160, "stroke": "#FFFFFF33", "stroke_width": 14}
    ]},
    {"name": "arc", "layer": 11, "elements": [
      {"id": "ring-arc", "type": "ellipse", "start": 0, "end": 3000, "x": 960, "y": 540, "origin": "center", "width": 160, "height": 160, "stroke": "#FF5A36", "stroke_width": 14, "trim_start": 0, "trim_end": 0.25, "trim_offset": [{"t": 0, "v": 0}, {"t": 3000, "v": 3, "ease": "linear"}]}
    ]}
  ]
}
```

- **Speed:** about one turn a second. `linear` only: any other ease stalls the arc once a cycle.
- **The loop's join:** the last key sits on the loop's end, so no frame reaches it and `validate` says so with `R-KEYFRAME-UNREACHED`. Here that is expected: the frame that would reach it is the loop's first, three whole turns on.
- **Breathing arc:** key `trim_end` between 0.1 and 0.6 as well, on its own ease; the offset keeps it turning.
- **Ends:** an `ellipse`'s or a `rect`'s trim ends are butt. For round ends, draw the ring as a closed `path` (four cubics) with `"stroke_cap": "round"`.
- **On a `rect`** the window turns the corners with the rect's own square join, a quarter turn being a quarter of the perimeter, not a corner.
- **Look:** `frame` where the arc crosses 3 o'clock, the ring's start point, and check there is no notch; then `preview` one full turn.

### Flip a card

A card turning over is two elements in the same place: the front swivels 0 → 180 and the back −180 → 0, on the same keys and curve. Each draws nothing while it faces away, so exactly one side shows at a time, and neither shows at the edge-on instant.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 2000, "output": "out/card-flip.mp4",
  "tracks": [
    {"name": "back", "layer": 10, "elements": [
      {"id": "card-back", "type": "rect", "start": 0, "end": 2000, "x": 960, "y": 540, "origin": "center", "width": 480, "height": 300, "fill": "#FF5A36", "radius": 24, "swivel": [{"t": 400, "v": -180}, {"t": 1200, "v": 0, "ease": [0.65, 0, 0.35, 1]}], "perspective": 1800}
    ]},
    {"name": "front", "layer": 11, "elements": [
      {"id": "card-front", "type": "rect", "start": 0, "end": 2000, "x": 960, "y": 540, "origin": "center", "width": 480, "height": 300, "fill": "#F2E6C9", "radius": 24, "swivel": [{"t": 400, "v": 0}, {"t": 1200, "v": 180, "ease": [0.65, 0, 0.35, 1]}], "perspective": 1800}
    ]}
  ]
}
```

- **Perspective:** 4–7 × the card's half-diagonal (283 px here). Below 2 × it the near edge goes soft, and `validate` says so with `R-PROJECTION-SOFT`.
- **Curve:** no overshoot. An ease that carries an angle past 90° blinks the card out for those frames.
- **Turning about the other axis:** key `tilt` instead of `swivel`, the front 0 → 180 and the back −180 → 0.
- **A mirrored back,** the front seen through the card, is a second element with `"scale": [-1, 1]`.
- **Shadows** tilt with the card. A shadow that stays on the ground is its own element.
- **Length:** 600–900 ms.
- **Look:** `frame` a quarter and three quarters of the way through, and check one side shows; then `preview` the flip.

### Swing a door

A panel hinged on one edge: put `origin` on the hinge and key `swivel`. With `"origin": "center-left"`, a positive swivel sends the free edge away from the viewer.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 2000, "output": "out/door.mp4",
  "tracks": [
    {"name": "doorway", "layer": 10, "elements": [
      {"id": "doorway", "type": "rect", "start": 0, "end": 2000, "x": 960, "y": 540, "origin": "center", "width": 480, "height": 640, "fill": "#FFD60A"}
    ]},
    {"name": "door", "layer": 11, "elements": [
      {"id": "door", "type": "rect", "start": 0, "end": 2000, "x": 720, "y": 540, "origin": "center-left", "width": 480, "height": 640, "fill": "#A0522D", "swivel": [{"t": 300, "v": 0}, {"t": 1300, "v": 75, "ease": [0.34, 1.2, 0.64, 1]}], "perspective": 2200}
    ]}
  ]
}
```

- **Opening angle:** 60–80°. A small overshoot settles the swing; keep the peak under 90°.
- **Perspective:** more than the distance from the hinge's midpoint to the far corners (577 px here), or `E-PROJECTION-EYE` names the value that passes; at least twice it keeps the near edge sharp. 4–5 × the width reads as a natural lens.
- **Length:** 800–1200 ms, with the door held shut for a beat first.
- **Look:** `frame` at the widest swing and check the hinge edge has not moved; then `preview` the swing.

### Procedural keyframes, expressions, and audio reactivity

High-frequency shake, inertial bounce, repeating cycles, noisy-curve smoothing, exponential zooms, audio-reactive pulses, and monotonic auto-Bezier tangents are baked into ordinary keyframes with `python3 scripts/keyframes.py <project> <spec> [--check]` (run with `--help` for full option defaults). It samples procedural curves on drawn frames (`floor(n * 1000 / fps)`), thins redundant points with Ramer–Douglas–Peucker simplification (`tol`), replaces the `[start, end]` keyframe range idempotently, and runs `validate` before printing the updated project: <!-- guard-ok: python3 floor tol -->

```json fragment
{
  "operations": [
    {"op": "wiggle", "id": "title", "property": "x", "start": 666, "end": 1000, "freq": 8.0, "amp": 18.0, "octaves": 2, "mult": 0.5, "seed": 7, "tol": 1.0},
    {"op": "bounce", "id": "card", "property": "y", "start": 300, "end": 1400, "freq": 3.0, "decay": 5.0, "tol": 1.0},
    {"op": "loop", "id": "badge", "property": "scale", "mode": "pingpong", "start": 0, "slice_end": 600, "end": 3000},
    {"op": "smooth", "id": "cam", "property": "x", "start": 0, "end": 2000, "window_ms": 120, "tol": 0.5},
    {"op": "exp_scale", "id": "map", "property": "scale", "start": 0, "end": 2000, "from": 1.0, "to": 16.0, "tol": 0.005},
    {"op": "audio", "id": "ring", "property": "scale", "audio_id": "beat", "start": 0, "end": 2000, "floor_db": -40.0, "peak_db": -6.0, "min_v": 1.0, "max_v": 1.35, "window_ms": 50, "tol": 0.01},
    {"op": "auto_bezier", "id": "card", "property": "x", "start": 0, "end": 1000}
  ]
}
```

- **`wiggle`:** deterministic 1D/2D octave-summed value noise around the existing value or keyframe curve (`seed` makes re-runs byte-identical; `"stepped": true` emits `step` keyframes for posterized/glitch holds). <!-- guard-ok: wiggle seed stepped -->
- **`bounce`:** inertial decay after the landing keyframe at `start` (`t1`), derived from incoming velocity $v_{\text{in}}$ via $v(t) = v(t_1) + v_{\text{in}} \cdot \frac{\sin(2\pi f \Delta t)}{2\pi f \cdot e^{d \Delta t}}$ until the amplitude falls below `tol`. <!-- guard-ok: bounce t1 tol -->
- **`loop`:** repeats the keyframe slice in `[start, slice_end]` up to `end` in `cycle` (clocks/loaders, inserting a `step` reset at `t_m + 1`), `pingpong` (breathing/bobbing, reversing values and mirroring eases), or `offset` (cumulative stair-step walk cycles). <!-- guard-ok: slice_end cycle pingpong offset -->
- **`smooth`:** symmetric box-filter moving average of width `window_ms` over a dense or jittery keyframe curve, followed by RDP thinning. <!-- guard-ok: smooth window_ms RDP -->
- **`exp_scale`:** visually constant-rate zoom $s(t) = s_0 \cdot (s_1 / s_0)^{(t - t_0)/(t_1 - t_0)}$ so deep zooms (such as $1\times \to 16\times$, whose geometric midpoint at halfway is $\sqrt{s_0 s_1} = 4\times$) do not rush the start and stall at the end. <!-- guard-ok: exp_scale -->
- **`audio`:** decodes the referenced `audio` or `video` element's clip slice (`source_start` to `source_end`, weighted by element `volume` and `audio.master`) with `ffmpeg`, computes per-frame RMS in dBFS, and maps `[floor_db, peak_db]` into `[min_v, max_v]`. Pass `--check` to verify whether baked audio keyframes are still in sync with the audio track. <!-- guard-ok: ffmpeg dBFS floor_db peak_db min_v max_v -->
- **`auto_bezier`:** computes Fritsch–Carlson monotonic cubic spline physical slopes $m_i = dv/dt$ across existing keyframes in `[start, end]`, clamps local extrema to $m_i = 0$ so the curve never overshoots, and writes slope-matched `[x1, y1, x2, y2]` handles rounded to 6 decimal places. <!-- guard-ok: auto_bezier x1 y1 x2 y2 -->
- **Look:** `preview` across the baked `[start, end]` window to confirm the motion settles cleanly at the boundaries.

### Smooth pass-through across keyframes (continuous and auto Bezier)

Because `ease` on keyframe $k_i$ describes strictly the segment entering $k_i$ from $k_{i-1}$, chaining `"ease": "ease-in-out"` into `"ease": "ease-in-out"` across a monotonic three-keyframe move ($v_0 < v_1 < v_2$ or $v_0 > v_1 > v_2$) falls into the **accidental midpoint pause** trap: the element decelerates to a complete stop ($v' = 0$) at the intermediate waypoint $k_1$ before accelerating again (`validate` does not flag this, because a deliberate pause at a waypoint is valid staging). When an element should glide continuously through $k_1$ without stopping or kinking, either run `scripts/keyframes.py` with `"op": "auto_bezier"` or write slope-matched cubic Bezier handles `[x1, y1, x2, y2]` directly: <!-- guard-ok: op auto_bezier x1 y1 x2 y2 -->

1. **Match physical velocity at the shared knot:** on segment $i$ ($\Delta t_i = t_i - t_{i-1}$, $\Delta v_i = v_i - v_{i-1}$, secant $\delta_i = \Delta v_i / \Delta t_i$), the incoming and outgoing physical velocities at interior keyframe $k_i$ are:
   $$v'_{\text{in}}(k_i) = \frac{1 - y_{2, i}}{1 - x_{2, i}} \cdot \frac{\Delta v_i}{\Delta t_i} = \frac{y_{1, i+1}}{x_{1, i+1}} \cdot \frac{\Delta v_{i+1}}{\Delta t_{i+1}} = v'_{\text{out}}(k_i) = m_i$$
2. **Compute the Fritsch–Carlson monotonic slope $m_1$ for a 3-keyframe transition $(t_0, v_0) \to (t_1, v_1) \to (t_2, v_2)$:**
   - If $k_1$ is a local extremum ($\delta_1 \cdot \delta_2 \le 0$), clamp $m_1 = 0$ to prevent overshoot.
   - Otherwise, use the weighted harmonic mean of the adjacent secants:
     $$m_1 = \frac{3(\Delta t_1 + \Delta t_2)}{\frac{2\Delta t_2 + \Delta t_1}{\delta_1} + \frac{\Delta t_2 + 2\Delta t_1}{\delta_2}}$$
     (which reduces to $\frac{2\delta_1\delta_2}{\delta_1 + \delta_2}$ when $\Delta t_1 = \Delta t_2$), clamped to $|m_1| \le 3\min(|\delta_1|, |\delta_2|)$.
3. **Convert $m_1$ to $1/3$-time Bezier handles ($x_1 = 1/3 \approx 0.333333$, $x_2 = 2/3 \approx 0.666667$, rounded to 6 decimal places):** with boundary slopes at rest ($m_0 = m_2 = 0$), segment 1 gets $y_{1,1} = 0$, $y_{2,1} = 1 - \frac{m_1 \Delta t_1}{3 \Delta v_1}$ and segment 2 gets $y_{1,2} = \frac{m_1 \Delta t_2}{3 \Delta v_2}$, $y_{2,2} = 1$. For example, moving `x` from `100` (`t: 0`) through `300` (`t: 500`, $\delta_1 = 0.4$) to `900` (`t: 1000`, $\delta_2 = 1.2$) gives $m_1 = 0.6\text{ px/ms}$, `{"t": 500, "v": 300, "ease": [0.333333, 0.0, 0.666667, 0.5]}`, and `{"t": 1000, "v": 900, "ease": [0.333333, 0.166667, 0.666667, 1.0]}`.

### Extrapolate after a keyframe (`loopOut("continue")`)

To keep an element moving at its final keyframe's velocity after the last keyframe $t_n$ (After Effects' `loopOut("continue")`), do not run a per-frame script: compute the incoming velocity $v' = (v_n - v_{n-1}) / (t_n - t_{n-1})$ from the final two keyframes and append a single `linear` keyframe at $t_{\text{end}}$ with $v(t_{\text{end}}) = v_n + v' \cdot (t_{\text{end}} - t_n)$. For example, if `x` moves linearly from `200` at `t: 0` to `500` at `t: 500` ($v' = 0.6\text{ px/ms}$) and the element ends at `2000`, append `{"t": 2000, "v": 1400, "ease": "linear"}`.

### Time-reverse keyframes

To play a keyframe sequence $[t_0, t_m]$ backward over the same span (or back-to-back after an entrance):

1. Reverse the keyframe values $v'_k = v_{m-k}$ and mirror the segment timestamps $t'_k = t_0 + (t_m - t_{m-k})$.
2. Mirror each reversed segment's easing curve: `linear` and `step` stay unchanged, `ease-in` swaps with `ease-out`, `ease-in-out` stays `ease-in-out`, and a cubic bezier `[x1, y1, x2, y2]` becomes `[1 - x2, 1 - y2, 1 - x1, 1 - y1]`. <!-- guard-ok: x1 y1 x2 y2 -->
3. To append a reversed pass automatically after an entrance or pulse, run `scripts/keyframes.py` with `"op": "loop"` and `"mode": "pingpong"` over two cycle lengths. <!-- guard-ok: op pingpong -->

### Tapered strokes, boolean cutouts and path modifiers

Montagent strokes have a single uniform `stroke_width`, `path` elements carry one contour, and procedural path operators do not run at render time (ADR-0226). Bake variable-width tapered strokes, boolean unions/intersections, offset outlines, pucker/bloat, radial twist, zig-zag ridges and seeded wiggles at write time with `python3 scripts/paths.py <project> <spec>` (run it with `--help` for the spec and Python functions): <!-- guard-ok: scripts -->

- **Tapered and wave strokes (`taper`):** converts an open or closed curve into a closed, filled `path` outline (`"closed": true` with `fill` and no `stroke`) whose thickness ramps over `start_length` and `end_length` from `start_width` to `width_px` to `end_width`, shaped by `start_ease` and `end_ease`, with optional sinusoidal width modulation (`wave_amount`, `wave_length`, `wave_phase`) and `cap` (`butt`, `round`, `square`). <!-- guard-ok: taper start_length end_length start_width width_px end_width start_ease end_ease wave_amount wave_length wave_phase cap -->
- **Boolean paths (`boolean`) and cutouts:** combines two or more polygons with `union`, `subtract`, `intersect` or `exclude`. For a shape with an interior hole (a ring, badge cutout or keyhole), either pass `"holes_as_mask": true` to `paths.py` or write the outer shape with an inner inverted `mask` (`"invert": true`) in `effects` so the hole punches cleanly through the fill: <!-- guard-ok: boolean union subtract intersect exclude holes_as_mask -->

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 2000, "output": "out/cutout.mp4",
  "tracks": [
    {"name": "badge", "layer": 10, "elements": [
      {"id": "donut-badge", "type": "path", "start": 0, "end": 2000, "x": 960, "y": 540, "origin": "center", "width": 320, "height": 320, "closed": true, "fill": "#FF5A36", "points": [{"at": [40, 40]}, {"at": [280, 40]}, {"at": [280, 280]}, {"at": [40, 280]}], "effects": [{"name": "mask", "shape": "path", "points": [{"at": [110, 110]}, {"at": [210, 110]}, {"at": [210, 210]}, {"at": [110, 210]}], "invert": true}]}
    ]}
  ]
}
```

- **Procedural path modifiers (`offset`, `pucker_bloat`, `twist`, `zig_zag`, `wiggle`):** `offset` expands or contracts a contour by `distance` pixels with `miter`, `bevel` or `round` joins (`line_join`, `miter_limit`); `pucker_bloat` pulls vertices toward or away from `center` while pushing cubic handles (`in`, `out`) in the opposite radial direction; `twist` rotates vertices and handles around `center` by `angle` degrees decaying quadratically to `radius`; `zig_zag` subdivides segments into `ridges` alternating peaks of `size` pixels (corner vertices or `"smooth": true` spline handles); and `wiggle` displaces vertices from a deterministic `seed` (`octaves`, `amplitude`, `frequency`), outputting either a static vertex list or frame-aligned `points` keyframes when `"animate": true`. <!-- guard-ok: pucker_bloat twist zig_zag wiggle distance line_join miter_limit ridges smooth octaves amplitude frequency animate -->
- **Look:** `frame` the baked element at rest to verify integer coordinates sit cleanly inside `width × height` with no self-intersection; for animated `wiggle` paths, `preview` across the span. <!-- guard-ok: wiggle -->

### Simultaneous and sequential trim across sibling paths

Each `path` element trims its own single contour from 0 to 1. To draw a multi-stroke icon, signature or diagram on screen, write one `path` element per contour on sibling tracks:

- **Simultaneous trim:** give every sibling `path` the exact same `trim_end` (or `trim_start`) keyframe times and easing curve so all contours draw on together.
- **Sequential trim (`trim_sequential`):** run `python3 scripts/paths.py <project> <spec>` with `"op": "trim_sequential"` (or call `paths.trim_sequential(paths, start=..., end=..., ease=...)`). It measures each contour's arc length and partitions `[trim_start_ms, trim_end_ms]` proportionally so the pen moves at a steady speed from one contour to the next: <!-- guard-ok: trim_sequential op trim_start_ms trim_end_ms -->

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 2000, "output": "out/check-seq.mp4",
  "tracks": [
    {"name": "stem-1", "layer": 10, "elements": [
      {"id": "check-short", "type": "path", "start": 0, "end": 2000, "x": 960, "y": 540, "origin": "center", "width": 400, "height": 300, "closed": false, "stroke": "#38BDF8", "stroke_width": 14, "stroke_cap": "round", "trim_start": 0, "trim_end": [{"t": 200, "v": 0}, {"t": 500, "v": 1, "ease": "linear"}], "points": [{"at": [80, 160]}, {"at": [160, 240]}]}
    ]},
    {"name": "stem-2", "layer": 11, "elements": [
      {"id": "check-long", "type": "path", "start": 0, "end": 2000, "x": 960, "y": 540, "origin": "center", "width": 400, "height": 300, "closed": false, "stroke": "#38BDF8", "stroke_width": 14, "stroke_cap": "round", "trim_start": 0, "trim_end": [{"t": 500, "v": 0}, {"t": 1100, "v": 1, "ease": [0.65, 0, 0.35, 1]}], "points": [{"at": [160, 240]}, {"at": [320, 80]}]}
    ]}
  ]
}
```

- **Look:** `frame` at the handoff instant between contours (`t = 500` here) to confirm the first contour is complete before the second starts; then `preview` the whole draw.

### Multi-point colour wash (4-Color Gradient), conic sweeps and off-axis highlights

An atmospheric multi-colour wash (After Effects's 4-Color Gradient) is two to four full-frame `rect` elements over a dark `background`, each filled with a `radial` or `two_point_conical` gradient that fades from its spot colour to `#00000000` and blended `screen` (or `add`). Key each layer's `center` (and `focal`) slowly across the span so the colour pools drift without banding or hard seams.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#0B0D14", "duration": 3000, "output": "out/wash.mp4",
  "tracks": [
    {"name": "lobe-1", "layer": 1, "elements": [
      {"id": "lobe-warm", "type": "rect", "start": 0, "end": 3000, "x": 0, "y": 0, "origin": "top-left", "width": 1920, "height": 1080, "blend": "screen", "fill": {"gradient": "radial", "center": [{"t": 0, "v": [0.22, 0.28]}, {"t": 2966, "v": [0.32, 0.36], "ease": "ease-in-out"}], "radius": 0.75, "stops": [{"offset": 0, "color": "#FF5A36BF"}, {"offset": 1, "color": "#FF5A3600"}]}}
    ]},
    {"name": "lobe-2", "layer": 2, "elements": [
      {"id": "lobe-cool", "type": "rect", "start": 0, "end": 3000, "x": 0, "y": 0, "origin": "top-left", "width": 1920, "height": 1080, "blend": "screen", "fill": {"gradient": "two_point_conical", "center": [0.76, 0.68], "radius": 0.8, "focal": [{"t": 0, "v": [0.64, 0.56]}, {"t": 2966, "v": [0.7, 0.62], "ease": "ease-in-out"}], "stops": [{"offset": 0, "color": "#2E86FFBF"}, {"offset": 1, "color": "#2E86FF00"}]}}
    ]},
    {"name": "lobe-3", "layer": 3, "elements": [
      {"id": "lobe-violet", "type": "rect", "start": 0, "end": 3000, "x": 0, "y": 0, "origin": "top-left", "width": 1920, "height": 1080, "blend": "screen", "fill": {"gradient": "radial", "center": [0.78, 0.22], "radius": 0.65, "stops": [{"offset": 0, "color": "#8A3FFC99"}, {"offset": 1, "color": "#8A3FFC00"}]}}
    ]}
  ]
}
```

- **Fade to the same hue at alpha zero:** write the outer stop as the spot colour with `00` alpha (`#FF5A3600`, not `#00000000`), and keep peak alpha around `99`–`CC` so overlapping `screen` lobes do not clip to white.
- **Off-axis specular highlights (`two_point_conical`):** place `focal` between `center` and the light source (`0` offset sits at `focal`, `1` on the outer circle of `radius` around `center`) to shade spheres, badges and glossy cards, or to stretch one wash lobe toward a corner.
- **Conic sweeps (`sweep`):** `{"gradient": "sweep", "center": [0.5, 0.5], "angle": 0, "stops": [...]}` starts at 12 o'clock and sweeps 360° clockwise. Match the first and last stop colours for a seamless colour wheel or sheen, or keep them distinct for a radar sweep or directional wipe and key `angle`.
- **Look:** `frame` at the start and end of the drift, and check that foreground copy stays legible over the brightest overlap of the lobes.


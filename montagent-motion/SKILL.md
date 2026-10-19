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

Lines that arrive a word or a letter at a time are set with the bundled script, not written by hand. `python3 scripts/type_on.py <project> <spec>` (run it with `--help` for the spec) measures the line with `measure`, places each word or letter where the whole line would set it, and prints the project with those elements added:

- **Words landing on beats:** `"by": "word"`, `"enter": "pop"`, and one time per word in `times`. A `highlights` entry recolours one word on its beat.
- **Typing:** `"by": "letter"`, 60–150 ms between letters (irregular reads more human: vary ±30 ms), and a `cursor` that blinks at 500–600 ms per cycle while idle, stays solid while typing, and steps ahead of each letter.
- **Tracked titles:** do not split the title into letters. Write one `text` element with `letter_spacing`, in thousandths of an em (`size × letter_spacing / 1000` px after each letter; negative tightens). Key it to drift a title apart: `"letter_spacing": [{"t": 0, "v": 0}, {"t": 800, "v": 120, "ease": [0.65, 0, 0.35, 1]}]`. Any non-zero value switches the optional ligatures off, and a joining script such as Arabic takes no spacing. <!-- guard-ok: times highlights cursor -->

It writes one element per unit and marks each one `caption: false`, so the caption checks skip them.

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

### Multi-scene transitions via ProRes handover

When creating push, wipe, slide, or crossfade transitions between complex multi-element scenes:

1. **Pre-render individual scenes to ProRes 422**:
   ```sh
   montagent render scenes/scene_a.montagent.json --output intermediates/scene_a.mov
   montagent render scenes/scene_b.montagent.json --output intermediates/scene_b.mov
   ```
2. <!-- guard-ok: scene_a scene_b -->**Assemble in the master project as `video` elements on staggered tracks**:
   Place `scene_a` on track 1 and `scene_b` on track 2 with an overlapping window `[t_trans_start, t_trans_end]`.
3. **Add native transition element**:
   ```json fragment
   {
     "id": "trans-scene-a-to-b",
     "type": "transition",
     "from": "scene-a",
     "to": "scene-b",
     "start": 5500,
     "end": 6000,
     "kind": "push",
     "direction": "left",
     "ease": "ease-out"
   }
   ```

<!-- guard-ok: yuv422p10le -->
**Operational costs to disclose:**
- **Two render passes**: each scene must be rendered prior to the master timeline render.
- **Intermediate disk overhead**: ~58 MB per 6-second 1080p30 scene in ProRes 422 standard (`yuv422p10le`).
- **Cache invalidation**: edits made to a nested scene file do NOT automatically invalidate or update the intermediate `.mov`; the scene must be explicitly re-rendered.


# Trailer effects

Trailers, and any piece that borrows their effects: slammed titles, flash frames, shake, glitch cuts, chromatic splits, glows, HUDs. They are all ordinary keyframes and static effects. Several are sampled per frame (shake, jitter, glitch), so write them with a generator script from the beat sheet, and keep per-frame keyframes to the effect's own window.

## Trailer grammar

- **Cards and shots alternate.** A text card holds 1–2 beats; a shot holds 2–4. Cards carry the story in three to five words each.
- **Hits land on beats.** Every slam, flash and hard cut sits on a beat of the score.
- **Accelerate.** The last montage cuts on every beat, then every half beat in its final bar.
- **The drop.** Half a beat to one beat of black and silence right before the title hit: the title lands harder out of nothing.
- **The title is last** and holds longest (2–4 s), with the date or call to action under it.

## Recipes

### Slam

A title that lands hard: it starts big and hits its size fast, with no overshoot, then the frame shakes.

- **Scale:** from 1.3–1.6 down to 1.0 over 120–200 ms, with `[0.05, 0.7, 0.1, 1]`. Opacity from 0 to 1 over the first 2 frames.
- **Flash:** a full-frame rect in white (or the accent) on the hit, `opacity` from 0.8–1.0 down to 0 over 3–5 frames.
- **Shake:** on the hit, offset `x` and `y` of everything that should shake, per frame, for 6–10 frames. Start at 12–24 px (at 1080p) and decay each frame by a factor of 0.6–0.75, alternating sign. Use `linear` between the per-frame keyframes.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#000000", "duration": 2000, "output": "out/slam.mp4",
  "fonts": {"title": [{"file": "fonts/Inter-Bold.ttf"}]},
  "fontVendor": {"fonts/Inter-Bold.ttf": {"licence": "OFL-1.1", "source": "https://github.com/rsms/inter", "sha256": "288316099b1e0a47a4716d159098005eef7c0066921f34e3200393dbdb01947f"}},
  "tracks": [
    {"name": "title", "layer": 20, "elements": [
      {"id": "title", "type": "text", "start": 500, "end": 2000, "x": [{"t": 666, "v": 960}, {"t": 700, "v": 978, "ease": "linear"}, {"t": 733, "v": 948, "ease": "linear"}, {"t": 766, "v": 969, "ease": "linear"}, {"t": 800, "v": 954, "ease": "linear"}, {"t": 833, "v": 963, "ease": "linear"}, {"t": 866, "v": 960, "ease": "linear"}], "y": 540, "origin": "center", "width": 1600, "height": 170, "font": "title", "size": 140, "color": "#F5F0E6", "align": "center", "runs": [{"text": "HAS A PRICE"}], "scale": [{"t": 500, "v": [1.5, 1.5]}, {"t": 666, "v": [1.0, 1.0], "ease": [0.05, 0.7, 0.1, 1]}], "opacity": [{"t": 500, "v": 0.0}, {"t": 566, "v": 1.0, "ease": "linear"}], "effects": [{"name": "shadow", "dx": 0, "dy": 0, "radius": 28, "color": "#E8B04A", "opacity": 0.7}], "caption": false}
    ]},
    {"name": "flash", "layer": 30, "elements": [
      {"id": "flash", "type": "rect", "start": 666, "end": 833, "x": 0, "y": 0, "origin": "top-left", "width": 1920, "height": 1080, "fill": "#FFFFFF", "opacity": [{"t": 666, "v": 0.9}, {"t": 800, "v": 0.0, "ease": "ease-out"}]}
    ]}
  ]
}
```

The title slams from 1.5× to size by 666 ms, the white flash fires on the landing, and the title shakes for 6 frames. Its glow is a `shadow` with zero offset.

### Glow

A `shadow` with `dx` and `dy` 0, `radius` 16–40, in a warm or accent colour at `opacity` 0.5–0.9. Effects don't animate, so for a glow that swells, crossfade a glowing copy of the element over its plain one over 200–400 ms.

### Focus pull

A copy with `blur` (`radius` 12–24) sits over the sharp element and fades out over 300–500 ms with `ease-in-out`. The sharp one is fully opaque underneath throughout.

### Chromatic split

Two tinted copies of a title, one red (`#FF2A2A`) and one cyan (`#2AF0FF`), sit below the sharp title with `"blend": "screen"` at `opacity` 0.5–0.7, offset 4–10 px to either side. They snap together over 150–250 ms, or jitter on a glitch. Screen brightens the ground under each copy, so the split reads over footage as well as over black.

### Glitch cut

The outgoing shot is cut into 3–6 horizontal bands: one copy per band, each with a static rect `mask` over its band. For 4–8 frames each band jumps sideways 20–80 px, on a new random offset every frame (`step` eases). Alternate a red and a cyan `tint` (`amount` 0.3–0.5) across the bands. The hard cut to the next shot lands on the beat right after.

### Light sweeps, flares and embers

For a light bar, use a long `rect` with a `linear` gradient `fill` that fades to transparent at both ends (`#FFFFFF00`, `#FFE0B0`, `#FFFFFF00`), rotated to the diagonal. For a soft glow, use an `ellipse` with a `radial` gradient fading to transparent. Use still PNG plates with soft alpha only for what a gradient cannot draw (a flare streak, ember dots). Lay any of them over the shot with `"blend": "screen"`, or `"add"` for a hotter core. Move them across the title or shot over 600–1200 ms, at `opacity` 0.4–0.8. A screened plate only lightens, so it reads as light over bright shots too. Keep the shot it lights beneath it: over the black `background` alone, screen draws what normal draws, and `validate` says so.

### Letterbox

Two black rects, top and bottom. For 2.39:1 in a 1920×1080 frame, each is 138 px high. They slide in from off-frame over 400–600 ms with `ease-out`, or are simply there from the first frame.

### HUD from shapes

- **Lines and frames:** a line is a two-vertex open `path` (`"closed": false`, a `stroke`, `stroke_width` 2–3), at any angle or bent through handles; a frame is an unfilled rect with the same stroke. One accent colour, at `opacity` 0.6–0.85. Keep each vertex at least half the stroke width inside the path's box, or `validate` refuses it.
- **Rings:** unfilled ellipses with a stroke. One or two turn slowly, one turn per 8–20 s, `linear`.
- **Readouts:** typed with `scripts/type_on.py` (letters at 30–60 ms each), in small caps text at 2–3 % of the short side: readouts are texture, not copy, so they sit under the reading floor.
- **Blinks and ticks:** dots and markers that toggle on `step` every half beat.
- **Build:** the lines draw on by growing from an edge (see `SKILL.md`), then the rings, then the readouts.

## Look

Load `montagent-craft`. Then:

- `frame` on each hit, and on the frame after it: the slam has landed, and the flash is at its peak.
- `preview` the span around each glitch and shake, and check they settle back exactly to rest.
- `frame` the title at the middle of its hold: it's complete, sharp, and clear of any sweep or flare.

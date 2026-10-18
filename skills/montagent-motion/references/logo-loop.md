# Logo loop

A sting that plays on repeat. The join is the piece: a viewer shouldn't be able to say where it starts. So plan the cycle backwards from its last frame, which has to equal its first.

## The cycle

| Phase | Share of the loop | What happens |
|---|---|---|
| **Rest** | 3–8 % | The empty ground: the frame the loop starts and ends on. |
| **Build** | 30–40 % | The mark's parts arrive one after another. |
| **Hold** | 25–35 % | The mark, name and any tagline are complete and still, or with one small secondary move (a blinking cursor, a soft pulse). |
| **Clear** | 15–20 % | Everything leaves. |
| **Rest** | 3–8 % | Empty ground again, identical to the first frame. |

Set the project's `loop` to true. `validate` then checks a clip that runs across the join, but it doesn't compare the first and last frames. The look step below does that.

## Recipes

- **Parts arrive one after another:** stagger them by 150–300 ms. Each one either pops (see the pop in `SKILL.md`) or flies in from off-frame. A fly-in starts one part-width beyond the frame edge and lands on the overshoot curve `[0.34, 1.56, 0.64, 1]` (or the gentler `[0.34, 1.25, 0.64, 1]`) over 500–800 ms. Bring each part in from the side nearest its resting place.
- **A spin on the way in:** `rotation` from 0 to a whole number of turns (1080 for three), easing out so it slows into place and settles upright. Keep its fastest frame under 45° of turn: a square turned near 90° a frame looks still, and one turned near 180° strobes. The first frame of a curve turns about `y1 / x1` times the average rate, so a strong ease-out like `[0.16, 1, 0.3, 1]` suits one turn or less. For three turns use `[0.3, 0.3, 0.5, 1]` over 1300–1500 ms (it peaks near 1.6 times the average). Start the spin with the part's fly-in, and end it last of all the parts' arrivals, so the settle is the build's final beat.
- **A cursor and typed name:** use `scripts/type_on.py` with a cursor. It blinks with a hard on/off (`step`), 500–600 ms per cycle. The name types at 80–150 ms per letter, starting a blink or two after the cursor appears.
- **Clear:** all together, or the reverse of the build order (last in, first out), 250–400 ms each, scaling to 0 or fading with `ease-in`. Finish the clear at least 3 frames before the end, so the final rest is truly still.

```json
{
  "frame": {"width": 1080, "height": 1080}, "fps": 30, "background": "#F5F0E6", "duration": 3000, "loop": true, "output": "out/sting.mp4",
  "tracks": [
    {"name": "tile", "layer": 10, "elements": [
      {"id": "tile", "type": "rect", "start": 0, "end": 3000, "x": [{"t": 100, "v": -120}, {"t": 800, "v": 540, "ease": [0.34, 1.25, 0.64, 1]}], "y": 540, "origin": "center", "width": 200, "height": 200, "fill": "#101418", "radius": 40, "rotation": [{"t": 100, "v": 0}, {"t": 1433, "v": 1080, "ease": [0.3, 0.3, 0.5, 1]}], "scale": [{"t": 2300, "v": [1.0, 1.0]}, {"t": 2633, "v": [0.0, 0.0], "ease": [0.5, 0, 0.75, 0]}]}
    ]}
  ]
}
```

The tile flies in from the left, spins three turns into place, holds, then shrinks away. It's gone by 2633 ms, 11 frames before the end.

## Look

Load `montagent-craft`. Then:

- `frame` at 0 and on the last drawn frame, and compare them: they should be the same picture.
- `preview` the build, and check the parts arrive one at a time and the spinning part settles square.
- `frame` at the middle of the hold: the assembled mark matches the brand's construction exactly (positions, gaps, which part is the accent).

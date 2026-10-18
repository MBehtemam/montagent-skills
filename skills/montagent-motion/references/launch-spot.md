# Launch-spot structure

A launch spot, product ad, intro or outro has one job: land one idea and leave the brand on screen. This is its shape at 10–30 s. Scale the sections to the brief's length; keep their order.

| Section | Length | What it does |
|---|---|---|
| **Hook** | the first bar (about 2 s) | The idea in six words or fewer, arriving a word per beat. No logo yet: the idea earns the logo. |
| **Show** | two to four bars | The product doing the thing: real screenshots or recordings, one idea per shot, 2–4 s each, joined on bar lines. |
| **Proof** | one bar | One number, one small chart, or a triad of three words, growing in on beats. |
| **Brand** | the last 1.5–3 s | The wordmark revealed on a downbeat, then fully visible and still for at least 1.5 s. A call to action or URL sits under it, smaller. |

## Rules that hold across sections

- **One focal thing at a time.** When a new section starts, the last one's elements have gone, or are clearly behind.
- **Three colours:** the ground, the ink and one accent. The accent marks one thing per section (the hook's key word, the tallest bar, the brand bar). A second use of it steals the first's weight.
- **Mark sections with the ground.** Swapping the ground between dark and light on a downbeat is a cut the viewer feels without a transition.
- **Hook type is display size, bold;** labels are label size. Both sizes, and the safe area every word stays inside, are in `montagent-craft`.
- **Every section change is a downbeat.** Stagger inside a section on half beats.
- **Music:** the bed plays from 0 at a steady level (`volume` 0.6–0.9 when nothing speaks over it), then fades to 0 over the last 0.8–1.5 s, reaching 0 on the final frame.

```json
{
  "frame": {"width": 1920, "height": 1080}, "fps": 30, "background": "#101418", "duration": 6000, "output": "out/outro.mp4",
  "tracks": [
    {"name": "ground", "layer": 1, "elements": [
      {"id": "light", "type": "rect", "start": 2000, "end": 6000, "x": 0, "y": 0, "origin": "top-left", "width": 1920, "height": 1080, "fill": "#F5F0E6"}
    ]},
    {"name": "music", "layer": 0, "elements": [
      {"id": "bed", "type": "audio", "start": 0, "end": 6000, "source": "media/bed.wav", "source_start": 0, "source_end": 6000, "volume": [{"t": 4800, "v": 0.8}, {"t": 5966, "v": 0.0, "ease": "linear"}]}
    ]}
  ]
}
```

The ground swaps from dark to light on the 2 s downbeat. The bed holds at 0.8, then fades out over the last 1.2 s.

## Look

Load `montagent-craft`. Then:

- `preview` the hook, from 0 to just past its last word.
- `frame` one frame either side of each section change: the old section has cleared, and the new one has started on the beat.
- `frame` the brand at the moment it is first fully revealed, and on the last frame: the same, and complete.
- After the render, read what `verify` says about the audio: it flags a mix that goes silent where something should be heard.

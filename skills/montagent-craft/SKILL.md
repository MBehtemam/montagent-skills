---
name: montagent-craft
description: "Timing, easing and layout craft for any Montagent video: beat grids from music, easing and hold lengths, safe areas, type scale, restraint. Load before judging whether a piece looks right."
---

# Craft: timing, easing and layout

The numbers that hold in every Montagent piece, whatever its job, shape or frame rate. Times are in milliseconds. Sizes are fractions of the frame, measured against its **short side** (the height of a wide frame, the width of a tall one), so they hold at any size and aspect ratio. A Job skill's recipe gives its own numbers for its own move; inside that recipe, its numbers win.

## The look

At every look step, check the frames the step names against each line below, and the whole video once more before you render. Judge what is in the frame, never what you meant to build. A line you could not check from what you looked at counts as unchecked: look again.

1. **On the beat.** Every cut, entrance and section change sits on the drawn frame of its beat, or at most one frame early ([Beat grid](#beat-grid)). `query --from --to` lists the cuts; compare them with the grid.
2. **Inside the safe area.** Every word sits inside title-safe, and every face and product inside action-safe ([Safe areas](#safe-areas)). For text, `query --at <t> --json` gives each element's ink box in pixels.
3. **Big enough.** No text meant to be read is under 3 % of the short side, and the levels are clearly apart ([Type](#type)).
4. **Readable.** Text against what is behind it reaches the contrast ratio in [Type](#type), in every frame it is up. Over footage or a photo, check the brightest and the busiest frame.
5. **One focal thing.** At any moment one thing leads: the newest, biggest, brightest or accented. Everything else has gone, is still, or is clearly behind ([Restraint](#restraint)).
6. **Smooth.** In `preview`, nothing strobes, judders, or shows as copies of itself ([Speed limits](#speed-limits)).
7. **Long enough to read.** Each line holds for its reading time before anything moves it ([Holds](#holds)).
8. **The end.** The last frame is complete and still, and has been for at least 1 s. Sound reaches 0 on that frame.

The look is done when every line holds on every tile of the contact sheet, and at every frame the step named. Fix what fails, then go back to `montagent`'s check step.

## Beat grid

Music sets the clock. Find the tempo and the first downbeat before you place anything.

- **Tempo stated** in the brief or the asset notes: use it, with the downbeat it states.
- **Tempo not stated:** run `python3 scripts/beat_grid.py <project> <spec>` (run it with `--help` for the spec). It listens to the track, places it so a downbeat lands where you want it, and fades it out on the last drawn frame. It prints the project on stdout, so redirect that to a new file, and the grid as JSON on stderr. Read both confidences: under 1.5, or `downbeat_by` of `first`, the grid is a guess. Give `bpm` (and `downbeat`) in the spec when you know them, and say in your hand-off that the grid was estimated. <!-- workaround: #547 · replaced by: tempo and downbeat from probe --> <!-- guard-ok: bpm downbeat downbeat_by first -->
- **No music:** a 500 ms beat (120 BPM).

The arithmetic:

- A beat is `60000 / BPM` ms, a bar is four beats, and a phrase is four bars (sometimes eight).
- **Count from the first downbeat, never by adding.** The *n*th beat is `downbeat + n × beat`, then moved to its drawn frame: `floor(round(t * fps / 1000) * 1000 / fps)`. Adding a rounded beat over and over drifts by a frame every few bars. `measure --at` confirms an instant is drawn.
- At 90, 100 and 120 BPM a beat is a whole number of frames at 30 and 60 fps (also 24 fps at 90 and 120, and 25 fps at 100). At other tempos the beats fall 14, 14, 15… frames apart. That is fine when each beat is counted from the downbeat.

Where things go:

- **Section changes on downbeats**, and the biggest turn of the piece (the reveal, the brand) on the first downbeat of a phrase.
- **Main events on beats:** a cut, a word landing, a colour change. **Secondary motion on half or quarter beats:** a settle, a stagger inside a group, a label after its bar.
- **Which frame is "on":** a cut, a flash or a pop is on the beat at its first frame. A move longer than half a beat, whose arrival is the point, ends on the beat instead.
- **Early, never late:** viewers notice a picture that trails its sound from about 45 ms, which is a frame or two. A hit one frame early reads as on the beat; one frame late reads as late.

## Durations and easing

| Move | Length | Frames at 30 fps |
|---|---|---|
| A hit: a flash frame, a slam's impact, a hard swap | 70–130 ms (under 2 frames reads as a glitch) | 2–4 |
| A small move: a pop, a nudge, a label fading in | 200–350 ms | 6–10 |
| A standard move: a card in, a move across part of the frame | 400–600 ms | 12–18 |
| A heavy move: a hero reveal, a big push | 700–1000 ms | 21–30 |
| A drift: a push-in, a slow float | the whole time on screen | |

- **Exits run at 60–70 % of the entrance they undo.**
- **Stagger** items in a group by 60–130 ms (2–4 frames at 30 fps), and keep the whole stagger under 500 ms. A longer group gives each item its own beat instead.
- **Curves.** Arriving things decelerate; leaving things accelerate; things moving between two places on screen ease both ways. Pick one curve per role for the whole piece and keep it: the curve is part of the piece's voice.

| Role | Curve | Peak speed, × the average |
|---|---|---|
| Entrance with a long settle | `[0.16, 1, 0.3, 1]` | 6.3 |
| Gentler entrance | `[0.25, 1, 0.5, 1]` | 4.0 |
| Pop with about 10 % overshoot | `[0.34, 1.56, 0.64, 1]` | 4.6 |
| Exit | `ease-in` | 1.7 |
| Between two places, wipes, sweeps | `[0.65, 0, 0.35, 1]` | 2.9 |
| Spin | `[0.3, 0.3, 0.5, 1]` | 1.6 |
| Drift, sound fades, constant spin | `linear` | 1.0 |

The peak column feeds the speed check below: the fastest instant of a move is its average speed times that number.

## Speed limits

For a fast move, set `motion_blur` on the moving element (`"shutter": 180`, `"samples"` 8–16) rather than slowing the move. It is not a default: put it on the elements that move fast, not on everything. An element without it is drawn as one sharp image per frame, so a fast move shows as separate copies, and the limits below hold for it. Check the fastest frame of every move: `distance × peak ÷ (length in frames)`.

- **Travel:** a move's step at its fastest frame stays under half the moving thing's own size along the move. Past its whole size, the eye sees two things.
- **Rotation:** under 45° a frame at the fastest frame. Something that repeats as it turns (a four-spoked shape, a dial of twelve ticks) must stay under half its repeat angle a frame, or it seems to turn backwards: under 45° for four spokes, under 15° for twelve ticks. Three turns in 1 s on `[0.16, 1, 0.3, 1]` peak at about 200° a frame at 30 fps: that strobes.
- **Read while moving:** text, a face or a screenshot that keeps moving while it is read (a crawl, a pan across a screenshot, a long drift) crosses at most 15 % of the frame width per second. That is cinema's rule of a full frame width in no less than 7 s.
- **Flashes:** at most three full-frame or large brightness flips in any one second, glitch cuts and strobes included.

## Holds

- **Reading time:** 330 ms per word (about three words a second), plus a beat to notice the line arrived. Never under 1 s for a line, and rounded up to the next beat.
- **Too long:** a frame with nothing moving for more than about 7 s reads as stalled. Give it a drift, or move on.
- **The end:** the last frame complete and still for at least 1 s (a brand or a call to action: 1.5 s or more).

## Safe areas

The edges of the picture get cropped, covered or overlooked. Keep what matters inside these boxes. Grounds, bleeds and backgrounds run to the edge and past it.

| Frame | Title-safe: every word | Action-safe: faces, products, the action |
|---|---|---|
| Wide or square (16:9, 4:3, 1:1) | 5 % in from every edge | 3.5 % in from every edge |
| Tall (9:16, 4:5) | 5 % in from the sides, 12.5 % from top and bottom | 3.5 % in from every edge |

On 1920×1080, title-safe is x 96–1824, y 54–1026. On 1080×1920, it is x 54–1026, y 240–1680. When the brief says the video plays in a feed whose player draws its own buttons and captions over the picture, also keep text out of the bottom fifth.

## Type

Sizes are the font's `size` as a fraction of the short side.

| Level | Size | At 1080 |
|---|---|---|
| Display: the hook, the one big word | 7–12 % | 76–130 px |
| Headline | 5–7 % | 54–76 px |
| Body, captions | 5–6.7 % | 54–72 px |
| Labels, small print | 3.5–4.5 % | 38–49 px |
| Nothing meant to be read | under 3 % | 32 px |

- **Steps:** two levels in one frame differ by at least 1.25×; with less, they read as a mistake rather than a hierarchy.
- **Lines:** at most 42 characters, and at most two lines for anything read while things move. A hook is six words or fewer.
- **Faces:** one family, in two weights far apart (bold display, regular body). A second family only when it contrasts plainly: a serif or a mono beside a sans.
- **Contrast** (WCAG's ratio, from the two colours' relative luminance): at least 4.5:1 for body, captions and labels, and at least 3:1 at display size. Over footage or a photo the ratio changes every frame, so give text a ground of its own: a pill, a bar or a shadow.

## Restraint

- **One idea per shot**, with room around it. A frame that has to be read in parts is two shots.
- **Three colours:** a ground, an ink, and one accent. The accent marks one thing at a time; a second use steals the first one's weight.
- **One focal move at a time**, plus at most one slow ambient drift under it.
- **Effects serve the brief.** Glows, glitches, chromatic splits, shakes, flares and particle bursts belong in a trailer that asks for them; in an ad or an explainer they read as noise.
- **No made-up chrome.** Corner labels, timecodes, frame counters, "REC" marks and HUD frames go in only when the brief asks for them.
- **Real material over stand-ins.** Use the brief's screenshots, footage and brand; a product UI redrawn by hand looks wrong next to the real one.

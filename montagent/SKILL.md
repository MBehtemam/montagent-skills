---
name: montagent
description: "Make, edit or check a video with Montagent: the loop from project file to delivered MP4, what Montagent can and can't do yet, and which Montagent skill covers the job. Load first, before any other Montagent skill, whenever a task mentions Montagent or asks for a video with it."
---

# Montagent

A Montagent video is one JSON project file. You write it with your ordinary file tools. Montagent's tools check it, measure it, show it and render it.

## Environment

You need a shell with the `montagent` CLI on `PATH`, Python 3, and ideally the Montagent MCP server. The MCP tools and the CLI share their verbs, so use whichever is to hand. `fmt`, `fonts` and `probe` exist only on the CLI. <!-- workaround: #455 · replaced by: font vendoring, fmt and probe over MCP --> With MCP alone and no shell, a project that has text cannot be rendered: tell the user to install the CLI.

**The binary wins.** These skills describe Montagent's `main` branch. <!-- guard-ok: main workaround --> When a finding, a refusal or `--help` disagrees with a skill, do what the binary says. An unknown-key or unknown-code error on something a skill taught means the installed binary is older than the skill: report `montagent --version`, then upgrade or use the marked workaround.

## Learning the format

1. Read `montagent://format.md` in full, then each page it lists before you write what that page covers. Together they hold the rules the schema can't express, and each one fits in one read.
2. Open [the starter project](references/starter-project.md) and build from it. It shows the keys most pieces need.
3. When you need a key the starter doesn't show, read `montagent://schema/index.json`. It lists every element type and effect with its required keys, and the URI of the piece that holds each one's rules. Read the piece you need, not the whole schema.
4. Read `montagent <verb> --help` for one verb at the moment you first use it, not up front. MCP tool descriptions say the same.

## The loop

Run every step, in order, every time the project changes.

1. **Scaffold.** `create_project`, or copy the starter into your working directory.
2. **Fonts** (only when there is text). For each face, run `montagent fonts vendor <project> <font file>`. Then write the chain entry it prints into `fonts` yourself.
3. **Build.** Write the project, or generate it with a script when the structure repeats (per-letter typing, a rig baked frame by frame, captions from word timings). Where a Job skill ships a script for the job in its `scripts/` folder, run that script rather than writing your own. Use `measure` to size text boxes. Only drawn frames reach the video. Put every cut, and every keyframe that ends a move, on an instant that `measure --at` confirms is drawn.
4. **Check.** `montagent fmt <project>`, then `validate`. Fix every error. The first time you get findings, open [the findings guide](references/findings.md). Act on every finding it doesn't list as noise.
5. **Look.** Load `montagent-craft` before judging anything. Call `montagent frame --from` and `--to` over the whole video, or a stretch of it. You get a contact sheet: one tile for each visual state. Its provenance list tells you which element drew each tile. To look closely at one tile, call `frame` at the instant its line lists. For motion, `preview` a span of a few seconds around the beat. When a span is refused, the refusal names ranges that fit. Fix what you see, then go back to step 4.
6. **Render**, once, in the foreground, as a call of its own, and wait for it to exit. A render that your shell tool moves to the background is still running: wait on it until it exits. End your turn only after it has.

   One exception, for a long render, decided by a calculation. First render a slice of a few seconds with `render --from --to`, over the stretch with the most on screen. Its RENDER line gives the slice's frames and the seconds it took; divide them for the slice's frames per second. Divide the whole video's frame count (its length times its frame rate) by that. If the answer is above about 120 s: <!-- workaround: #873 · replaced by: render --estimate -->
   - Pass `--progress-file` with a fresh path (`progress_file` on MCP). It writes a JSON status file to poll (state, phase, frames, ETA). Run the render in the background. <!-- guard-ok: progress_file -->
   - Poll the file every 10 to 30 s. Read `state`, `phase` and `eta_note` there. `fps` is the rate over the recent window, the only rate the file carries (there is no `fps_window`). `started_at` and `updated_at` are UTC, ending in `Z`. `wall_clock_gap_ms` is the wall clock the run's own `elapsed_s` missed: a large value means the wall clock moved on while the run's own clock did not (the machine slept). It does not say the render is alive: judge that by `updated_at` changing, as below. Don't work progress out yourself, and don't write a wrapper script that guesses at it. <!-- guard-ok: state phase eta_note fps_window started_at wall_clock_gap_ms elapsed_s -->
   - Stop polling when `state` is `done`, `failed` or `cancelled`, or when the file is stale: `state` is `running` and `updated_at` has not changed across polls spanning at least `max(3 × write_interval_s, 10 s)`. A stale file means the render died. Compare the file with your earlier reads of it, never with your own clock. `pid` means something only on the machine running the render. <!-- guard-ok: state done failed cancelled running updated_at pid -->
   - To learn what a slow slice spends its time on, add `--profile` (`profile` on MCP) to the slice render and read `render.profile` with `--json`: CPU ms per element, element type and effect, and the stage split. Per element, `frames_painted` counts frames it was drawn on and `frames_reused` frames its pixels were copied from the static prefix of unchanging bottom layers. A profiled run is timed, so don't take its seconds as the slice's speed. <!-- guard-ok: profile frames_painted frames_reused -->
   - Don't end your turn before then, and don't delete the file.
   - On MCP, a background render needs a client that can make a second call while `render` is open. Without one, stay on the call and follow its progress notifications.
7. **Verify.** Run `verify` on the project. It proves the MP4 was rendered from this version of the project and measures what is in it. On an error, render again.

The video is **delivered** when `verify` passes on the last edit.

## What Montagent does, and which skill covers it

This is the capability map. Read it before you design, so the brief does not lean on something Montagent lacks. Each line names the capability and the keys that spell it; `montagent://format.md` with its pages, and the schema, hold their values and rules.

### What it does

**Elements and placement**

- Images, video, text, rectangles, ellipses and nested sequences, placed and sized on a frame, layered on tracks: `image`, `video`, `text`, `rect`, `ellipse`, `nest`, `x`, `y`, `width`, `height`, `origin`, `layer`.
- Lines, polygons and curves drawn through vertices with handles, filled or stroked with a chosen corner join and end cap, dashed or dotted, the vertex list keyable: `path`, `closed`, `points`, `at`, `in`, `out`, `stroke_join`, `stroke_miter_limit`, `stroke_cap`, `stroke_dash`, `stroke_dash_offset`.
- Dashed outlines on rectangles, ellipses and paths, with the dashes marching along them: `stroke_dash`, `stroke_dash_offset`.
- A shape morphing into an unlike one, with matching vertex lists written by hand: `path`, `points`.
- Draw a stroke on along its outline, or orbit an arc around a ring, on paths, rectangles and ellipses: `trim_start`, `trim_end`, `trim_offset`.

**Motion**

- Keyframe position, scale, rotation and opacity, with named easings or a cubic bezier (overshoot included): `scale`, `rotation`, `opacity`, `ease`.
- Turn any visual element in perspective about its own axes, as in a card flip, a door swing or a tilted screen: `swivel`, `tilt`, `perspective`.
- Keyframe a shape's size, corner radius, fill, stroke and dash offset, and a text element's colour and stroke: `width`, `height`, `radius`, `fill`, `stroke`, `stroke_width`, `stroke_dash_offset`, `color`.
- Motion blur on a moving element: `motion_blur`.

**Paint**

- Timed colour on a word inside text, by recolouring that word's run: `highlight`.
- Linear and radial gradients as the fill or stroke of a shape, and the colour or stroke of a text element, with the angle, centre, radius and stops animating in place: `gradient`, `angle`, `center`, `radius`, `stops`, `offset`.

**Text**

- Text in fonts you vendor, as runs with their own size and colour: `fonts`, `size`, `color`.
- Letter spacing on a whole text element, keyable: `letter_spacing`.
- A text element's letters, words or lines animating one after another, with one singled out: `units`, `unit`.
- One line of text bent along its own curve (straight, arc, wave or circle) and sliding along it: `path` (the `path` element's points) and `path_offset` on `text`, with `align`.

**Compositing**

- Crossfade between clips, and a cut between clips: `transition`, `step`. Write `"audio": "constant_power"` on every new transition between clips that sound, so the sound crossfades too; absent keeps the hard audio cut.
- Wipe, slide and push between clips, travelling in a direction, with an ease: `kind`, `direction`, `ease`.
- Chroma key: `chroma`.
- Blend an element into what is beneath it, as screen, add, multiply or overlay: `blend`.
- Keep everything outside a mask shape instead of inside it: `mask`, `invert`.
- Soften a mask's edge, and animate the softness: `mask`, `feather`.
- Mask an element through any closed outline drawn point by point, and animate the outline: `mask`, `shape`, `points`.

**Effects**

- Blur, shadow, mask, tint, saturation, brightness, contrast, ASC CDL color grading and 3D LUT cube grading: `blur`, `shadow`, `mask`, `tint`, `saturation`, `brightness`, `contrast`, `cdl`, `lut3d`.
- Film grain that re-rolls every frame from a literal seed, on an element or as a grey `rect` texture blended `overlay`: `grain`, `seed`, `size`, `mono`.
- Posterize an element's colours into a few flat steps: `posterize`, `levels`.
- A bloom from an element's bright parts: `glow`, `threshold`, `radius`, `intensity`.
- Smear an element along one direction, whether or not it moves: `directional_blur`, `angle`, `length`.
- A texture or glow laid over footage, as a `rect` carrying an effect and a blend, the way a vignette or a light leak is built: `rect`, `effects`, `blend`.
- A look outside this vocabulary, drawn in your own code, pre-rendered to lossless footage with alpha and placed as a `video`, with a recipe that rebuilds it: `video` (`montagent-prerender`).
- A vector drawing (SVG), brought in as one image: rasterised once to a PNG at the size it is shown, placed as an `image`, with a recipe that rebuilds it: `image` (`montagent-prerender`).
- A Lottie animation, brought in as footage: rendered frame by frame, one fresh player per frame, into lossless footage with alpha, placed as a `video`, with a recipe that rebuilds it: `video` (`montagent-prerender`).
- Keyframe any effect's numbers and colours, and reveal an element through a keyed mask: `effects`, `radius`, `dx`, `dy`, `color`, `opacity`, `x`, `y`, `width`, `height`, `amount`, `tolerance`, `softness`, `spill`, `levels`, `threshold`, `intensity`, `angle`, `length`.

**Time**

- Per-clip speed, and a check on clips that run across a loop's join: `speed`, `loop`.
- Speed ramps, reverse and freeze frames on a video, as a curve of source times: `source_time`.

**Audio**

- Audio on tracks, with per-clip volume: `audio`, `volume`.
- A crossfade between two audio clips, or between two clips' sound alone: `kind: "audio_crossfade"`, `audio` (`constant_power` unless both sides are the same source, then `constant_gain`). Fading a clip against silence stays a `volume` ramp.
- EQ on an audio or video clip, stackable and in list order: a high-pass or low-pass at 12, 24 or 48 dB/oct, a low or high shelf, a bell, or a parametric biquad band (`audio_effects`: `highpass`, `lowpass`, `shelf`, `bell`, `equalizer`, `frequency_hz`, `slope_db_per_oct`, `side`, `gain_db`, `q`, `enabled`).
- Even out or hold a clip's level before `volume`: `audio_effects` with `compressor` (`threshold_db`, `ratio`, `attack_ms`, `release_ms`, `makeup_db`), `gate` (`threshold_db`, `attack_ms`, `release_ms`), and `limiter` (`ceiling_db`, `release_ms`); every key is required.
- Bring a clip to a written loudness with one measured gain, before `volume`: `audio_effects` with `normalize_loudness` (`target_lufs`, -40..-6, required, one per clip).

### Which skill covers it

| The piece | Load |
|---|---|
| Graphics and text: launch spots, product and social ads, intros and outros, kinetic and typed text, logo reveals and loops, trailer effects | `montagent-motion` |
| Recorded video: talking heads, green screen, captions, lower-thirds, picture-in-picture, music under a voice | `montagent-footage` |
| A look the effects list lacks (distortions, mosaic, lens flare, a code-drawn pattern), drawn in code and brought in as footage | `montagent-prerender` |
| A vector drawing (SVG), brought in as one image: rasterised once to a PNG and placed as an `image` | `montagent-prerender` |
| A Lottie animation, brought in as footage: rendered frame by frame to lossless footage with alpha and placed as a `video` | `montagent-prerender` |
| A character that moves or talks: rig, poses, lip sync, blinks | `montagent-character` |
| Timing, easing, layout, and judging whether it looks right | `montagent-craft`, at every look step |

A piece can mix these: load each skill whose row it touches.

A piece can mix these: load each skill whose row it touches.

### What it can't do yet

Each item names the issue whose close retires it. Tell the user when the brief depends on one.

- Parenting, groups and cameras. Bake the hierarchy to per-element keyframes (`montagent-character`). <!-- workaround: #499 · replaced by: parenting or a group transform -->
- Changing an element's image over time. Use one element per image, each shown for its own span (`montagent-character`). <!-- workaround: #518 · replaced by: an image that changes over time -->
- Reading a track's tempo or beats. Find the beat grid with the script in `montagent-craft`. <!-- workaround: #547 · replaced by: tempo and downbeat from probe -->

### Not by design

Montagent refuses these on purpose, so do not wait for them. Each line gives what to do instead and the decision that refused it.

- Spring easing. Use a cubic bezier with overshoot, or keyframes baked out. ([ADR-0146](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0146-an-animatable-property-is-one-the-schema-types-so-colour-blends-premultiplied-and-spring-easing-is-refused.md))
- A repeat or copy construct. Write each copy out as its own element. ([ADR-0148](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0148-a-repeat-does-not-enter-and-a-stagger-enters-only-across-the-units-of-one-text-element.md))
- A matte taken from another element. Use the element's own `mask`. ([ADR-0150](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0150-wipe-slide-and-push-enter-as-transition-kinds-and-a-matte-from-another-element-is-refused.md))
- Automatic vertex matching between unlike paths. Pad the lists by hand (`montagent-motion`). ([ADR-0162](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0162-a-morph-between-unlike-shapes-is-written-as-matching-vertex-lists-and-no-rule-resamples-them.md))
- Keyframe expressions, or links between values. Write literal keyframes. ([ADR-0145](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0145-capcut-and-premiere-are-where-precedent-is-looked-for-first-and-a-capability-with-none-enters-by-the-entry-test.md))
- A native SVG or Lottie source. Pre-render it once with `montagent-prerender`: an SVG as one PNG, a Lottie as footage. ([ADR-0171](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0171-svg-and-lottie-do-not-enter-as-sources-and-each-is-pre-rendered-through-the-skill.md))
- An open shader or script file. Pre-render the look with `montagent-prerender` and bring it in as footage ([ADR-0156](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0156-four-named-effects-join-the-effects-list-and-a-code-drawn-piece-enters-as-pre-rendered-footage.md)). ([ADR-0017](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0017-closed-schema-no-escape-hatch.md))

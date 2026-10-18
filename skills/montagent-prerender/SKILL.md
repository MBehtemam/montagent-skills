---
name: montagent-prerender
description: "Bring code-drawn visuals, Lottie animation, 3D scenes, or stabilized source video into Montagent as lossless footage, or an SVG still as one PNG, each with a rebuild recipe. Load for a look outside the effects list, generative visuals, SVG, Lottie or 3D model input, or source-video stabilization, reference-frame locking, ping-pong and slow-down."
---

# Pre-render: generated visuals and stabilized footage

Five routes, one set of [common rules](#common-rules). A **code-drawn piece** becomes footage, placed as a `video`: read it first. An **SVG still** becomes one PNG, placed as an `image`: jump to [the SVG route](#the-svg-route). A **Lottie animation** becomes footage too, drawn one fresh player per frame: jump to [the Lottie route](#the-lottie-route). A **3D scene** becomes transparent footage or a still PNG: jump to [the 3D scene route](#the-3d-scene-route). **Source-video stabilization** bakes a new clip: jump to [the stabilize route](#the-stabilize-route). All run outside the render, so every painter decodes the same pixels.

Montagent has no shader or script file ([ADR-0017](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0017-closed-schema-no-escape-hatch.md)). A look outside the `effects` list is drawn in your own code, encoded once as footage, and placed as an ordinary `video`. The format, the schema and the painter stay as they are ([ADR-0156](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0156-four-named-effects-join-the-effects-list-and-a-code-drawn-piece-enters-as-pre-rendered-footage.md) §7, [ADR-0233](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0233-3d-models-and-multichannel-passes-are-refused-as-native-sources-and-3d-scenes-pre-render-via-headless-recipes.md)).

## When to reach for it

Take the named route first. Read the `effects` list in `montagent://schema/index.json`: when a member makes the look (blur, shadow, tint, a `blend`, a keyed `mask`), use it. Pre-render only when no member, paint or blend composes the look: distortions, mosaic, lens flare, particles, a procedural pattern, or an external 3D model/scene.

Reach for the SVG route when you are handed a vector drawing (a logo, an icon, an illustration) as an SVG file, or when a still is easiest to draw as SVG. No element accepts an SVG file ([ADR-0171](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0171-svg-and-lottie-do-not-enter-as-sources-and-each-is-pre-rendered-through-the-skill.md)). An SVG that animates (SMIL or CSS) is not this route: it rasterises as one still frame and the motion is lost. Key the placed image's own `scale`, `rotation` and `opacity` instead.

Reach for the 3D scene route when you are handed a 3D asset (`.glb`, `.gltf`, `.obj`, `.fbx`, `.blend`, `.c4d`) or a 3D scene. No element accepts a 3D model or multichannel pass ([ADR-0167](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0167-an-element-may-be-projected-never-placed-swivel-tilt-and-perspective-join-the-transform.md), [ADR-0233](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0233-3d-models-and-multichannel-passes-are-refused-as-native-sources-and-3d-scenes-pre-render-via-headless-recipes.md)). Headless rendering produces transparent ProRes 4444 / PNG footage outside the render, ready for direct 2D placement.

Reach for the Lottie route when you are handed a Lottie JSON file (an After Effects export, a LottieFiles animation), or when a motion is easiest to take from one. No element accepts a Lottie file ([ADR-0171](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0171-svg-and-lottie-do-not-enter-as-sources-and-each-is-pre-rendered-through-the-skill.md)). It costs three things. **A fixed resolution:** the footage is raster at the size you render it. **A recipe toolchain:** a Lottie player installed to reproduce the piece (never to render the project). **Footage size:** PNG in a MOV runs from about 6 MB per second for smooth art to 141 MB per second for noisy art, at 1080p and 25 fps, so render at the size shown and no larger. If the motion is a few shapes, keying native `rect`, `ellipse` and `path` elements is smaller and stays sharp.

A pre-rendered piece is fixed footage. Its size, fps and length are set when you render it. Changing the look means rendering again, so settle the brief's size, fps and duration first, and match the project's `fps`.

## Common rules

Every route reads these. They are written once.

- **Size.** Rasterise or draw at the largest size the piece is ever shown, after `fit`, `scale` and any keyed zoom, as a literal pixel `width` and `height`. Never derive it from an SVG's `viewBox`: a `viewBox` sets the drawing's proportions, not its pixels, and the tools disagree on a file with none. Write the size in the recipe. A later zoom past it resamples a raster, so re-run the recipe larger instead of scaling up. <!-- guard-ok: viewBox -->
- **Text.** Vendored fonts only, or text converted to outlines. Never a system font: a machine without it draws something else. A font that cannot be found is a build failure, not a dropped span. `usvg`, for one, logs the miss and skips the text, so `build` reads the SVG's `font-family` values against the font files you list in `fonts`, and fails on the rasteriser's own font warning too. <!-- guard-ok: build usvg fonts font-family viewBox -->
- **Recipe.** Source copy, exact commands, tool versions, size, and a hash of the **decoded** pixels, taken through the same read the decoder uses. The rebuild reports a match or the first difference, and never compares file bytes. [The recipe](#the-recipe) says where it lives.

## The steps

Run every step, in order. The piece is **placed** when step 5 passes.

1. **Draw.** Write code, in any tool, that produces RGBA frames of a fixed `width`, `height` and `frames` count: transparent where nothing is drawn. It writes raw RGBA to stdout, or PNG files `f00000.png`, `f00001.png` and so on into the folder named by `PRERENDER_FRAMES_DIR`. Read its size from `PRERENDER_WIDTH`, `PRERENDER_HEIGHT`, `PRERENDER_FPS` and `PRERENDER_FRAMES`. Use integer arithmetic or a fixed seed, so a second run draws the same bytes. [The sample piece](references/sample_piece.py) is the smallest working one. <!-- guard-ok: PRERENDER_FRAMES_DIR PRERENDER_WIDTH PRERENDER_HEIGHT PRERENDER_FPS PRERENDER_FRAMES frames -->
2. **Spec.** Write a build spec next to the code: `name`, `out` (the project's media folder), `width`, `height`, `fps`, `frames`, `render` (the argv that runs your code), `files` (every file the code needs), and `input` of `"png"` when it writes PNGs. Run `python3 scripts/prerender.py --help` for every key. Add `versions` for any library whose version changes the pixels (a canvas library, a headless browser). <!-- guard-ok: versions name out render files input -->
3. **Build.** `python3 scripts/prerender.py build <spec>`. It runs the code, encodes **one** `<name>.mov`, decodes it, and fails on the first frame that differs from what your code drew. Read its last line: `N frames, decoded = drawn`.
4. **Place.** Add the footage to the project as a plain `video` element (below), or run `python3 scripts/prerender.py place <project> <placing>`, where `<placing>` is a JSON file `{"source": "media/<name>.mov"}` plus any of `id`, `at`, `x`, `y`, `origin`, `width`, `height`, `fit`, `track`, `layer`. It prints the project with the element added, so redirect that to a new file. <!-- guard-ok: at origin track layer fit -->
5. **Check.** `validate` the project and fix every error. Then `montagent probe` the footage and confirm it reports alpha (`carries: true`). Only then `frame` a tile where the piece is up and check the transparent parts show what is behind.

```json
{
  "frame": {"width": 640, "height": 360}, "fps": 25, "background": "#101418", "duration": 480, "output": "out/pulse.mp4",
  "tracks": [
    {"name": "prerender", "layer": 10, "elements": [
      {"id": "pulse", "type": "video", "start": 0, "end": 480, "source": "media/pulse.mov", "source_start": 0, "source_end": 480, "volume": 0, "x": 320, "y": 180, "origin": "center", "width": 320, "height": 240, "fit": "contain"}
    ]}
  ]
}
```

The element is an ordinary `video`: key `opacity`, `scale` and `position`, add `effects` and a `blend`, and lay it on a track like any clip. The footage has no sound, so `volume` is 0. Its `end` minus `start` is the footage's length; `source_end` is the same length. <!-- guard-ok: position -->

## The SVG route

**Input:** an SVG file, and the pixel size from the common rules.

1. **Vendor the fonts** the SVG's text uses, with `montagent fonts vendor`, and set each `<text>` in that family with a `font-family` attribute. Or convert the text to outlines in your drawing tool and use no font.
2. **Spec.** Write a build spec beside the SVG with `"input": "svg"`: `name`, `out`, `svg`, the literal `width` and `height`, `render` (the rasteriser's argv, with `{width}`, `{height}` and `{out}` where they go), `files`, `fonts` and `versions`. There is no fps and no frame count. <!-- guard-ok: input svg name out render files fonts versions width height fps viewBox -->
3. **Rasterise.** `python3 scripts/prerender.py build <spec>` runs the rasteriser once, outside the render. Any tool that writes one RGBA PNG will do: the `resvg` command line, a headless browser, Inkscape. Skip system fonts and hand it the vendored ones, as in the spec below. It writes `<name>.png` and its recipe, and fails on a missing font. <!-- guard-ok: build resvg -->
4. **Place** the PNG as a plain `image` element (below), or run `python3 scripts/prerender.py place <project> <placing>` with `{"source": "media/<name>.png", "duration": <ms>}` plus any of `id`, `at`, `x`, `y`, `origin`, `width`, `height`, `fit`, `track`, `layer`. <!-- guard-ok: duration at origin track layer fit -->
5. **Check.** Run `validate` and fix every error, then `frame` a tile where the image is up and check the transparent parts show what is behind.

The sample spec, for [the sample SVG](references/sample_art.svg) (shapes, a gradient and text set in a vendored font), rasterised at three times its `viewBox`: <!-- guard-ok: viewBox -->

```json fragment
{
  "name": "mark", "out": "media", "input": "svg", "svg": "sample_art.svg", "width": 480, "height": 270,
  "render": ["resvg", "--skip-system-fonts", "--use-font-file", "Inter-Bold.ttf", "-w", "{width}", "-h", "{height}", "sample_art.svg", "{out}"],
  "files": ["sample_art.svg"], "fonts": ["Inter-Bold.ttf"],
  "versions": {"resvg": ["resvg", "--version"]}
}
```

The PNG has intrinsic pixel dimensions, so it enters as an ordinary `image`, and [ADR-0015](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0015-fit-is-a-derivation-claim-and-gravity-retires.md)'s `fit` rules apply as for any PNG: `contain` with the box's own aspect, or `literal`. Placing it at its own size, with `fit` of `contain`, is a 1:1 draw. Show it larger than the size you rasterised and the raster is resampled: run the recipe again at the larger size.

```json
{
  "frame": {"width": 640, "height": 360}, "fps": 25, "background": "#101418", "duration": 2000, "output": "out/mark.mp4",
  "tracks": [
    {"name": "art", "layer": 10, "elements": [
      {"id": "mark", "type": "image", "start": 0, "end": 2000, "source": "media/mark.png", "x": 320, "y": 180, "origin": "center", "width": 480, "height": 270, "fit": "contain"}
    ]}
  ]
}
```

Run `validate`. The image is an ordinary one: key `opacity`, `scale` and `position`, add `effects`, lay it on a track. <!-- guard-ok: position -->

## The Lottie route

**Input:** a Lottie JSON file, a size, an fps and a frame range. The Lottie's own `w`, `h` and `fr` are inputs to choose from, not rules: the size follows the common rules (the largest size shown, as literals), and you write the fps and the frame count in the spec. <!-- guard-ok: w h fr -->

1. **Choose a player** that can write RGBA frames, and record its name and version in `versions`. The skill does not pick one: the pre-render runs once outside the render and the painters never see the player. [The sample player](references/lottie_frame.py) is ThorVG through `pip install thorvg-python==1.1.3`. <!-- guard-ok: versions -->
2. **Spec.** Write a build spec beside the Lottie with `"input": "lottie"`: `name`, `out`, `lottie`, the literal `width` and `height`, `fps`, `frames`, `render`, `files`, `fonts` and `versions`. `render` is the player's argv, with `{width}`, `{height}`, `{frame}` and `{out}` where they go: it draws **one** frame as raw RGBA into `{out}`. Optional `start` and `step` set which Lottie frame each footage frame is (frame `i` is `start + i * step`; `step` defaults to the Lottie's `fr` divided by `fps`). Run `python3 scripts/prerender.py --help` for every key. <!-- guard-ok: input name out lottie width height fps frames render files fonts versions start step build w h fr i -->
3. **Build.** `python3 scripts/prerender.py build <spec>` first reads the Lottie and refuses it, naming each case, if it uses an **expression**, a **layer effect** the player is not recorded as drawing (list the ones it is in `allow_effects`), or **text** whose font has neither embedded glyph paths nor a vendored file in `fonts`. A player drops all of these without a sound, so a build that carried on would ship a different animation. It then runs `render` once per frame, a **new process each time**, reads the player's own report of what it skipped (any line saying skipped, ignored or unsupported is a build failure: treat it as one), encodes **one** `<name>.mov` as [the codec](#the-codec) says, and fails on the first frame that differs from what the player drew. <!-- guard-ok: build allow_effects fonts -->
4. **Place** the footage as a plain `video` element, or with `place` as in [the steps](#the-steps). Run `validate` and `montagent probe` the MOV: confirm it reports alpha (`carries: true`). Then `frame` a tile where the piece is up and check the transparent parts show what is behind. <!-- guard-ok: place -->

**Why a fresh player per frame.** The harness never seeks one player forward. ThorVG ignores a frame change under 0.001, so where a seek lands depends on the previous seek, and Skottie's seek mutates its animation object. A frame drawn after others can differ from the same frame drawn first, and the rebuild would not match. A player whose seek is a pure function of the frame number may be reused only if you checked that (draw frames in two orders and compare decoded hashes) and wrote the check in the spec's `notes`, which the recipe keeps. Otherwise use one process per frame, as `build` does. <!-- guard-ok: build notes -->

**Text.** A Lottie whose text names a font needs that font vendored (`montagent fonts vendor`, listed in `fonts`, and handed to the player); one with embedded glyph paths needs none. A font that cannot be found is a build failure.

The sample spec, for [the sample Lottie](references/sample_lottie.json) (shapes, an embedded-glyph text layer and a keyed fade, with transparent areas), 50 frames at 25 fps: <!-- guard-ok: fonts -->

```json fragment
{
  "name": "lottie", "out": "media", "input": "lottie", "lottie": "sample_lottie.json", "width": 320, "height": 180, "fps": 25, "frames": 50,
  "render": ["python3", "lottie_frame.py", "sample_lottie.json", "{width}", "{height}", "{frame}", "{out}"],
  "files": ["sample_lottie.json", "lottie_frame.py"],
  "versions": {"thorvg-python": ["python3", "-c", "import importlib.metadata as m; print(m.version('thorvg-python'))"]}
}
```

The footage is an ordinary `video`, placed at its own size with `fit` of `contain`:

```json
{
  "frame": {"width": 640, "height": 360}, "fps": 25, "background": "#101418", "duration": 2000, "output": "out/lottie.mp4",
  "tracks": [
    {"name": "art", "layer": 10, "elements": [
      {"id": "lottie", "type": "video", "start": 0, "end": 2000, "source": "media/lottie.mov", "source_start": 0, "source_end": 2000, "volume": 0, "x": 320, "y": 180, "origin": "center", "width": 320, "height": 180, "fit": "contain"}
    ]}
  ]
}
```

Run `validate`. Key `opacity`, `scale` and `position`, add `effects`, lay it on a track like any clip. Do not retime or restyle the animation inside the project: change the Lottie or the spec and run `build` again. <!-- guard-ok: position build -->

## The 3D scene route

**Input:** a 3D model asset (`.glb`, `.gltf`, `.obj`, `.fbx`, `.blend`, `.c4d`) or headless scene script, a size, an fps, and a duration.

No element accepts a 3D model or multichannel 3D render pass natively ([ADR-0167](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0167-an-element-may-be-projected-never-placed-swivel-tilt-and-perspective-join-the-transform.md), [ADR-0233](https://github.com/MBehtemam/Montagent/blob/main/docs/adr/0233-3d-models-and-multichannel-passes-are-refused-as-native-sources-and-3d-scenes-pre-render-via-headless-recipes.md)). 3D scenes execute headlessly outside the render, producing transparent video or still PNG footage.

1. **Deterministic headless engine.** Use Blender CLI (`blender -b`) or headless Three.js / Puppeteer. Pin camera parameters, lighting, and rendering seeds:
   - For Blender: enable transparent background (`bpy.context.scene.render.film_transparent = True`), pin render engine (`CYCLES` with pinned CPU device and fixed seed, or deterministic `BLENDER_EEVEE_NEXT`), and output frames to `PRERENDER_FRAMES_DIR`.
   - Record exact toolchain and engine versions in `versions`.
2. **Spec.** Write a build spec with `"input": "png"`: `name`, `out`, the literal `width` and `height`, `fps`, `frames`, `render`, `files`, and `versions`. `render` runs the headless command exporting RGBA PNG frames.
3. **Build.** `python3 scripts/prerender.py build <spec>`. It runs the headless renderer, encodes transparent footage (`.mov`), and checks decoded frame hashes. Animated sequences export as ProRes 4444 (`alpha: true`, ADR-0203) or PNG-in-MOV; single frames export as PNG.
4. **Place.** Place into `project.json` as an ordinary `video` or `image` element, with standard 2D transforms, `swivel`, `tilt`, `effects[]`, and `blend`.
5. **Check.** Run `validate`, `montagent probe` the footage to verify alpha, and `frame` to confirm compositing.

The sample spec for a headless Blender spin:

```json fragment
{
  "name": "product_spin", "out": "media", "input": "png", "width": 640, "height": 360, "fps": 25, "frames": 75,
  "render": ["blender", "-b", "scene.blend", "-P", "render_turntable.py", "-o", "{frames_dir}/f######.png", "-s", "1", "-e", "75", "-a"],
  "files": ["scene.blend", "render_turntable.py"],
  "versions": {"blender": ["blender", "--version"]}
}
```

## The stabilize route

Reach for this route when a source video needs stabilization, a lock to a reference frame, or baked ping-pong and slow-down (including optical-flow slow motion via `ffmpeg -vf minterpolate` when `frame_blend: "mix"` on the `video` element is insufficient; ADR-0232). Bake a **new lossless clip**, then place it as an ordinary `video` under the common rules. [US-10's resolution](https://github.com/MBehtemam/Montagent/issues/920#issuecomment-6109518213) keeps this work in the skill under ADR-0156 §7 / ADR-0171: no format change or ADR, and no `stabilize` effect. For a very short clip, literal keyframes for `scale` and `source_time` are an alternative; paper fill needs new pixels and belongs in the bake. <!-- guard-ok: stabilize source_time minterpolate frame_blend -->

Read [the stabilize recipe](references/stabilize.md) for this branch. It includes [a narrow reference script](references/stabilize.py) for opaque ink on light, uniform paper: measure ink centroid and spread per frame, fit a cubic, re-place with subpixel transforms, fill with paper colour or replicated edges, and encode lossless. The script is **non-normative**: the acceptance check decides whether the bake is usable. Use another external tracker for footage outside that scope.

## The codec

Footage (the code-drawn, Lottie and stabilize routes) is **PNG in a MOV**, `-c:v png -pix_fmt rgba`, and `build` writes exactly that. It is the codec checked to return every byte of RGBA, alpha included, through Montagent's decoder. Keep `-pix_fmt rgba` explicit: left to itself, ffmpeg can pick `rgb24` and drop the alpha. <!-- guard-ok: build rgb24 -->

Any `yuva` pixel format is not exact from RGBA: FFV1 `yuva444p` and VP9 lossless both change pixels, and ProRes 4444 is lossy. A lossy or `yuva` encode makes the recipe's hashes meaningless, so do not swap one in. FFV1 with `bgra` also round-trips and is smaller on noisy frames, but this skill uses PNG. <!-- guard-ok: yuva yuva444p rgb24 bgra -->

If `build` stops on a missing `png` encoder, the installed ffmpeg is unusual: install a standard build. The encoder is built in by default. <!-- guard-ok: build png -->

## The recipe

The common rules' recipe, in full. `build` writes `<name>.recipe/` beside the footage (beside the PNG, on the SVG route). It holds a copy of the code (the SVG and the font files on the SVG route; the Lottie, the player script and the fonts on the Lottie route), and `recipe.json`: the commands, the tool versions, the size, fps and frame count, and the hash of every **decoded** frame, read with `-f rawvideo -pix_fmt rgba`. The project never names the recipe or the code. <!-- guard-ok: build -->

To rebuild, or to check the footage still matches what its recipe made:

```sh
python3 scripts/prerender.py rebuild <name>.recipe
```

It re-runs the code from the recipe's own copy, encodes again, and compares decoded-frame hashes, never file bytes (container metadata changes the bytes and not the pixels). It prints `rebuild: match` and `footage: match`, or the first frame that differs and exits 1. After you edit the code, copy it into the recipe by running `build` again. A mismatch with the code unchanged means a tool version changed: compare `versions` in `recipe.json` against the machine. <!-- guard-ok: build versions --> On the SVG route the recipe is one frame: the command with its literal size, the rasteriser's version, and one decoded-pixel hash. `rebuild` re-runs the rasteriser and reports `rebuild: match`, or the first pixel that differs; a font the recipe's copy no longer holds fails it. To change the drawing, edit your SVG and run `build` again. The recipe, like the SVG, stays outside the project file. <!-- guard-ok: rebuild build --> On the Lottie route the recipe also lists each footage frame's Lottie frame, the player's name and version, and any `allow_effects` and `notes`; `rebuild` reads the Lottie again and refuses it for an expression, as `build` does, then compares decoded-frame hashes and reports the first footage frame that differs, so editing one keyframe is named by the frame it first changes. <!-- guard-ok: rebuild build allow_effects notes -->

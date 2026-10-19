# Stabilize source footage: bake, accept, place

Use this recipe for source-video stabilization, reference-frame locking, ping-pong or slow-down. The output is one lossless clip. The project names only that clip as an ordinary `video`; the tracker and recipe stay outside it. Read the skill's common size, text and recipe rules first.

## Choose the input and lock

The [reference script](stabilize.py) is **non-normative**, scoped to an opaque, unchanging ink drawing on uniform light paper. It corrects translation and isotropic size drift; it does not track rotation, parallax, occlusion, changing ink or general scenes. Inspect the source first. For other footage, use another external tracker and retain the recipe fields and acceptance check below.

Choose a zero-based reference frame whose ink is complete and inside the canvas. Choose a literal RGB paper colour. The script weights ink by darkness relative to that colour, measures centroid and RMS radial spread for every frame, and fits each of those three measurements with a least-squares cubic in normalized frame time. It locks the result to the **measured** centroid and spread of the chosen reference. Bilinear inverse sampling provides subpixel transforms. This is a recipe algorithm, not part of Montagent's format.

Match source pixels to the largest size shown, and source fps to project fps, before baking. The script requires at least four frames with constant timing and rejects a size or fps mismatch. It holds frames in memory and samples pixels in Python: use short clips at the size needed, and expect a slow offline bake for large frames. It drops source audio; place sound separately if needed.

## Bake

Write a spec beside the source. Paths resolve against the spec's folder. Run the script's `--help` for the complete CLI. This example locks frame 12, fills newly exposed pixels with light paper, plays forward then backward without repeating turn endpoints, and repeats each frame twice at unchanged fps to slow down. <!-- guard-ok: reference_frame fill paper ping_pong slowdown -->

```json fragment
{
  "source": "drawing.mov", "name": "drawing-locked", "out": "media",
  "width": 640, "height": 480, "fps": 25,
  "reference_frame": 12, "fill": "paper", "paper": [240, 240, 240],
  "ping_pong": true, "slowdown": 2
}
```

```sh
python3 references/stabilize.py build drawing.spec.json
```

`fill: paper` uses the literal opaque RGB colour outside the source. `fill: edge` replicates the closest source edge, including bilinear interpolation at the boundary. Slow-down is a positive integer frame repetition factor, with no synthesized in-between frames. For N source frames, the forward bake has N frames; ping-pong has 2N−2. Multiply by slow-down for the final frame count. Timing is baked into the clip; place it at the recorded fps. <!-- guard-ok: fill paper edge slowdown ping_pong N -->

The wrapper reuses `scripts/prerender.py` to encode PNG-in-MOV with explicit RGBA, decode it, and verify every frame against the raw transformed pixels. Only a successful acceptance check and lossless verification produce a usable bake.

## Recipe and rebuild

Beside the MOV, `<name>.recipe/` contains the source video, reference script and settings in `source/`, and `recipe.json`. The recipe records: <!-- guard-ok: source -->

- Original source SHA-256, zero-based reference frame, cubic fit model, fill rule and literal paper colour.
- Exact render, encode and decode commands; pixel size, fps, source and output frame counts; ping-pong and slow-down settings.
- Exact Python, ffmpeg and ffprobe versions, captured at build time and **pinned** in the copied settings. Rebuild refuses different versions. Preserve that toolchain to rebuild; to deliberately upgrade it, build a new recipe and accept its output again.
- SHA-256 of every decoded RGBA output frame. Compare decoded pixels, never MOV file bytes.

The stabilization settings also appear in the recipe's `stabilize` section. The copied settings are what the render command consumes. <!-- guard-ok: stabilize -->

```sh
python3 references/stabilize.py rebuild media/drawing-locked.recipe
```

A rebuild uses the recipe's source copy, checks its hash and tool pins, re-runs stabilization and acceptance, encodes again, and reports `rebuild: match` and `footage: match`, or the first differing frame. The existing `scripts/prerender.py rebuild` command works too. A source change or a tool-version mismatch fails. Changing the source, reference, fill or timing means building a new recipe.

## Accept and place

**Acceptance decides, regardless of the tracker.** Residual size drift must be **under 1%** relative to the reference, and the clip must have **no black edges**. The script checks RMS ink spread on every transformed frame and refuses drift of 1% or more, blank ink, non-opaque pixels, and pure black perimeter pixels. Cubic motion that does not explain a source is a failed bake, not a reason to loosen the threshold.

Inspect decoded frames throughout the clip, including the lock, turn and both ends. Check that the drawing holds its reference position and size, paper fill matches, and no dark wedges, stretched edge content, clipping or visible jitter remain. The script's pure-black perimeter check is a narrow automated guard; visual inspection catches near-black seams and tracking mistakes. A failed check means change the external tracking/fill method and bake again.

Place the accepted MOV with `scripts/prerender.py place` as in the main skill, then `validate`, `probe` its alpha capability, and `frame` representative tiles. The output is opaque RGBA, with volume 0; its duration and source range follow the baked frame count and fps. The recipe is never named by the project.

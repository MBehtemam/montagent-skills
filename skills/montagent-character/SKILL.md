---
name: montagent-character
description: "Cut-out character animation in Montagent: mascots and puppets built from a rig of parts, posing and gestures, lip sync to a voice line from visemes, blinks. Use when a Montagent video has a character that moves or talks."
---

# Animating a cut-out character

Recipes for a character built from a rig of parts: a body, a head, arms in two pieces, and face overlays (mouth shapes and a blink) drawn on the head's own canvas. They slot into `montagent`'s loop at the build step; load `montagent` first if you haven't. For a short where a character speaks a line, open [the character-short structure](references/character-short.md) before you plan.

## What the rig must give you

Read the rig's description before anything else. You need, for every part: its image, its size, its **pivot** (the joint it turns about, as a point in the original drawing), its **parent**, and the order the parts draw in, back to front. You also need a table from the voice's viseme ids to the mouth shapes. Each part's image must be padded so that its pivot is the exact centre of its canvas. The face overlays share the head's canvas and pivot.

If the brief supplies only a single drawing, with no parts or pivots, you can't cut a rig blind. Tell the user, and ask for a pre-cut rig.

## Bake the rig

<!-- workaround: #499 · replaced by: parenting or a group transform -->
<!-- workaround: #518 · replaced by: an image that changes over time -->

Montagent has no parenting, and an element can't change its image. So a character is baked: the bundled script works out every part's on-screen position and rotation from its parents at every drawn frame, and writes each mouth shape and blink as its own element, shown for its own span with the head's transform. Don't write this yourself.

`python3 scripts/bake_rig.py <project> <rig> <spec>` prints the project with one track per part added. Run it with `--help` for the spec: where the character stands, named poses, the moves between them, swings, hops, the voice and its viseme file, and the blinks. Run it again after every change to the spec. It replaces only the tracks it wrote. Keep the spec next to the project: it is the character's real source.

**Read its report.** It lists every mouth span it merged, the largest gap between any child and its parent over every drawn frame, and the instants to look at: each move's arrival and each joint's extreme angles. Positions are whole pixels, so a gap of up to about 1.5 px is rounding, hidden by the round joints. A larger gap means the rig's pivots are wrong.

`validate` reports `R-EASE-INERT` on each pose the character holds, and `N-TRACK-GAP` on the mouth and blink tracks between spans. Both are expected (see the findings guide).

The baked result looks like this: each part is centred on its pivot, with keyframes only where it moves, and each mouth or blink element copies the head's transform over its span.

```json
{
  "frame": {"width": 640, "height": 360}, "fps": 30, "background": "#2E3440", "duration": 2000, "output": "out/baked.mp4",
  "tracks": [
    {"name": "set", "layer": 0, "elements": [
      {"id": "set", "type": "image", "start": 0, "end": 2000, "source": "media/still.png", "x": 0, "y": 0, "origin": "top-left", "width": 640, "height": 360, "fit": "literal"}
    ]},
    {"name": "puppet-torso", "layer": 10, "elements": [
      {"id": "puppet-torso", "type": "image", "start": 0, "end": 2000, "source": "rig/parts/torso.png", "x": 320, "y": 330, "origin": "center", "fit": "literal", "width": 80, "height": 280}
    ]},
    {"name": "puppet-head", "layer": 12, "elements": [
      {"id": "puppet-head", "type": "image", "start": 0, "end": 2000, "source": "rig/parts/head.png", "x": 320, "y": 190, "origin": "center", "fit": "literal", "width": 90, "height": 160, "rotation": [{"t": 0, "v": 0}, {"t": 500, "v": 6.0, "ease": "linear"}, {"t": 1000, "v": 0.0, "ease": "linear"}]}
    ]},
    {"name": "puppet-mouth", "layer": 13, "elements": [
      {"id": "puppet-mouth-0", "type": "image", "start": 400, "end": 700, "source": "rig/parts/mouth_open.png", "x": 320, "y": 190, "origin": "center", "fit": "literal", "width": 24, "height": 60, "rotation": [{"t": 400, "v": 4.8}, {"t": 500, "v": 6.0, "ease": "linear"}, {"t": 666, "v": 4.0, "ease": "linear"}]}
    ]}
  ]
}
```

## Recipes

Every recipe gives starting ranges, not answers. Each ends in a **look step**: load `montagent-craft`, then look where the step says before you move on.

Angles are in degrees from the drawn rest pose, each relative to its parent, and positive turns clockwise on screen. So an arm on the viewer's right rises with negative angles, and one on the viewer's left rises with positive ones.

### Stand it in the set

- **Backdrop:** a full-frame set image at `origin` `top-left`, at 0, 0, the size of the frame, on the lowest layer. Set the `origin` explicitly.
- **Feet on the floor:** the rig's root (the body, pivoting at the feet) goes where the floor meets the wall's shadow line, or a little in front of it. On a 1080-tall set, the floor's top edge is usually 80–85 % of the way down, so put the feet 5–10 % below that.
- **Size:** the character 55–75 % of the frame's height, set by the spec's scale (frame px per drawing px). Measure the visible character, not the padded drawing: the drawing's height times the scale overstates it.
- **Place:** off-centre to the side opposite its prop or card, a third of the way in, unless it stands alone.
- **Look:** `frame` at a resting moment, and check the feet sit on the floor, not floating above it or sunk into it, and that the head is clear of the frame's top by at least 5 %.

### Entrance: hop in

- **Hops:** 2–3, each 300–450 ms, getting lower: the first 8–12 % of the character's height, the last 4–6 %. The horizontal move covers the same span on `ease-out`, so the last hop lands softly.
- **Pose:** arms down while it hops. Land on a drawn frame, and hold 150–300 ms before the first gesture.
- **Timing:** finish before the voice starts, with at least 200 ms to spare.
- **Look:** `frame --from --to --keyframes` over the entrance. Check the feet touch the floor at each landing tile, and no part trails or jumps ahead of the body.

### Gestures

A gesture is a named pose, and moves into and out of it. Give each move a lead-in time (the spec's `in`) so the pose holds until it sets off. <!-- guard-ok: in -->

- **Arms down:** from a rest pose with the arms held out, turn each upper arm 40–55° towards the body, and the forearm 5–15° further.
- **Wave:** the upper arm raised 40–50° from rest, out to the side, and the forearm 25–35° further up. Swing the forearm from the elbow by 15–20° each way, with a period of 350–450 ms, for at least 2 full swings (800 ms or more). Raise it higher and the hand goes behind the head at the swing's inward extreme: the head draws over the arms.
- **Point at something:** the upper arm near horizontal towards the target (10–25° up from rest for an arm held out and down), and the forearm within 20° of straight, so the hand aims at the target's near edge. Arrive 1–3 frames before the word that names it.
- **Cheer:** both upper arms up 40–50°, and the forearms a further 20–30° up. Bend them further and the hands tuck behind the head at the overshoot's peak.
- **Moves:** in over 250–400 ms. Arrive on the overshoot bezier `[0.34, 1.56, 0.64, 1]`, and go back to rest on `ease-in-out`. For follow-through, add a second move that names only the forearm, 2–4 frames after the upper arm's.
- **Never frozen:** the head tilts 2–5° on stressed words, as a short swing or a move there and back over 250–400 ms. A character that holds a pose for more than 1.5 s with nothing moving reads as a still.
- **Look:** for each gesture, `frame --at` the instants the bake report lists for that joint's extremes. Check the hand is clear of the head and frame edge, and the pose reads as the gesture without the sound. Then `frame --crop` at the shoulder and the elbow on the most raised pose, at true scale, and check for a gap or a loose part.

### Lip sync from visemes

<!-- workaround: #518 · replaced by: an image that changes over time -->

The bake writes the mouth from the voice's viseme file. Each viseme id maps to a mouth through the rig's table, and silence is the beak or lips at rest, with no overlay. Name the voice element and the viseme file in the spec. The mouth then follows that element's start and source range, so moving the voice and baking again keeps the sync.

- **Shortest shape:** 2 frames. The bake merges a shorter one into the shape before it and reports each merge. A dozen merges in a 6 s line is normal.
- **Lead:** 0 ms. If the mouth feels late when you watch the render, lead by one frame (33 ms at 30 fps), never more.
- **Timings:** probe the voice file. When its length disagrees with the viseme file's stated duration, trust the probe.
- **Look:** `query --at` the middle of three spoken words, and check one mouth element is on at each. Then `query --at` the middle of the longest pause and after the line ends, and check none is.

### Blinks

<!-- workaround: #518 · replaced by: an image that changes over time -->

- **Length:** 3 frames (100 ms at 30 fps), 4 at most.
- **Rhythm:** every 2–4 s, irregular, never on a beat. Put one just after a big move lands, and one in a pause in the line. At least 2 in any 8 s.
- **Avoid:** a blink in the same frame as a gesture's arrival, which hides the arrival.
- **Look:** `frame --at` the middle frame of one blink, and check the closed eyes sit exactly on the head, at its tilt.

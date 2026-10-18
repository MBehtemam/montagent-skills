# A character short

A short of 6–15 s where a mascot or puppet speaks one line in a set, gestures at something, and ends on a brand moment. Plan it on the voice: the line's word timings are the clock for every gesture, prop and cut.

## Structure

| Beat | Length | What happens |
|---|---|---|
| Entrance | 0.6–1.2 s | The character hops or walks in and lands in its spot, arms down. The voice hasn't started. |
| Greeting | the first phrase | A wave, arriving 1–3 frames before the first stressed word. |
| The point | the middle phrases | A prop or card pops in beside the character as the word that names it is said, and the arm on that side points at it. A picture inside the card changes on the word that changes it, not before. |
| Payoff | the last phrase, then 0.8–1.5 s | The brand lockup lands, and the character cheers or nods. Hold the final pose with a blink or a small head tilt, so the end isn't a freeze. |

- **One gesture per phrase.** Go back towards rest between gestures, even part of the way. A character that jumps straight from pose to pose looks mechanical.
- **Gestures land on stressed words,** not on the start of a phrase. Find the stress in the word timings: usually the longest word, or the name.
- **The voice starts on a drawn frame** after the entrance has landed. Leave 0.5–1 s of picture after it ends.
- **A prop or card** sits on the side the character faces or points to, clear of the head and hands at every pose. Its pop and the point arrive within 100 ms of each other. The card's recipes (a pop on the overshoot bezier, a picture that changes) are in `montagent-motion`.
- **No music** unless the brief asks for it.

## A spec to start from

For a 1920×1080, 8 s short, with a rig whose drawing is about 1500 px tall, standing on a floor at about y 990, and a voice element starting at 1000. Tune the angles on the look steps: they depend on the rig's rest pose.

```json fragment
{
  "prefix": "char", "layer": 10, "start": 0, "end": 8000, "scale": 0.65,
  "place": [{"t": 0, "x": -350, "y": 990}, {"t": 800, "x": 760, "ease": "ease-out"}],
  "hops": [{"from": 0, "to": 400, "height": 70}, {"from": 400, "to": 800, "height": 45}],
  "poses": {
    "down": {"upper_arm_left": -50, "upper_arm_right": 50, "forearm_left": -10, "forearm_right": 10},
    "wave": {"upper_arm_right": -45, "forearm_right": -30},
    "point": {"upper_arm_right": -15, "forearm_right": 10},
    "cheer": {"upper_arm_left": 46, "upper_arm_right": -46, "forearm_left": 26, "forearm_right": -26},
    "nod": {"head": 4}, "level": {"head": 0}
  },
  "moves": [
    {"t": 0, "pose": "down"},
    {"t": 1250, "pose": "wave", "in": 300, "ease": [0.34, 1.56, 0.64, 1]},
    {"t": 2300, "pose": "down", "in": 350},
    {"t": 3700, "pose": "point", "in": 350, "ease": [0.34, 1.56, 0.64, 1]},
    {"t": 3800, "pose": "nod", "in": 200}, {"t": 4100, "pose": "level", "in": 300},
    {"t": 5900, "pose": "down", "in": 350},
    {"t": 7000, "pose": "cheer", "in": 300, "ease": [0.34, 1.56, 0.64, 1]}
  ],
  "swings": [{"joint": "forearm_right", "from": 1250, "to": 2100, "degrees": 18, "period": 400}],
  "voice": {"id": "voice", "visemes": "voice/line-1.json"},
  "blinks": {"part": "eyes_closed", "at": [2600, 4900, 6400, 7500], "frames": 3}
}
```

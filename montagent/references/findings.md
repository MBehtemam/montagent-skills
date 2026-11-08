# Findings guide

Each finding explains itself: its text says what is wrong, and an advise-class finding also gives the repair. This guide lists only the findings that fire on correct work, and what to do about each. Act on every finding it doesn't list.

## Caption checks on text that isn't a caption

`R-CAPTION-MIN-DURATION`, `R-CAPTION-NO-AUDIO`, `R-CAPTION-PACE` and `R-CAPTION-REPEAT-DURATION` fire on every text element that doesn't say `caption: false`. Write `caption: false` on titles, typed letters, kinetic words, labels and HUD text, and the four checks skip it. On real captions (words that transcribe speech), leave the field out and act on the findings.

## `R-EASE-INERT` on a deliberate hold

A hold is two equal keyframes in a row: a title that waits before it leaves, or a pose in a rig baked frame by frame. `R-EASE-INERT` fires on every hold, whichever ease you give it, and that is by design: it makes you confirm that the stillness is meant. When it is, skip the finding and don't spend turns rewriting the hold to quiet it. When the hold ends in an instant change rather than a move, write that change as a `step` to the new value (see the starter's title). That needs no hold, so nothing fires.

## Audio effects, `pan` and `channels`

- `E-NOISE-RANGE`, `E-PAN-RANGE` and `E-ECHO-RANGE` give the nearest valid bound in their repair: clamp `reduction_db` to `5..20`, `pan` to `-1..1`, and `echo`'s `delay_ms` (`1..2000`), `feedback` (`0..0.95`) and `mix` (`0..1`) to their bounds.
- `R-PAN-INERT` (`pan: 0`) and `R-CHANNELS-INERT` (`channels: "stereo"`) flag explicit identity values that emit no filter; delete the field unless pinning to the default is deliberate.
- `R-CHANNELS-ON-MONO-SOURCE` fires when `channels` is `"swap"`, `"mono"`, `"left"` or `"right"` on a 1-channel source (which upmixes to identical L and R on the bus before `channels` runs); remove `channels`.
- `R-NOISE-AFTER-COMPRESSOR` fires when `reduce_noise` follows `compressor` on the same element; move `reduce_noise` ahead of `compressor` so noise reduction sees the uncompressed noise floor.
- `R-ECHO-HOT` fires when enabled `echo` members have a combined worst-case peak gain above `3.0×`; lower `mix` or `feedback`, or follow with a `limiter`. `N-ECHO-NO-OP` (`mix < 0.001`) and `N-ECHO-TAPS-CAPPED` (8th tap `> 0.01`) are informational notes.

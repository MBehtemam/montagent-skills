# Findings guide

Each finding explains itself: its text says what is wrong, and an advise-class finding also gives the repair. This guide lists only the findings that fire on correct work, and what to do about each. Act on every finding it doesn't list.

## Caption checks on text that isn't a caption

`R-CAPTION-MIN-DURATION`, `R-CAPTION-NO-AUDIO`, `R-CAPTION-PACE` and `R-CAPTION-REPEAT-DURATION` fire on every text element that doesn't say `caption: false`. Write `caption: false` on titles, typed letters, kinetic words, labels and HUD text, and the four checks skip it. On real captions (words that transcribe speech), leave the field out and act on the findings.

## `R-EASE-INERT` on a deliberate hold

A hold is two equal keyframes in a row: a title that waits before it leaves, or a pose in a rig baked frame by frame. `R-EASE-INERT` fires on every hold, whichever ease you give it, and that is by design: it makes you confirm that the stillness is meant. When it is, skip the finding and don't spend turns rewriting the hold to quiet it. When the hold ends in an instant change rather than a move, write that change as a `step` to the new value (see the starter's title). That needs no hold, so nothing fires.

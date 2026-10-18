#!/usr/bin/env python3
"""Find a music track's beat grid, lay the track in so a downbeat lands where you want it,
and print the grid on the project's own frames.

    python3 beat_grid.py <project> <spec>

Requires Python >= 3.9
Standard library only, plus ffmpeg on PATH.
# workaround: #547 · replaced by: tempo and downbeat from probe
drift-guard: type_on.montagent.json beat_grid.spec.json

Montagent reads no tempo from an audio file, so this listens to it: it decodes the track
with ffmpeg, follows its onsets (the moments it gets suddenly louder), takes the tempo from
how those repeat, finds where the beats fall, and picks as the downbeat the beat of each
bar that hits hardest. Give `bpm` when the track states it, and `downbeat` too when you
know it, and less is guessed.

Prints <project> with the track on the spec's track, placed so the first downbeat it found
plays at `at`, held at `volume`, and faded to 0 over the last `fade` ms so that it reaches 0
on its last drawn frame. Running it again replaces that track.

On stderr it prints the grid as JSON, in project milliseconds, every time on a drawn frame:

    {"bpm": 100.0, "beat": 600.0, "bar": 2400.0, "source_downbeat": 300,
     "tempo_confidence": 3.1, "downbeat_confidence": 1.6,
     "downbeats": [0, 2400, ...], "beats": [0, 600, 1200, ...]}

A confidence is the winner's score over the runner-up's (tempo: over the median tempo).
Under 1.5 the guess is weak: listen to the track, or look at its waveform, and give `bpm`
or `downbeat` in the spec. A tempo off by exactly 2x or 0.5x is the usual mistake: set
`range` to the tempo you hear.

<spec> is a JSON file:

    {
      "source": "media/bed.wav",  required: the track, relative to <project>
      "id": "bed",                the audio element's id (default "music")
      "track": "music",           the track's name (default "music")
      "layer": 0,                 (default 0)
      "at": 0,                    the project time the first downbeat plays at (default 0)
      "bpm": 120,                 the tempo, when it is known: skips the tempo search
      "downbeat": 0,              the first downbeat in the source (ms), when it is known
      "range": [70, 180],         the tempos to consider, in BPM (default [60, 200])
      "beats_per_bar": 4,         (default 4)
      "volume": 0.8,              (default 0.8)
      "fade": 1000                the fade-out at the end, in ms; 0 for none (default 1000)
    }
"""

import json
import math
import os
import subprocess
import sys
from array import array

RATE = 11025  # decode rate: enough for drums, small enough for plain Python
HOP = 64  # one onset sample every 5.8 ms
TIE = 1.15  # a downbeat louder than the bar's next-loudest beat by less than this is a tie


def main(argv):
    if "--help" in argv or "-h" in argv or len(argv) != 2:
        print(__doc__)
        return 0 if "--help" in argv or "-h" in argv else 2
    project_path, spec_path = argv
    with open(project_path) as f:
        project = json.load(f)
    with open(spec_path) as f:
        spec = json.load(f)
    fps = project["fps"]

    def on_frame(t):
        """The drawn instant nearest to t: frame n is drawn at floor(n * 1000 / fps)."""
        return math.floor(round(t * fps / 1000) * 1000 / fps)

    def last_drawn(end):
        """The last drawn instant before a half-open end."""
        return math.floor((math.ceil(end * fps / 1000) - 1) * 1000 / fps)

    source = os.path.join(os.path.dirname(os.path.abspath(project_path)), spec["source"])
    per_bar = spec.get("beats_per_bar", 4)
    samples = decode(source)
    length = len(samples) * 1000 / RATE
    energy = loudness(samples)
    onsets = onset_strength(energy)

    tempo_confidence = None
    if "bpm" in spec:
        bpm = float(spec["bpm"])
    else:
        low, high = spec.get("range", [60, 200])
        bpm, tempo_confidence = find_tempo(onsets, low, high)
    beat = 60000 / bpm

    downbeat_confidence, downbeat_by = None, "spec"
    if "downbeat" in spec:
        downbeat = float(spec["downbeat"])
    else:
        phase = find_phase(onsets, beat)
        if "bpm" not in spec:
            beat, phase = fit_beats(onsets, beat, phase)
            bpm = 60000 / beat
        if phase > beat * 7 / 8:
            phase -= beat  # a beat a few ms before the track starts is a beat at its start
        downbeat, downbeat_confidence, downbeat_by = find_downbeat(energy, beat, phase, per_bar)

    # Lay the track in: its first downbeat plays at `at`.
    at = spec.get("at", 0)
    source_start = downbeat - at
    start = 0
    if source_start < 0:
        start, source_start = on_frame(-source_start), 0
    source_start = round(source_start)
    end = min(project["duration"], start + math.floor(length - source_start))
    if end < project["duration"]:
        print(f"the track runs out at {end} ms, before the project's {project['duration']} ms",
              file=sys.stderr)
    element = {
        "id": spec.get("id", "music"), "type": "audio", "start": start, "end": end,
        "source": spec["source"], "source_start": source_start,
        "source_end": source_start + (end - start),
    }
    volume, fade = spec.get("volume", 0.8), spec.get("fade", 1000)
    if fade:
        last = last_drawn(end)
        element["volume"] = [{"t": on_frame(last - fade), "v": volume},
                             {"t": last, "v": 0.0, "ease": "linear"}]
    else:
        element["volume"] = volume

    name = spec.get("track", "music")
    tracks = [t for t in project.get("tracks", []) if t["name"] != name]
    tracks.append({"name": name, "layer": spec.get("layer", 0), "elements": [element]})
    project["tracks"] = tracks
    json.dump(project, sys.stdout, indent=2)
    print()

    # The grid, in project time, from the first beat on screen to the element's end.
    first = at - math.floor((at - start) / beat) * beat
    beats, downbeats, k = [], [], 0
    while first + k * beat < end:
        t = first + k * beat
        beats.append(on_frame(t))
        if round((t - at) / beat) % per_bar == 0:
            downbeats.append(on_frame(t))
        k += 1
    grid = {
        "bpm": round(bpm, 2), "beat": round(beat, 2), "bar": round(beat * per_bar, 2),
        "source_downbeat": round(downbeat),
        "tempo_confidence": tempo_confidence, "downbeat_confidence": downbeat_confidence, "downbeat_by": downbeat_by,
        "downbeats": downbeats, "beats": beats,
    }
    print(json.dumps(grid), file=sys.stderr)
    return 0


def decode(path):
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
        capture_output=True,
    )
    if out.returncode != 0:
        sys.exit(f"ffmpeg could not decode {path}:\n{out.stderr.decode()[-2000:]}")
    samples = array("h")
    samples.frombytes(out.stdout[: len(out.stdout) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    return samples


def loudness(samples):
    """Each hop's mean power, on a log scale."""
    energy = []
    for i in range(0, len(samples) - HOP + 1, HOP):
        frame = samples[i:i + HOP]
        energy.append(math.log(1e-3 + sum(v * v for v in frame) / HOP))
    return energy


def onset_strength(energy):
    """How much louder each hop is than the one before; never negative."""
    onsets = [0.0] + [max(0.0, b - a) for a, b in zip(energy, energy[1:])]
    peak = max(onsets) or 1.0
    return [o / peak for o in onsets]


def strength_at(onsets, ms):
    """The strongest onset within a hop of ms: beats land within a few ms of a hop."""
    i = round(ms * RATE / 1000 / HOP)
    return max(onsets[max(0, i - 1):i + 2] or [0.0])


def find_tempo(onsets, low, high):
    """The tempo whose period the onsets repeat at best, leaning towards 120 BPM, then
    refined by fitting a comb of beats to the whole track."""
    hop_ms = HOP * 1000 / RATE
    n = len(onsets)
    scores = {}
    for lag in range(max(1, int(60000 / high / hop_ms)), int(60000 / low / hop_ms) + 1):
        if lag >= n:
            break
        r = sum(onsets[i] * onsets[i + lag] for i in range(n - lag)) / (n - lag)
        bpm = 60000 / (lag * hop_ms)
        # A gentle prior: one octave either side of 120 BPM halves the weight.
        scores[lag] = r * math.exp(-0.5 * math.log2(bpm / 120) ** 2)
    if not scores:
        sys.exit("the track is too short to find a tempo in: give `bpm` in the spec")
    best = max(scores, key=scores.get)
    ranked = sorted(scores.values())
    confidence = round(scores[best] / (ranked[len(ranked) // 2] or 1e-9), 2)
    coarse = 60000 / (best * hop_ms)
    candidates = [coarse * (1 + d / 1000) for d in range(-40, 41, 1)]
    bpm = max(candidates, key=lambda b: comb(onsets, 60000 / b, find_phase(onsets, 60000 / b)))
    return bpm, confidence


def comb(onsets, beat, phase):
    length = len(onsets) * HOP * 1000 / RATE
    times = [phase + k * beat for k in range(int((length - phase) / beat) + 1)]
    return sum(strength_at(onsets, t) for t in times) / max(1, len(times))


def find_phase(onsets, beat):
    """Where in the first beat the beats fall: the offset whose comb hits hardest."""
    step = HOP * 1000 / RATE
    offsets = [k * step for k in range(int(beat / step) + 1)]
    return max(offsets, key=lambda p: comb(onsets, beat, p))


def fit_beats(onsets, beat, phase):
    """Sharpen the comb: find the onset peak nearest each beat it predicts, and fit a
    straight line through the strong ones. Returns (beat, phase) in ms."""
    hop_ms = HOP * 1000 / RATE
    length = len(onsets) * hop_ms
    reach = max(1, round(beat / 8 / hop_ms))
    points = []
    k = 0
    while phase + k * beat < length:
        i = max(0, round((phase + k * beat) / hop_ms))
        window = range(max(0, i - reach), min(len(onsets), i + reach + 1))
        if window:
            j = max(window, key=lambda w: onsets[w])
            if onsets[j] > 0.3:
                points.append((k, j * hop_ms))
        k += 1
    if len(points) < 4:
        return beat, phase
    n = len(points)
    mk = sum(k for k, _ in points) / n
    mt = sum(t for _, t in points) / n
    slope = sum((k - mk) * (t - mt) for k, t in points) / sum((k - mk) ** 2 for k, _ in points)
    return slope, mt - slope * mk


def find_downbeat(energy, beat, phase, per_bar):
    """The first beat of the bar: of the bar's beats, the loudest on average over the
    100 ms after it lands."""
    hop_ms = HOP * 1000 / RATE
    span = max(1, round(100 / hop_ms))
    length = len(energy) * hop_ms
    floor = min(energy)
    totals = [0.0] * per_bar
    counts = [0] * per_bar
    k = 0
    while phase + k * beat < length:
        i = max(0, round((phase + k * beat) / hop_ms))
        window = energy[i:i + span]
        if window:
            totals[k % per_bar] += sum(window) / len(window) - floor
            counts[k % per_bar] += 1
        k += 1
    means = [t / max(1, c) for t, c in zip(totals, counts)]
    order = sorted(range(per_bar), key=lambda j: means[j], reverse=True)
    confidence = round(means[order[0]] / (means[order[1]] or 1e-9), 2) if per_bar > 1 else None
    if confidence is None or confidence >= TIE:
        return phase + order[0] * beat, confidence, "loudest"
    # No beat of the bar stands out: most music starts on a downbeat, so take the first
    # beat that has sound.
    heard = floor + 0.5 * (max(energy) - floor)
    k = 0
    while phase + k * beat < length:
        i = max(0, round((phase + k * beat) / hop_ms))
        if max(energy[i:i + span] or [floor]) >= heard:
            return phase + k * beat, confidence, "first"
        k += 1
    return phase, confidence, "first"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

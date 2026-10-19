#!/usr/bin/env python3
"""Non-normative ink-on-paper reference, never a renderer effect (#934).

Requires Python >= 3.9; standard library and ffmpeg/ffprobe on PATH.
    python3 stabilize.py build <spec.json>
    python3 stabilize.py rebuild <name.recipe>
    python3 stabilize.py render <settings.json>   internal raw RGBA producer

Spec: source, name, width, height, fps, reference_frame (zero-based), fill
(paper|edge), paper ([R,G,B]); optional out (.), ping_pong (false), slowdown
(positive integer, default 1). Source must be opaque, constant-rate ink on
uniform light paper, at the specified size and fps, at least four frames.
Tracks darkness-weighted centroid and RMS radial spread with a cubic fit.
Bilinear inverse sampling locks to the measured reference frame. Paper fill
uses the literal colour; edge fill clamps coordinates. No rotation, parallax,
changing drawings, occlusion or arbitrary scene tracking. All frames are held
in memory: use short clips. Acceptance, rather than this tracker, decides.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction


def fail(message):
    raise ValueError(message)


def command(argv, **kwargs):
    return subprocess.run(list(map(str, argv)), check=True, **kwargs)


def versions():
    return {"python": sys.version.split()[0], **{
        tool: command([tool, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
        for tool in ("ffmpeg", "ffprobe")}}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(frame, width, paper):
    total = sx = sy = squared = 0.0
    for offset in range(0, len(frame), 4):
        r, g, b, alpha = frame[offset:offset + 4]
        if alpha != 255:
            fail("source must be opaque ink on paper")
        weight = max(0.0, sum(paper) / 3 - (r + g + b) / 3)
        x, y = (offset // 4) % width, (offset // 4) // width
        total += weight
        sx += weight * x
        sy += weight * y
        squared += weight * (x * x + y * y)
    if total == 0:
        fail("frame has no measurable ink")
    cx, cy = sx / total, sy / total
    spread = math.sqrt(max(0.0, squared / total - cx * cx - cy * cy))
    if spread == 0:
        fail("ink has zero spread")
    return cx, cy, spread


def cubic(values):
    """Least squares in normalized frame time; pivoted 4x4 elimination."""
    times = [2 * i / (len(values) - 1) - 1 for i in range(len(values))]
    matrix = [[sum(t ** (row + col) for t in times) for col in range(4)] +
              [sum(value * t ** row for t, value in zip(times, values))]
              for row in range(4)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda row: abs(matrix[row][col]))
        matrix[col], matrix[pivot] = matrix[pivot], matrix[col]
        divisor = matrix[col][col]
        if abs(divisor) < 1e-12:
            fail("cubic fit is singular")
        matrix[col] = [v / divisor for v in matrix[col]]
        for row in range(4):
            if row != col:
                factor = matrix[row][col]
                matrix[row] = [a - factor * b for a, b in zip(matrix[row], matrix[col])]
    coefficients = [matrix[i][4] for i in range(4)]
    return [sum(value * t ** power for power, value in enumerate(coefficients)) for t in times]


def transform(frame, width, height, measured, reference, settings):
    cx, cy, spread = measured
    rx, ry, reference_spread = reference
    if spread <= 0:
        fail("cubic fitted a non-positive spread")
    ratio = spread / reference_spread
    paper = bytes(settings["paper"] + [255])

    def pixel(x, y):
        if settings["fill"] == "paper" and not (0 <= x < width and 0 <= y < height):
            return paper
        x, y = min(width - 1, max(0, x)), min(height - 1, max(0, y))
        offset = (y * width + x) * 4
        return frame[offset:offset + 4]

    result = bytearray()
    for y in range(height):
        for x in range(width):
            u, v = cx + (x - rx) * ratio, cy + (y - ry) * ratio
            left, top = math.floor(u), math.floor(v)
            dx, dy = u - left, v - top
            samples = (pixel(left, top), pixel(left + 1, top),
                       pixel(left, top + 1), pixel(left + 1, top + 1))
            weights = ((1 - dx) * (1 - dy), dx * (1 - dy), (1 - dx) * dy, dx * dy)
            result.extend(round(sum(sample[channel] * weight for sample, weight in zip(samples, weights)))
                          for channel in range(4))
    return bytes(result)


def render(settings_path):
    settings = json.loads(Path(settings_path).read_text())
    if versions() != settings["versions"]:
        fail("tool versions differ from recipe pins")
    if digest(settings["source"]) != settings["source_sha256"]:
        fail("source hash differs from recipe")
    width, height = settings["width"], settings["height"]
    raw = command(["ffmpeg", "-v", "error", "-i", settings["source"], "-map", "0:v:0",
                   "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgba", "-"], capture_output=True).stdout
    size = width * height * 4
    if len(raw) != size * settings["source_frames"]:
        fail("decoded source frame count or size differs from recipe")
    frames = [raw[i:i + size] for i in range(0, len(raw), size)]
    measured = [measure(frame, width, settings["paper"]) for frame in frames]
    reference = measured[settings["reference_frame"]]
    fits = list(zip(*(cubic([row[column] for row in measured]) for column in range(3))))
    stabilized = [transform(frame, width, height, fitted, reference, settings)
                  for frame, fitted in zip(frames, fits)]
    drift = max(abs(measure(frame, width, settings["paper"])[2] / reference[2] - 1)
                for frame in stabilized)
    if drift >= 0.01:
        fail(f"residual size drift {drift:.2%}, must be under 1%; use another tracker")
    for frame in stabilized:
        for y in range(height):
            for x in range(width):
                if x in (0, width - 1) or y in (0, height - 1):
                    offset = (y * width + x) * 4
                    if sum(frame[offset:offset + 3]) == 0:
                        fail("black edge in stabilized clip")
    order = list(range(len(frames)))
    if settings["ping_pong"]:
        order += list(range(len(frames) - 2, 0, -1))
    print(f"acceptance: residual size drift {drift:.4%}, no black edges", file=sys.stderr)
    for index in order:
        for _ in range(settings["slowdown"]):
            sys.stdout.buffer.write(stabilized[index])


def build(spec_path):
    spec_path = Path(spec_path).resolve()
    spec = json.loads(spec_path.read_text())
    for key in ("source", "name", "width", "height", "fps", "reference_frame", "fill", "paper"):
        if key not in spec:
            fail(f"spec needs {key}")
    for key in ("width", "height", "slowdown"):
        value = spec.get(key, 1)
        if type(value) is not int or value <= 0:
            fail(f"{key} must be a positive integer")
    if spec["fill"] not in ("paper", "edge"):
        fail("fill must be paper or edge")
    if (not isinstance(spec["paper"], list) or len(spec["paper"]) != 3 or
            any(type(v) is not int or not 0 <= v <= 255 for v in spec["paper"]) or
            min(spec["paper"]) < 128):
        fail("paper must be three light RGB bytes (128..255)")
    if type(spec.get("ping_pong", False)) is not bool:
        fail("ping_pong must be boolean")
    if not isinstance(spec["name"], str) or Path(spec["name"]).name != spec["name"] or spec["name"] in ("", ".", ".."):
        fail("name must be one filename component")
    fps = Fraction(str(spec["fps"]))
    if fps <= 0:
        fail("fps must be positive")
    source = (spec_path.parent / spec["source"]).resolve()
    probe = json.loads(command(["ffprobe", "-v", "error", "-select_streams", "v:0",
                               "-show_streams", "-show_frames", "-of", "json", source],
                              capture_output=True).stdout)
    stream = probe["streams"][0]
    count = len(probe["frames"])
    if count < 4:
        fail("cubic fit needs at least four source frames")
    if (stream["width"], stream["height"]) != (spec["width"], spec["height"]):
        fail("size must match source pixels; choose its largest shown size before baking")
    if Fraction(stream["avg_frame_rate"]) != fps:
        fail("fps must match source; resample to project fps before stabilization")
    times = [Fraction(frame["best_effort_timestamp"]) * Fraction(stream["time_base"])
             for frame in probe["frames"]]
    if any(abs((b - a) * fps - 1) > Fraction(1, 1000) for a, b in zip(times, times[1:])):
        fail("source must have constant frame timing")
    reference = spec["reference_frame"]
    if type(reference) is not int or not 0 <= reference < count:
        fail("reference_frame is outside source")
    settings = {key: spec[key] for key in ("width", "height", "fps", "reference_frame", "fill", "paper")}
    settings.update(source="source.mov", source_sha256=digest(source), source_frames=count,
                    fit_model="cubic", versions=versions(), ping_pong=spec.get("ping_pong", False),
                    slowdown=spec.get("slowdown", 1))
    frames = (2 * count - 2 if settings["ping_pong"] else count) * settings["slowdown"]
    harness = Path(__file__).resolve().parents[1] / "scripts/prerender.py"
    out = (spec_path.parent / spec.get("out", ".")).resolve()
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        shutil.copyfile(source, work / "source.mov")
        shutil.copyfile(__file__, work / "stabilize.py")
        (work / "stabilize.json").write_text(json.dumps(settings, indent=2) + "\n")
        build_spec = dict(name=spec["name"], out=str(out), width=spec["width"], height=spec["height"],
                          fps=spec["fps"], frames=frames, render=[sys.executable, "stabilize.py", "render", "stabilize.json"],
                          files=["source.mov", "stabilize.py", "stabilize.json"])
        (work / "build.json").write_text(json.dumps(build_spec))
        command([sys.executable, harness, "build", work / "build.json"])
    recipe_path = out / f"{spec['name']}.recipe/recipe.json"
    recipe = json.loads(recipe_path.read_text())
    recipe["stabilize"] = settings
    recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")


def main():
    if len(sys.argv) == 1 or sys.argv[1] in ("--help", "-h"):
        print(__doc__)
    elif len(sys.argv) == 3 and sys.argv[1] == "build":
        build(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "render":
        render(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "rebuild":
        harness = Path(__file__).resolve().parents[1] / "scripts/prerender.py"
        command([sys.executable, harness, "rebuild", sys.argv[2]])
    else:
        fail("use build <spec>, rebuild <recipe-dir>, or --help")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, IndexError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"stabilize: {error}")

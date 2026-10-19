#!/usr/bin/env python3
"""Turn a code-drawn piece or a Lottie into lossless footage, or an SVG into one PNG, with a
recipe beside it, rebuild it, and place it in a project.

    python3 prerender.py build <spec>             render, encode, verify, write the recipe
    python3 prerender.py rebuild <recipe-dir>     re-run the recipe, compare decoded frames
    python3 prerender.py place <project> <spec>   print <project> with the footage added
                                                  (a video, or an image for a .png)

Requires Python >= 3.9
Standard library only, plus ffmpeg on PATH (and `montagent` for `place`).
drift-guard: place type_on.montagent.json prerender.spec.json

`build` takes a JSON spec:

    {
      "name": "pulse",                 required: the footage is <out>/<name>.mov
      "out": "media",                  folder for the footage and its recipe (default ".")
      "width": 160, "height": 120,     required
      "fps": 25, "frames": 48,         required (fps may be a rational such as "30000/1001")
      "render": ["python3", "sample_piece.py"],  required: your code, as an argv
      "files": ["sample_piece.py"],    required: every file the code needs, copied into the recipe
      "input": "rgba",                 "rgba" (default): the code writes raw RGBA frames to stdout
                                       "png": it writes f00000.png, f00001.png ... into
                                       $PRERENDER_FRAMES_DIR
      "versions": {"pillow": ["python3", "-c", "import PIL; print(PIL.__version__)"]}
    }

An SVG still is the other input, `"input": "svg"`: one rasteriser run, one PNG, one frame.

    {
      "name": "mark", "out": "media",  the PNG is <out>/<name>.png, its recipe <out>/<name>.recipe/
      "svg": "art.svg",                required: the SVG, one of `files`
      "width": 480, "height": 270,     required: literal pixels, the largest size the piece is
                                       ever shown at; never read from the SVG's viewBox
      "render": ["resvg", "--skip-system-fonts", "--use-font-file", "Inter-Bold.ttf",
                 "-w", "{width}", "-h", "{height}", "art.svg", "{out}"],
                                       required: any tool that writes one RGBA PNG to {out};
                                       {width} and {height} are filled in with the literals
      "files": ["art.svg"],            required (the fonts below are added to it)
      "fonts": ["Inter-Bold.ttf"],     the vendored font files. Every font-family the SVG sets must
                                       be one of them, and the build fails otherwise; so does a
                                       font warning from the rasteriser. No fps, no frame count.
      "versions": {"resvg": ["resvg", "--version"]}   required: the rasteriser's version
    }

A Lottie animation is the third input, `"input": "lottie"`: footage, one fresh player per frame.

    {
      "name": "intro", "out": "media",  the footage is <out>/<name>.mov
      "lottie": "intro.json",          required: the Lottie file, one of `files`
      "width": 320, "height": 180,     required: literal pixels, the largest size the piece is
                                       ever shown at; the Lottie's own w and h are not read
      "fps": 25, "frames": 50,         required: the footage's, written here; the Lottie's own
                                       fr is an input to choose from, not a rule
      "start": 0, "step": 1,           the Lottie frame of footage frame 0 (default 0) and the
                                       Lottie frames per footage frame (default fr / fps); the
                                       frame of footage frame i is start + i * step, and a
                                       frame past the Lottie's out point fails
      "render": ["python3", "lottie_frame.py", "intro.json", "{width}", "{height}", "{frame}", "{out}"],
                                       required: the player, as an argv. It is run once per
                                       frame, a new process each time, and writes that frame as
                                       raw RGBA to {out}. Never one instance seeked forward
      "files": ["intro.json", "lottie_frame.py"],  required
      "fonts": ["Inter-Bold.ttf"],     the vendored font files, for text that has no embedded glyphs
      "allow_effects": ["Fill"],       layer effects (by name) the player is known to draw
      "notes": "...",                  kept in the recipe, e.g. the check that lets a player be reused
      "versions": {"thorvg": ["python3", "-c", "..."]}   required: the player's name and version
    }

The build fails, naming each, on a Lottie that uses an expression, a layer effect not in
`allow_effects`, or text whose font has neither embedded glyphs nor a vendored file, and on any
stderr line from the player that reports something skipped or ignored.

Paths in the spec resolve against the spec's folder, and the code runs there. It reads its
size from the environment: PRERENDER_WIDTH, PRERENDER_HEIGHT, PRERENDER_FPS,
PRERENDER_FRAMES (and PRERENDER_FRAMES_DIR for "png"). Use integer arithmetic or a fixed
seed, so the same code draws the same frames.

The footage is PNG in MOV, `-c:v png -pix_fmt rgba`, the one codec checked to return every
byte of RGBA, alpha included. `build` decodes it and fails on the first frame that differs
from what the code drew. The recipe, <out>/<name>.recipe/, holds the source files and
recipe.json (commands, tool versions, size, fps, frame count, one hash per decoded frame).
No project names it.

`rebuild` re-runs the recipe from its own copy of the code and compares decoded-frame hashes,
never file bytes. It also decodes the placed footage and compares that. Exit 0 on a match,
1 on a difference, with the first frame that differs.

`place` takes the project and a spec {"source": "media/pulse.mov", "id": "pulse",
"track": "prerender", "layer": 10, "at": 0, "x": ..., "y": ..., "origin": "center",
"width": ..., "height": ...}; every key but `source` is optional. It probes the footage,
refuses it when `probe` does not report alpha, and prints the project with a plain `video`
element added. For a `.png` it adds a plain `image` element instead, of the PNG's own pixel
size and `"fit": "contain"`, shown for `"duration"` ms (default: to the project's end).
An SVG's rebuild reports the first pixel that differs.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import struct
import tempfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

ENCODE = ["ffmpeg", "-y", "-v", "error", "{input}", "-c:v", "png", "-pix_fmt", "rgba", "{out}"]
DECODE = ["ffmpeg", "-v", "error", "{input}", "-f", "rawvideo", "-pix_fmt", "rgba", "-"]


def fail(message):
    sys.exit(f"prerender: {message}")


def run(argv, **kw):
    try:
        return subprocess.run(argv, check=True, **kw)
    except FileNotFoundError:
        fail(f"`{argv[0]}` is not on PATH")
    except subprocess.CalledProcessError as e:
        fail(f"`{' '.join(map(str, argv))}` exited {e.returncode}")


def expand(template, input, out=None):
    """Fill `{input}` (a list of arguments) and `{out}` (a path) into a command template."""
    argv = []
    for part in template:
        argv.extend(input if part == "{input}" else [out if part == "{out}" else part])
    return argv


def frames_input(recipe, work):
    """The ffmpeg input arguments that read the drawn frames from `work`."""
    fps = str(recipe["fps"])
    if recipe["input"] == "png":
        return ["-framerate", fps, "-start_number", "0", "-i", str(work / "f%05d.png")]
    size = f"{recipe['width']}x{recipe['height']}"
    return ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", size, "-r", fps,
            "-i", str(work / "frames.rgba")]  # fmt: skip


FONT_WARNING = re.compile(r"(?i)font.*(warn|no match|not found|missing|fail)|(warn|no match|not found|missing|fail).*font")


def draw_svg(recipe, source_dir, work):
    """Run the rasteriser once, to `work/f00000.png`; a font problem it reports is a failure."""
    out = work / "f00000.png"
    argv = [out.as_posix() if part == "{out}" else part for part in recipe["render"]]
    try:
        done = subprocess.run(argv, cwd=source_dir, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        fail(f"`{argv[0]}` is not on PATH")
    sys.stderr.write(done.stderr)
    if done.returncode != 0:
        fail(f"`{' '.join(argv)}` exited {done.returncode}")
    for line in done.stderr.splitlines():
        if FONT_WARNING.search(line):
            fail(f"the rasteriser could not set the text in a vendored font: {line.strip()}")
    if not out.exists():
        fail("the rasteriser wrote no PNG to {out}: the render argv needs `{out}` where the PNG goes")
    want = (recipe["width"], recipe["height"])
    got = png_size(out)
    if got != want:
        fail(f"the PNG is {got[0]}x{got[1]}, not the recipe's {want[0]}x{want[1]}: "
             "pass the literal size to the rasteriser")


def png_size(path):
    head = Path(path).read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        fail(f"{path} is not a PNG")
    return struct.unpack(">II", head[16:24])


GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "inherit", "initial"}


def font_families(path):
    """Lower-cased family names (name ids 1 and 16) of every face in a TTF, OTF or TTC."""
    data = Path(path).read_bytes()
    heads = [0]
    if data[:4] == b"ttcf":
        (count,) = struct.unpack(">I", data[8:12])
        heads = [struct.unpack(">I", data[12 + 4 * i : 16 + 4 * i])[0] for i in range(count)]
    names = set()
    for head in heads:
        (tables,) = struct.unpack(">H", data[head + 4 : head + 6])
        for i in range(tables):
            tag, _, offset, _ = struct.unpack(">4sIII", data[head + 12 + 16 * i : head + 28 + 16 * i])
            if tag != b"name":
                continue
            _, count, strings = struct.unpack(">HHH", data[offset : offset + 6])
            for j in range(count):
                platform, _, _, name_id, length, at = struct.unpack(
                    ">HHHHHH", data[offset + 6 + 12 * j : offset + 18 + 12 * j])
                if name_id in (1, 16):
                    raw = data[offset + strings + at : offset + strings + at + length]
                    names.add(raw.decode("utf-16-be" if platform in (0, 3) else "latin-1").strip().lower())
    return names


def check_fonts(svg_path, font_paths):
    """Fail unless every text span's font-family names a vendored font. Never a system font."""
    known = set()
    for font in font_paths:
        known |= font_families(font)
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError as e:
        fail(f"{svg_path} is not well-formed XML: {e}")
    parents = {child: parent for parent in root.iter() for child in parent}

    def families(value):
        return [f.strip().strip("'\"").strip() for f in value.split(",") if f.strip()]

    def own(el):
        if "font-family" in el.attrib:
            return families(el.attrib["font-family"])
        found = re.search(r"font-family\s*:\s*([^;]+)", el.attrib.get("style", ""))
        return families(found.group(1)) if found else None

    def vet(chain, where):
        if not chain or chain[0].lower() not in known:
            fail(f"{where} sets font-family `{', '.join(chain)}`, which is not a vendored font "
                 f"(vendored: {', '.join(sorted(known)) or 'none'}): vendor it or convert the text to outlines")

    local = lambda el: el.tag.rsplit("}", 1)[-1]
    for el in root.iter():
        if local(el) == "style":
            for found in re.finditer(r"font-family\s*:\s*([^;}]+)", el.text or ""):
                vet(families(found.group(1)), "a <style> rule")
        elif (chain := own(el)) is not None:
            vet(chain, f"<{local(el)}>")
    for el in root.iter():
        if local(el) != "text":
            continue
        node = el
        while node is not None and own(node) is None:
            node = parents.get(node)
        if node is None:
            fail("a <text> has no font-family, so the rasteriser would use a system font: "
                 "set font-family to a vendored font on it or on a parent")


SKIPPED = re.compile(r"(?i)skip|unsupported|not supported|ignor|dropp?ed|warn|not found|missing")


def lottie_layers(root):
    """Every layer of a Lottie, the root's and each precomp asset's."""
    yield from root.get("layers", [])
    for asset in root.get("assets", []):
        yield from asset.get("layers", [])


def lottie_expressions(node, found):
    """Append every expression a property carries (a string `x` beside its `k`)."""
    if isinstance(node, dict):
        if isinstance(node.get("x"), str) and "k" in node:
            found.append(node["x"])
        for value in node.values():
            lottie_expressions(value, found)
    elif isinstance(node, list):
        for value in node:
            lottie_expressions(value, found)


def check_lottie(path, font_paths, allow_effects=()):
    """Fail, naming each, on what a player would skip: expressions, layer effects not allowed,
    and text whose font has no embedded glyphs and no vendored file."""
    try:
        root = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        fail(f"{path} is not a readable Lottie JSON file: {e}")
    known = set()
    for font in font_paths:
        known |= font_families(font)
    fonts = {f.get("fName"): f for f in root.get("fonts", {}).get("list", [])}
    glyphs = {(c.get("fFamily"), c.get("style"), c.get("ch")) for c in root.get("chars", [])}
    problems = []
    for layer in lottie_layers(root):
        name = layer.get("nm", f"layer {layer.get('ind', '?')}")
        found = []
        lottie_expressions(layer, found)
        for expression in found:
            problems.append(f"layer `{name}` uses an expression: {expression.strip().splitlines()[0][:60]}")
        for effect in layer.get("ef", []):
            label = effect.get("mn") or effect.get("nm") or "unnamed"
            if label not in allow_effects and effect.get("nm") not in allow_effects:
                problems.append(f"layer `{name}` uses the layer effect `{label}`, which the player is not "
                                "recorded as drawing (`allow_effects` names the ones it is)")
        if layer.get("ty") != 5:
            continue
        for key in layer.get("t", {}).get("d", {}).get("k", []):
            style = key.get("s", {})
            font = fonts.get(style.get("f"))
            if font is None:
                problems.append(f"text layer `{name}` names the font `{style.get('f')}`, which the "
                                "Lottie does not list in `fonts`")
                continue
            family = font.get("fFamily")
            letters = {c for c in style.get("t", "") if c not in " \r\n\u0003"}
            bare = sorted(c for c in letters if (family, font.get("fStyle"), c) not in glyphs)
            if bare and (family or "").lower() not in known:
                problems.append(f"text layer `{name}` is set in `{family}` with no embedded glyphs for "
                                f"{''.join(bare)!r} and no vendored font file for it "
                                f"(vendored: {', '.join(sorted(known)) or 'none'}): embed the glyphs or vendor it")
    if problems:
        fail("the player would skip or substitute what the Lottie asks for:\n  " + "\n  ".join(problems))


def lottie_frame_list(spec, root):
    """The Lottie frame of every footage frame: start + i * step, exactly, then as a float."""
    fps = Fraction(str(spec["fps"]))
    step = Fraction(str(spec["step"])) if "step" in spec else Fraction(str(root["fr"])) / fps
    start = Fraction(str(spec.get("start", 0)))
    frames = [start + step * i for i in range(spec["frames"])]
    if frames and frames[-1] > Fraction(str(root.get("op", 0))):
        fail(f"footage frame {spec['frames'] - 1} is Lottie frame {float(frames[-1])}, past the "
             f"animation's out point {root.get('op')}: shorten `frames` or change `start` and `step`")
    return [float(f) for f in frames]


def draw_lottie(recipe, source_dir, work):
    """One fresh player process per frame; a skip or an ignore it reports is a failure."""
    size = recipe["width"] * recipe["height"] * 4
    one = work / "one.rgba"
    with open(work / "frames.rgba", "wb") as frames:
        for i, frame in enumerate(recipe["lottie_frames"]):
            one.unlink(missing_ok=True)
            argv = [part.replace("{frame}", repr(frame)).replace("{out}", one.as_posix())
                    for part in recipe["render"]]
            try:
                done = subprocess.run(argv, cwd=source_dir, stderr=subprocess.PIPE, text=True)
            except FileNotFoundError:
                fail(f"`{argv[0]}` is not on PATH")
            sys.stderr.write(done.stderr)
            if done.returncode != 0:
                fail(f"`{' '.join(argv)}` exited {done.returncode}")
            for line in done.stderr.splitlines():
                if SKIPPED.search(line):
                    fail(f"the player reports something skipped on footage frame {i}: {line.strip()}")
            data = one.read_bytes() if one.exists() else b""
            if len(data) != size:
                fail(f"footage frame {i}: the player wrote {len(data)} bytes to {{out}}, not "
                     f"{recipe['width']}x{recipe['height']} RGBA ({size})")
            frames.write(data)


def draw(recipe, source_dir, work):
    if recipe["input"] == "lottie":
        return draw_lottie(recipe, source_dir, work)
    if recipe["input"] == "svg":
        return draw_svg(recipe, source_dir, work)
    env = dict(os.environ)
    env.update(
        PRERENDER_WIDTH=str(recipe["width"]),
        PRERENDER_HEIGHT=str(recipe["height"]),
        PRERENDER_FPS=str(recipe["fps"]),
        PRERENDER_FRAMES=str(recipe["frames"]),
        PRERENDER_FRAMES_DIR=str(work),
    )
    if recipe["input"] == "png":
        run(recipe["render"], cwd=source_dir, env=env)
    else:
        with open(work / "frames.rgba", "wb") as f:
            run(recipe["render"], cwd=source_dir, env=env, stdout=f)


def stream_hashes(argv, size):
    """sha256 of each `size`-byte frame that `argv` writes to stdout."""
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE)
    hashes = []
    while True:
        chunk = proc.stdout.read(size)
        if not chunk:
            break
        if len(chunk) != size:
            fail("a partial frame came back")
        hashes.append(hashlib.sha256(chunk).hexdigest())
    if proc.wait() != 0:
        fail(f"`{' '.join(argv)}` failed")
    return hashes


def drawn_hashes(recipe, work):
    """Hashes of the frames the code drew: bytes of frames.rgba, or the PNGs decoded."""
    size = recipe["width"] * recipe["height"] * 4
    if recipe["input"] in ("rgba", "lottie"):
        data = (work / "frames.rgba").read_bytes()
        if len(data) != size * recipe["frames"]:
            fail(f"the code wrote {len(data)} bytes, not {recipe['frames']} frames of {size}")
        return [hashlib.sha256(data[i : i + size]).hexdigest() for i in range(0, len(data), size)]
    return stream_hashes(expand(DECODE, input=["-start_number", "0", "-i", str(work / "f%05d.png")]), size)


def encode(recipe, work, out):
    if recipe["input"] == "svg":  # the rasteriser's PNG is the footage, as written
        shutil.copyfile(work / "f00000.png", out)
        return
    run(expand(ENCODE, input=frames_input(recipe, work), out=str(out)))


def decoded_hashes(recipe, footage):
    size = recipe["width"] * recipe["height"] * 4
    return stream_hashes(expand(DECODE, input=["-i", str(footage)]), size)


def first_difference(want, got):
    for i in range(max(len(want), len(got))):
        if i >= len(want) or i >= len(got) or want[i] != got[i]:
            return i
    return None


def tool_versions(spec):
    found = {"python": sys.version.split()[0]}
    line = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout
    found["ffmpeg"] = line.splitlines()[0] if line else "unknown"
    for name, argv in spec.get("versions", {}).items():
        out = subprocess.run(argv, capture_output=True, text=True, cwd=spec["_dir"])
        text = (out.stdout.strip() or out.stderr.strip()).splitlines()
        found[name] = text[0] if text else "unknown"
    return found


def build(spec_path):
    spec_path = Path(spec_path).resolve()
    spec = json.loads(spec_path.read_text())
    spec["_dir"] = spec_path.parent
    kind = spec.get("input", "rgba")
    if kind not in ("rgba", "png", "svg", "lottie"):
        fail('`input` is "rgba", "png", "svg" or "lottie"')
    still = kind == "svg"
    lottie = kind == "lottie"
    extra = ("svg", "versions") if still else ("fps", "frames", "lottie", "versions") if lottie else ("fps", "frames")
    for key in ("name", "width", "height", "render", "files") + extra:
        if key not in spec:
            fail(f"the spec needs `{key}`" + (": the size is literal pixels, never read from a viewBox"
                                              if key in ("width", "height") and still else ""))
    if still:
        if spec["svg"] not in spec["files"]:
            fail("`svg` is one of `files`")
        spec["files"] = list(spec["files"]) + [f for f in spec.get("fonts", []) if f not in spec["files"]]
        check_fonts(spec["_dir"] / spec["svg"], [spec["_dir"] / f for f in spec.get("fonts", [])])
    if lottie:
        if spec["lottie"] not in spec["files"]:
            fail("`lottie` is one of `files`")
        spec["files"] = list(spec["files"]) + [f for f in spec.get("fonts", []) if f not in spec["files"]]
        fonts = [spec["_dir"] / f for f in spec.get("fonts", [])]
        check_lottie(spec["_dir"] / spec["lottie"], fonts, spec.get("allow_effects", []))
        lottie_frames = lottie_frame_list(spec, json.loads((spec["_dir"] / spec["lottie"]).read_text()))
    out_dir = (spec["_dir"] / spec.get("out", ".")).resolve()
    recipe_dir = out_dir / f"{spec['name']}.recipe"
    footage = out_dir / (f"{spec['name']}.png" if still else f"{spec['name']}.mov")
    out_dir.mkdir(parents=True, exist_ok=True)
    if recipe_dir.exists():
        shutil.rmtree(recipe_dir)
    for rel in spec["files"]:
        target = recipe_dir / "source" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(spec["_dir"] / rel, target)

    recipe = {"name": spec["name"], "width": spec["width"], "height": spec["height"]}
    if still:
        literal = {"{width}": str(spec["width"]), "{height}": str(spec["height"])}
        recipe.update(
            frames=1, input="svg", svg=spec["svg"], fonts=spec.get("fonts", []),
            render=[literal.get(part, part) for part in spec["render"]], decode=DECODE,
        )  # fmt: skip
    elif lottie:
        literal = {"{width}": str(spec["width"]), "{height}": str(spec["height"])}
        recipe.update(
            fps=spec["fps"], frames=spec["frames"], input="lottie", lottie=spec["lottie"],
            fonts=spec.get("fonts", []), allow_effects=spec.get("allow_effects", []),
            lottie_frames=lottie_frames, render=[literal.get(part, part) for part in spec["render"]],
            encode=ENCODE, decode=DECODE,
        )  # fmt: skip
        if "notes" in spec:
            recipe["notes"] = spec["notes"]
    else:
        recipe.update(
            fps=spec["fps"], frames=spec["frames"], input=kind,
            render=spec["render"], encode=ENCODE, decode=DECODE,
        )  # fmt: skip
    recipe["footage"] = os.path.relpath(footage, recipe_dir)
    recipe["versions"] = tool_versions(spec)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        draw(recipe, spec["_dir"], work)
        drawn = drawn_hashes(recipe, work)
        encode(recipe, work, footage)
    decoded = decoded_hashes(recipe, footage)
    bad = first_difference(drawn, decoded)
    if bad is not None:
        fail(f"the footage does not return the drawn pixels: frame {bad} differs")
    recipe["decoded_frame_sha256"] = decoded
    (recipe_dir / "recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
    print(f"footage {footage}\nrecipe  {recipe_dir}\n{len(decoded)} frames, decoded = drawn",
          file=sys.stderr)  # fmt: skip


def rebuild(recipe_dir):
    recipe_dir = Path(recipe_dir).resolve()
    recipe = json.loads((recipe_dir / "recipe.json").read_text())
    want = recipe["decoded_frame_sha256"]
    placed = (recipe_dir / recipe["footage"]).resolve()
    still = recipe["input"] == "svg"
    if still:
        source = recipe_dir / "source"
        check_fonts(source / recipe["svg"], [source / f for f in recipe["fonts"]])
    if recipe["input"] == "lottie":
        source = recipe_dir / "source"
        check_lottie(source / recipe["lottie"], [source / f for f in recipe["fonts"]], recipe["allow_effects"])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        draw(recipe, recipe_dir / "source", work)
        encode(recipe, work, work / ("rebuilt.png" if still else "rebuilt.mov"))
        rebuilt = decoded_hashes(recipe, work / ("rebuilt.png" if still else "rebuilt.mov"))
        ok = report("rebuild", want, rebuilt)
        if still and not ok and placed.exists():
            print(first_pixel_difference(recipe, placed, work / "rebuilt.png"))
    if placed.exists():
        ok &= report("footage", want, decoded_hashes(recipe, placed))
    else:
        print(f"footage: {placed} is missing")
        ok = False
    sys.exit(0 if ok else 1)


def raw_pixels(path):
    out = subprocess.run(expand(DECODE, input=["-i", str(path)]), capture_output=True)
    return out.stdout


def first_pixel_difference(recipe, was, now):
    """Where the rebuilt PNG first departs from the placed one, as x, y and both RGBA values."""
    a, b = raw_pixels(was), raw_pixels(now)
    for i in range(0, min(len(a), len(b)), 4):
        if a[i : i + 4] != b[i : i + 4]:
            x, y = (i // 4) % recipe["width"], (i // 4) // recipe["width"]
            return (f"first pixel that differs: ({x}, {y}), placed {tuple(a[i : i + 4])}, "
                    f"rebuilt {tuple(b[i : i + 4])}")
    return "no pixel differs in the first frames compared"


def report(label, want, got):
    bad = first_difference(want, got)
    if bad is None:
        print(f"{label}: match, {len(want)} frames")
        return True
    print(f"{label}: differs, first at frame {bad} ({len(want)} recorded, {len(got)} decoded)")
    return False


def place(project_path, spec_path):
    project_path = Path(project_path).resolve()
    project = json.loads(project_path.read_text())
    spec = json.loads(Path(spec_path).read_text())
    source = spec["source"]
    image = Path(source).suffix.lower() == ".png"
    probed = subprocess.run(["montagent", "probe", "--json", str(project_path.parent / source)],
                            capture_output=True, text=True)  # fmt: skip
    if not probed.stdout:
        fail(f"`montagent probe` printed nothing: {probed.stderr.strip()}")
    media = json.loads(probed.stdout)["media"][0]
    if not media["alpha"]["carries"]:
        fail(f"`probe` reports no alpha on {source}: encode it with `-pix_fmt rgba`")
    at = spec.get("at", 0)
    frame = project["frame"]
    if image:
        length = spec.get("duration", project.get("duration", 0) - at)
        if length <= 0:
            fail("an image needs `duration` in the placing spec, or a project `duration` past `at`")
        timing = {"source": source}
    else:
        length = media["quad"]["video_stream_ms"]
        timing = {"source": source, "source_start": 0, "source_end": length, "volume": 0}
    box = {"width": spec.get("width", media["dimensions"]["width"]),
           "height": spec.get("height", media["dimensions"]["height"])}  # fmt: skip
    fit = {"fit": spec.get("fit", "contain")}
    element = {
        "id": spec.get("id", Path(source).stem), "type": "image" if image else "video",
        "start": at, "end": at + length, **timing,
        "x": spec.get("x", frame["width"] // 2), "y": spec.get("y", frame["height"] // 2),
        "origin": spec.get("origin", "center"),
        # `validate` keeps each type's keys in its own order: an image has `fit` last
        **(box | fit if image else fit | box),
    }  # fmt: skip
    name = spec.get("track", "prerender")
    track = next((t for t in project["tracks"] if t["name"] == name), None)
    if track is None:
        track = {"name": name, "layer": spec.get("layer", 10), "elements": []}
        project["tracks"].append(track)
    track["elements"] = [e for e in track["elements"] if e["id"] != element["id"]] + [element]
    project["duration"] = max(project.get("duration", 0), element["end"])
    print(json.dumps(project, indent=2))


def main(argv):
    if not argv or argv[0] in ("--help", "-h"):
        print(__doc__)
    elif argv[0] == "build" and len(argv) == 2:
        build(argv[1])
    elif argv[0] == "rebuild" and len(argv) == 2:
        rebuild(argv[1])
    elif argv[0] == "place" and len(argv) == 3:
        place(argv[1], argv[2])
    else:
        fail("usage: build <spec> | rebuild <recipe-dir> | place <project> <spec>")


if __name__ == "__main__":
    main(sys.argv[1:])

#!/usr/bin/env python3
"""Expand compact mark declarations into canonical `.montagent.json` elements (US-4, #1152, #951).

    python3 marks.py <spec.json> <project.montagent.json> [--prune-overrides] [--adopt-edits | --force] [--inspect]

Requires Python >= 3.9
Standard library only (`montagent` on PATH for final validation).
drift-guard: marks.spec.json marks.montagent.json

Accepts a compact JSON spec containing:
  - `defaults`: shared element fields (plus optional `style`, `fade_in_ms`, `fade_out_ms`,
    `ease`, `track_prefix` defaulting to `"marks"`, `max_tracks` defaulting to 40, and
    `layer` / `layer_base` defaulting to 20),
  - `marks`: list of mark declarations, each carrying an explicit `id` or deriving a
    deterministic slug from `(type, start, label)` so inserting, removing, or reordering
    marks never shifts sibling IDs,
  - `overrides`: map of `<id> -> {field: value}` merged over the mark and shared defaults.

Behavior:
  - Packs non-overlapping marks deterministically across reused tracks (`<track_prefix>_1`,
    `<track_prefix>_2`, ...) and emits canonical elements with `"id": "mark_<id>"`,
    preserving all non-generated tracks and elements in `<project.montagent.json>`.
  - Places fade-out terminal keyframes on the last sampled frame instant strictly before
    `end` at the project's `fps` so `montagent validate` raises zero `R-KEYFRAME-UNREACHED`
    findings.
  - Refuses with a non-zero exit code when `overrides` names an `id` not present in `marks`,
    unless `--prune-overrides` is passed (which removes orphaned override entries).
  - Writes `<spec>.manifest.json` beside the compact spec file storing per-element SHA-256
    digests and source provenance. On subsequent runs, if any existing `mark_<id>` element in
    `<project.montagent.json>` was directly edited since the last generation, stops with a
    non-zero exit code and prints the per-element diff unless `--adopt-edits` (which folds
    direct JSON edits back into `overrides` in `<spec.json>`) or `--force` (which overwrites
    direct JSON edits from the compact spec) is passed.
  - `--inspect` prints a provenance table mapping each `mark_<id>`, assigned track,
    `[start, end)` window, and applied override keys back to its source mark entry.
"""

import copy
from fractions import Fraction
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HELPER_ONLY_KEYS = {
    "id",
    "kind",
    "anchor",
    "duration",
    "label",
    "text",
    "style",
    "fade_in_ms",
    "fade_out_ms",
    "ease",
    "track_prefix",
    "max_tracks",
    "layer_base",
}

CANONICAL_ELEMENT_ORDER = [
    "id",
    "type",
    "group",
    "start",
    "end",
    "layer",
    "source",
    "source_start",
    "source_end",
    "source_time",
    "x",
    "y",
    "motion_path",
    "origin",
    "width",
    "height",
    "fit",
    "clip",
    "font",
    "size",
    "line_height",
    "color",
    "align",
    "runs",
    "closed",
    "fill",
    "stroke",
    "stroke_width",
    "stroke_join",
    "stroke_miter_limit",
    "stroke_cap",
    "stroke_dash",
    "stroke_dash_offset",
    "trim_start",
    "trim_end",
    "trim_offset",
    "radius",
    "points",
    "letter_spacing",
    "features",
    "units",
    "path",
    "path_offset",
    "scale",
    "rotation",
    "swivel",
    "tilt",
    "perspective",
    "opacity",
    "blend",
    "motion_blur",
    "role",
    "speed",
    "overrun",
    "frame_blend",
    "volume",
    "pan",
    "channels",
    "markers",
    "effects",
    "audio_effects",
    "caption",
    "tracks",
]


def ceil_div(num: int, den: int) -> int:
    return -((-num) // den)


def fps_ratio(fps_field: Any) -> Tuple[int, int]:
    if isinstance(fps_field, dict):
        return int(fps_field["num"]), int(fps_field["den"])
    if isinstance(fps_field, (list, tuple)) and len(fps_field) == 2:
        return int(fps_field[0]), int(fps_field[1])
    if isinstance(fps_field, int) and not isinstance(fps_field, bool):
        return fps_field, 1
    fr = Fraction(str(fps_field))
    return fr.numerator, fr.denominator


def on_frame_instant(t_ms: float, fps_num: int, fps_den: int = 1) -> int:
    step_den = fps_den * 1000
    frame_idx = (2 * int(round(t_ms)) * fps_num + step_den) // (2 * step_den)
    return (frame_idx * step_den) // fps_num


def last_drawn_instant(end_ms: int, fps_num: int, fps_den: int = 1) -> int:
    step_den = fps_den * 1000
    last_frame = ceil_div(int(end_ms) * fps_num, step_den) - 1
    if last_frame < 0:
        return 0
    return (last_frame * step_den) // fps_num


def first_drawn_ceil_instant(start_ms: int, fps_num: int, fps_den: int = 1) -> int:
    step_den = fps_den * 1000
    first_frame = ceil_div(max(0, int(start_ms)) * fps_num, step_den)
    return ceil_div(first_frame * step_den, fps_num)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "item"


def normalize_mark_id(raw_id: str) -> str:
    s = str(raw_id).strip()
    if s.startswith("mark_"):
        s = s[len("mark_") :]
    return s


def derive_mark_id(mark: Dict[str, Any], defaults: Dict[str, Any], seen: Dict[str, int]) -> str:
    if "id" in mark and mark["id"] is not None and str(mark["id"]).strip() != "":
        base = normalize_mark_id(str(mark["id"]))
    else:
        el_type = str(mark.get("type") or mark.get("kind") or defaults.get("type") or "rect")
        start_val = int(round(float(mark.get("start", mark.get("anchor", 0)))))
        label_val = mark.get("label")
        if label_val is None:
            label_val = mark.get("text")
        if label_val is None and isinstance(mark.get("runs"), list):
            label_val = "".join(str(r.get("text", "")) for r in mark["runs"] if isinstance(r, dict))
        if label_val is None:
            label_val = f"{mark.get('x', 0)}_{mark.get('y', 0)}"
        base = slugify(f"{el_type}_{start_val}_{label_val}")

    count = seen.get(base, 0) + 1
    seen[base] = count
    return base if count == 1 else f"{base}_{count}"


def canonicalize_element(raw: Dict[str, Any]) -> Dict[str, Any]:
    ordered: Dict[str, Any] = {}
    for key in CANONICAL_ELEMENT_ORDER:
        if key in raw:
            ordered[key] = raw[key]
    for key, val in raw.items():
        if key not in ordered:
            ordered[key] = val
    return ordered


def element_sha256(element: Dict[str, Any]) -> str:
    canon = canonicalize_element(element)
    payload = json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_fade_keyframes(
    start: int,
    end: int,
    fade_in_ms: int,
    fade_out_ms: int,
    ease: Any,
    peak_opacity: float,
    fps_num: int,
    fps_den: int,
) -> Any:
    if fade_in_ms <= 0 and fade_out_ms <= 0:
        return None
    last_t = max(start, last_drawn_instant(end, fps_num, fps_den))
    if last_t <= start:
        return peak_opacity

    peak = round(float(peak_opacity), 4)
    kfs: List[Dict[str, Any]] = []

    if fade_in_ms > 0 and fade_out_ms > 0:
        t_in = min(last_t, max(start + 1, on_frame_instant(start + fade_in_ms, fps_num, fps_den)))
        t_out = max(t_in, min(last_t, on_frame_instant(last_t - fade_out_ms, fps_num, fps_den)))
        kfs.append({"t": start, "v": 0.0})
        kfs.append({"t": t_in, "v": peak, "ease": ease})
        if t_out > t_in and t_out < last_t:
            kfs.append({"t": t_out, "v": peak, "ease": "linear"})
        if last_t > kfs[-1]["t"]:
            kfs.append({"t": last_t, "v": 0.0, "ease": ease})
        else:
            kfs[-1] = {"t": last_t, "v": 0.0, "ease": ease}
    elif fade_in_ms > 0:
        t_in = min(last_t, max(start + 1, on_frame_instant(start + fade_in_ms, fps_num, fps_den)))
        kfs.append({"t": start, "v": 0.0})
        kfs.append({"t": t_in, "v": peak, "ease": ease})
    else:
        # fade_out_ms > 0 only
        t_out = max(start, min(last_t - 1, on_frame_instant(last_t - fade_out_ms, fps_num, fps_den)))
        first_ceil = first_drawn_ceil_instant(start, fps_num, fps_den)
        if t_out < first_ceil:
            t_out = start
        kfs.append({"t": t_out, "v": peak})
        kfs.append({"t": last_t, "v": 0.0, "ease": ease})

    return kfs


def find_mark_lines(spec_text: str, count: int) -> List[int]:
    lines: List[int] = []
    in_marks = False
    for line_no, line in enumerate(spec_text.splitlines(), 1):
        if not in_marks and re.search(r'"marks"\s*:\s*\[', line):
            in_marks = True
        if in_marks and "{" in line:
            # Skip the outer object or `defaults` before `"marks"`
            lines.append(line_no)
            if len(lines) >= count:
                break
    while len(lines) < count:
        lines.append(1)
    return lines


def resolve_paths(pos0: str, pos1: str) -> Tuple[Path, Path]:
    p0, p1 = Path(pos0), Path(pos1)
    d0 = json.loads(p0.read_text(encoding="utf-8"))
    if isinstance(d0, dict) and "marks" in d0 and "fps" not in d0:
        return p0, p1
    return p1, p0


def manifest_path_for(spec_path: Path) -> Path:
    return Path(f"{spec_path}.manifest.json")


def find_montagent() -> Optional[str]:
    root = Path(__file__).resolve().parents[3]
    candidates = [
        os.environ.get("MONTAGENT"),
        shutil.which("montagent"),
        str(root / "target/debug/montagent"),
        str(root / "target/release/montagent"),
        str(Path.home() / ".cargo/shared-target/debug/montagent"),
        str(Path.home() / ".cargo/shared-target/release/montagent"),
    ]
    for cand in candidates:
        for path in (cand, cand and cand + ".exe"):
            if path and Path(path).is_file():
                return str(Path(path).resolve())
    return None


def validate_project(project_data: Dict[str, Any], project_path: Path) -> int:
    montagent_bin = find_montagent()
    if not montagent_bin:
        sys.stderr.write("marks: `montagent` is not on PATH, so the result was not validated\n")
        return 1
    fd, scratch = tempfile.mkstemp(
        prefix=".marks-validate-",
        suffix=".montagent.json",
        dir=str(project_path.resolve().parent),
    )
    scratch_path = Path(scratch)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        out = subprocess.run(
            [montagent_bin, "validate", str(scratch_path), "--json"],
            capture_output=True,
            text=True,
        )
        try:
            report = json.loads(out.stdout)
            errors = int(report["summary"]["error"])
        except (ValueError, KeyError):
            sys.stderr.write(out.stdout + out.stderr)
            return 1
        unreached = [
            f
            for f in report.get("findings", [])
            if f.get("code") == "R-KEYFRAME-UNREACHED"
            and str(f.get("fields", {}).get("element", "")).startswith("mark_")
        ]
        if errors > 0 or unreached:
            text_out = subprocess.run(
                [montagent_bin, "validate", str(scratch_path)],
                capture_output=True,
                text=True,
            )
            sys.stderr.write(
                (text_out.stdout + text_out.stderr).replace(str(scratch_path), str(project_path))
            )
            return 1
        return 0
    finally:
        scratch_path.unlink(missing_ok=True)


def expand_marks(
    spec: Dict[str, Any],
    project: Dict[str, Any],
    spec_lines: List[int],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str, int]:
    raw_defaults = copy.deepcopy(spec.get("defaults") or {})
    style_defaults = raw_defaults.pop("style", {}) if isinstance(raw_defaults.get("style"), dict) else {}
    defaults: Dict[str, Any] = {**style_defaults, **raw_defaults}

    track_prefix = str(defaults.get("track_prefix", "marks"))
    max_tracks = int(defaults.get("max_tracks", 40))
    base_layer = int(defaults.get("layer", defaults.get("layer_base", 20)))
    fps_num, fps_den = fps_ratio(project.get("fps", 30))

    raw_overrides = spec.get("overrides") or {}
    normalized_overrides: Dict[str, Dict[str, Any]] = {}
    for k, v in raw_overrides.items():
        if isinstance(v, dict):
            normalized_overrides[normalize_mark_id(k)] = copy.deepcopy(v)

    seen_ids: Dict[str, int] = {}
    expanded_records: List[Dict[str, Any]] = []

    for idx, raw_mark in enumerate(spec.get("marks") or []):
        mark_id = derive_mark_id(raw_mark, defaults, seen_ids)
        element_id = f"mark_{mark_id}"
        ovr = normalized_overrides.get(mark_id, {})

        mark_style = raw_mark.get("style") if isinstance(raw_mark.get("style"), dict) else {}
        ovr_style = ovr.get("style") if isinstance(ovr.get("style"), dict) else {}

        merged: Dict[str, Any] = {}
        for layer_dict in (defaults, mark_style, raw_mark, ovr_style, ovr):
            for k, v in layer_dict.items():
                if k != "style":
                    merged[k] = copy.deepcopy(v)

        el_type = str(merged.get("type") or merged.get("kind") or "rect")
        start = int(round(float(merged.get("start", merged.get("anchor", 0)))))
        if "end" in merged and merged["end"] is not None and ("duration" not in ovr or "end" in ovr):
            end = int(round(float(merged["end"])))
        elif "duration" in merged and merged["duration"] is not None:
            end = start + int(round(float(merged["duration"])))
        else:
            end = start + 1000

        if end <= start:
            raise ValueError(f"Mark '{mark_id}' has invalid range [{start}, {end})")

        element: Dict[str, Any] = {
            "id": element_id,
            "type": el_type,
            "start": start,
            "end": end,
        }

        for k, v in merged.items():
            if k in HELPER_ONLY_KEYS or k in ("id", "type", "start", "end", "layer"):
                continue
            element[k] = copy.deepcopy(v)

        # Element-level layer override if explicitly set on mark or override
        if "layer" in raw_mark or "layer" in ovr:
            element["layer"] = merged["layer"]

        # Apply sensible defaults per element type so minimal compact specs validate cleanly
        element.setdefault("origin", "center")
        element.setdefault("x", 540)
        element.setdefault("y", 960)
        if el_type in ("rect", "ellipse"):
            element.setdefault("width", 100)
            element.setdefault("height", 100)
            if "fill" not in element and "stroke" not in element:
                element["fill"] = "#FF5A36"
        elif el_type == "text":
            element.setdefault("width", 400)
            element.setdefault("height", 80)
            fonts_map = project.get("fonts") or {}
            default_font = next(iter(fonts_map.keys()), "caption")
            element.setdefault("font", default_font)
            element.setdefault("size", 48)
            element.setdefault("color", "#F5F0E6")
            if "runs" not in element:
                txt = merged.get("text", merged.get("label", mark_id))
                element["runs"] = [{"text": str(txt)}]

        # Synthesize fade keyframes unless explicit keyframe list was provided on `opacity` in override
        explicit_opacity_kfs = isinstance(ovr.get("opacity"), list) or (
            isinstance(raw_mark.get("opacity"), list) and "fade_in_ms" not in ovr and "fade_out_ms" not in ovr
        )
        if not explicit_opacity_kfs:
            fade_in_ms = int(round(float(merged.get("fade_in_ms", 0) or 0)))
            fade_out_ms = int(round(float(merged.get("fade_out_ms", 0) or 0)))
            ease = merged.get("ease", "ease-in-out")
            base_op = merged.get("opacity", 1.0)
            peak_op = float(base_op) if isinstance(base_op, (int, float)) else 1.0
            fade_kfs = build_fade_keyframes(
                start, end, fade_in_ms, fade_out_ms, ease, peak_op, fps_num, fps_den
            )
            if fade_kfs is not None:
                element["opacity"] = fade_kfs

        element = canonicalize_element(element)
        line_no = spec_lines[idx] if idx < len(spec_lines) else 1
        expanded_records.append(
            {
                "id": element_id,
                "mark_id": mark_id,
                "source_index": idx,
                "source_line": line_no,
                "start": start,
                "end": end,
                "overrides": sorted(ovr.keys()),
                "element": element,
            }
        )

    # Deterministic interval-graph track packing across non-overlapping tracks
    packing_order = sorted(
        expanded_records,
        key=lambda r: (r["start"], r["end"], r["id"]),
    )
    packed_tracks: List[Dict[str, Any]] = []
    for rec in packing_order:
        placed_track: Optional[Dict[str, Any]] = None
        for tr in packed_tracks:
            if tr["last_end"] <= rec["start"]:
                placed_track = tr
                break
        if placed_track is None:
            track_num = len(packed_tracks) + 1
            if track_num > max_tracks:
                raise RuntimeError(
                    f"marks: packing requires > {max_tracks} concurrent tracks at t={rec['start']} ms "
                    f"(mark {rec['id']!r})"
                )
            placed_track = {
                "name": f"{track_prefix}_{track_num}",
                "layer": base_layer + track_num - 1,
                "last_end": rec["end"],
                "elements": [],
            }
            packed_tracks.append(placed_track)
        placed_track["elements"].append(rec["element"])
        placed_track["last_end"] = rec["end"]
        rec["track"] = placed_track["name"]

    out_tracks = [
        {"name": tr["name"], "layer": tr["layer"], "elements": tr["elements"]}
        for tr in packed_tracks
    ]
    return expanded_records, out_tracks, track_prefix, max_tracks


def diff_elements(old_el: Dict[str, Any], new_el: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
    diffs: Dict[str, Tuple[Any, Any]] = {}
    all_keys = list(dict.fromkeys(list(old_el.keys()) + list(new_el.keys())))
    for k in all_keys:
        if k == "id":
            continue
        if old_el.get(k) != new_el.get(k):
            diffs[k] = (old_el.get(k), new_el.get(k))
    return diffs


def format_provenance_table(records: List[Dict[str, Any]], spec_name: str) -> str:
    headers = ("ELEMENT_ID", "TRACK", "WINDOW", "SOURCE", "OVERRIDES")
    rows: List[Tuple[str, str, str, str, str]] = []
    for r in sorted(records, key=lambda x: (x["start"], x["end"], x["id"])):
        window = f"[{r['start']}, {r['end']})"
        source = f"{spec_name}:L{r['source_line']} (marks[{r['source_index']}])"
        ovrs = ", ".join(r["overrides"]) if r["overrides"] else "-"
        rows.append((r["id"], r["track"], window, source, ovrs))

    widths = [
        max(len(headers[col]), *(len(row[col]) for row in rows)) if rows else len(headers[col])
        for col in range(len(headers))
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [
        fmt.format(*headers),
        "  ".join("-" * w for w in widths),
    ]
    for row in rows:
        lines.append(fmt.format(*row))
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args or "-h" in args or "--help" in args:
        sys.stdout.write(__doc__ or "")
        return 0 if args else 2

    prune_overrides = False
    adopt_edits = False
    force = False
    inspect_mode = False
    positional: List[str] = []

    for arg in args:
        if arg == "--prune-overrides":
            prune_overrides = True
        elif arg == "--adopt-edits":
            adopt_edits = True
        elif arg == "--force":
            force = True
        elif arg == "--inspect":
            inspect_mode = True
        elif arg.startswith("-"):
            sys.stderr.write(f"marks: unknown option {arg!r}\n")
            return 2
        else:
            positional.append(arg)

    if adopt_edits and force:
        sys.stderr.write("marks: pass at most one of --adopt-edits or --force\n")
        return 2
    if len(positional) != 2:
        sys.stderr.write(
            "Usage: marks.py <spec.json> <project.montagent.json> "
            "[--prune-overrides] [--adopt-edits | --force] [--inspect]\n"
        )
        return 2

    spec_path, project_path = resolve_paths(positional[0], positional[1])
    spec_text = spec_path.read_text(encoding="utf-8")
    spec = json.loads(spec_text)
    project = json.loads(project_path.read_text(encoding="utf-8"))

    # 1. Check for orphaned overrides before expanding
    raw_defaults = spec.get("defaults") or {}
    seen_for_check: Dict[str, int] = {}
    valid_mark_ids = {
        derive_mark_id(m, raw_defaults, seen_for_check) for m in (spec.get("marks") or [])
    }
    raw_overrides = spec.get("overrides") or {}
    orphaned_keys = [
        k for k in raw_overrides.keys() if normalize_mark_id(k) not in valid_mark_ids
    ]
    if orphaned_keys:
        if not prune_overrides:
            sys.stderr.write(
                "marks: orphaned override IDs not present in `marks`: "
                + ", ".join(repr(k) for k in sorted(orphaned_keys))
                + " (pass --prune-overrides to remove them)\n"
            )
            return 1
        for k in orphaned_keys:
            raw_overrides.pop(k, None)
        spec["overrides"] = raw_overrides
        spec_text = json.dumps(spec, indent=2, ensure_ascii=False) + "\n"
        spec_path.write_text(spec_text, encoding="utf-8")

    # 2. Check existing `.montagent.json` against `<spec>.manifest.json`
    mpath = manifest_path_for(spec_path)
    if mpath.is_file() and not inspect_mode:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        manifest_elements: Dict[str, Any] = manifest.get("elements") or {}
        current_elements = {
            e.get("id"): e
            for t in (project.get("tracks") or [])
            for e in (t.get("elements") or [])
            if isinstance(e, dict) and e.get("id") in manifest_elements
        }
        drifted: List[Tuple[str, str, Dict[str, Tuple[Any, Any]], Dict[str, Any]]] = []
        for el_id, m_entry in manifest_elements.items():
            if el_id not in current_elements:
                continue
            cur_el = current_elements[el_id]
            cur_sha = element_sha256(cur_el)
            if cur_sha != m_entry.get("sha256"):
                prev_el = m_entry.get("element") or {}
                diffs = diff_elements(prev_el, cur_el)
                drifted.append((el_id, m_entry.get("mark_id", normalize_mark_id(el_id)), diffs, cur_el))

        if drifted:
            if not adopt_edits and not force:
                sys.stderr.write(
                    f"marks: refusing to overwrite direct edits in {project_path.name} "
                    "(pass --adopt-edits to fold into overrides or --force to discard):\n"
                )
                for el_id, _mark_id, diffs, _cur_el in drifted:
                    for field_name, (was_val, now_val) in diffs.items():
                        sys.stderr.write(
                            f"  {el_id}.{field_name}: {json.dumps(was_val)} -> {json.dumps(now_val)}\n"
                        )
                return 1
            if adopt_edits:
                overrides_map = spec.setdefault("overrides", {})
                for _el_id, mark_id, diffs, cur_el in drifted:
                    target_key = mark_id
                    for existing_k in overrides_map:
                        if normalize_mark_id(existing_k) == mark_id:
                            target_key = existing_k
                            break
                    ovr_entry = overrides_map.setdefault(target_key, {})
                    for field_name in diffs:
                        if field_name in cur_el:
                            ovr_entry[field_name] = copy.deepcopy(cur_el[field_name])
                spec_text = json.dumps(spec, indent=2, ensure_ascii=False) + "\n"
                spec_path.write_text(spec_text, encoding="utf-8")

    spec_lines = find_mark_lines(spec_text, len(spec.get("marks") or []))
    try:
        records, packed_tracks, track_prefix, _max_tracks = expand_marks(spec, project, spec_lines)
    except (ValueError, RuntimeError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    # Preserve all non-generated tracks and elements
    prev_generated_ids = set()
    if mpath.is_file():
        try:
            prev_manifest = json.loads(mpath.read_text(encoding="utf-8"))
            prev_generated_ids.update((prev_manifest.get("elements") or {}).keys())
        except ValueError:
            pass

    gen_track_pattern = re.compile(rf"^{re.escape(track_prefix)}_\d+$")
    preserved_tracks: List[Dict[str, Any]] = []
    for tr in project.get("tracks") or []:
        t_name = str(tr.get("name", ""))
        is_gen_track = bool(gen_track_pattern.match(t_name))
        kept_elements = []
        for el in tr.get("elements") or []:
            el_id = str(el.get("id", ""))
            if el_id in prev_generated_ids or (is_gen_track and el_id.startswith("mark_")):
                continue
            kept_elements.append(el)
        if kept_elements or not is_gen_track:
            new_tr = copy.deepcopy(tr)
            new_tr["elements"] = kept_elements
            preserved_tracks.append(new_tr)

    updated_project = copy.deepcopy(project)
    updated_project["tracks"] = preserved_tracks + packed_tracks

    rc = validate_project(updated_project, project_path)
    if rc != 0:
        return rc

    if inspect_mode:
        sys.stdout.write(format_provenance_table(records, spec_path.name))
        return 0

    # Write updated project and manifest
    out_json = json.dumps(updated_project, indent=2, ensure_ascii=False) + "\n"
    project_path.write_text(out_json, encoding="utf-8")

    manifest_data = {
        "spec": spec_path.name,
        "track_prefix": track_prefix,
        "elements": {
            r["id"]: {
                "id": r["id"],
                "mark_id": r["mark_id"],
                "source_index": r["source_index"],
                "source_line": r["source_line"],
                "track": r["track"],
                "start": r["start"],
                "end": r["end"],
                "overrides": r["overrides"],
                "sha256": element_sha256(r["element"]),
                "element": r["element"],
            }
            for r in records
        },
    }
    mpath.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sys.stdout.write(out_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())

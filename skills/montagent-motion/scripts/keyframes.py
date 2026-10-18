#!/usr/bin/env python3
"""Generate or transform motion keyframes on a Montagent project from a spec (ADR-0217, ADR-0219).

Requires Python >= 3.9
Standard library only (`ffmpeg` is invoked lazily only when an `"audio"` operation is present
in `<spec>`, and `montagent` on PATH for final validation).
drift-guard: keyframes.montagent.json keyframes.spec.json

Usage:
    python3 skills/montagent-motion/scripts/keyframes.py <project.montagent.json> <keyframes.spec.json> [--check]

Operations (`op` in each entry of `<spec>`'s `"operations"` list):
  - `wiggle`: seeded smooth or stepped 1D/2D noise over `[start, end]`, thinned by `tol`.
  - `bounce`: decaying inertial overshoot after a settling keyframe over `[start, end]`.
  - `loop`: repeats an authored keyframe slice in `"cycle"`, `"pingpong"`, or `"offset"` mode.
  - `smooth`: rolling-window box filter (`window_ms`) + Ramer-Douglas-Peucker thinning (`tol`).
  - `exp_scale`: optical constant-rate zoom `s0 * (s1 / s0)^u` over `[start, end]`.
  - `audio`: maps per-frame audio RMS dBFS (`[floor_db, peak_db]`) onto `[min_v, max_v]`.
  - `auto_bezier`: Fritsch-Carlson monotonic cubic spline tangent smoothing over `[start, end]`.

With `--check`, exits 0 if the target properties in `<project>` already match what `<spec>`
produces, or 1 if they have drifted (printing nothing to stdout).
"""

import copy
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

Value = Union[int, float, List[float]]

INTEGER_PROPERTIES = {
    "x",
    "y",
    "width",
    "height",
    "radius",
    "stroke_width",
    "stroke_dash_offset",
    "letter_spacing",
    "source_time",
    "feather",
    "levels",
}

NON_NEGATIVE_INTEGER_PROPERTIES = {
    "width",
    "height",
    "radius",
    "stroke_width",
    "source_time",
    "feather",
}

PAIR_PROPERTIES = {
    "scale",
    "center",
    "focal",
}

DEFAULT_PROPERTY_VALUES: Dict[str, Any] = {
    "x": 0,
    "y": 0,
    "width": 100,
    "height": 100,
    "radius": 0,
    "stroke_width": 0,
    "stroke_dash_offset": 0,
    "trim_start": 0.0,
    "trim_end": 1.0,
    "trim_offset": 0.0,
    "letter_spacing": 0,
    "path_offset": 0.0,
    "scale": [1.0, 1.0],
    "rotation": 0.0,
    "swivel": 0.0,
    "tilt": 0.0,
    "perspective": 1000.0,
    "opacity": 1.0,
    "volume": 1.0,
}

# Canonical key order tail so newly inserted properties never trigger a LAYOUT finding.
CANONICAL_TAIL_ORDER = [
    "x",
    "y",
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
    "fill",
    "stroke",
    "stroke_width",
    "stroke_cap",
    "stroke_join",
    "miter_limit",
    "stroke_dash",
    "stroke_dash_offset",
    "trim_start",
    "trim_end",
    "trim_offset",
    "radius",
    "letter_spacing",
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
    "volume",
    "effects",
    "audio_effects",
    "caption",
]

NAMED_BEZIERS: Dict[str, Tuple[float, float, float, float]] = {
    "ease": (0.25, 0.1, 0.25, 1.0),
    "ease-in": (0.42, 0.0, 1.0, 1.0),
    "ease-out": (0.0, 0.0, 0.58, 1.0),
    "ease-in-out": (0.42, 0.0, 0.58, 1.0),
}


def fps_float(fps_field: Any) -> float:
    if isinstance(fps_field, (int, float)):
        return float(fps_field)
    if isinstance(fps_field, dict):
        return float(fps_field["num"]) / float(fps_field["den"])
    return 30.0


def on_frame(t_ms: float, fps: float) -> int:
    frame_idx = round(t_ms * fps / 1000.0)
    return int(math.floor(frame_idx * 1000.0 / fps))


def drawn_frames(t0: float, t1: float, fps: float) -> List[int]:
    start_t = on_frame(t0, fps)
    end_t = on_frame(t1, fps)
    if end_t <= start_t:
        return [start_t]
    n0 = max(0, int(round(start_t * fps / 1000.0)))
    n1 = max(n0, int(round(end_t * fps / 1000.0)))
    times: List[int] = []
    for n in range(n0, n1 + 1):
        t = int(math.floor(n * 1000.0 / fps))
        if not times or t > times[-1]:
            times.append(t)
    if times[0] != start_t:
        times[0] = start_t
    if times[-1] != end_t:
        times[-1] = end_t
    return times


def is_pair_property(prop_leaf: str, current_val: Any, op: dict) -> bool:
    if prop_leaf in PAIR_PROPERTIES:
        return True
    if isinstance(current_val, list):
        if len(current_val) == 2 and all(isinstance(x, (int, float)) for x in current_val):
            return True
        if current_val and isinstance(current_val[0], dict) and isinstance(current_val[0].get("v"), list):
            return True
    for k in ("base", "from", "to", "s0", "s1", "min_v", "max_v", "amp"):
        v = op.get(k)
        if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
            return True
    return False


def is_integer_property(prop_leaf: str, effect_name: Optional[str]) -> bool:
    if effect_name == "mask":
        return prop_leaf in {"x", "y", "width", "height", "radius", "feather"}
    if effect_name == "posterize":
        return prop_leaf == "levels"
    if effect_name is not None:
        return False
    return prop_leaf in INTEGER_PROPERTIES


def format_value(val: Any, prop_leaf: str, is_pair: bool, is_int: bool) -> Any:
    if is_pair:
        if isinstance(val, (int, float)):
            val = [ float(val), float(val) ]
        return [round(float(val[0]), 4), round(float(val[1]), 4)]
    v = float(val[0] if isinstance(val, list) else val)
    if is_int:
        iv = int(round(v))
        if prop_leaf in NON_NEGATIVE_INTEGER_PROPERTIES:
            iv = max(0, iv)
        elif prop_leaf == "levels":
            iv = min(256, max(2, iv))
        return iv
    if prop_leaf == "opacity" or prop_leaf in {"trim_start", "trim_end", "tolerance", "softness", "spill", "threshold"}:
        v = min(1.0, max(0.0, v))
    elif prop_leaf == "volume" or prop_leaf in {"perspective", "intensity", "length"}:
        v = max(0.0, v)
    elif prop_leaf == "path_offset":
        v = min(2.0, max(-1.0, v))
    return round(v, 4)


def to_pair(val: Any) -> List[float]:
    if isinstance(val, list):
        return [float(val[0]), float(val[1])]
    return [float(val), float(val)]


def to_scalar(val: Any) -> float:
    if isinstance(val, list):
        return float(val[0])
    return float(val)


def cubic_bezier_at(u: float, x1: float, y1: float, x2: float, y2: float) -> float:
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0

    def sample_x(s: float) -> float:
        return ((1.0 - 3.0 * x2 + 3.0 * x1) * s * s * s
                + (3.0 * x2 - 6.0 * x1) * s * s
                + 3.0 * x1 * s)

    def sample_y(s: float) -> float:
        return ((1.0 - 3.0 * y2 + 3.0 * y1) * s * s * s
                + (3.0 * y2 - 6.0 * y1) * s * s
                + 3.0 * y1 * s)

    lo, hi = 0.0, 1.0
    s = u
    for _ in range(24):
        x = sample_x(s) - u
        if abs(x) < 1e-7:
            break
        if x > 0.0:
            hi = s
        else:
            lo = s
        s = 0.5 * (lo + hi)
    return sample_y(s)


def ease_progress(u: float, ease: Any) -> float:
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    if ease is None or ease == "linear":
        return u
    if ease == "step":
        return 0.0
    if isinstance(ease, str) and ease in NAMED_BEZIERS:
        x1, y1, x2, y2 = NAMED_BEZIERS[ease]
        return cubic_bezier_at(u, x1, y1, x2, y2)
    if isinstance(ease, list) and len(ease) == 4:
        return cubic_bezier_at(u, float(ease[0]), float(ease[1]), float(ease[2]), float(ease[3]))
    return u


def lerp_val(a: Any, b: Any, p: float) -> Any:
    if isinstance(a, list) or isinstance(b, list):
        pa, pb = to_pair(a), to_pair(b)
        return [pa[0] + p * (pb[0] - pa[0]), pa[1] + p * (pb[1] - pa[1])]
    return float(a) + p * (float(b) - float(a))


def eval_keyframes(keyframes_or_static: Any, t_ms: float, default: Any = 0.0) -> Any:
    if keyframes_or_static is None:
        return copy.deepcopy(default)
    if isinstance(keyframes_or_static, (int, float)):
        return float(keyframes_or_static)
    if isinstance(keyframes_or_static, list):
        if not keyframes_or_static:
            return copy.deepcopy(default)
        if isinstance(keyframes_or_static[0], (int, float)):
            return [float(keyframes_or_static[0]), float(keyframes_or_static[1])]
        kfs = keyframes_or_static
        if t_ms <= kfs[0]["t"]:
            v0 = kfs[0]["v"]
            return list(v0) if isinstance(v0, list) else float(v0)
        if t_ms >= kfs[-1]["t"]:
            vn = kfs[-1]["v"]
            return list(vn) if isinstance(vn, list) else float(vn)
        for i in range(len(kfs) - 1):
            a, b = kfs[i], kfs[i + 1]
            if a["t"] <= t_ms <= b["t"]:
                dt = b["t"] - a["t"]
                if dt <= 0:
                    return list(b["v"]) if isinstance(b["v"], list) else float(b["v"])
                u = (t_ms - a["t"]) / float(dt)
                p = ease_progress(u, b.get("ease", "linear"))
                return lerp_val(a["v"], b["v"], p)
    return copy.deepcopy(default)


def val_distance(a: Any, b: Any) -> float:
    if isinstance(a, list) or isinstance(b, list):
        pa, pb = to_pair(a), to_pair(b)
        return max(abs(pa[0] - pb[0]), abs(pa[1] - pb[1]))
    return abs(float(a) - float(b))


def simplify(samples: List[Tuple[int, Any]], tol: float) -> List[Tuple[int, Any]]:
    """Ramer-Douglas-Peucker piecewise-linear curve thinning over (t, v) samples."""
    if len(samples) <= 2 or tol <= 0.0:
        return list(samples)
    t_a, v_a = samples[0]
    t_b, v_b = samples[-1]
    dt = float(t_b - t_a)
    max_err = -1.0
    split_idx = -1
    for i in range(1, len(samples) - 1):
        t_i, v_i = samples[i]
        u = (t_i - t_a) / dt if dt > 0.0 else 0.0
        interp = lerp_val(v_a, v_b, u)
        err = val_distance(v_i, interp)
        if err > max_err:
            max_err = err
            split_idx = i
    if max_err > tol and split_idx != -1:
        left = simplify(samples[: split_idx + 1], tol)
        right = simplify(samples[split_idx:], tol)
        return left[:-1] + right
    return [samples[0], samples[-1]]


def normalize_keyframe_list(raw_kfs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure strictly ascending t, no ease on first record, ease on every subsequent record."""
    if not raw_kfs:
        return []
    by_t: Dict[int, Dict[str, Any]] = {}
    for kf in raw_kfs:
        t = int(kf["t"])
        by_t[t] = dict(kf)
        by_t[t]["t"] = t
    sorted_kfs = [by_t[t] for t in sorted(by_t)]
    out: List[Dict[str, Any]] = []
    for idx, kf in enumerate(sorted_kfs):
        rec: Dict[str, Any] = {"t": kf["t"]}
        if "t_from" in kf:
            rec["t_from"] = kf["t_from"]
        rec["v"] = kf["v"]
        if idx > 0:
            rec["ease"] = kf.get("ease", "linear")
        out.append(rec)
    return out


def splice_keyframes(
    existing: Any,
    new_kfs: List[Dict[str, Any]],
    t0: int,
    t1: int,
) -> List[Dict[str, Any]]:
    before: List[Dict[str, Any]] = []
    after: List[Dict[str, Any]] = []
    if isinstance(existing, list) and existing and isinstance(existing[0], dict):
        for kf in existing:
            if kf["t"] < t0:
                before.append(dict(kf))
            elif kf["t"] > t1:
                after.append(dict(kf))
    return normalize_keyframe_list(before + new_kfs + after)


def resolve_target(
    element: Dict[str, Any],
    prop_spec: str,
    effect_ref: Any = None,
) -> Tuple[Dict[str, Any], str, str, Optional[str]]:
    """Return (container_dict, key_in_container, prop_leaf, effect_name)."""
    if effect_ref is not None:
        effects = element.get("effects") or []
        if isinstance(effect_ref, int):
            eff = effects[effect_ref]
            return eff, prop_spec, prop_spec, eff.get("name")
        for eff in effects:
            if eff.get("name") == effect_ref:
                return eff, prop_spec, prop_spec, eff.get("name")
        raise ValueError(f"Element '{element.get('id')}' has no effect '{effect_ref}'")

    m = re.match(r"^effects\[(\d+)\]\.([a-zA-Z0-9_]+)$", prop_spec)
    if m:
        idx = int(m.group(1))
        leaf = m.group(2)
        effects = element.get("effects") or []
        if idx < 0 or idx >= len(effects):
            raise ValueError(f"Element '{element.get('id')}' has no effects[{idx}]")
        eff = effects[idx]
        return eff, leaf, leaf, eff.get("name")

    m_named = re.match(r"^effects\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)$", prop_spec)
    if m_named:
        eff_name, leaf = m_named.group(1), m_named.group(2)
        for eff in element.get("effects") or []:
            if eff.get("name") == eff_name:
                return eff, leaf, leaf, eff_name
        raise ValueError(f"Element '{element.get('id')}' has no effect '{eff_name}'")

    if "." in prop_spec:
        head, leaf = prop_spec.split(".", 1)
        sub = element.get(head)
        if isinstance(sub, dict):
            return sub, leaf, leaf, None

    return element, prop_spec, prop_spec, None


def set_in_canonical_order(container: Dict[str, Any], key: str, value: Any, is_element: bool) -> None:
    if key in container or not is_element:
        container[key] = value
        return
    prefix = ["id", "type", "group", "start", "end", "layer", "source", "source_start", "source_end", "source_time"]
    full_order = prefix + CANONICAL_TAIL_ORDER
    key_rank = full_order.index(key) if key in full_order else len(full_order)
    items = list(container.items())
    rebuilt: Dict[str, Any] = {}
    inserted = False
    for k, v in items:
        r = full_order.index(k) if k in full_order else len(full_order)
        if not inserted and key_rank < r:
            rebuilt[key] = value
            inserted = True
        rebuilt[k] = v
    if not inserted:
        rebuilt[key] = value
    container.clear()
    container.update(rebuilt)


def lattice_hash(ix: int, seed: int, octave: int, axis: int) -> float:
    """Deterministic hash in [-1.0, 1.0] using 64-bit SplitMix64 mixing."""
    x = (
        (ix * 0x9E3779B97F4A7C15)
        ^ (seed * 0xBF58476D1CE4E5B9)
        ^ (octave * 0x94D049BB133111EB)
        ^ (axis * 0x2545F4914F6CDD1D)
    ) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    x = (x ^ (x >> 31)) & 0xFFFFFFFFFFFFFFFF
    unit = (x >> 11) * (1.0 / (1 << 53))
    return unit * 2.0 - 1.0


def smooth_noise_1d(pos: float, seed: int, octave: int, axis: int, stepped: bool) -> float:
    ix = int(math.floor(pos))
    if stepped:
        return lattice_hash(ix, seed, octave, axis)
    frac = pos - ix
    fade = frac * frac * (3.0 - 2.0 * frac)
    v0 = lattice_hash(ix, seed, octave, axis)
    v1 = lattice_hash(ix + 1, seed, octave, axis)
    return v0 + fade * (v1 - v0)


def op_wiggle(
    current_val: Any,
    op: Dict[str, Any],
    el_start: int,
    el_end: int,
    fps: float,
    prop_leaf: str,
    is_pair: bool,
    is_int: bool,
) -> Tuple[List[Dict[str, Any]], int, int]:
    t0 = on_frame(float(op.get("start", op.get("t0", el_start))), fps)
    t1 = on_frame(float(op.get("end", op.get("t1", el_end))), fps)
    freq = float(op.get("freq", 4.0))
    amp = op.get("amp", [0.1, 0.1] if is_pair else (10.0 if is_int else 0.1))
    octaves = max(1, int(op.get("octaves", 1)))
    mult = float(op.get("mult", 0.5))
    seed = int(op.get("seed", 0))
    stepped = bool(op.get("stepped", False))
    default_tol = 0.5 if is_int else 0.005
    tol = float(op.get("tol", default_tol))

    default_base = DEFAULT_PROPERTY_VALUES.get(prop_leaf, [1.0, 1.0] if is_pair else 0.0)
    if "base" in op:
        base_source = op["base"]
    elif isinstance(current_val, list) and current_val and isinstance(current_val[0], dict):
        # Strip interior points inside (t0, t1) so re-running wiggle on an already-wiggled
        # range recovers the clean endpoint-interpolated base curve idempotently.
        boundary = [kf for kf in current_val if kf["t"] <= t0 or kf["t"] >= t1]
        base_source = normalize_keyframe_list(boundary) if boundary else current_val
    else:
        base_source = current_val if current_val is not None else default_base

    times = drawn_frames(t0, t1, fps)
    amp_pair = to_pair(amp) if is_pair else [float(amp), float(amp)]
    samples: List[Tuple[int, Any]] = []

    for idx, t in enumerate(times):
        base_t = eval_keyframes(base_source, float(t), default_base)
        # Pin exact endpoints t0 and t1 to base curve for clean joins & idempotent re-runs
        if idx == 0 or idx == len(times) - 1:
            samples.append((t, format_value(base_t, prop_leaf, is_pair, is_int)))
            continue
        sec = (t - t0) / 1000.0
        if is_pair:
            bp = to_pair(base_t)
            out_pair = [bp[0], bp[1]]
            for axis in (0, 1):
                offset = 0.0
                for k in range(octaves):
                    fk = freq * (2.0 ** k)
                    ak = amp_pair[axis] * (mult ** k)
                    offset += ak * smooth_noise_1d(fk * sec + 0.37, seed, k, axis, stepped)
                out_pair[axis] += offset
            samples.append((t, format_value(out_pair, prop_leaf, is_pair, is_int)))
        else:
            bs = to_scalar(base_t)
            offset = 0.0
            for k in range(octaves):
                fk = freq * (2.0 ** k)
                ak = amp_pair[0] * (mult ** k)
                offset += ak * smooth_noise_1d(fk * sec + 0.37, seed, k, 0, stepped)
            samples.append((t, format_value(bs + offset, prop_leaf, is_pair, is_int)))

    thinned = simplify(samples, tol)
    ease_mode = "step" if stepped else "linear"
    kfs: List[Dict[str, Any]] = []
    for i, (t, v) in enumerate(thinned):
        rec: Dict[str, Any] = {"t": t, "v": format_value(v, prop_leaf, is_pair, is_int)}
        if i > 0:
            rec["ease"] = ease_mode
        kfs.append(rec)
    return kfs, t0, t1


def op_bounce(
    current_val: Any,
    op: Dict[str, Any],
    el_start: int,
    el_end: int,
    fps: float,
    prop_leaf: str,
    is_pair: bool,
    is_int: bool,
) -> Tuple[List[Dict[str, Any]], int, int]:
    freq = float(op.get("freq", 3.0))
    decay = float(op.get("decay", 5.0))
    max_bounces = op.get("max_bounces")
    default_tol = 0.5 if is_int else 0.005
    tol = float(op.get("tol", default_tol))

    raw_start = op.get("t1", op.get("start"))
    raw_end = op.get("t2", op.get("end", el_end))
    t2 = on_frame(float(raw_end), fps)

    kfs_in: List[Dict[str, Any]] = []
    if isinstance(current_val, list) and current_val and isinstance(current_val[0], dict):
        kfs_in = [dict(k) for k in current_val]

    if raw_start is not None:
        t1 = on_frame(float(raw_start), fps)
        # If start was given as the first keyframe t0 and there is a second keyframe before t2,
        # use the second keyframe as the settling instant t1.
        if kfs_in and t1 == kfs_in[0]["t"] and len(kfs_in) >= 2 and kfs_in[1]["t"] < t2:
            if "t1" not in op and "velocity" not in op and "v_in" not in op:
                t1 = on_frame(float(kfs_in[1]["t"]), fps)
    elif len(kfs_in) >= 2:
        t1 = on_frame(float(kfs_in[1]["t"]), fps)
    else:
        t1 = on_frame(float(el_start), fps)

    # Strip any previously generated bounce keyframes strictly inside (t1, t2]
    pre_kfs = [k for k in kfs_in if k["t"] <= t1]
    default_base = DEFAULT_PROPERTY_VALUES.get(prop_leaf, [1.0, 1.0] if is_pair else 0.0)

    if "v1" in op or "to" in op:
        v1 = op.get("v1", op.get("to"))
    elif pre_kfs:
        v1 = pre_kfs[-1]["v"]
    else:
        v1 = eval_keyframes(current_val, float(t1), default_base)

    if "velocity" in op or "v_in" in op:
        v_in = op.get("velocity", op.get("v_in"))
    elif len(pre_kfs) >= 2:
        k_prev, k_curr = pre_kfs[-2], pre_kfs[-1]
        dt_sec = max(1e-3, (k_curr["t"] - k_prev["t"]) / 1000.0)
        if is_pair:
            p0, p1 = to_pair(k_prev["v"]), to_pair(k_curr["v"])
            v_in = [(p1[0] - p0[0]) / dt_sec, (p1[1] - p0[1]) / dt_sec]
        else:
            v_in = (to_scalar(k_curr["v"]) - to_scalar(k_prev["v"])) / dt_sec
    elif "from" in op or "v0" in op:
        v0 = op.get("from", op.get("v0"))
        t0_prev = float(op.get("t0", el_start))
        dt_sec = max(1e-3, (t1 - t0_prev) / 1000.0)
        if is_pair:
            p0, p1 = to_pair(v0), to_pair(v1)
            v_in = [(p1[0] - p0[0]) / dt_sec, (p1[1] - p0[1]) / dt_sec]
        else:
            v_in = (to_scalar(v1) - to_scalar(v0)) / dt_sec
    else:
        v_in = [1.0, 1.0] if is_pair else 100.0

    omega = 2.0 * math.pi * max(0.1, freq)
    times = drawn_frames(t1, t2, fps)
    samples: List[Tuple[int, Any]] = []

    for idx, t in enumerate(times):
        if idx == 0 or idx == len(times) - 1:
            samples.append((t, format_value(v1, prop_leaf, is_pair, is_int)))
            continue
        dt = (t - t1) / 1000.0
        if max_bounces is not None and dt * freq * 2.0 > float(max_bounces):
            samples.append((t, format_value(v1, prop_leaf, is_pair, is_int)))
            continue
        factor = math.sin(omega * dt) / (math.exp(decay * dt) * omega)
        if is_pair:
            p1 = to_pair(v1)
            pv = to_pair(v_in)
            val = [p1[0] + pv[0] * factor, p1[1] + pv[1] * factor]
        else:
            val = to_scalar(v1) + to_scalar(v_in) * factor
        samples.append((t, format_value(val, prop_leaf, is_pair, is_int)))

    thinned = simplify(samples, tol)
    settle_ease = pre_kfs[-1].get("ease", "linear") if len(pre_kfs) >= 2 else "linear"
    kfs: List[Dict[str, Any]] = []
    for i, (t, v) in enumerate(thinned):
        rec: Dict[str, Any] = {"t": t, "v": format_value(v, prop_leaf, is_pair, is_int)}
        if i == 0:
            rec["ease"] = settle_ease
        else:
            rec["ease"] = "linear"
        kfs.append(rec)
    return kfs, t1, t2


def reverse_ease(ease: Any) -> Any:
    """Mirror an incoming keyframe ease for time-reversed segments (ADR-0217 §1.2)."""
    if ease == "ease-in":
        return "ease-out"
    if ease == "ease-out":
        return "ease-in"
    if isinstance(ease, list) and len(ease) == 4:
        x1, y1, x2, y2 = float(ease[0]), float(ease[1]), float(ease[2]), float(ease[3])
        return [
            round(1.0 - x2, 4),
            round(1.0 - y2, 4),
            round(1.0 - x1, 4),
            round(1.0 - y1, 4),
        ]
    return ease if ease is not None else "linear"


def build_loop_from_slice(
    base_slice: List[Dict[str, Any]],
    mode: str,
    t_end: int,
    fps: float,
    prop_leaf: str,
    is_pair: bool,
    is_int: bool,
) -> List[Dict[str, Any]]:
    if len(base_slice) < 2:
        return [dict(k) for k in base_slice]
    t0 = int(base_slice[0]["t"])
    tm = int(base_slice[-1]["t"])
    period = tm - t0
    if period <= 0:
        return [dict(k) for k in base_slice]

    v0 = base_slice[0]["v"]
    vm = base_slice[-1]["v"]
    if is_pair:
        p0, pm = to_pair(v0), to_pair(vm)
        delta_v: Any = [pm[0] - p0[0], pm[1] - p0[1]]
    else:
        delta_v = to_scalar(vm) - to_scalar(v0)

    out: List[Dict[str, Any]] = [dict(k) for k in base_slice]
    cycle_idx = 1
    while True:
        cycle_start = t0 + cycle_idx * period
        if cycle_start >= t_end:
            break
        if mode == "pingpong" and (cycle_idx % 2 == 1):
            # Reversed pass: traverse segments m..1, shifting incoming ease to opposite end
            for j in range(len(base_slice) - 1, 0, -1):
                dt_from_end = tm - int(base_slice[j - 1]["t"])
                t_new = on_frame(float(cycle_start + dt_from_end), fps)
                if t_new > t_end:
                    break
                seg_ease = base_slice[j].get("ease", "linear")
                out.append(
                    {
                        "t": t_new,
                        "v": format_value(base_slice[j - 1]["v"], prop_leaf, is_pair, is_int),
                        "ease": reverse_ease(seg_ease),
                    }
                )
        elif mode == "offset":
            for j in range(1, len(base_slice)):
                dt_from_start = int(base_slice[j]["t"]) - t0
                t_new = on_frame(float(cycle_start + dt_from_start), fps)
                if t_new > t_end:
                    break
                vj = base_slice[j]["v"]
                if is_pair:
                    pj = to_pair(vj)
                    v_new: Any = [pj[0] + cycle_idx * delta_v[0], pj[1] + cycle_idx * delta_v[1]]
                else:
                    v_new = to_scalar(vj) + cycle_idx * delta_v
                out.append(
                    {
                        "t": t_new,
                        "v": format_value(v_new, prop_leaf, is_pair, is_int),
                        "ease": base_slice[j].get("ease", "linear"),
                    }
                )
        else:
            # "cycle" mode
            if val_distance(v0, vm) > 1e-6:
                reset_t = cycle_start + 1
                if reset_t < t_end:
                    out.append(
                        {
                            "t": reset_t,
                            "v": format_value(v0, prop_leaf, is_pair, is_int),
                            "ease": "step",
                        }
                    )
            for j in range(1, len(base_slice)):
                dt_from_start = int(base_slice[j]["t"]) - t0
                t_new = on_frame(float(cycle_start + dt_from_start), fps)
                if t_new > t_end:
                    break
                out.append(
                    {
                        "t": t_new,
                        "v": format_value(base_slice[j]["v"], prop_leaf, is_pair, is_int),
                        "ease": base_slice[j].get("ease", "linear"),
                    }
                )
        cycle_idx += 1

    return normalize_keyframe_list(out)


def op_loop(
    current_val: Any,
    op: Dict[str, Any],
    el_start: int,
    el_end: int,
    fps: float,
    prop_leaf: str,
    is_pair: bool,
    is_int: bool,
) -> Tuple[List[Dict[str, Any]], int, int]:
    mode = str(op.get("mode", "cycle")).lower()
    if mode not in {"cycle", "pingpong", "offset"}:
        raise ValueError(f"Unsupported loop mode '{mode}'")

    kfs_in: List[Dict[str, Any]] = []
    if "keyframes" in op and isinstance(op["keyframes"], list):
        kfs_in = [dict(k) for k in op["keyframes"]]
    elif isinstance(current_val, list) and current_val and isinstance(current_val[0], dict):
        kfs_in = [dict(k) for k in current_val]

    if len(kfs_in) < 2:
        raise ValueError(f"loop on '{prop_leaf}' requires at least 2 keyframes")

    t0 = int(op.get("start", op.get("t0", kfs_in[0]["t"])))
    t1 = on_frame(float(op.get("end", op.get("t1", el_end))), fps)
    window_kfs = [dict(k) for k in kfs_in if t0 <= k["t"] <= t1]

    slice_end = op.get("slice_end", op.get("cycle_end"))
    if slice_end is None and "period" in op:
        slice_end = t0 + int(op["period"])

    if slice_end is not None:
        base_slice = [k for k in window_kfs if k["t"] <= int(slice_end)]
    else:
        # Detect if window_kfs is already the output of an earlier loop run so re-runs
        # without explicit slice_end remain strictly idempotent.
        base_slice = window_kfs
        norm_window = normalize_keyframe_list(window_kfs)
        for m in range(2, len(window_kfs)):
            candidate = window_kfs[:m]
            rebuilt = build_loop_from_slice(candidate, mode, t1, fps, prop_leaf, is_pair, is_int)
            if rebuilt == norm_window:
                base_slice = candidate
                break

    looped = build_loop_from_slice(base_slice, mode, t1, fps, prop_leaf, is_pair, is_int)
    return looped, int(base_slice[0]["t"]), t1


def op_smooth(
    current_val: Any,
    op: Dict[str, Any],
    el_start: int,
    el_end: int,
    fps: float,
    prop_leaf: str,
    is_pair: bool,
    is_int: bool,
) -> Tuple[List[Dict[str, Any]], int, int]:
    kfs_in: List[Dict[str, Any]] = []
    if isinstance(current_val, list) and current_val and isinstance(current_val[0], dict):
        kfs_in = [dict(k) for k in current_val]
    if len(kfs_in) < 2:
        raise ValueError(f"smooth on '{prop_leaf}' requires an existing keyframe list")

    t0 = on_frame(float(op.get("start", op.get("t0", kfs_in[0]["t"]))), fps)
    t1 = on_frame(float(op.get("end", op.get("t1", kfs_in[-1]["t"]))), fps)
    window_ms = float(op.get("window_ms", op.get("window", 100.0)))
    default_tol = 0.5 if is_int else 0.01
    tol = float(op.get("tol", default_tol))

    times = drawn_frames(t0, t1, fps)
    raw_samples = [(t, eval_keyframes(kfs_in, float(t))) for t in times]

    half_frames = max(1, int(round((window_ms / 1000.0) * fps))) if window_ms > 0.0 else 0
    smoothed: List[Tuple[int, Any]] = []
    n_samples = len(raw_samples)
    for idx, (t, val) in enumerate(raw_samples):
        r = min(half_frames, idx, n_samples - 1 - idx)
        if r <= 0:
            smoothed.append((t, format_value(val, prop_leaf, is_pair, is_int)))
            continue
        neighbors = [raw_samples[j][1] for j in range(idx - r, idx + r + 1)]
        if is_pair:
            avg_x = sum(to_pair(v)[0] for v in neighbors) / len(neighbors)
            avg_y = sum(to_pair(v)[1] for v in neighbors) / len(neighbors)
            smoothed.append((t, format_value([avg_x, avg_y], prop_leaf, is_pair, is_int)))
        else:
            avg = sum(to_scalar(v) for v in neighbors) / len(neighbors)
            smoothed.append((t, format_value(avg, prop_leaf, is_pair, is_int)))

    thinned = simplify(smoothed, tol)
    out: List[Dict[str, Any]] = []
    for i, (t, v) in enumerate(thinned):
        rec: Dict[str, Any] = {"t": t, "v": format_value(v, prop_leaf, is_pair, is_int)}
        if i > 0:
            rec["ease"] = "linear"
        out.append(rec)
    return out, t0, t1


def op_exp_scale(
    current_val: Any,
    op: Dict[str, Any],
    el_start: int,
    el_end: int,
    fps: float,
    prop_leaf: str,
    is_pair: bool,
    is_int: bool,
) -> Tuple[List[Dict[str, Any]], int, int]:
    t0 = on_frame(float(op.get("start", op.get("t0", el_start))), fps)
    t1 = on_frame(float(op.get("end", op.get("t1", el_end))), fps)
    default_base = [1.0, 1.0] if is_pair else 1.0
    s0 = op.get("from", op.get("s0", op.get("v0", eval_keyframes(current_val, float(t0), default_base))))
    s1 = op.get("to", op.get("s1", op.get("v1", eval_keyframes(current_val, float(t1), default_base))))
    tol = float(op.get("tol", 0.002))

    times = drawn_frames(t0, t1, fps)
    span = max(1.0, float(t1 - t0))
    samples: List[Tuple[int, Any]] = []

    if is_pair:
        p0, p1 = to_pair(s0), to_pair(s1)
        if p0[0] <= 0 or p0[1] <= 0 or p1[0] <= 0 or p1[1] <= 0:
            raise ValueError("exp_scale requires strictly positive start and end scale values")
        for t in times:
            u = (t - t0) / span
            vx = p0[0] * ((p1[0] / p0[0]) ** u)
            vy = p0[1] * ((p1[1] / p0[1]) ** u)
            samples.append((t, format_value([vx, vy], prop_leaf, is_pair, is_int)))
    else:
        v0, v1 = to_scalar(s0), to_scalar(s1)
        if v0 <= 0 or v1 <= 0:
            raise ValueError("exp_scale requires strictly positive start and end scale values")
        for t in times:
            u = (t - t0) / span
            v = v0 * ((v1 / v0) ** u)
            samples.append((t, format_value(v, prop_leaf, is_pair, is_int)))

    thinned = simplify(samples, tol)
    out: List[Dict[str, Any]] = []
    for i, (t, v) in enumerate(thinned):
        rec: Dict[str, Any] = {"t": t, "v": format_value(v, prop_leaf, is_pair, is_int)}
        if i > 0:
            rec["ease"] = "linear"
        out.append(rec)
    return out, t0, t1


def decode_audio_f32le(audio_path: Path, sample_rate: int = 22050) -> List[float]:
    res = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(audio_path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    raw = res.stdout
    count = len(raw) // 4
    return list(struct.unpack(f"<{count}f", raw[: count * 4]))


def op_audio(
    project: Dict[str, Any],
    current_val: Any,
    op: Dict[str, Any],
    el_start: int,
    el_end: int,
    fps: float,
    prop_leaf: str,
    is_pair: bool,
    is_int: bool,
    base_dir: Path,
    pcm_cache: Dict[Path, List[float]],
) -> Tuple[List[Dict[str, Any]], int, int]:
    t0 = on_frame(float(op.get("start", op.get("t0", el_start))), fps)
    t1 = on_frame(float(op.get("end", op.get("t1", el_end))), fps)
    floor_db = float(op.get("floor_db", -45.0))
    peak_db = float(op.get("peak_db", -6.0))
    min_v = op.get("min_v", op.get("min", [1.0, 1.0] if is_pair else 0.0))
    max_v = op.get("max_v", op.get("max", [1.25, 1.25] if is_pair else 1.0))
    window_ms = float(op.get("window_ms", op.get("smooth_ms", 0.0)))
    default_tol = 0.5 if is_int else 0.005
    tol = float(op.get("tol", default_tol))

    audio_el: Optional[Dict[str, Any]] = None
    audio_id = op.get("audio_id", op.get("source_id", op.get("voice")))
    if audio_id:
        for tr in project.get("tracks", []):
            for cand in tr.get("elements", []):
                if cand.get("id") == audio_id:
                    audio_el = cand
                    break
        if audio_el is None:
            raise ValueError(f"Audio element '{audio_id}' not found in project")
    elif "source" not in op and "file" not in op:
        for tr in project.get("tracks", []):
            for cand in tr.get("elements", []):
                if cand.get("type") in {"audio", "video"} and "source" in cand:
                    audio_el = cand
                    break

    if audio_el is not None:
        rel_src = audio_el["source"]
        audio_start_tl = int(audio_el.get("start", 0))
        source_start_ms = float(audio_el.get("source_start", 0))
        speed = float(audio_el.get("speed", 1.0))
    else:
        rel_src = op.get("source", op.get("file"))
        if not rel_src:
            raise ValueError("audio operation requires 'audio_id' or 'source'")
        audio_start_tl = int(op.get("audio_start", 0))
        source_start_ms = float(op.get("source_start", 0))
        speed = float(op.get("speed", 1.0))

    audio_path = (base_dir / rel_src).resolve()
    if not audio_path.exists():
        audio_path = Path(rel_src).resolve()

    sr = 22050
    if audio_path not in pcm_cache:
        pcm_cache[audio_path] = decode_audio_f32le(audio_path, sr)
    pcm = pcm_cache[audio_path]

    times = drawn_frames(t0, t1, fps)
    frame_dur_ms = max(1.0, 1000.0 / fps)
    rms_win_ms = max(frame_dur_ms, window_ms) if window_ms > 0 else frame_dur_ms
    db_span = peak_db - floor_db if abs(peak_db - floor_db) > 1e-6 else 1.0

    raw_samples: List[Tuple[int, Any]] = []
    for t in times:
        src_ms = source_start_ms + (t - audio_start_tl) * speed
        i0 = max(0, int((src_ms / 1000.0) * sr))
        i1 = min(len(pcm), int(((src_ms + rms_win_ms * speed) / 1000.0) * sr))
        if i1 > i0 and i0 < len(pcm):
            chunk = pcm[i0:i1]
            mean_sq = sum(s * s for s in chunk) / len(chunk)
            rms = math.sqrt(mean_sq)
            db = 20.0 * math.log10(max(rms, 1e-6))
        else:
            db = floor_db
        u = min(1.0, max(0.0, (db - floor_db) / db_span))
        mapped = lerp_val(min_v, max_v, u)
        raw_samples.append((t, format_value(mapped, prop_leaf, is_pair, is_int)))

    thinned = simplify(raw_samples, tol)
    out: List[Dict[str, Any]] = []
    for i, (t, v) in enumerate(thinned):
        rec: Dict[str, Any] = {"t": t, "v": format_value(v, prop_leaf, is_pair, is_int)}
        if i > 0:
            rec["ease"] = "linear"
        out.append(rec)
    return out, t0, t1


def op_auto_bezier(
    current_val: Any,
    op: Dict[str, Any],
    el_start: int,
    el_end: int,
    fps: float,
    prop_leaf: str,
    is_pair: bool,
    is_int: bool,
) -> Tuple[List[Dict[str, Any]], int, int]:
    """Compute Fritsch-Carlson monotonic cubic spline handles for smooth pass-through (ADR-0219)."""
    kfs_in: List[Dict[str, Any]] = []
    if "keyframes" in op and isinstance(op["keyframes"], list):
        kfs_in = [dict(k) for k in op["keyframes"]]
    elif isinstance(current_val, list) and current_val and isinstance(current_val[0], dict):
        kfs_in = [dict(k) for k in current_val]

    if len(kfs_in) < 2:
        raise ValueError(f"auto_bezier on '{prop_leaf}' requires at least 2 keyframes")

    t0 = int(op.get("start", op.get("t0", kfs_in[0]["t"])))
    t1 = int(op.get("end", op.get("t1", kfs_in[-1]["t"])))
    slice_kfs = [dict(k) for k in kfs_in if t0 <= int(k["t"]) <= t1]
    if len(slice_kfs) < 2:
        return slice_kfs, t0, t1

    axis = 0
    if is_pair:
        vals_0 = [to_pair(k["v"])[0] for k in slice_kfs]
        vals_1 = [to_pair(k["v"])[1] for k in slice_kfs]
        if max(vals_0) - min(vals_0) < 1e-9 and max(vals_1) - min(vals_1) >= 1e-9:
            axis = 1

    def scalar_v(val: Any) -> float:
        if isinstance(val, list):
            return float(val[axis])
        return float(val)

    n_segs = len(slice_kfs) - 1
    dt_list: List[float] = []
    dv_list: List[float] = []
    secants: List[float] = []
    for j in range(1, len(slice_kfs)):
        dt = float(int(slice_kfs[j]["t"]) - int(slice_kfs[j - 1]["t"]))
        dv = scalar_v(slice_kfs[j]["v"]) - scalar_v(slice_kfs[j - 1]["v"])
        dt_list.append(dt)
        dv_list.append(dv)
        secants.append(dv / dt if dt > 0.0 else 0.0)

    m0 = float(op.get("start_slope", op.get("m0", 0.0)))
    mn = float(op.get("end_slope", op.get("mn", 0.0)))
    slopes: List[float] = [0.0] * (n_segs + 1)
    slopes[0] = m0
    slopes[n_segs] = mn

    for i in range(1, n_segs):
        d_prev = secants[i - 1]
        d_next = secants[i]
        if d_prev * d_next <= 0.0:
            slopes[i] = 0.0
        else:
            dt_prev = dt_list[i - 1]
            dt_next = dt_list[i]
            w1 = 2.0 * dt_next + dt_prev
            w2 = dt_next + 2.0 * dt_prev
            m_i = (w1 + w2) / (w1 / d_prev + w2 / d_next)
            max_mag = 3.0 * min(abs(d_prev), abs(d_next))
            if abs(m_i) > max_mag:
                m_i = math.copysign(max_mag, m_i)
            slopes[i] = m_i

    x1 = round(1.0 / 3.0, 6)
    x2 = round(2.0 / 3.0, 6)
    out: List[Dict[str, Any]] = [dict(slice_kfs[0])]
    for j in range(1, len(slice_kfs)):
        kf = dict(slice_kfs[j])
        dt = dt_list[j - 1]
        dv = dv_list[j - 1]
        if abs(dv) <= 1e-12:
            y1 = 0.0
            y2 = 1.0
        else:
            y1 = round((slopes[j - 1] * dt) / (3.0 * dv), 6)
            y2 = round(1.0 - (slopes[j] * dt) / (3.0 * dv), 6)
            if abs(y1) < 1e-12:
                y1 = 0.0
            if abs(y2) < 1e-12:
                y2 = 0.0
        kf["ease"] = [x1, y1, x2, y2]
        out.append(kf)

    return out, int(slice_kfs[0]["t"]), int(slice_kfs[-1]["t"])


def extract_operations(spec: Any) -> List[Dict[str, Any]]:
    if isinstance(spec, list):
        return spec
    if isinstance(spec, dict):
        if "operations" in spec:
            return spec["operations"]
        if "passes" in spec:
            return spec["passes"]
        if "op" in spec or "pass" in spec or "type" in spec:
            return [spec]
    raise ValueError("Spec must contain an 'operations' list or be an operation object")


def find_element(project: Dict[str, Any], el_id: str) -> Dict[str, Any]:
    for track in project.get("tracks", []):
        for el in track.get("elements", []):
            if el.get("id") == el_id:
                return el
    raise ValueError(f"Element '{el_id}' not found in project")


def apply_spec(
    project: Dict[str, Any],
    spec: Any,
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    updated = copy.deepcopy(project)
    fps = fps_float(updated.get("fps", 30))
    ops = extract_operations(spec)
    resolved_dir = base_dir if base_dir is not None else Path.cwd()
    pcm_cache: Dict[Path, List[float]] = {}

    for op in ops:
        op_name = str(op.get("op", op.get("pass", op.get("type", "")))).lower()
        el_id = op.get("id", op.get("element"))
        if not el_id:
            raise ValueError(f"Operation '{op_name}' is missing target element 'id'")
        prop_spec = op.get("property", op.get("prop"))
        if not prop_spec:
            prop_spec = "scale" if op_name == "exp_scale" else None
        if not prop_spec:
            raise ValueError(f"Operation '{op_name}' on '{el_id}' is missing 'property'")

        element = find_element(updated, el_id)
        el_start = int(element.get("start", 0))
        el_end = int(element.get("end", updated.get("duration", 1000)))
        container, key, prop_leaf, eff_name = resolve_target(element, prop_spec, op.get("effect"))
        current_val = container.get(key)
        is_pair = is_pair_property(prop_leaf, current_val, op)
        is_int = is_integer_property(prop_leaf, eff_name)

        if op_name == "wiggle":
            new_kfs, t0, t1 = op_wiggle(
                current_val, op, el_start, el_end, fps, prop_leaf, is_pair, is_int
            )
        elif op_name == "bounce":
            new_kfs, t0, t1 = op_bounce(
                current_val, op, el_start, el_end, fps, prop_leaf, is_pair, is_int
            )
        elif op_name == "loop":
            new_kfs, t0, t1 = op_loop(
                current_val, op, el_start, el_end, fps, prop_leaf, is_pair, is_int
            )
        elif op_name == "smooth":
            new_kfs, t0, t1 = op_smooth(
                current_val, op, el_start, el_end, fps, prop_leaf, is_pair, is_int
            )
        elif op_name == "exp_scale":
            new_kfs, t0, t1 = op_exp_scale(
                current_val, op, el_start, el_end, fps, prop_leaf, is_pair, is_int
            )
        elif op_name == "audio":
            new_kfs, t0, t1 = op_audio(
                updated,
                current_val,
                op,
                el_start,
                el_end,
                fps,
                prop_leaf,
                is_pair,
                is_int,
                resolved_dir,
                pcm_cache,
            )
        elif op_name == "auto_bezier":
            new_kfs, t0, t1 = op_auto_bezier(
                current_val, op, el_start, el_end, fps, prop_leaf, is_pair, is_int
            )
        else:
            raise ValueError(f"Unknown keyframe operation '{op_name}'")

        spliced = splice_keyframes(current_val, new_kfs, t0, t1)
        set_in_canonical_order(container, key, spliced, container is element)

    return updated


def validate_project(project_data: Dict[str, Any], project_path: Path) -> None:
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=".keyframes-validate-",
        suffix=".montagent.json",
        dir=str(project_path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(project_data, f, indent=2)
            f.write("\n")
        res = subprocess.run(
            ["montagent", "validate", "--json", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        if res.stdout:
            try:
                report = json.loads(res.stdout)
                errors = [
                    f for f in report.get("findings", []) if f.get("class") == "error"
                ]
                if errors:
                    sys.stderr.write(res.stdout)
                    sys.exit(1)
                return
            except json.JSONDecodeError:
                pass
        if res.returncode != 0:
            sys.stderr.write(res.stderr or res.stdout)
            sys.exit(res.returncode)
    finally:
        tmp_path.unlink(missing_ok=True)


def main(argv: Optional[List[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args or "-h" in args or "--help" in args:
        sys.stdout.write(__doc__ or "")
        return 0 if args else 2

    check_only = False
    positional: List[str] = []
    for arg in args:
        if arg == "--check":
            check_only = True
        elif arg.startswith("-"):
            sys.stderr.write(f"Unknown option: {arg}\n")
            return 2
        else:
            positional.append(arg)

    if len(positional) != 2:
        sys.stderr.write(
            "Usage: keyframes.py <project.montagent.json> <keyframes.spec.json> [--check]\n"
        )
        return 2

    project_path = Path(positional[0]).resolve()
    spec_path = Path(positional[1]).resolve()
    project = json.loads(project_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    updated = apply_spec(project, spec, base_dir=project_path.parent)

    if check_only:
        if updated != project:
            sys.stderr.write(
                f"{project_path.name}: keyframes have drifted from {spec_path.name}\n"
            )
            return 1
        return 0

    validate_project(updated, project_path)
    sys.stdout.write(json.dumps(updated, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

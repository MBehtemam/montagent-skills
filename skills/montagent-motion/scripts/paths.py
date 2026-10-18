#!/usr/bin/env python3
"""Bake write-time path geometry and sequential trim timings into a Montagent project.

Requires Python >= 3.9
drift-guard: paths.montagent.json paths.spec.json

Usage:
    python3 skills/montagent-motion/scripts/paths.py <project.json> <spec.json>

Implements ADR-0226 write-time path operations:
- taper: variable-width / wave stroke baked into a closed filled path outline
- boolean: 2D polygon boolean operations (union, subtract, intersect, exclude)
- offset: inward/outward path offset with miter, bevel, or round joins
- pucker_bloat: radial vertex/handle pucker and bloat around a center
- twist: radial vortex twist around a center
- zig_zag: corner or smooth ridge/valley subdivision along path segments
- wiggle: seeded deterministic procedural displacement (static or keyframed)
- trim_sequential: arc-length-proportional sequential trim_start/trim_end keyframes
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

Point2D = Tuple[float, float]
Bounds = Tuple[int, int, int, int]
VertexDict = Dict[str, Any]


# ---------------------------------------------------------------------------
# Low-level geometry & cubic Bezier helpers
# ---------------------------------------------------------------------------


def _clamp_int(val: float, lo: Optional[int] = None, hi: Optional[int] = None) -> int:
    iv = int(round(val))
    if lo is not None and iv < lo:
        iv = lo
    if hi is not None and iv > hi:
        iv = hi
    return iv


def _make_vertex(
    x: float,
    y: float,
    in_dx: Optional[float] = None,
    in_dy: Optional[float] = None,
    out_dx: Optional[float] = None,
    out_dy: Optional[float] = None,
    bounds: Optional[Bounds] = None,
    keep_zero_handles: bool = False,
) -> VertexDict:
    min_x, min_y, max_x, max_y = bounds if bounds is not None else (None, None, None, None)
    ax = _clamp_int(x, min_x, max_x)
    ay = _clamp_int(y, min_y, max_y)
    v: VertexDict = {"at": [ax, ay]}
    if in_dx is not None and in_dy is not None:
        hx = _clamp_int(ax + in_dx, min_x, max_x) - ax
        hy = _clamp_int(ay + in_dy, min_y, max_y) - ay
        if keep_zero_handles or hx != 0 or hy != 0:
            v["in"] = [hx, hy]
    if out_dx is not None and out_dy is not None:
        hx = _clamp_int(ax + out_dx, min_x, max_x) - ax
        hy = _clamp_int(ay + out_dy, min_y, max_y) - ay
        if keep_zero_handles or hx != 0 or hy != 0:
            v["out"] = [hx, hy]
    return v


def _extract_vertices(path_like: Any) -> List[VertexDict]:
    if isinstance(path_like, dict) and "points" in path_like:
        pts = path_like["points"]
    else:
        pts = path_like
    out: List[VertexDict] = []
    for item in pts:
        if isinstance(item, dict) and "at" in item:
            v: VertexDict = {"at": [float(item["at"][0]), float(item["at"][1])]}
            if "in" in item and item["in"] is not None:
                v["in"] = [float(item["in"][0]), float(item["in"][1])]
            if "out" in item and item["out"] is not None:
                v["out"] = [float(item["out"][0]), float(item["out"][1])]
            out.append(v)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append({"at": [float(item[0]), float(item[1])]})
        else:
            raise ValueError(f"Unsupported vertex representation: {item!r}")
    return out


def _has_curves(pts: Sequence[VertexDict]) -> bool:
    for p in pts:
        if "in" in p or "out" in p:
            return True
    return False


def _cubic_eval(p0: Point2D, p1: Point2D, p2: Point2D, p3: Point2D, t: float) -> Point2D:
    mt = 1.0 - t
    c0 = mt * mt * mt
    c1 = 3.0 * mt * mt * t
    c2 = 3.0 * mt * t * t
    c3 = t * t * t
    return (
        c0 * p0[0] + c1 * p1[0] + c2 * p2[0] + c3 * p3[0],
        c0 * p0[1] + c1 * p1[1] + c2 * p2[1] + c3 * p3[1],
    )


def _cubic_tangent(p0: Point2D, p1: Point2D, p2: Point2D, p3: Point2D, t: float) -> Point2D:
    mt = 1.0 - t
    dx = (
        3.0 * mt * mt * (p1[0] - p0[0])
        + 6.0 * mt * t * (p2[0] - p1[0])
        + 3.0 * t * t * (p3[0] - p2[0])
    )
    dy = (
        3.0 * mt * mt * (p1[1] - p0[1])
        + 6.0 * mt * t * (p2[1] - p1[1])
        + 3.0 * t * t * (p3[1] - p2[1])
    )
    length = math.hypot(dx, dy)
    if length < 1e-9:
        dx = p3[0] - p0[0]
        dy = p3[1] - p0[1]
        length = math.hypot(dx, dy)
    if length < 1e-9:
        return (1.0, 0.0)
    return (dx / length, dy / length)


def _segment_control_points(v0: VertexDict, v1: VertexDict) -> Tuple[Point2D, Point2D, Point2D, Point2D, bool]:
    p0 = (float(v0["at"][0]), float(v0["at"][1]))
    p3 = (float(v1["at"][0]), float(v1["at"][1]))
    out0 = v0.get("out")
    in1 = v1.get("in")
    is_curved = (out0 is not None and (out0[0] != 0 or out0[1] != 0)) or (
        in1 is not None and (in1[0] != 0 or in1[1] != 0)
    )
    p1 = (p0[0] + (out0[0] if out0 else 0.0), p0[1] + (out0[1] if out0 else 0.0))
    p2 = (p3[0] + (in1[0] if in1 else 0.0), p3[1] + (in1[1] if in1 else 0.0))
    return p0, p1, p2, p3, is_curved


def _flatten_path(
    points: Sequence[Any],
    closed: bool = False,
    steps_per_curve: int = 16,
) -> List[Point2D]:
    verts = _extract_vertices(points)
    n = len(verts)
    if n == 0:
        return []
    seg_count = n if closed else n - 1
    result: List[Point2D] = []
    for i in range(seg_count):
        v0 = verts[i]
        v1 = verts[(i + 1) % n]
        p0, p1, p2, p3, is_curved = _segment_control_points(v0, v1)
        if not is_curved:
            if i == 0:
                result.append(p0)
            result.append(p3)
        else:
            start_step = 0 if i == 0 else 1
            for s in range(start_step, steps_per_curve + 1):
                t = s / float(steps_per_curve)
                result.append(_cubic_eval(p0, p1, p2, p3, t))
    if closed and len(result) > 1 and math.hypot(result[0][0] - result[-1][0], result[0][1] - result[-1][1]) < 1e-6:
        result.pop()
    return result


def _sample_backbone_with_tangents(
    points: Sequence[Any],
    closed: bool = False,
    samples: Optional[int] = None,
) -> List[Tuple[Point2D, Point2D, float]]:
    """Return [(point, unit_tangent, cumulative_arc_length), ...] along the path."""
    verts = _extract_vertices(points)
    n = len(verts)
    if n < 2:
        raise ValueError("Path requires at least 2 vertices")
    seg_count = n if closed else n - 1
    raw_samples: List[Tuple[Point2D, Point2D]] = []
    steps_per_seg = max(8, (samples // max(1, seg_count)) if samples else 16)
    for i in range(seg_count):
        v0 = verts[i]
        v1 = verts[(i + 1) % n]
        p0, p1, p2, p3, _ = _segment_control_points(v0, v1)
        start_step = 0 if i == 0 else 1
        for s in range(start_step, steps_per_seg + 1):
            t = s / float(steps_per_seg)
            pt = _cubic_eval(p0, p1, p2, p3, t)
            tan = _cubic_tangent(p0, p1, p2, p3, t)
            raw_samples.append((pt, tan))

    out: List[Tuple[Point2D, Point2D, float]] = []
    arc = 0.0
    for idx, (pt, tan) in enumerate(raw_samples):
        if idx > 0:
            prev_pt = raw_samples[idx - 1][0]
            arc += math.hypot(pt[0] - prev_pt[0], pt[1] - prev_pt[1])
        out.append((pt, tan, arc))
    return out


def _dedupe_int_vertices(verts: Sequence[VertexDict], closed: bool = True, min_verts: int = 3) -> List[VertexDict]:
    cleaned: List[VertexDict] = []
    for v in verts:
        if (
            cleaned
            and cleaned[-1]["at"] == v["at"]
            and "in" not in v
            and "out" not in v
            and "in" not in cleaned[-1]
            and "out" not in cleaned[-1]
        ):
            continue
        cleaned.append(v)
    if (
        closed
        and len(cleaned) > min_verts
        and cleaned[0]["at"] == cleaned[-1]["at"]
        and "in" not in cleaned[-1]
        and "out" not in cleaned[-1]
    ):
        cleaned.pop()
    return cleaned


# ---------------------------------------------------------------------------
# 1. Stroke Taper (and wave modulation) -> closed filled outline
# ---------------------------------------------------------------------------


def _normalize_fraction(val: float) -> float:
    v = float(val)
    if v > 1.0:
        v = v / 100.0
    return max(0.0, min(1.0, v))


def _apply_ease_power(t: float, ease: float) -> float:
    """Shape ramp parameter t in [0, 1] with ease in [-1, 1] (or [-100, 100])."""
    t = max(0.0, min(1.0, t))
    e = float(ease)
    if abs(e) > 1.0:
        e = max(-1.0, min(1.0, e / 100.0))
    if abs(e) < 1e-6:
        return t
    if e > 0:
        # Smooth/ease-in-out towards higher ease
        power = 1.0 + 2.0 * e
        return 1.0 - pow(1.0 - t, power)
    else:
        power = 1.0 - 2.0 * e
        return pow(t, power)


def taper(
    points: Sequence[Any],
    start_width: Optional[float] = None,
    end_width: Optional[float] = None,
    *,
    width: float = 20.0,
    start_length: float = 0.0,
    end_length: float = 0.0,
    start_ease: float = 0.0,
    end_ease: float = 0.0,
    wave_amount: float = 0.0,
    wave_length: float = 0.0,
    wave_phase: float = 0.0,
    cap: str = "butt",
    closed: bool = False,
    samples: Optional[int] = None,
    bounds: Optional[Bounds] = None,
) -> List[VertexDict]:
    """Convert an open or closed path into a closed filled outline with variable stroke width."""
    sl = _normalize_fraction(start_length)
    el = _normalize_fraction(end_length)
    sw = float(width if start_width is None else start_width)
    ew = float(width if end_width is None else end_width)
    mid_w = float(width)

    # If caller specified start_width / end_width directly without start_length / end_length,
    # interpolate smoothly along the full path from start_width to end_width.
    full_linear = sl == 0.0 and el == 0.0 and (start_width is not None or end_width is not None)

    sampled = _sample_backbone_with_tangents(points, closed=closed, samples=samples)
    total_len = max(1e-6, sampled[-1][2])

    left_side: List[Point2D] = []
    right_side: List[Point2D] = []

    for pt, tan, s in sampled:
        u = s / total_len
        if full_linear and wave_amount == 0.0:
            t_eased = _apply_ease_power(u, start_ease if start_ease != 0.0 else end_ease)
            w = sw + (ew - sw) * t_eased
        elif full_linear:
            w = sw + (ew - sw) * u
        else:
            if sl > 0.0 and u < sl:
                t_local = _apply_ease_power(u / sl, start_ease)
                w = sw + (mid_w - sw) * t_local
            elif el > 0.0 and u > 1.0 - el:
                t_local = _apply_ease_power((1.0 - u) / el, end_ease)
                w = ew + (mid_w - ew) * t_local
            else:
                w = mid_w

        if wave_amount != 0.0 and wave_length > 0.0:
            wa = float(wave_amount)
            if abs(wa) > 1.0:
                wa = wa / 100.0
            phase_rad = math.radians(wave_phase) if abs(wave_phase) > 2.0 * math.pi else float(wave_phase)
            w = w * (1.0 + wa * math.sin(2.0 * math.pi * (s / float(wave_length)) + phase_rad))

        half_w = max(0.5, w * 0.5)
        nx, ny = -tan[1], tan[0]
        left_side.append((pt[0] + nx * half_w, pt[1] + ny * half_w))
        right_side.append((pt[0] - nx * half_w, pt[1] - ny * half_w))

    outline_pts: List[Point2D] = []

    # Start cap
    p_start, tan_start, _ = sampled[0]
    r_start = max(0.5, math.hypot(left_side[0][0] - p_start[0], left_side[0][1] - p_start[1]))
    if not closed and cap == "round" and r_start >= 1.5:
        base_angle = math.atan2(right_side[0][1] - p_start[1], right_side[0][0] - p_start[0])
        for k in range(1, 6):
            ang = base_angle - (math.pi * k / 6.0)
            outline_pts.append((p_start[0] + r_start * math.cos(ang), p_start[1] + r_start * math.sin(ang)))
    elif not closed and cap == "square" and r_start >= 1.0:
        nx, ny = -tan_start[1], tan_start[0]
        outline_pts.append(
            (
                p_start[0] - tan_start[0] * r_start - nx * r_start,
                p_start[1] - tan_start[1] * r_start - ny * r_start,
            )
        )
        outline_pts.append(
            (
                p_start[0] - tan_start[0] * r_start + nx * r_start,
                p_start[1] - tan_start[1] * r_start + ny * r_start,
            )
        )

    outline_pts.extend(left_side)

    # End cap
    p_end, tan_end, _ = sampled[-1]
    r_end = max(0.5, math.hypot(left_side[-1][0] - p_end[0], left_side[-1][1] - p_end[1]))
    if not closed and cap == "round" and r_end >= 1.5:
        base_angle = math.atan2(left_side[-1][1] - p_end[1], left_side[-1][0] - p_end[0])
        for k in range(1, 6):
            ang = base_angle - (math.pi * k / 6.0)
            outline_pts.append((p_end[0] + r_end * math.cos(ang), p_end[1] + r_end * math.sin(ang)))
    elif not closed and cap == "square" and r_end >= 1.0:
        nx, ny = -tan_end[1], tan_end[0]
        outline_pts.append(
            (
                p_end[0] + tan_end[0] * r_end + nx * r_end,
                p_end[1] + tan_end[1] * r_end + ny * r_end,
            )
        )
        outline_pts.append(
            (
                p_end[0] + tan_end[0] * r_end - nx * r_end,
                p_end[1] + tan_end[1] * r_end - ny * r_end,
            )
        )

    outline_pts.extend(reversed(right_side))

    verts = [_make_vertex(px, py, bounds=bounds) for px, py in outline_pts]
    return _dedupe_int_vertices(verts, closed=True, min_verts=3)


# ---------------------------------------------------------------------------
# 2. 2D Polygon Boolean Operations (union, subtract, intersect, exclude)
# ---------------------------------------------------------------------------


def _signed_area(poly: Sequence[Point2D]) -> float:
    area = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        area += x0 * y1 - x1 * y0
    return 0.5 * area


def _ensure_orientation(poly: Sequence[Point2D], positive: bool = True) -> List[Point2D]:
    pts = list(poly)
    if len(pts) < 3:
        return pts
    area = _signed_area(pts)
    if (area < 0.0) == positive:
        pts.reverse()
    return pts


def _point_in_poly(pt: Point2D, poly: Sequence[Point2D]) -> bool:
    """Ray-casting point-in-polygon check."""
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            x_int = (x1 - x0) * (y - y0) / (y1 - y0 + 1e-18) + x0
            if x < x_int:
                inside = not inside
    return inside


def _seg_intersections(a0: Point2D, a1: Point2D, b0: Point2D, b1: Point2D) -> List[Tuple[float, float]]:
    """Return parameters (t, u) in [0, 1] x [0, 1] where segments a0->a1 and b0->b1 intersect."""
    rx, ry = a1[0] - a0[0], a1[1] - a0[1]
    sx, sy = b1[0] - b0[0], b1[1] - b0[1]
    denom = rx * sy - ry * sx
    qpx, qpy = b0[0] - a0[0], b0[1] - a0[1]
    eps = 1e-9
    if abs(denom) > eps:
        t = (qpx * sy - qpy * sx) / denom
        u = (qpx * ry - qpy * rx) / denom
        if -eps <= t <= 1.0 + eps and -eps <= u <= 1.0 + eps:
            return [(max(0.0, min(1.0, t)), max(0.0, min(1.0, u)))]
        return []

    # Collinear check
    cross = qpx * ry - qpy * rx
    if abs(cross) > 1e-6:
        return []
    r_len2 = rx * rx + ry * ry
    s_len2 = sx * sx + sy * sy
    if r_len2 < eps or s_len2 < eps:
        return []
    results: List[Tuple[float, float]] = []
    for u_val, pt in ((0.0, b0), (1.0, b1)):
        t_val = ((pt[0] - a0[0]) * rx + (pt[1] - a0[1]) * ry) / r_len2
        if -eps <= t_val <= 1.0 + eps:
            results.append((max(0.0, min(1.0, t_val)), u_val))
    for t_val, pt in ((0.0, a0), (1.0, a1)):
        u_val = ((pt[0] - b0[0]) * sx + (pt[1] - b0[1]) * sy) / s_len2
        if -eps <= u_val <= 1.0 + eps:
            results.append((t_val, max(0.0, min(1.0, u_val))))
    return results


def _simplify_collinear(poly: Sequence[Point2D], eps: float = 1e-4) -> List[Point2D]:
    pts: List[Point2D] = []
    for p in poly:
        if not pts or math.hypot(p[0] - pts[-1][0], p[1] - pts[-1][1]) > eps:
            pts.append(p)
    if len(pts) > 1 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) <= eps:
        pts.pop()
    if len(pts) < 3:
        return pts
    changed = True
    while changed and len(pts) >= 3:
        changed = False
        n = len(pts)
        next_pts: List[Point2D] = []
        for i in range(n):
            p_prev = pts[(i - 1) % n]
            p_curr = pts[i]
            p_next = pts[(i + 1) % n]
            v1x, v1y = p_curr[0] - p_prev[0], p_curr[1] - p_prev[1]
            v2x, v2y = p_next[0] - p_curr[0], p_next[1] - p_curr[1]
            l1 = math.hypot(v1x, v1y)
            l2 = math.hypot(v2x, v2y)
            if l1 < eps or l2 < eps:
                changed = True
                continue
            cross = abs(v1x * v2y - v1y * v2x) / (l1 * l2)
            dot = (v1x * v2x + v1y * v2y) / (l1 * l2)
            if cross < 1e-4 and dot > 0:
                changed = True
                continue
            next_pts.append(p_curr)
        pts = next_pts
    return pts


def _boolean_pair_polygons(
    poly_a: Sequence[Point2D],
    poly_b: Sequence[Point2D],
    op: str,
) -> List[List[Point2D]]:
    a = _ensure_orientation(poly_a, positive=True)
    b = _ensure_orientation(poly_b, positive=True)
    if len(a) < 3 or len(b) < 3:
        return []

    segs_a = [(a[i], a[(i + 1) % len(a)]) for i in range(len(a))]
    segs_b = [(b[i], b[(i + 1) % len(b)]) for i in range(len(b))]

    splits_a: List[List[float]] = [[0.0, 1.0] for _ in segs_a]
    splits_b: List[List[float]] = [[0.0, 1.0] for _ in segs_b]

    for ia, (a0, a1) in enumerate(segs_a):
        for ib, (b0, b1) in enumerate(segs_b):
            for t, u in _seg_intersections(a0, a1, b0, b1):
                splits_a[ia].append(t)
                splits_b[ib].append(u)

    def _subsegments(segs: List[Tuple[Point2D, Point2D]], splits: List[List[float]]) -> List[Tuple[Point2D, Point2D]]:
        out: List[Tuple[Point2D, Point2D]] = []
        for (p0, p1), ts in zip(segs, splits):
            ts_sorted = sorted(ts)
            uniq: List[float] = []
            for tv in ts_sorted:
                if not uniq or abs(tv - uniq[-1]) > 1e-7:
                    uniq.append(tv)
            for k in range(len(uniq) - 1):
                t0, t1 = uniq[k], uniq[k + 1]
                q0 = (p0[0] + (p1[0] - p0[0]) * t0, p0[1] + (p1[1] - p0[1]) * t0)
                q1 = (p0[0] + (p1[0] - p0[0]) * t1, p0[1] + (p1[1] - p0[1]) * t1)
                if math.hypot(q1[0] - q0[0], q1[1] - q0[1]) > 1e-6:
                    out.append((q0, q1))
        return out

    all_candidate_segs = _subsegments(segs_a, splits_a) + _subsegments(segs_b, splits_b)

    op_norm = op.lower().strip()
    if op_norm == "union":
        pred: Callable[[bool, bool], bool] = lambda in_a, in_b: in_a or in_b
    elif op_norm in ("intersect", "intersection"):
        pred = lambda in_a, in_b: in_a and in_b
    elif op_norm in ("subtract", "difference"):
        pred = lambda in_a, in_b: in_a and not in_b
    elif op_norm in ("exclude", "xor"):
        pred = lambda in_a, in_b: in_a != in_b
    else:
        raise ValueError(f"Unsupported boolean operation: {op!r}")

    def _quant_pt(p: Point2D) -> Tuple[int, int]:
        return (int(round(p[0] * 1000.0)), int(round(p[1] * 1000.0)))

    seen_undirected = set()
    directed_edges: List[Tuple[Point2D, Point2D]] = []

    for p0, p1 in all_candidate_segs:
        k0, k1 = _quant_pt(p0), _quant_pt(p1)
        if k0 == k1:
            continue
        undir_key = (min(k0, k1), max(k0, k1))
        if undir_key in seen_undirected:
            continue
        seen_undirected.add(undir_key)

        mx, my = 0.5 * (p0[0] + p1[0]), 0.5 * (p0[1] + p1[1])
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        length = math.hypot(dx, dy)
        nx, ny = -dy / length, dx / length
        eps = min(1e-3, length * 0.1)
        p_left = (mx + nx * eps, my + ny * eps)
        p_right = (mx - nx * eps, my - ny * eps)

        in_left = pred(_point_in_poly(p_left, a), _point_in_poly(p_left, b))
        in_right = pred(_point_in_poly(p_right, a), _point_in_poly(p_right, b))

        if in_left == in_right:
            continue
        # Orient edge so the interior (True) lies to the left (positive normal side)
        if in_left:
            directed_edges.append((p0, p1))
        else:
            directed_edges.append((p1, p0))

    # Chain directed edges into closed loops
    adj: Dict[Tuple[int, int], List[int]] = {}
    for idx, (p0, _) in enumerate(directed_edges):
        adj.setdefault(_quant_pt(p0), []).append(idx)

    used = [False] * len(directed_edges)
    loops: List[List[Point2D]] = []

    for start_idx in range(len(directed_edges)):
        if used[start_idx]:
            continue
        used[start_idx] = True
        p0, p1 = directed_edges[start_idx]
        loop: List[Point2D] = [p0]
        start_key = _quant_pt(p0)
        curr_pt = p1
        curr_key = _quant_pt(curr_pt)
        guard = 0
        while curr_key != start_key and guard <= len(directed_edges) + 2:
            guard += 1
            loop.append(curr_pt)
            candidates = [i for i in adj.get(curr_key, []) if not used[i]]
            if not candidates:
                break
            next_idx = candidates[0]
            used[next_idx] = True
            curr_pt = directed_edges[next_idx][1]
            curr_key = _quant_pt(curr_pt)
        cleaned = _simplify_collinear(loop)
        if len(cleaned) >= 3:
            loops.append(cleaned)

    loops.sort(key=lambda poly: abs(_signed_area(poly)), reverse=True)
    return loops


def boolean_contours(
    paths: Sequence[Any],
    op: str = "union",
    *,
    bounds: Optional[Bounds] = None,
) -> List[List[VertexDict]]:
    """Perform a 2D boolean operation across 2+ paths and return all resulting closed contours."""
    if len(paths) < 2:
        raise ValueError("boolean() requires at least 2 paths")
    polys = [_flatten_path(p, closed=True) for p in paths]
    current_loops = [polys[0]]
    for next_poly in polys[1:]:
        if not current_loops:
            break
        primary = current_loops[0]
        current_loops = _boolean_pair_polygons(primary, next_poly, op)

    contours: List[List[VertexDict]] = []
    for loop in current_loops:
        verts = [_make_vertex(px, py, bounds=bounds) for px, py in loop]
        verts = _dedupe_int_vertices(verts, closed=True, min_verts=3)
        if len(verts) >= 3:
            contours.append(verts)
    return contours


def boolean(
    paths: Sequence[Any],
    op: str = "union",
    *,
    bounds: Optional[Bounds] = None,
) -> List[VertexDict]:
    """Perform a 2D boolean operation across 2+ paths and return a single closed vertex list."""
    contours = boolean_contours(paths, op=op, bounds=bounds)
    if not contours:
        return []
    if len(contours) == 1:
        return contours[0]
    # If multiple contours exist (e.g. exclude or hole cut without mask), bridge them into one closed contour
    combined: List[VertexDict] = list(contours[0])
    for extra in contours[1:]:
        combined.append(copy.deepcopy(extra[0]))
        combined.extend(copy.deepcopy(extra))
        combined.append(copy.deepcopy(combined[0]))
    return combined


# ---------------------------------------------------------------------------
# 3. Offset Paths (miter, bevel, round joins)
# ---------------------------------------------------------------------------


def offset(
    points: Sequence[Any],
    distance: float,
    *,
    miter_limit: float = 4.0,
    line_join: str = "miter",
    closed: bool = True,
    bounds: Optional[Bounds] = None,
) -> List[VertexDict]:
    """Offset a path inward or outward by `distance` pixels using miter, bevel, or round joins."""
    pts = _flatten_path(points, closed=closed)
    n = len(pts)
    if n < (3 if closed else 2):
        raise ValueError("Not enough points to offset")

    # Normalize polygon orientation so outward normal points outside the polygon
    if closed:
        area = _signed_area(pts)
        # In screen coords (y down), clockwise (0,0)->(100,0)->(100,100)->(0,100) has positive signed area.
        # Outward normal for (dx, dy) in positive-area polygon is (dy, -dx) / len.
        sign = 1.0 if area >= 0.0 else -1.0
    else:
        sign = 1.0

    d = float(distance) * sign
    join_kind = line_join.lower().strip()
    if join_kind not in ("miter", "bevel", "round"):
        raise ValueError(f"Unsupported line_join: {line_join!r}")

    def _edge_normal(p0: Point2D, p1: Point2D) -> Tuple[Point2D, Point2D]:
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        length = math.hypot(dx, dy)
        if length < 1e-9:
            return (1.0, 0.0), (0.0, -1.0)
        tx, ty = dx / length, dy / length
        nx, ny = ty, -tx
        return (tx, ty), (nx, ny)

    result_pts: List[Point2D] = []
    if not closed:
        # Open path offset shifts vertices along averaged vertex normals
        for i in range(n):
            if i == 0:
                _, n0 = _edge_normal(pts[0], pts[1])
                result_pts.append((pts[0][0] + n0[0] * d, pts[0][1] + n0[1] * d))
            elif i == n - 1:
                _, n_last = _edge_normal(pts[n - 2], pts[n - 1])
                result_pts.append((pts[n - 1][0] + n_last[0] * d, pts[n - 1][1] + n_last[1] * d))
            else:
                _, n_prev = _edge_normal(pts[i - 1], pts[i])
                _, n_next = _edge_normal(pts[i], pts[i + 1])
                bx, by = n_prev[0] + n_next[0], n_prev[1] + n_next[1]
                blen = math.hypot(bx, by)
                if blen < 1e-6:
                    result_pts.append((pts[i][0] + n_prev[0] * d, pts[i][1] + n_prev[1] * d))
                else:
                    bx, by = bx / blen, by / blen
                    cos_half = max(0.25, bx * n_prev[0] + by * n_prev[1])
                    scale = min(float(miter_limit), 1.0 / cos_half)
                    result_pts.append((pts[i][0] + bx * d * scale, pts[i][1] + by * d * scale))
        return [_make_vertex(px, py, bounds=bounds) for px, py in result_pts]

    for i in range(n):
        p_prev = pts[(i - 1) % n]
        p_curr = pts[i]
        p_next = pts[(i + 1) % n]
        t1, n1 = _edge_normal(p_prev, p_curr)
        t2, n2 = _edge_normal(p_curr, p_next)

        o1 = (p_curr[0] + n1[0] * d, p_curr[1] + n1[1] * d)
        o2 = (p_curr[0] + n2[0] * d, p_curr[1] + n2[1] * d)

        # Compute intersection of offset lines (o1 + s * t1) and (o2 + u * t2)
        denom = t1[0] * t2[1] - t1[1] * t2[0]
        if abs(denom) < 1e-6:
            result_pts.append(o2)
            continue

        qpx, qpy = o2[0] - o1[0], o2[1] - o1[1]
        s_param = (qpx * t2[1] - qpy * t2[0]) / denom
        miter_pt = (o1[0] + s_param * t1[0], o1[1] + s_param * t1[1])
        miter_dist = math.hypot(miter_pt[0] - p_curr[0], miter_pt[1] - p_curr[1])
        abs_d = max(1e-6, abs(d))
        ratio = miter_dist / abs_d

        if join_kind == "bevel":
            result_pts.append(o1)
            result_pts.append(o2)
        elif join_kind == "round":
            ang1 = math.atan2(o1[1] - p_curr[1], o1[0] - p_curr[0])
            ang2 = math.atan2(o2[1] - p_curr[1], o2[0] - p_curr[0])
            diff = ang2 - ang1
            while diff <= -math.pi:
                diff += 2.0 * math.pi
            while diff > math.pi:
                diff -= 2.0 * math.pi
            steps = 4
            for k in range(steps + 1):
                ang = ang1 + diff * (k / float(steps))
                result_pts.append((p_curr[0] + abs_d * math.cos(ang), p_curr[1] + abs_d * math.sin(ang)))
        else:
            # miter join with miter_limit fallback to bevel
            if ratio <= float(miter_limit) + 1e-6:
                result_pts.append(miter_pt)
            else:
                result_pts.append(o1)
                result_pts.append(o2)

    verts = [_make_vertex(px, py, bounds=bounds) for px, py in result_pts]
    return _dedupe_int_vertices(verts, closed=True, min_verts=3)


# ---------------------------------------------------------------------------
# 4. Pucker & Bloat
# ---------------------------------------------------------------------------


def pucker_bloat(
    points: Sequence[Any],
    amount: float,
    *,
    center: Optional[Point2D] = None,
    closed: bool = True,
    bounds: Optional[Bounds] = None,
) -> List[VertexDict]:
    """Pull vertices toward/away from center while moving cubic Bezier handles oppositely."""
    verts = _extract_vertices(points)
    n = len(verts)
    if n < 2:
        return []

    if center is None:
        cx = sum(v["at"][0] for v in verts) / float(n)
        cy = sum(v["at"][1] for v in verts) / float(n)
    else:
        cx, cy = float(center[0]), float(center[1])

    amt = float(amount)
    if abs(amt) > 1.0:
        amt = amt / 100.0

    out: List[VertexDict] = []
    for i, v in enumerate(verts):
        vx, vy = float(v["at"][0]), float(v["at"][1])
        v_prev = verts[(i - 1) % n]["at"]
        v_next = verts[(i + 1) % n]["at"]

        # Positive amount (bloat): move anchors slightly toward center, pull segment mid-handles outward
        # Negative amount (pucker): move anchors outward, pull handles toward center
        anchor_shift = -0.35 * amt
        nx = vx + (cx - vx) * anchor_shift
        ny = vy + (cy - vy) * anchor_shift

        # Base incoming/outgoing handle positions at 1/3 along adjacent segments, then radial push
        base_in_x = vx + (v_prev[0] - vx) / 3.0
        base_in_y = vy + (v_prev[1] - vy) / 3.0
        base_out_x = vx + (v_next[0] - vx) / 3.0
        base_out_y = vy + (v_next[1] - vy) / 3.0

        handle_push = 0.85 * amt
        in_abs_x = base_in_x + (base_in_x - cx) * handle_push
        in_abs_y = base_in_y + (base_in_y - cy) * handle_push
        out_abs_x = base_out_x + (base_out_x - cx) * handle_push
        out_abs_y = base_out_y + (base_out_y - cy) * handle_push

        in_dx: Optional[float] = in_abs_x - nx
        in_dy: Optional[float] = in_abs_y - ny
        out_dx: Optional[float] = out_abs_x - nx
        out_dy: Optional[float] = out_abs_y - ny

        if not closed:
            if i == 0:
                in_dx, in_dy = None, None
            if i == n - 1:
                out_dx, out_dy = None, None

        out.append(_make_vertex(nx, ny, in_dx, in_dy, out_dx, out_dy, bounds=bounds))
    return out


# ---------------------------------------------------------------------------
# 5. Twist
# ---------------------------------------------------------------------------


def twist(
    points: Sequence[Any],
    angle: float,
    *,
    center: Optional[Point2D] = None,
    radius: Optional[float] = None,
    closed: bool = True,
    bounds: Optional[Bounds] = None,
) -> List[VertexDict]:
    """Rotate vertices and handles around `center` with angle decaying quadratically with radius."""
    verts = _extract_vertices(points)
    n = len(verts)
    if n == 0:
        return []

    if center is None:
        cx = sum(v["at"][0] for v in verts) / float(n)
        cy = sum(v["at"][1] for v in verts) / float(n)
    else:
        cx, cy = float(center[0]), float(center[1])

    max_dist = max(math.hypot(v["at"][0] - cx, v["at"][1] - cy) for v in verts)
    rad = float(radius) if radius is not None else max(1.0, max_dist * 1.25)
    rad = max(1e-6, rad)
    angle_rad = math.radians(float(angle))

    def _twist_point(px: float, py: float) -> Point2D:
        dx, dy = px - cx, py - cy
        r = math.hypot(dx, dy)
        if r >= rad:
            return (px, py)
        falloff = 1.0 - (r / rad) ** 2
        theta = angle_rad * falloff
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        return (cx + dx * cos_t - dy * sin_t, cy + dx * sin_t + dy * cos_t)

    out: List[VertexDict] = []
    for i, v in enumerate(verts):
        vx, vy = float(v["at"][0]), float(v["at"][1])
        tx, ty = _twist_point(vx, vy)
        in_dx: Optional[float] = None
        in_dy: Optional[float] = None
        out_dx: Optional[float] = None
        out_dy: Optional[float] = None
        if "in" in v:
            hx, hy = _twist_point(vx + v["in"][0], vy + v["in"][1])
            in_dx, in_dy = hx - tx, hy - ty
        if "out" in v:
            hx, hy = _twist_point(vx + v["out"][0], vy + v["out"][1])
            out_dx, out_dy = hx - tx, hy - ty
        if not closed:
            if i == 0:
                in_dx, in_dy = None, None
            if i == n - 1:
                out_dx, out_dy = None, None
        out.append(_make_vertex(tx, ty, in_dx, in_dy, out_dx, out_dy, bounds=bounds))
    return out


# ---------------------------------------------------------------------------
# 6. Zig Zag
# ---------------------------------------------------------------------------


def zig_zag(
    points: Sequence[Any],
    ridges: int = 4,
    size: float = 10.0,
    *,
    smooth: bool = False,
    closed: bool = False,
    bounds: Optional[Bounds] = None,
) -> List[VertexDict]:
    """Subdivide path segments into alternating ridges and valleys (corner or smooth)."""
    verts = _extract_vertices(points)
    n = len(verts)
    if n < 2:
        raise ValueError("zig_zag requires at least 2 vertices")

    ridge_count = max(1, int(ridges))
    amp = float(size)
    seg_count = n if closed else n - 1

    # Each segment is subdivided into (ridges + 1) sub-steps with alternating normal displacement
    sub_steps = ridge_count + 1
    raw_nodes: List[Tuple[Point2D, Point2D, float]] = []

    for seg_idx in range(seg_count):
        v0 = verts[seg_idx]
        v1 = verts[(seg_idx + 1) % n]
        p0, p1, p2, p3, _ = _segment_control_points(v0, v1)
        seg_len = max(1.0, math.hypot(p3[0] - p0[0], p3[1] - p0[1]))
        handle_scale = seg_len / (sub_steps * 3.0)

        start_k = 0 if seg_idx == 0 else 1
        for k in range(start_k, sub_steps + 1):
            if closed and seg_idx == seg_count - 1 and k == sub_steps:
                continue
            t = k / float(sub_steps)
            base_pt = _cubic_eval(p0, p1, p2, p3, t)
            tan = _cubic_tangent(p0, p1, p2, p3, t)
            nx, ny = -tan[1], tan[0]
            if k == 0 or k == sub_steps:
                disp = 0.0
            else:
                sign = 1.0 if (k % 2 == 1) else -1.0
                disp = sign * amp
            pt = (base_pt[0] + nx * disp, base_pt[1] + ny * disp)
            raw_nodes.append((pt, tan, handle_scale))

    out: List[VertexDict] = []
    total = len(raw_nodes)
    for idx, (pt, tan, h_scale) in enumerate(raw_nodes):
        if not smooth:
            out.append(_make_vertex(pt[0], pt[1], bounds=bounds))
        else:
            in_dx: Optional[float] = -tan[0] * h_scale
            in_dy: Optional[float] = -tan[1] * h_scale
            out_dx: Optional[float] = tan[0] * h_scale
            out_dy: Optional[float] = tan[1] * h_scale
            if not closed:
                if idx == 0:
                    in_dx, in_dy = None, None
                if idx == total - 1:
                    out_dx, out_dy = None, None
            out.append(_make_vertex(pt[0], pt[1], in_dx, in_dy, out_dx, out_dy, bounds=bounds))
    return out


# ---------------------------------------------------------------------------
# 7. Wiggle Paths (deterministic PRNG, static or keyframed)
# ---------------------------------------------------------------------------


def _hash_unit_float(seed: int, vertex_idx: int, axis: int, octave: int, step: int) -> float:
    """Deterministic hash in [-1.0, 1.0] from integer coordinates."""
    msg = f"{seed}:{vertex_idx}:{axis}:{octave}:{step}".encode("ascii")
    digest = hashlib.sha256(msg).digest()
    val = int.from_bytes(digest[:8], "big")
    return (val / float((1 << 64) - 1)) * 2.0 - 1.0


def _smooth_noise_1d(seed: int, vertex_idx: int, axis: int, octave: int, phase: float) -> float:
    i0 = math.floor(phase)
    frac = phase - i0
    # Smoothstep interpolation
    u = frac * frac * (3.0 - 2.0 * frac)
    v0 = _hash_unit_float(seed, vertex_idx, axis, octave, i0)
    v1 = _hash_unit_float(seed, vertex_idx, axis, octave, i0 + 1)
    return v0 + (v1 - v0) * u


def _fractal_displacement(
    seed: int,
    vertex_idx: int,
    octaves: int,
    amplitude: float,
    phase: float,
) -> Point2D:
    dx = 0.0
    dy = 0.0
    amp = 1.0
    norm = 0.0
    freq_mul = 1.0
    for oct_idx in range(max(1, int(octaves))):
        dx += amp * _smooth_noise_1d(seed, vertex_idx, 0, oct_idx, phase * freq_mul)
        dy += amp * _smooth_noise_1d(seed, vertex_idx, 1, oct_idx, phase * freq_mul)
        norm += amp
        amp *= 0.5
        freq_mul *= 2.0
    scale = float(amplitude) / max(1e-9, norm)
    return (dx * scale, dy * scale)


def wiggle(
    points: Sequence[Any],
    *,
    seed: int = 1,
    octaves: int = 1,
    amplitude: float = 10.0,
    frequency: float = 2.0,
    fps: int = 30,
    start: int = 0,
    end: Optional[int] = None,
    step_ms: Optional[int] = None,
    closed: bool = False,
    bounds: Optional[Bounds] = None,
) -> Union[List[VertexDict], List[Dict[str, Any]]]:
    """Deterministically displace path vertices (static vertex list or keyframed `points` list)."""
    verts = _extract_vertices(points)
    n = len(verts)
    has_in = [("in" in v) for v in verts]
    has_out = [("out" in v) for v in verts]

    def _eval_at_time(t_sec: float, keep_handle_shape: bool) -> List[VertexDict]:
        phase = t_sec * float(frequency)
        frame_verts: List[VertexDict] = []
        for idx, v in enumerate(verts):
            dx, dy = _fractal_displacement(int(seed), idx, int(octaves), float(amplitude), phase)
            vx = float(v["at"][0]) + dx
            vy = float(v["at"][1]) + dy
            in_dx = v["in"][0] if has_in[idx] else None
            in_dy = v["in"][1] if has_in[idx] else None
            out_dx = v["out"][0] if has_out[idx] else None
            out_dy = v["out"][1] if has_out[idx] else None
            if not closed:
                if idx == 0:
                    in_dx, in_dy = None, None
                if idx == n - 1:
                    out_dx, out_dy = None, None
            frame_verts.append(
                _make_vertex(
                    vx,
                    vy,
                    in_dx,
                    in_dy,
                    out_dx,
                    out_dy,
                    bounds=bounds,
                    keep_zero_handles=keep_handle_shape,
                )
            )
        return frame_verts

    if end is None or int(end) <= int(start):
        return _eval_at_time(float(start) / 1000.0, keep_handle_shape=False)

    start_ms = int(start)
    end_ms = int(end)
    fps_int = max(1, int(fps))
    unit_ms = max(1, 1000 // math.gcd(1000, fps_int))
    if step_ms is None:
        target_interval = max(unit_ms, int(round(1000.0 / max(1.0, float(frequency) * 2.0))))
        mult = max(1, int(round(target_interval / float(unit_ms))))
        interval = mult * unit_ms
    else:
        interval = max(1, int(step_ms))

    times: List[int] = list(range(start_ms, end_ms, interval))
    if not times or times[-1] != end_ms:
        times.append(end_ms)

    keyframes: List[Dict[str, Any]] = []
    for idx, t_ms in enumerate(times):
        v_now = _eval_at_time(t_ms / 1000.0, keep_handle_shape=True)
        kf: Dict[str, Any] = {
            "t": t_ms,
            "v": v_now,
        }
        if idx > 0 and v_now != keyframes[-1]["v"]:
            kf["ease"] = "linear"
        keyframes.append(kf)
    return keyframes


# ---------------------------------------------------------------------------
# 8. Sequential Trim Paths across sibling contours
# ---------------------------------------------------------------------------


def path_arc_length(points: Sequence[Any], closed: bool = False) -> float:
    sampled = _sample_backbone_with_tangents(points, closed=closed)
    return sampled[-1][2] if sampled else 0.0


def trim_sequential(
    paths: Sequence[Any],
    *,
    start: int = 0,
    end: int = 1000,
    ease: str = "linear",
    mode: str = "end",
    overlap: float = 0.0,
) -> List[Dict[str, Any]]:
    """Compute staggered trim_start / trim_end keyframe schedules proportional to path arc lengths."""
    if not paths:
        return []
    lengths: List[float] = []
    for p in paths:
        is_closed = bool(p.get("closed", False)) if isinstance(p, dict) else False
        pts = p["points"] if isinstance(p, dict) and "points" in p else p
        lengths.append(max(1.0, path_arc_length(pts, closed=is_closed)))

    total_len = sum(lengths)
    total_dur = max(1, int(end) - int(start))
    ov = max(0.0, min(0.9, float(overlap)))

    schedules: List[Dict[str, Any]] = []
    cursor = float(start)
    ease_norm = str(ease).replace("_", "-") if isinstance(ease, str) else ease
    for idx, seg_len in enumerate(lengths):
        frac = seg_len / total_len
        seg_dur = total_dur * frac
        t0 = int(round(cursor))
        if idx == len(lengths) - 1:
            t1 = int(end)
        else:
            t1 = max(t0 + 1, int(round(cursor + seg_dur)))
        cursor += seg_dur * (1.0 - ov)

        if mode == "start":
            schedules.append(
                {
                    "trim_start": [
                        {"t": t0, "v": 0},
                        {"t": t1, "v": 1, "ease": ease_norm},
                    ],
                    "trim_end": 1,
                }
            )
        else:
            schedules.append(
                {
                    "trim_start": 0,
                    "trim_end": [
                        {"t": t0, "v": 0},
                        {"t": t1, "v": 1, "ease": ease_norm},
                    ],
                }
            )
    return schedules


# ---------------------------------------------------------------------------
# CLI Project & Spec Application
# ---------------------------------------------------------------------------


def _find_or_create_track(project: Dict[str, Any], track_name: str, layer: int) -> Dict[str, Any]:
    for track in project.setdefault("tracks", []):
        if track.get("name") == track_name:
            return track
    track = {"name": track_name, "layer": layer, "elements": []}
    project["tracks"].append(track)
    return track


def _find_element(project: Dict[str, Any], element_id: str) -> Optional[Dict[str, Any]]:
    for track in project.get("tracks", []):
        for el in track.get("elements", []):
            if el.get("id") == element_id:
                return el
    return None


def _element_bounds(el: Dict[str, Any], stroke_width: float = 0.0, miter_limit: float = 4.0) -> Bounds:
    w = int(el.get("width", 400))
    h = int(el.get("height", 400))
    if stroke_width > 0.0:
        join = el.get("stroke_join", "miter")
        k = float(miter_limit) if join == "miter" else (math.sqrt(2.0) if join == "round" else 1.0)
        inset = int(math.ceil(k * float(stroke_width) / 2.0))
    else:
        inset = 0
    return (inset, inset, max(inset, w - inset), max(inset, h - inset))


def _build_base_element(op_spec: Dict[str, Any], default_closed: bool) -> Dict[str, Any]:
    el: Dict[str, Any] = {
        "type": "path",
        "id": op_spec["id"],
        "start": int(op_spec.get("start", 0)),
        "end": int(op_spec.get("end", 3000)),
        "x": int(op_spec.get("x", 100)),
        "y": int(op_spec.get("y", 100)),
        "width": int(op_spec.get("width", 400)),
        "height": int(op_spec.get("height", 400)),
        "closed": bool(op_spec.get("closed", default_closed)),
        "points": [],
    }
    for key in (
        "origin",
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
        "opacity",
        "rotation",
        "scale",
        "blend",
        "effects",
    ):
        if key in op_spec:
            el[key] = copy.deepcopy(op_spec[key])
    return el


def _apply_operation(project: Dict[str, Any], op_spec: Dict[str, Any]) -> None:
    op = op_spec.get("op")
    if not op:
        raise ValueError(f"Operation spec missing 'op': {op_spec!r}")

    target_id = op_spec.get("target")
    target_el = _find_element(project, target_id) if target_id else None

    if op == "taper":
        el = target_el or _build_base_element(op_spec, default_closed=True)
        el["closed"] = True
        if "fill" not in el and "stroke" in el:
            el["fill"] = el.pop("stroke")
        el.pop("stroke", None)
        el.pop("stroke_width", None)
        b = _element_bounds(el, 0.0)
        pts = op_spec.get("points") or el.get("points")
        el["points"] = taper(
            pts,
            start_width=op_spec.get("start_width"),
            end_width=op_spec.get("end_width"),
            width=float(op_spec.get("width_px", op_spec.get("stroke_width", 20.0))),
            start_length=float(op_spec.get("start_length", 0.0)),
            end_length=float(op_spec.get("end_length", 0.0)),
            start_ease=float(op_spec.get("start_ease", 0.0)),
            end_ease=float(op_spec.get("end_ease", 0.0)),
            wave_amount=float(op_spec.get("wave_amount", 0.0)),
            wave_length=float(op_spec.get("wave_length", 0.0)),
            wave_phase=float(op_spec.get("wave_phase", 0.0)),
            cap=str(op_spec.get("cap", "butt")),
            closed=bool(op_spec.get("input_closed", False)),
            samples=op_spec.get("samples"),
            bounds=b,
        )
        if target_el is None:
            track = _find_or_create_track(project, op_spec.get("track", "paths"), int(op_spec.get("layer", 10)))
            track["elements"].append(el)

    elif op == "boolean":
        el = target_el or _build_base_element(op_spec, default_closed=True)
        el["closed"] = True
        sw = float(el.get("stroke_width", 0.0)) if "stroke" in el else 0.0
        b = _element_bounds(el, sw, float(el.get("stroke_miter_limit", 4.0)))
        mode = str(op_spec.get("mode", "union"))
        contours = boolean_contours(op_spec["paths"], op=mode, bounds=b)
        if not contours:
            raise ValueError(f"Boolean operation {mode!r} produced an empty contour")
        if op_spec.get("holes_as_mask", False) and len(contours) > 1:
            el["points"] = contours[0]
            effects = list(el.get("effects", []))
            for hole in contours[1:]:
                effects.append(
                    {
                        "name": "mask",
                        "shape": "path",
                        "points": hole,
                        "invert": True,
                    }
                )
            el["effects"] = effects
        else:
            el["points"] = boolean(op_spec["paths"], op=mode, bounds=b)
        if target_el is None:
            track = _find_or_create_track(project, op_spec.get("track", "paths"), int(op_spec.get("layer", 10)))
            track["elements"].append(el)

    elif op == "offset":
        el = target_el or _build_base_element(op_spec, default_closed=True)
        closed = bool(op_spec.get("closed", el.get("closed", True)))
        el["closed"] = closed
        sw = float(el.get("stroke_width", 0.0)) if "stroke" in el else 0.0
        b = _element_bounds(el, sw, float(el.get("stroke_miter_limit", 4.0)))
        pts = op_spec.get("points") or el.get("points")
        el["points"] = offset(
            pts,
            float(op_spec.get("distance", 10.0)),
            miter_limit=float(op_spec.get("miter_limit", 4.0)),
            line_join=str(op_spec.get("line_join", "miter")),
            closed=closed,
            bounds=b,
        )
        if target_el is None:
            track = _find_or_create_track(project, op_spec.get("track", "paths"), int(op_spec.get("layer", 10)))
            track["elements"].append(el)

    elif op == "pucker_bloat":
        el = target_el or _build_base_element(op_spec, default_closed=True)
        closed = bool(op_spec.get("closed", el.get("closed", True)))
        el["closed"] = closed
        sw = float(el.get("stroke_width", 0.0)) if "stroke" in el else 0.0
        b = _element_bounds(el, sw, float(el.get("stroke_miter_limit", 4.0)))
        pts = op_spec.get("points") or el.get("points")
        center = tuple(op_spec["center"]) if "center" in op_spec and op_spec["center"] is not None else None
        el["points"] = pucker_bloat(
            pts,
            float(op_spec.get("amount", 30.0)),
            center=center,  # type: ignore[arg-type]
            closed=closed,
            bounds=b,
        )
        if target_el is None:
            track = _find_or_create_track(project, op_spec.get("track", "paths"), int(op_spec.get("layer", 10)))
            track["elements"].append(el)

    elif op == "twist":
        el = target_el or _build_base_element(op_spec, default_closed=True)
        closed = bool(op_spec.get("closed", el.get("closed", True)))
        el["closed"] = closed
        sw = float(el.get("stroke_width", 0.0)) if "stroke" in el else 0.0
        b = _element_bounds(el, sw, float(el.get("stroke_miter_limit", 4.0)))
        pts = op_spec.get("points") or el.get("points")
        center = tuple(op_spec["center"]) if "center" in op_spec and op_spec["center"] is not None else None
        el["points"] = twist(
            pts,
            float(op_spec.get("angle", 90.0)),
            center=center,  # type: ignore[arg-type]
            radius=float(op_spec["radius"]) if "radius" in op_spec and op_spec["radius"] is not None else None,
            closed=closed,
            bounds=b,
        )
        if target_el is None:
            track = _find_or_create_track(project, op_spec.get("track", "paths"), int(op_spec.get("layer", 10)))
            track["elements"].append(el)

    elif op == "zig_zag":
        el = target_el or _build_base_element(op_spec, default_closed=False)
        closed = bool(op_spec.get("closed", el.get("closed", False)))
        el["closed"] = closed
        sw = float(el.get("stroke_width", 0.0)) if "stroke" in el else 0.0
        b = _element_bounds(el, sw, float(el.get("stroke_miter_limit", 4.0)))
        pts = op_spec.get("points") or el.get("points")
        el["points"] = zig_zag(
            pts,
            ridges=int(op_spec.get("ridges", 4)),
            size=float(op_spec.get("size", 10.0)),
            smooth=bool(op_spec.get("smooth", False)),
            closed=closed,
            bounds=b,
        )
        if target_el is None:
            track = _find_or_create_track(project, op_spec.get("track", "paths"), int(op_spec.get("layer", 10)))
            track["elements"].append(el)

    elif op == "wiggle":
        el = target_el or _build_base_element(op_spec, default_closed=True)
        closed = bool(op_spec.get("closed", el.get("closed", True)))
        el["closed"] = closed
        sw = float(el.get("stroke_width", 0.0)) if "stroke" in el else 0.0
        b = _element_bounds(el, sw, float(el.get("stroke_miter_limit", 4.0)))
        pts = op_spec.get("points") or el.get("points")
        animate = bool(op_spec.get("animate", False))
        wiggle_start = int(op_spec.get("wiggle_start", 0))
        fps_int = max(1, int(project.get("fps", 30)))
        unit_ms = max(1, 1000 // math.gcd(1000, fps_int))
        el_dur = int(el["end"]) - int(el["start"])
        default_end = ((el_dur - 1) // unit_ms) * unit_ms if animate and el_dur > unit_ms else None
        wiggle_end = int(op_spec["wiggle_end"]) if "wiggle_end" in op_spec else default_end
        el["points"] = wiggle(
            pts,
            seed=int(op_spec.get("seed", 1)),
            octaves=int(op_spec.get("octaves", 1)),
            amplitude=float(op_spec.get("amplitude", 10.0)),
            frequency=float(op_spec.get("frequency", 2.0)),
            fps=fps_int,
            start=wiggle_start,
            end=wiggle_end,
            step_ms=op_spec.get("step_ms"),
            closed=closed,
            bounds=b,
        )
        if target_el is None:
            track = _find_or_create_track(project, op_spec.get("track", "paths"), int(op_spec.get("layer", 10)))
            track["elements"].append(el)

    elif op == "trim_sequential":
        items = op_spec.get("paths", [])
        schedules = trim_sequential(
            items,
            start=int(op_spec.get("trim_start_ms", 0)),
            end=int(op_spec.get("trim_end_ms", 1000)),
            ease=str(op_spec.get("ease", "linear")),
            mode=str(op_spec.get("mode", "end")),
            overlap=float(op_spec.get("overlap", 0.0)),
        )
        base_layer = int(op_spec.get("layer", 10))
        base_track_name = str(op_spec.get("track", "paths"))
        for idx, (item, sched) in enumerate(zip(items, schedules)):
            if isinstance(item, dict) and "target" in item:
                el = _find_element(project, item["target"])
                if el is None:
                    raise ValueError(f"trim_sequential target not found: {item['target']!r}")
                el["trim_start"] = sched["trim_start"]
                el["trim_end"] = sched["trim_end"]
            else:
                merged = dict(op_spec)
                if isinstance(item, dict):
                    merged.update(item)
                merged["id"] = item.get("id", f"{op_spec.get('id', 'trim_seg')}_{idx + 1}")
                el = _build_base_element(merged, default_closed=bool(merged.get("closed", False)))
                el["points"] = _extract_vertices(item)
                for v in el["points"]:
                    v["at"] = [int(round(v["at"][0])), int(round(v["at"][1]))]
                    if "in" in v:
                        v["in"] = [int(round(v["in"][0])), int(round(v["in"][1]))]
                    if "out" in v:
                        v["out"] = [int(round(v["out"][0])), int(round(v["out"][1]))]
                el["trim_start"] = sched["trim_start"]
                el["trim_end"] = sched["trim_end"]
                track_name = item.get("track", f"{base_track_name}_{idx + 1}" if len(items) > 1 else base_track_name)
                layer = int(item.get("layer", base_layer + idx))
                track = _find_or_create_track(project, track_name, layer)
                track["elements"].append(el)
    else:
        raise ValueError(f"Unknown path operation: {op!r}")


def apply_spec(project: Dict[str, Any], spec: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(project)
    ops = spec.get("ops") if "ops" in spec else [spec]
    for op_spec in ops:
        _apply_operation(out, op_spec)
    return out


def _validate_project_if_available(project: Dict[str, Any], reference_dir: Path) -> None:
    montagent_bin = os.environ.get("MONTAGENT_BIN") or shutil.which("montagent")
    if not montagent_bin:
        return
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".montagent.json",
        dir=str(reference_dir),
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp_path = Path(tmp.name)
        json.dump(project, tmp, indent=2)
        tmp.write("\n")
    try:
        subprocess.run([montagent_bin, "fmt", str(tmp_path)], check=False, capture_output=True, text=True)
        res = subprocess.run([montagent_bin, "validate", str(tmp_path)], check=False, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"montagent validate failed:\n{res.stdout}\n{res.stderr}")
        formatted = json.loads(tmp_path.read_text(encoding="utf-8"))
        project.clear()
        project.update(formatted)
    finally:
        tmp_path.unlink(missing_ok=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0 if args else 2
    if len(args) != 2:
        sys.stderr.write("Usage: paths.py <project.json> <spec.json>\n")
        return 2

    project_path = Path(args[0]).resolve()
    spec_path = Path(args[1]).resolve()
    project = json.loads(project_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    updated = apply_spec(project, spec)
    _validate_project_if_available(updated, project_path.parent)
    sys.stdout.write(json.dumps(updated, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

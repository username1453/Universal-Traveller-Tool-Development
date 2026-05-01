#!/usr/bin/env python3

"""
Traveller Starport Map Generator v2
=====================================

Generates a procedural starport town map from a Traveller UWP code.
UWP format: X#######-#
  Position 0:  Starport class (A-E, X)
  Position 1:  Size         (hex 0-F)
  Position 2:  Atmosphere   (hex 0-F)
  Position 3:  Hydrosphere  (hex 0-F)
  Position 4:  Population   (hex 0-F)
  Position 5:  Government   (hex 0-F)
  Position 6:  Law          (hex 0-F)
  Position 8:  Tech level   (hex 0-F+)
  (Position 7 is the '-')

Usage:
    python starport_generator.py A867A74-9
    python starport_generator.py C4387B6-A --seed 42 --layout organic
    python starport_generator.py B563652-8 --no-river --no-lake --output mymap.png
"""

import argparse
import json
import math
import random
from dataclasses import dataclass
from typing import List, Tuple, Optional

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
import matplotlib.patheffects as path_effects

# ─────────────────────────────────────────────────────────────────────────────
# UWP Parsing
# ─────────────────────────────────────────────────────────────────────────────

def hex_to_int(c: str) -> int:
    """Traveller uses extended hex (0-9, A-Z except I and O)."""
    c = c.upper()
    if c.isdigit():
        return int(c)
    order = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # skip I and O
    if c in order:
        return 10 + order.index(c)
    raise ValueError(f"Invalid UWP digit: {c!r}")

@dataclass
class UWP:
    starport: str
    size: int
    atmosphere: int
    hydrosphere: int
    population: int
    government: int
    law: int
    tech: int
    raw: str

    @classmethod
    def parse(cls, s: str) -> "UWP":
        s = s.strip().upper()
        if len(s) < 9 or s[7] != "-":
            raise ValueError(f"UWP must be 'X######-#' format, got: {s}")
        starport = s[0]
        if starport not in "ABCDEX":
            raise ValueError(f"Starport class must be A-E or X, got: {starport}")
        
        return cls(
            starport=starport,
            size=hex_to_int(s[1]),
            atmosphere=hex_to_int(s[2]),
            hydrosphere=hex_to_int(s[3]),
            population=hex_to_int(s[4]),
            government=hex_to_int(s[5]),
            law=hex_to_int(s[6]),
            tech=hex_to_int(s[8]),
            raw=s,
        )

# ─────────────────────────────────────────────────────────────────────────────
# Building Definitions
# ─────────────────────────────────────────────────────────────────────────────

COMMON_BUILDINGS = [
    ("Housing",        6.0),
    ("Public Space",   2.0),
    ("Restaurant",     1.5),
    ("Tavern",         1.0),
    ("Startown Bar",   1.0),
    ("Club",           0.8),
    ("Lodging",        1.2),
    ("Grocery",        1.2),
    ("General Store",  1.0),
    ("Clothing Shop",  0.8),
    ("Entertainment",  0.8),
    ("Mechanic",       0.7),
    ("Vehicle Lot",    0.5),
    ("Broker",         0.6),
    ("Recruiter",      0.4),
    ("Hospital",       0.4),
    ("Archive",        0.3),
]

# Shape assigned to each building type
BUILDING_SHAPES = {
    "Housing":            "rectangle",
    "Public Space":       "square",
    "Restaurant":         "circle",
    "Tavern":             "rhombus",
    "Startown Bar":       "rhombus",
    "Club":               "hexagon",
    "Lodging":            "rectangle",
    "Grocery":            "square",
    "General Store":      "square",
    "Clothing Shop":      "oval",
    "Entertainment":      "octagon",
    "Mechanic":           "rectangle",
    "Vehicle Lot":        "rectangle",
    "Broker":             "triangle",
    "Recruiter":          "triangle",
    "Hospital":           "octagon",
    "Archive":            "hexagon",
    # Special / conditional
    "Criminal Den":       "triangle",
    "Weapons Shop":       "rhombus",
    "Cybernetics Clinic": "hexagon",
    "Police Station":     "octagon",
    "Black Market":       "triangle",
    "Mercenary Office":   "rhombus",
    "Government Office":  "octagon",
    "Megacorp Office":    "hexagon",
    "Bank":               "octagon",
}

# These building types are never labeled
NO_LABEL = {"Housing"}
STARPORT_SHAPES = ["circle", "hexagon", "octagon"]

COLORS = {
    "ground":   "#b8c98a",
    "water":    "#6a9fb8",
    "road":     "#3d3d3d",
    "building": "#cd5c5c",
    "special":  "#a04848",
    "starport": "#8b7355",
    "text":     "#000000",
    "halo":     "#ffffff",
}

# ─────────────────────────────────────────────────────────────────────────────
# Population-based city bounds
# ─────────────────────────────────────────────────────────────────────────────

def city_bounds(
    pop: int,
    full_bounds: Tuple[float, float, float, float],
) -> Tuple[float, float, float, float]:
    """
    Return a centred sub-region of full_bounds scaled by population.
    Pop 0 → 10%, Pop 1 → 15%, Pop 2 → 20%, …, Pop 9+ → 100%.
    The starport area always gets at least 30% so class-A ports fit at pop 0.
    """
    xmin, ymin, xmax, ymax = full_bounds
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    w, h   = xmax - xmin, ymax - ymin
    
    # fraction of full bounding box used for city activity
    frac = max(0.10, min(1.0, 0.10 + pop * 0.09))   # 10 % at pop=0 … 91 % at pop=9, cap at 100 %
    hw, hh = w * frac / 2, h * frac / 2
    
    return (cx - hw, cy - hh, cx + hw, cy + hh)

# ─────────────────────────────────────────────────────────────────────────────
# Shape polygon factory
# ─────────────────────────────────────────────────────────────────────────────

def make_shape_polygon(
    shape: str, cx: float, cy: float, width: float, height: float, angle: float
) -> List[Tuple[float, float]]:
    """Return a list of (x,y) vertices for the given shape, rotated by angle degrees."""
    ca = math.cos(math.radians(angle))
    sa = math.sin(math.radians(angle))

    def rot(lx: float, ly: float) -> Tuple[float, float]:
        return (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca)

    r = (width + height) / 4   # effective radius for circular/polygonal shapes
    w2, h2 = width / 2, height / 2
    
    if shape == "circle":
        n = 32
        return [rot(r * math.cos(2 * math.pi * i / n),
                    r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    elif shape == "square":
        s = min(w2, h2)
        return [rot(lx, ly) for lx, ly in [(-s, -s), (s, -s), (s, s), (-s, s)]]
    elif shape == "rectangle":
        return [rot(lx, ly) for lx, ly in [(-w2,-h2),(w2,-h2),(w2,h2),(-w2,h2)]]
    elif shape == "triangle":
        return [rot(lx, ly) for lx, ly in [(0, h2), (-w2, -h2), (w2, -h2)]]
    elif shape == "oval":
        n = 24
        return [rot(w2 * math.cos(2 * math.pi * i / n),
                    h2 * math.sin(2 * math.pi * i / n)) for i in range(n)]
    elif shape == "rhombus":
        return [rot(lx, ly) for lx, ly in [(0,-h2),(w2,0),(0,h2),(-w2,0)]]
    elif shape == "hexagon":
        return [rot(r * math.cos(math.pi / 2 + 2 * math.pi * i / 6),
                    r * math.sin(math.pi / 2 + 2 * math.pi * i / 6)) for i in range(6)]
    elif shape == "octagon":
        return [rot(r * math.cos(2 * math.pi * i / 8),
                    r * math.sin(2 * math.pi * i / 8)) for i in range(8)]
    else:
        return [rot(lx, ly) for lx, ly in [(-w2,-h2),(w2,-h2),(w2,h2),(-w2,h2)]]

# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Building:
    name: str
    x: float
    y: float
    width: float
    height: float
    angle: float = 0.0
    kind: str = "common"
    label: Optional[str] = None
    shape: str = "rectangle"

    def polygon(self) -> List[Tuple[float, float]]:
        return make_shape_polygon(self.shape, self.x, self.y,
                                  self.width, self.height, self.angle)

    def bbox(self) -> Tuple[float, float, float, float]:
        pts = self.polygon()
        xs, ys = zip(*pts)
        return min(xs), min(ys), max(xs), max(ys)

    def overlaps(self, other: "Building", pad: float = 5.0) -> bool:
        a = self.bbox()
        b = other.bbox()
        return not (a[2] + pad < b[0] or b[2] + pad < a[0]
                    or a[3] + pad < b[1] or b[3] + pad < a[1])

@dataclass
class Road:
    points: List[Tuple[float, float]]
    width: float = 6.0

@dataclass
class WaterFeature:
    kind: str                           # "river" or "lake"
    points: List[Tuple[float, float]]
    width: float = 14.0                 # used for rivers

# ─────────────────────────────────────────────────────────────────────────────
# Geometry helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pt_seg_dist(px: float, py: float,
                 x1: float, y1: float,
                 x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    lsq = dx * dx + dy * dy
    if lsq == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / lsq))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

def _point_in_polygon(x: float, y: float, poly: List[Tuple[float, float]]) -> bool:
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

def _point_in_any_water(x: float, y: float, water: List[WaterFeature]) -> bool:
    for wf in water:
        if wf.kind == "lake":
            if _point_in_polygon(x, y, wf.points):
                return True
        else:  # river
            for i in range(len(wf.points) - 1):
                if _pt_seg_dist(x, y, *wf.points[i], *wf.points[i + 1]) < wf.width / 2 + 8:
                    return True
    return False

def _building_in_water(b: Building, water: List[WaterFeature]) -> bool:
    if _point_in_any_water(b.x, b.y, water):
        return True
    for px, py in b.polygon():
        if _point_in_any_water(px, py, water):
            return True
    return False

def _road_crosses_lake(pts: List[Tuple[float, float]],
                       lake_poly: List[Tuple[float, float]],
                       checks: int = 10) -> bool:
    for i in range(len(pts) - 1):
        p1, p2 = pts[i], pts[i + 1]
        for k in range(checks + 1):
            t = k / checks
            x = p1[0] + t * (p2[0] - p1[0])
            y = p1[1] + t * (p2[1] - p1[1])
            if _point_in_polygon(x, y, lake_poly):
                return True
    return False

def _road_too_parallel_close(
    new_pts: List[Tuple[float, float]],
    existing: List[Road],
    min_buf: float = 30.0,
    n_samples: int = 7,
) -> bool:
    if not existing:
        return False
    n = len(new_pts)
    close_count = 0
    for k in range(n_samples):
        t = (k + 0.5) / n_samples
        target = t * (n - 1)
        idx = min(int(target), n - 2)
        frac = target - idx
        px = new_pts[idx][0] + frac * (new_pts[idx + 1][0] - new_pts[idx][0])
        py = new_pts[idx][1] + frac * (new_pts[idx + 1][1] - new_pts[idx][1])
        md = float("inf")
        for r in existing:
            for j in range(len(r.points) - 1):
                d = _pt_seg_dist(px, py, *r.points[j], *r.points[j + 1])
                if d < md:
                    md = d
        if md < min_buf:
            close_count += 1
    return close_count > n_samples // 2

def _curved_line(
    p1: Tuple[float, float], p2: Tuple[float, float],
    rng: random.Random, wobble: float = 12.0, segments: int = 12,
) -> List[Tuple[float, float]]:
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1:
        return [p1, p2]
    nx, ny = -dy / length, dx / length
    
    actual_wobble = min(wobble, length * 0.25)
    off = rng.uniform(-actual_wobble, actual_wobble)
    
    pts = []
    for i in range(segments + 1):
        t = i / segments
        bx = x1 + dx * t
        by = y1 + dy * t
        curve = math.sin(math.pi * t) * off
        pts.append((bx + nx * curve, by + ny * curve))
    return pts

def _subdivide_road(road: Road, max_len: float = 40.0) -> Road:
    pts = road.points
    new_pts = [pts[0]]
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        seg_len = math.hypot(x2 - x1, y2 - y1)
        n = max(1, math.ceil(seg_len / max_len))
        for k in range(1, n + 1):
            t = k / n
            new_pts.append((x1 + t * (x2 - x1), y1 + t * (y2 - y1)))
    return Road(new_pts, road.width)

# ─────────────────────────────────────────────────────────────────────────────
# Road / building overlap helpers
# ─────────────────────────────────────────────────────────────────────────────

def _building_on_road(b: Building, roads: List[Road], clearance: float = 4.0) -> bool:
    radius = math.hypot(b.width, b.height) / 2.0
    effective_radius = radius * 0.8
    for road in roads:
        half_w = road.width / 2 + clearance
        for i in range(len(road.points) - 1):
            dist = _pt_seg_dist(b.x, b.y, *road.points[i], *road.points[i + 1])
            if dist < (effective_radius + half_w):
                return True
    return False

# ─────────────────────────────────────────────────────────────────────────────
# River-crossing angle & culling helpers
# ─────────────────────────────────────────────────────────────────────────────

def _lines_intersect(p1: Tuple[float, float], p2: Tuple[float, float],
                     p3: Tuple[float, float], p4: Tuple[float, float]) -> bool:
    def ccw(A, B, C):
        return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)

def _road_crosses_any_river(road: Road, rivers: List[WaterFeature]) -> bool:
    for rv in rivers:
        for i in range(len(road.points) - 1):
            for j in range(len(rv.points) - 1):
                if _lines_intersect(road.points[i], road.points[i+1],
                                    rv.points[j], rv.points[j+1]):
                    return True
    return False

def _point_on_any_water(pt: Tuple[float, float], water: List[WaterFeature]) -> bool:
    x, y = pt
    for wf in water:
        if wf.kind == "lake":
            if _point_in_polygon(x, y, wf.points):
                return True
        else:
            for i in range(len(wf.points) - 1):
                if _pt_seg_dist(x, y, *wf.points[i], *wf.points[i+1]) < wf.width / 2 + 4:
                    return True
    return False

def _trim_road_endpoints(road: Road, water: List[WaterFeature]) -> Optional[Road]:
    pts = list(road.points)
    while len(pts) >= 2 and _point_on_any_water(pts[0], water):
        pts.pop(0)
    while len(pts) >= 2 and _point_on_any_water(pts[-1], water):
        pts.pop()
    if len(pts) < 2:
        return None
    if _point_on_any_water(pts[0], water) or _point_on_any_water(pts[-1], water):
        return None
    return Road(pts, road.width)

def _clip_road_at_polygons(road: Road, polys: List[List[Tuple[float, float]]]) -> List[Road]:
    segments: List[Road] = []
    current: List[Tuple[float, float]] = []
    for pt in road.points:
        inside = any(_point_in_polygon(pt[0], pt[1], poly) for poly in polys)
        if inside:
            if len(current) >= 2:
                segments.append(Road(list(current), road.width))
            current = []
        else:
            current.append(pt)
    if len(current) >= 2:
        segments.append(Road(list(current), road.width))
    return [s for s in segments if
            sum(math.hypot(s.points[k+1][0]-s.points[k][0],
                           s.points[k+1][1]-s.points[k][1])
                for k in range(len(s.points)-1)) > 20]

def _clip_road_at_water(road: Road, water: List[WaterFeature]) -> List[Road]:
    """
    Split a road wherever it crosses over water features.
    Samples dynamically along segments to prevent jumping entirely over thin rivers.
    """
    segments: List[Road] = []
    current: List[Tuple[float, float]] = []
    
    pts = road.points
    for i in range(len(pts) - 1):
        p1 = pts[i]
        p2 = pts[i+1]
        seg_len = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
        steps = max(2, int(math.ceil(seg_len / 4.0)))
        
        for k in range(steps):
            t = k / steps
            if i > 0 and k == 0:
                continue 
            x = p1[0] + t * (p2[0] - p1[0])
            y = p1[1] + t * (p2[1] - p1[1])
            
            if _point_on_any_water((x, y), water):
                if len(current) >= 2:
                    segments.append(Road(list(current), road.width))
                current = []
            else:
                current.append((x, y))
                
    last_pt = pts[-1]
    if not _point_on_any_water(last_pt, water):
        current.append(last_pt)
        
    if len(current) >= 2:
        segments.append(Road(list(current), road.width))
        
    valid_segments = []
    for s in segments:
        length = sum(math.hypot(s.points[k+1][0]-s.points[k][0], 
                                s.points[k+1][1]-s.points[k][1]) 
                     for k in range(len(s.points)-1))
        if length > 20:
            valid_segments.append(s)
            
    return valid_segments

def _cull_water_roads(
    roads: List[Road],
    rivers: List[WaterFeature],
    lake_polys: List[List[Tuple[float, float]]],
    max_river_crossings: Optional[int] = None,
    water_all: Optional[List[WaterFeature]] = None,
) -> List[Road]:
    """
    Lakes / starport clearance: CLIP roads.
    Rivers: CLIP roads crossing at too shallow an angle.
    If max_river_crossings is not None, enforce that cap by CLIPPING excess roads.
    """
    # --- Clip at lake/starport polygons ---
    if lake_polys:
        clipped: List[Road] = []
        for r in roads:
            clipped.extend(_clip_road_at_polygons(r, lake_polys))
        roads = clipped

    # --- River angle cull ---
    if rivers:
        good_roads = []
        for r in roads:
            ok = True
            for rv in rivers:
                for i in range(len(r.points) - 1):
                    for j in range(len(rv.points) - 1):
                        if _lines_intersect(r.points[i], r.points[i+1],
                                            rv.points[j], rv.points[j+1]):
                            road_dx = r.points[i+1][0] - r.points[i][0]
                            road_dy = r.points[i+1][1] - r.points[i][1]
                            riv_dx  = rv.points[j+1][0] - rv.points[j][0]
                            riv_dy  = rv.points[j+1][1] - rv.points[j][1]
                            rl  = math.hypot(road_dx, road_dy)
                            rvl = math.hypot(riv_dx,  riv_dy)
                            if rl > 0 and rvl > 0:
                                dot = abs(road_dx*riv_dx + road_dy*riv_dy) / (rl*rvl)
                                if math.degrees(math.acos(min(1.0, dot))) < 50.0:
                                    ok = False
            if ok:
                good_roads.append(r)
            else:
                # Clip out the river section rather than deleting the entire road
                good_roads.extend(_clip_road_at_water(r, rivers))
        roads = good_roads

    # --- Cap total river crossings ---
    if max_river_crossings is not None and rivers:
        crossing_roads = []
        non_crossing_roads = []
        for r in roads:
            if _road_crosses_any_river(r, rivers):
                crossing_roads.append(r)
            else:
                non_crossing_roads.append(r)
        
        kept_crossing = crossing_roads[:max_river_crossings]
        
        # Clip the excess instead of destroying them completely
        clipped_excess = []
        for r in crossing_roads[max_river_crossings:]:
            clipped_excess.extend(_clip_road_at_water(r, rivers))
            
        roads = non_crossing_roads + kept_crossing + clipped_excess

    # --- Trim endpoints that land on water ---
    if water_all:
        trimmed = []
        for r in roads:
            t = _trim_road_endpoints(r, water_all)
            if t is not None:
                trimmed.append(t)
        roads = trimmed

    return roads

# ─────────────────────────────────────────────────────────────────────────────
# Road generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_roads(
    layout: str, bounds: Tuple[float, float, float, float], pop: int, rng: random.Random,
    water: Optional[List[WaterFeature]] = None, starport_building: Optional[Building] = None,
) -> List[Road]:
    if pop == 0 and starport_building is None:
        return []

    if water is None:
        water = []
    
    lake_polys = [wf.points for wf in water if wf.kind == "lake"]
    rivers     = [wf for wf in water if wf.kind == "river"]

    if starport_building is not None:
        sp_cx, sp_cy = starport_building.x, starport_building.y
        sp_clearance = []
        for px, py in starport_building.polygon():
            dx, dy = px - sp_cx, py - sp_cy
            sp_clearance.append((sp_cx + dx * 1.5, sp_cy + dy * 1.5))
        lake_polys.append(sp_clearance)

    max_crossings = None if layout == "radial" else 3

    if layout == "grid":
        roads = _grid_roads(bounds, pop, rng)
        roads = _cull_water_roads(roads, rivers, lake_polys,
                                  max_river_crossings=max_crossings,
                                  water_all=water)
    elif layout == "radial":
        roads = _radial_roads(bounds, pop, rng, starport_building)
        roads = _cull_water_roads(roads, rivers, lake_polys,
                                  max_river_crossings=None,
                                  water_all=water)
    else:
        roads = _organic_roads(bounds, pop, rng, starport_building, rivers, lake_polys)
        roads = _cull_water_roads(roads, rivers, lake_polys,
                                  max_river_crossings=max_crossings,
                                  water_all=water)

    if starport_building is not None:
        roads = _ensure_starport_road(starport_building, roads, bounds, rng)

    return roads

def _grid_roads(bounds, pop, rng):
    xmin, ymin, xmax, ymax = bounds
    spacing = max(70, 170 - pop * 12) + rng.uniform(-8, 8)
    angle = rng.uniform(-10, 10)
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    ca = math.cos(math.radians(angle))
    sa = math.sin(math.radians(angle))

    def rotate(x, y):
        dx, dy = x - cx, y - cy
        return (cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)

    roads = []
    y = ymin - 60
    while y < ymax + 60:
        roads.append(_subdivide_road(Road(
            [rotate(xmin - 150, y), rotate(xmax + 150, y)],
            width=rng.choice([5, 6, 7]))))
        y += spacing
    x = xmin - 60
    while x < xmax + 60:
        roads.append(_subdivide_road(Road(
            [rotate(x, ymin - 150), rotate(x, ymax + 150)],
            width=rng.choice([5, 6, 7]))))
        x += spacing
    return roads

def _radial_roads(bounds, pop, rng, starport_building=None):
    xmin, ymin, xmax, ymax = bounds
    if starport_building is not None:
        cx, cy = starport_building.x, starport_building.y
        sp_r = max(starport_building.width, starport_building.height) / 2 * 1.2
    else:
        cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
        sp_r = 0.0

    max_r = max(xmax - xmin, ymax - ymin) * 0.65
    roads = []
    n_spokes = max(6, min(18, 5 + pop))
    n_rings  = max(4, min(10, 3 + pop // 2))
    base = rng.uniform(0, 2 * math.pi)

    for i in range(n_spokes):
        a = base + 2 * math.pi * i / n_spokes
        p1 = (cx + sp_r * math.cos(a), cy + sp_r * math.sin(a))
        p2 = (cx + max_r * math.cos(a), cy + max_r * math.sin(a))
        roads.append(_subdivide_road(Road([p1, p2], width=7)))

    for i in range(1, n_rings + 1):
        r = max_r * i / (n_rings + 0.5)
        n_pts = max(24, int(2 * math.pi * r / 25))
        pts = [(cx + r * math.cos(2 * math.pi * j / n_pts),
                cy + r * math.sin(2 * math.pi * j / n_pts)) for j in range(n_pts + 1)]
        roads.append(Road(pts, width=5))
    return roads

def _organic_road_pts(
    p1: Tuple[float, float], p2: Tuple[float, float],
    rng: random.Random, wavy: bool = False, segments: int = 12,
) -> List[Tuple[float, float]]:
    if not wavy:
        return [p1, p2]
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1:
        return [p1, p2]
    nx, ny = -dy / length, dx / length
    amp = min(rng.uniform(0.04, 0.09) * length, 18.0) * rng.choice([-1, 1])
    return [
        (x1 + dx * (i / segments) + nx * math.sin(math.pi * i / segments) * amp,
         y1 + dy * (i / segments) + ny * math.sin(math.pi * i / segments) * amp)
        for i in range(segments + 1)
    ]

def _road_parallel_too_close(
    new_pts: List[Tuple[float, float]],
    existing: List[Road],
    road_width: float,
) -> bool:
    if not existing or len(new_pts) < 2:
        return False
    bx1, by1 = new_pts[0]
    bx2, by2 = new_pts[-1]
    n_samples = 7
    close_count = 0
    for k in range(n_samples):
        t = (k + 0.5) / n_samples
        px = bx1 + (bx2 - bx1) * t
        py = by1 + (by2 - by1) * t
        min_d = float("inf")
        for r in existing:
            for si in range(len(r.points) - 1):
                d = _pt_seg_dist(px, py, *r.points[si], *r.points[si + 1])
                if d < min_d:
                    min_d = d
        if min_d < road_width:
            close_count += 1
    return close_count > n_samples // 2

def _organic_roads(bounds, pop, rng, starport_building=None, rivers=None, lake_polys=None):
    import time as _time
    _t0 = _time.time()
    _last_tick = [_t0]

    def _tick(label=""):
        now = _time.time()
        if now - _last_tick[0] >= 15:
            print(f"  [organic {int(now - _t0)}s] {label}", flush=True)
            _last_tick[0] = now

    xmin, ymin, xmax, ymax = bounds
    w, h = xmax - xmin, ymax - ymin
    MIN_BUF = 28
    
    cols = max(6, min(10, round((2 + pop // 2) * 1.15)))
    rows = max(6, min(10, round((2 + pop // 2) * 1.15)))
    nodes: List[Tuple[float, float]] = []
    
    if starport_building is not None:
        nodes.append((starport_building.x, starport_building.y))
        
    for i in range(rows):
        for j in range(cols):
            x = xmin + (j + 0.5 + rng.uniform(-0.3, 0.3)) * w / cols
            y = ymin + (i + 0.5 + rng.uniform(-0.3, 0.3)) * h / rows
            nodes.append((x, y))
            
    margin = 0.07
    n_perimeter = max(4, round(pop * 1.33))
    
    for _ in range(n_perimeter):
        side = rng.choice(["n", "s", "e", "w"])
        if side == "n":
            nodes.append((rng.uniform(xmin + w * margin, xmax - w * margin),
                          ymax - h * margin + rng.uniform(-h * 0.04, 0)))
        elif side == "s":
            nodes.append((rng.uniform(xmin + w * margin, xmax - w * margin),
                          ymin + h * margin + rng.uniform(0, h * 0.04)))
        elif side == "e":
            nodes.append((xmax - w * margin + rng.uniform(-w * 0.04, 0),
                          rng.uniform(ymin + h * margin, ymax - h * margin)))
        else:
            nodes.append((xmin + w * margin + rng.uniform(0, w * 0.04),
                          rng.uniform(ymin + h * margin, ymax - h * margin)))

    roads: List[Road] = []
    added: set = set()
    parent = list(range(len(nodes)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    WAVE_PROB = rng.uniform(0.20, 0.40)

    def try_road(i: int, j: int, force: bool = False) -> bool:
        _tick("building edges")
        key = (min(i, j), max(i, j))
        if key in added:
            return False
        x1, y1 = nodes[i]
        x2, y2 = nodes[j]
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist > w * 0.52 or dist < 18:
            return False
            
        crosses_river = False
        if rivers and not force:
            for rv in rivers:
                for k in range(len(rv.points) - 1):
                    if _lines_intersect(nodes[i], nodes[j], rv.points[k], rv.points[k + 1]):
                        crosses_river = True
                        rdx, rdy = x2 - x1, y2 - y1
                        vdx = rv.points[k + 1][0] - rv.points[k][0]
                        vdy = rv.points[k + 1][1] - rv.points[k][1]
                        rl  = math.hypot(rdx, rdy)
                        rvl = math.hypot(vdx, vdy)
                        if rl > 0 and rvl > 0:
                            dot = abs(rdx * vdx + rdy * vdy) / (rl * rvl)
                            if math.degrees(math.acos(min(1.0, dot))) < 50:
                                return False
                        break
                        
        if lake_polys and not force:
            for lp in lake_polys:
                if _road_crosses_lake([nodes[i], nodes[j]], lp):
                    return False
                    
        road_w = rng.choice([5, 6, 7])
        wavy = (not crosses_river) and (not force) and (rng.random() < WAVE_PROB)
        pts = _organic_road_pts((x1, y1), (x2, y2), rng, wavy=wavy, segments=12)
        
        if not force and _road_parallel_too_close(pts, roads, road_width=road_w + 4):
            return False
            
        added.add(key)
        roads.append(_subdivide_road(Road(pts, width=road_w)))
        union(i, j)
        return True

    for i in range(len(nodes)):
        _tick("phase 1")
        dists = sorted(
            [(math.hypot(nodes[j][0] - nodes[i][0],
                         nodes[j][1] - nodes[i][1]), j)
             for j in range(len(nodes)) if j != i]
        )
        for _, j in dists[:3]:
            try_road(i, j)

    for _ in range(max(3, round(pop * 1.33))):
        _tick("phase 2")
        i, j = rng.sample(range(len(nodes)), 2)
        try_road(i, j)

    root_node = 0
    max_iter = len(nodes) * 3
    for _itr in range(max_iter):
        _tick("phase 3 repair")
        root_comp = find(root_node)
        orphan = None
        for i in range(len(nodes)):
            if find(i) != root_comp:
                orphan = i
                break
        if orphan is None:
            break
            
        best_dist, best_root_node = float("inf"), root_node
        for i in range(len(nodes)):
            if find(i) == root_comp:
                d = math.hypot(nodes[i][0] - nodes[orphan][0],
                               nodes[i][1] - nodes[orphan][1])
                if d < best_dist:
                    best_dist, best_root_node = d, i
                    
        key = (min(best_root_node, orphan), max(best_root_node, orphan))
        if key not in added:
            x1, y1 = nodes[best_root_node]
            x2, y2 = nodes[orphan]
            pts = _organic_road_pts((x1, y1), (x2, y2), rng, wavy=False)
            roads.append(_subdivide_road(Road(pts, width=5)))
            added.add(key)
        union(best_root_node, orphan)

    return roads

def _ensure_starport_road(
    sp: Building, roads: List[Road], bounds: Tuple[float, float, float, float],
    rng: random.Random, connect_dist: float = 300.0,
) -> List[Road]:
    sx, sy = sp.x, sp.y
    half_w = sp.width / 2
    half_h = sp.height / 2
    all_pts = []
    
    for road in roads:
        all_pts.extend(road.points)
        
    if not all_pts:
        angle = rng.uniform(0, 2 * math.pi)
        edge_x = sx + (half_w + 10) * math.cos(angle)
        edge_y = sy + (half_h + 10) * math.sin(angle)
        far_x = sx + (half_w + 80) * math.cos(angle)
        far_y = sy + (half_h + 80) * math.sin(angle)
        roads.append(_subdivide_road(Road([(edge_x, edge_y), (far_x, far_y)], width=7)))
        return roads

    all_pts.sort(key=lambda pt: math.hypot(pt[0] - sx, pt[1] - sy))
    n_connections = rng.randint(2, 5)
    chosen_pts = []
    
    for pt in all_pts:
        if all(math.hypot(pt[0] - cp[0], pt[1] - cp[1]) > 60 for cp in chosen_pts):
            chosen_pts.append(pt)
        if len(chosen_pts) == n_connections:
            break
            
    if not chosen_pts:
        chosen_pts = [all_pts[0]]
        
    for pt in chosen_pts:
        dx = sx - pt[0]
        dy = sy - pt[1]
        dist = math.hypot(dx, dy)
        if dist > 0:
            ux, uy = dx / dist, dy / dist
            end_x = sx - ux * (half_w * 0.4)
            end_y = sy - uy * (half_h * 0.4)
            roads.append(_subdivide_road(
                Road([pt, (end_x, end_y)], width=7)
            ))
    return roads

# ─────────────────────────────────────────────────────────────────────────────
# Water generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_water(uwp: UWP, bounds, rng) -> List[WaterFeature]:
    water = []
    hydro = uwp.hydrosphere
    if hydro == 0:
        return water
        
    xmin, ymin, xmax, ymax = bounds
    w, h = xmax - xmin, ymax - ymin

    if hydro >= 2:
        side = rng.choice(["h", "v"])
        if side == "h":
            y0 = rng.uniform(ymin + h * 0.2, ymax - h * 0.2)
            p1 = (xmin - 50, y0 + rng.uniform(-h * 0.05, h * 0.05))
            p2 = (xmax + 50, y0 + rng.uniform(-h * 0.08, h * 0.08))
        else:
            x0 = rng.uniform(xmin + w * 0.2, xmax - w * 0.2)
            p1 = (x0 + rng.uniform(-w * 0.05, w * 0.05), ymin - 50)
            p2 = (x0 + rng.uniform(-w * 0.08, w * 0.08), ymax + 50)
        
        pts = []
        n_pts = 40
        waves = rng.uniform(1.5, 3.5)
        amp = rng.uniform(40, 90)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = math.hypot(dx, dy)
        nx, ny = -dy / length, dx / length
        for i in range(n_pts + 1):
            t = i / n_pts
            bx = p1[0] + dx * t
            by = p1[1] + dy * t
            curve = math.sin(t * math.pi * waves) * amp
            pts.append((bx + nx * curve, by + ny * curve))
            
        width = 10 + hydro * 1.5
        water.append(WaterFeature("river", pts, width=width))

    if hydro >= 7:
        edge = rng.choice(["n", "s", "e", "w"])
        if edge == "n":
            cx_l = rng.uniform(xmin + w * 0.6, xmax - w * 0.15)
            cy_l = ymax - h * 0.15
        elif edge == "s":
            cx_l = rng.uniform(xmin + w * 0.15, xmax - w * 0.6)
            cy_l = ymin + h * 0.15
        elif edge == "e":
            cx_l = xmax - w * 0.15
            cy_l = rng.uniform(ymin + h * 0.6, ymax - h * 0.15)
        else:
            cx_l = xmin + w * 0.15
            cy_l = rng.uniform(ymin + h * 0.15, ymax - h * 0.6)
            
        rx = rng.uniform(w * 0.07, w * 0.13)
        ry = rng.uniform(h * 0.07, h * 0.13)
        n_pts = 28
        pts = []
        for i in range(n_pts):
            a = 2 * math.pi * i / n_pts
            jitter = rng.uniform(0.82, 1.10)
            pts.append((cx_l + rx * math.cos(a) * jitter,
                        cy_l + ry * math.sin(a) * jitter))
        water.append(WaterFeature("lake", pts))

    return water

# ─────────────────────────────────────────────────────────────────────────────
# UWP-conditional building logic
# ─────────────────────────────────────────────────────────────────────────────

def roll_conditional_buildings(uwp: UWP, rng: random.Random) -> List[str]:
    out = []
    law, gov, tech, pop = uwp.law, uwp.government, uwp.tech, uwp.population
    if law < 10 and rng.random() * 100 >= law * 10:
        out.append("Criminal Den")
    if law <= 7:
        out.append("Weapons Shop")
    if tech >= 9 and law < 10 and gov < 13:
        out.append("Cybernetics Clinic")
    if law >= 10 or rng.random() * 100 < law * 10:
        out.append("Police Station")
    if law <= 4 or (gov >= 8 and law >= 9):
        out.append("Black Market")
    if gov == 7 or rng.random() < 0.30:
        out.append("Mercenary Office")
    if gov >= 2 and law >= 2:
        out.append("Government Office")
    if gov == 1:
        out.append("Megacorp Office")
    elif tech >= 8 and pop >= 7:
        if pop >= 8 or rng.random() < 0.50:
            out.append("Megacorp Office")
    if gov >= 1 and law >= 2 and pop >= 5 and tech >= 4:
        out.append("Bank")
    return out

def starport_size(starport: str) -> Tuple[float, float]:
    return {
        "A": (220, 150), "B": (190, 130), "C": (155, 115),
        "D": (120, 90),  "E": (160, 110), "X": (0, 0),
    }.get(starport, (0, 0))

# ─────────────────────────────────────────────────────────────────────────────
# Starport placement
# ─────────────────────────────────────────────────────────────────────────────

def _starport_near_river(x: float, y: float, sw: float, sh: float,
                          rivers: List[WaterFeature], clearance: float = 40.0) -> bool:
    radius = math.hypot(sw, sh) / 2 + clearance
    for rv in rivers:
        for i in range(len(rv.points) - 1):
            if _pt_seg_dist(x, y, *rv.points[i], *rv.points[i+1]) < radius:
                return True
    return False

def place_starport(uwp: UWP, bounds, layout: str, rng,
                   water: Optional[List[WaterFeature]] = None) -> Optional[Building]:
    if uwp.starport == "X":
        return None
    sw, sh = starport_size(uwp.starport)
    xmin, ymin, xmax, ymax = bounds
    shape = rng.choice(STARPORT_SHAPES)
    rivers = [wf for wf in water if wf.kind == "river"] if water else []
    MAX_ATTEMPTS = 20

    def _make_candidate() -> Tuple[float, float]:
        if layout == "radial":
            return (xmin + xmax) / 2, (ymin + ymax) / 2
        elif uwp.starport in ("A", "B", "E"):
            side = rng.choice(["n", "s", "e", "w"])
            m = 30
            if side == "n":
                return ((xmin + xmax) / 2 + rng.uniform(-60, 60), ymax - sh / 2 - m)
            elif side == "s":
                return ((xmin + xmax) / 2 + rng.uniform(-60, 60), ymin + sh / 2 + m)
            elif side == "e":
                return (xmax - sw / 2 - m, (ymin + ymax) / 2 + rng.uniform(-60, 60))
            else:
                return (xmin + sw / 2 + m, (ymin + ymax) / 2 + rng.uniform(-60, 60))
        else:
            cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
            return cx + rng.uniform(-50, 50), cy + rng.uniform(-50, 50)

    best_x, best_y = _make_candidate()
    best_is_clear = not _starport_near_river(best_x, best_y, sw, sh, rivers)
    
    for _ in range(MAX_ATTEMPTS - 1):
        if best_is_clear:
            break
        cx, cy = _make_candidate()
        clear = not _starport_near_river(cx, cy, sw, sh, rivers)
        if clear:
            best_x, best_y = cx, cy
            best_is_clear = True
            
    return Building(
        name="Starport", x=best_x, y=best_y, width=sw, height=sh,
        angle=0.0, kind="starport", label=f"Class {uwp.starport} Starport", shape=shape,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Building placement
# ─────────────────────────────────────────────────────────────────────────────

def _sample_roadside_points(
    roads: List[Road], bounds: Tuple[float, float, float, float], rng: random.Random, spacing: float = 14.0,
) -> List[Tuple[float, float, float, float]]:
    candidates = []
    xmin, ymin, xmax, ymax = bounds
    for road in roads:
        pts = road.points
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            seg_len = math.hypot(x2 - x1, y2 - y1)
            if seg_len < 1:
                continue
            n = max(1, int(seg_len / spacing))
            nx = -(y2 - y1) / seg_len
            ny = (x2 - x1) / seg_len
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            for j in range(n):
                t = (j + 0.5) / n
                sx = x1 + (x2 - x1) * t
                sy = y1 + (y2 - y1) * t
                for side in (1, -1):
                    off = rng.uniform(22, 34)
                    bx = sx + nx * side * off
                    by = sy + ny * side * off
                    if xmin + 5 <= bx <= xmax - 5 and ymin + 5 <= by <= ymax - 5:
                        candidates.append((bx, by, angle, off))
    rng.shuffle(candidates)
    return candidates

def place_buildings(
    uwp: UWP, bounds: Tuple[float, float, float, float], roads: List[Road],
    water: List[WaterFeature], rng: random.Random, starport_building: Optional[Building] = None,
) -> List[Building]:
    buildings: List[Building] = []
    if starport_building is not None:
        buildings.append(starport_building)
    if uwp.population == 0:
        return buildings

    n_target = max(len(COMMON_BUILDINGS) + 5, uwp.population * 17)
    unique_names   = roll_conditional_buildings(uwp, rng)
    common_names   = [name for name, _ in COMMON_BUILDINGS]
    common_weights = [w    for _, w    in COMMON_BUILDINGS]
    candidates = _sample_roadside_points(roads, bounds, rng, spacing=18.0)

    _CELL = 35.0
    _seg_buckets: dict = {}
    for _rd in roads:
        for _si in range(len(_rd.points) - 1):
            _ax, _ay = _rd.points[_si]
            _bx, _by = _rd.points[_si + 1]
            for _gx in range(int(min(_ax,_bx)//_CELL)-1, int(max(_ax,_bx)//_CELL)+2):
                for _gy in range(int(min(_ay,_by)//_CELL)-1, int(max(_ay,_by)//_CELL)+2):
                    _seg_buckets.setdefault((_gx,_gy), []).append((_ax, _ay, _bx, _by, _rd.width))

    def _on_road_fast(b: Building, clearance: float = 2.0) -> bool:
        radius = math.hypot(b.width, b.height) / 2.0 * 0.8
        gx = int(b.x // _CELL)
        gy = int(b.y // _CELL)
        threshold = radius + clearance + 5.0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for ax, ay, bx2, by, rw in _seg_buckets.get((gx+dx, gy+dy), []):
                    if _pt_seg_dist(b.x, b.y, ax, ay, bx2, by) < threshold + rw/2:
                        return True
        return False

    _BLDG_CELL = 60.0
    _bldg_buckets: dict = {}

    def _bldg_bucket_keys(b: Building):
        bx0, by0, bx1, by1 = b.bbox()
        for gx in range(int(bx0//_BLDG_CELL)-1, int(bx1//_BLDG_CELL)+2):
            for gy in range(int(by0//_BLDG_CELL)-1, int(by1//_BLDG_CELL)+2):
                yield (gx, gy)

    def _register_building(b: Building):
        for key in _bldg_bucket_keys(b):
            _bldg_buckets.setdefault(key, []).append(b)

    def _overlaps_any(b: Building, pad: float = 4.0) -> bool:
        for key in _bldg_bucket_keys(b):
            for other in _bldg_buckets.get(key, []):
                if b is not other and b.overlaps(other, pad=pad):
                    return True
        return False

    if starport_building is not None:
        _register_building(starport_building)

    _candidates_filtered = []
    _cand_near_water: List[bool] = []
    
    for _c in candidates:
        _cx, _cy, _ang, _off = _c
        if not (bounds[0]+5 <= _cx <= bounds[2]-5 and bounds[1]+5 <= _cy <= bounds[3]-5):
            continue
        if _point_in_any_water(_cx, _cy, water):
            continue
            
        _probe = Building("_", _cx, _cy, 8, 8, _ang, "common", None, "rectangle")
        if _on_road_fast(_probe, clearance=1.0):
            continue
            
        _close = False
        for _wf in water:
            if _wf.kind == "lake":
                _close = True; break
            for _k in range(len(_wf.points) - 1):
                if _pt_seg_dist(_cx, _cy, *_wf.points[_k], *_wf.points[_k+1]) < _wf.width/2 + 40:
                    _close = True; break
            if _close:
                break
                
        _candidates_filtered.append(_c)
        _cand_near_water.append(_close)

    candidates = _candidates_filtered
    _pool = list(range(len(candidates)))
    _pool_end = [len(_pool)]

    def _claim(idx_in_pool: int):
        end = _pool_end[0] - 1
        _pool[idx_in_pool] = _pool[end]
        _pool_end[0] = end

    def get_dims(name: str, kind: str) -> Tuple[float, float]:
        if kind == "special" or name in {
            "Hospital", "Archive", "Government Office", "Megacorp Office",
            "Bank", "Police Station", "Cybernetics Clinic", "Entertainment", "Club",
        }:
            return rng.uniform(26, 38), rng.uniform(20, 32)
        elif name == "Public Space":
            return rng.uniform(32, 52), rng.uniform(32, 52)
        elif name in {"Housing", "Lodging", "Mechanic", "Vehicle Lot"}:
            return rng.uniform(18, 30), rng.uniform(11, 18)
        else:
            return rng.uniform(14, 24), rng.uniform(11, 18)

    def try_place(name: str, kind: str = "common") -> bool:
        shape = BUILDING_SHAPES.get(name, "rectangle")
        bw, bh = get_dims(name, kind)
        if shape in ("circle", "hexagon", "octagon"):
            bw = bh = (bw + bh) / 2
            
        lbl = None if name in NO_LABEL else name
        pi = 0
        
        while pi < _pool_end[0]:
            idx = _pool[pi]
            cx, cy, angle, _ = candidates[idx]
            b = Building(name=name, x=cx, y=cy, width=bw, height=bh,
                         angle=angle, kind=kind, label=lbl, shape=shape)
                         
            if _building_in_water(b, water):
                _claim(pi); continue
                
            xs, ys = zip(*b.polygon())
            if (min(xs) < bounds[0] or max(xs) > bounds[2]
                    or min(ys) < bounds[1] or max(ys) > bounds[3]):
                _claim(pi); continue
                
            if _on_road_fast(b, clearance=2.0):
                pi += 1; continue
            if _overlaps_any(b, pad=4):
                pi += 1; continue
                
            buildings.append(b)
            _register_building(b)
            _claim(pi)
            return True
            
        return False

    placed = 0
    for name in unique_names:
        if try_place(name, "special"):
            placed += 1
    for name in common_names:
        if try_place(name, "common"):
            placed += 1
            
    no_progress = 0
    while placed < n_target:
        if no_progress >= max(10, _pool_end[0]):
            break
        name = rng.choices(common_names, weights=common_weights, k=1)[0]
        if try_place(name, "common"):
            placed += 1
            no_progress = 0
        else:
            no_progress += 1
            
    return buildings

# ─────────────────────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────────────────────

def _halo_text(ax, x, y, text, fontsize=7):
    t = ax.text(x, y, text, ha="center", va="center",
                fontsize=fontsize, color=COLORS["text"],
                zorder=20, family="sans-serif", weight="bold")
    t.set_path_effects([
        path_effects.Stroke(linewidth=2.2, foreground=COLORS["halo"]),
        path_effects.Normal(),
    ])
    return t

def render_map(uwp, roads, water, buildings, bounds, full_bounds, layout_name, output_path):
    xmin, ymin, xmax, ymax = full_bounds
    fig_w = 14
    aspect = (ymax - ymin) / (xmax - xmin)
    
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * aspect), dpi=120)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")

    ax.add_patch(MplPolygon(
        [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)],
        facecolor=COLORS["ground"], edgecolor="none", zorder=0))

    for wf in water:
        if wf.kind == "lake":
            ax.add_patch(MplPolygon(
                wf.points, facecolor=COLORS["water"],
                edgecolor="#4a7a90", linewidth=1.5, zorder=1, closed=True))
        else:
            xs, ys = zip(*wf.points)
            ax.plot(xs, ys, color=COLORS["water"], linewidth=wf.width,
                    solid_capstyle="round", solid_joinstyle="round", zorder=1)

    for r in roads:
        xs, ys = zip(*r.points)
        ax.plot(xs, ys, color="#1a1a1a", linewidth=r.width + 2.5,
                solid_capstyle="round", solid_joinstyle="round", zorder=2)
        ax.plot(xs, ys, color=COLORS["road"], linewidth=r.width,
                solid_capstyle="round", solid_joinstyle="round", zorder=3)

    special_queue: List[Building] = []
    common_queue:  List[Building] = []
    
    for b in buildings:
        poly = b.polygon()
        if b.kind == "starport":
            face, edge, lw = COLORS["starport"], "#5a4a36", 1.6
        elif b.kind == "special":
            face, edge, lw = COLORS["special"],  "#6a2a2a", 1.2
        else:
            face, edge, lw = COLORS["building"], "#7a3030", 0.8
            
        ax.add_patch(MplPolygon(poly, facecolor=face, edgecolor=edge,
                                linewidth=lw, zorder=5, closed=True))
                                
        if b.label and b.name not in NO_LABEL:
            if b.kind in ("starport", "special"):
                special_queue.append(b)
            else:
                common_queue.append(b)

    for b in special_queue:
        fs = 10 if b.kind == "starport" else 8
        _halo_text(ax, b.x, b.y, b.label, fontsize=fs)

    labeled_names: set = set()
    for b in common_queue:
        if b.name not in labeled_names:
            _halo_text(ax, b.x, b.y, b.label, fontsize=6)
            labeled_names.add(b.name)

    ax.set_title(f"Starport Town — UWP {uwp.raw}  ({layout_name} layout)",
                 fontsize=14, weight="bold", pad=10)
                 
    sub = (f"Starport {uwp.starport} | Size {uwp.size:X} | Atm {uwp.atmosphere:X} | "
           f"Hyd {uwp.hydrosphere:X} | Pop {uwp.population:X} | "
           f"Gov {uwp.government:X} | Law {uwp.law:X} | TL {uwp.tech:X}")
           
    ax.text(0.5, -0.04, sub, transform=ax.transAxes, ha="center", va="top",
            fontsize=9, color="#333")

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
        spine.set_linewidth(1.2)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=COLORS["ground"])
    plt.close(fig)

# ─────────────────────────────────────────────────────────────────────────────
# GeoJSON sidecar
# ─────────────────────────────────────────────────────────────────────────────

def export_geojson(uwp, roads, water, buildings, path):
    features = []
    for b in buildings:
        ring = b.polygon() + [b.polygon()[0]]
        features.append({
            "type": "Feature",
            "properties": {"name": b.name, "label": b.label, "kind": b.kind},
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })
    for r in roads:
        features.append({
            "type": "Feature",
            "properties": {"kind": "road", "width": r.width},
            "geometry": {"type": "LineString", "coordinates": list(r.points)},
        })
    for wf in water:
        if wf.kind == "lake":
            ring = wf.points + [wf.points[0]]
            features.append({
                "type": "Feature",
                "properties": {"kind": "lake"},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            })
        else:
            features.append({
                "type": "Feature",
                "properties": {"kind": "river", "width": wf.width},
                "geometry": {"type": "LineString", "coordinates": wf.points},
            })
            
    fc = {
        "type": "FeatureCollection",
        "properties": {"uwp": uwp.raw},
        "features": features,
    }
    
    with open(path, "w") as f:
        json.dump(fc, f, indent=2)

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate(
    uwp_str: str, output_path: str, seed=None, layout=None, geojson_path=None,
    size: int = 900, show_river: bool = True, show_lake: bool = True,
) -> dict:
    import time as _time
    _t0 = _time.time()
    
    def _progress(msg: str):
        print(f"  [{_time.time() - _t0:5.1f}s] {msg}", flush=True)

    uwp = UWP.parse(uwp_str)
    rng = random.Random(seed)
    full_bounds = (0, 0, size, size)
    
    if layout is None:
        layout = rng.choice(["grid", "radial", "organic"])
        
    _progress(f"layout={layout}  UWP={uwp_str}")
    bounds = city_bounds(uwp.population, full_bounds)
    water = generate_water(uwp, full_bounds, rng)
    
    if not show_river:
        water = [wf for wf in water if wf.kind != "river"]
    if not show_lake:
        water = [wf for wf in water if wf.kind != "lake"]
        
    _progress("water generated")
    starport_building = place_starport(uwp, bounds, layout, rng, water=water)
    _progress("starport placed")
    
    roads = generate_roads(layout, bounds, uwp.population, rng, water, starport_building)
    _progress(f"roads done ({len(roads)} roads)")
    
    buildings = place_buildings(uwp, bounds, roads, water, rng, starport_building)
    _progress(f"buildings placed ({len(buildings)} buildings)")
    
    render_map(uwp, roads, water, buildings, bounds, full_bounds, layout, output_path)
    _progress(f"map rendered → {output_path}")
    
    if geojson_path:
        export_geojson(uwp, roads, water, buildings, geojson_path)
        _progress(f"GeoJSON → {geojson_path}")
        
    return {
        "uwp":              uwp,
        "layout":           layout,
        "n_buildings":      len(buildings),
        "unique_buildings": [b.name for b in buildings if b.kind == "special"],
        "has_starport":     any(b.kind == "starport" for b in buildings),
    }

# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Traveller Starport Map Generator v2")
    p.add_argument("uwp", help="UWP code, e.g. A867A74-9")
    p.add_argument("--seed",    type=int, default=None)
    p.add_argument("--layout",  choices=["grid", "radial", "organic"], default=None)
    p.add_argument("--output",  default="starport_map.png")
    p.add_argument("--geojson", default=None)
    p.add_argument("--size",    type=int, default=900)
    p.add_argument("--no-river", action="store_true",
                   help="Suppress river even when hydrosphere >= 2")
    p.add_argument("--no-lake",  action="store_true",
                   help="Suppress lake even when hydrosphere >= 7")
                   
    args = p.parse_args()
    info = generate(
        args.uwp, args.output,
        seed=args.seed, layout=args.layout,
        geojson_path=args.geojson, size=args.size,
        show_river=not args.no_river,
        show_lake=not args.no_lake,
    )
    
    print(f"Generated map for UWP {info['uwp'].raw}")
    print(f"  Layout:   {info['layout']}")
    print(f"  Buildings:{info['n_buildings']}")
    print(f"  Unique:   {', '.join(info['unique_buildings']) or 'none'}")
    print(f"  Output:   {args.output}")

if __name__ == "__main__":
    main()
"""Integer grid primitives: Bresenham line, midpoint ellipse, thickness expansion."""

import math
from typing import Iterable


def thicken_points(
    points: Iterable[tuple[int, int]], thickness: int,
) -> list[tuple[int, int]]:
    """Expand each point with a square brush of *thickness* tiles.

    Returns deduplicated points sorted by (y, x).
    Thickness 1 returns the input unchanged.
    """
    pts = list(points)
    if thickness <= 1:
        return pts
    half = thickness // 2
    result: set[tuple[int, int]] = set()
    for x, y in pts:
        for dy in range(-half, -half + thickness):
            for dx in range(-half, -half + thickness):
                result.add((x + dx, y + dy))
    return sorted(result, key=lambda p: (p[1], p[0]))


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """All grid points along a line from (x0, y0) to (x1, y1), inclusive."""
    points: list[tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy

    return points


def midpoint_ellipse(cx: int, cy: int, rx: int, ry: int) -> list[tuple[int, int]]:
    """Perimeter tiles of an axis-aligned ellipse (midpoint algorithm).

    Returns an 8-connected set of grid points sorted by (y, x).
    Degenerate cases (rx==0 or ry==0) produce a straight line.
    """
    if rx <= 0 and ry <= 0:
        return [(cx, cy)]
    if rx <= 0:
        return [(cx, cy + y) for y in range(-ry, ry + 1)]
    if ry <= 0:
        return [(cx + x, cy) for x in range(-rx, rx + 1)]

    points: set[tuple[int, int]] = set()

    def _plot4(x: int, y: int) -> None:
        points.add((cx + x, cy + y))
        points.add((cx - x, cy + y))
        points.add((cx + x, cy - y))
        points.add((cx - x, cy - y))

    x = 0
    y = ry
    rx2 = rx * rx
    ry2 = ry * ry
    two_rx2 = 2 * rx2
    two_ry2 = 2 * ry2
    px = 0
    py = two_rx2 * y

    _plot4(x, y)

    # Region 1: slope magnitude < 1 (top arc)
    d1 = ry2 - rx2 * ry + rx2 / 4.0
    while px < py:
        x += 1
        px += two_ry2
        if d1 < 0:
            d1 += ry2 + px
        else:
            y -= 1
            py -= two_rx2
            d1 += ry2 + px - py
        _plot4(x, y)

    # Region 2: slope magnitude >= 1 (side arc)
    d2 = ry2 * (x + 0.5) ** 2 + rx2 * (y - 1) ** 2 - rx2 * ry2
    while y > 0:
        y -= 1
        py -= two_rx2
        if d2 > 0:
            d2 += rx2 - py
        else:
            x += 1
            px += two_ry2
            d2 += rx2 - py + px
        _plot4(x, y)

    return sorted(points, key=lambda p: (p[1], p[0]))


def _filled_ellipse(cx: int, cy: int, rx: int, ry: int) -> set[tuple[int, int]]:
    """All integer tiles inside or on the boundary of an ellipse."""
    if rx < 0 or ry < 0:
        return set()
    if rx == 0 and ry == 0:
        return {(cx, cy)}
    if rx == 0:
        return {(cx, cy + dy) for dy in range(-ry, ry + 1)}
    if ry == 0:
        return {(cx + dx, cy) for dx in range(-rx, rx + 1)}

    result: set[tuple[int, int]] = set()
    rx2 = rx * rx
    ry2 = ry * ry
    for dy in range(-ry, ry + 1):
        x_sq = rx2 * (1.0 - (dy * dy) / ry2)
        if x_sq < 0:
            continue
        x_max = int(math.sqrt(x_sq) + 0.5)
        for dx in range(-x_max, x_max + 1):
            result.add((cx + dx, cy + dy))
    return result


def filled_ellipse_ring(
    cx: int, cy: int, rx: int, ry: int, thickness: int,
) -> list[tuple[int, int]]:
    """Solid ring of tiles between an outer and inner ellipse.

    The outer boundary is the ellipse at (rx, ry).  The ring extends
    *thickness* tiles inward.  Guaranteed gap-free by scanline filling.
    """
    outer = _filled_ellipse(cx, cy, rx, ry)
    irx = rx - thickness
    iry = ry - thickness
    if irx > 0 and iry > 0:
        inner = _filled_ellipse(cx, cy, irx, iry)
        ring = outer - inner
    else:
        ring = outer
    return sorted(ring, key=lambda p: (p[1], p[0]))

# SPDX-License-Identifier: Apache-2.0
"""Portable metadata and grasp annotation checks against composed OpenUSD.

These establish annotation validity, never physical robot grasp success.
"""
import json
import math
from collections import Counter
from pathlib import Path

from pxr import Gf, Usd, UsdGeom


def _object(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return False
    return isinstance(value, dict) and bool(value)


def metadata_issues(stage):
    """Require a nonempty object in a supported layer key or same-name JSON."""
    layer = stage.GetRootLayer()
    found = False
    issues = []
    for key in ('SimReady_Metadata', 'simready_metadata'):
        if key in layer.customLayerData:
            if _object(layer.customLayerData[key]):
                found = True
            else:
                issues.append(f"customLayerData '{key}' must contain a nonempty metadata object")
    if layer.realPath:
        sidecar = Path(layer.realPath).with_suffix('.json')
        if sidecar.exists():
            try:
                valid = _object(json.loads(sidecar.read_text()))
            except (ValueError, OSError, UnicodeError):
                valid = False
            if valid:
                found = True
            else:
                issues.append('Same-name metadata sidecar must contain a nonempty JSON object')
    if not found:
        issues.append("Metadata must be a nonempty object in customLayerData 'SimReady_Metadata' "
                      "or 'simready_metadata', or a same-name JSON sidecar alongside the USD")
    return issues


def _inside_polygon(point, vertices, normal):
    # Project onto the strongest plane and use an odd-even crossing test,
    # including boundary points. This handles concave polygons without fan
    # triangulation, which could falsely fill holes in a polygon's outline.
    axis = max(range(3), key=lambda i: abs(normal[i]))
    axes = [i for i in range(3) if i != axis]
    x, y = (point[i] for i in axes)
    inside = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        ax, ay = (a[i] for i in axes)
        bx, by = (b[i] for i in axes)
        cross = (x-ax)*(by-ay) - (y-ay)*(bx-ax)
        if abs(cross) <= 1e-10 and min(ax,bx)-1e-10 <= x <= max(ax,bx)+1e-10 and min(ay,by)-1e-10 <= y <= max(ay,by)+1e-10:
            return True
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside = not inside
    return inside


def _polygon_normal(vertices):
    if len(vertices) < 3:
        return None
    normal = Gf.Vec3d(0)
    for p, q in zip(vertices, vertices[1:] + vertices[:1]):
        normal += Gf.Cross(p-vertices[0], q-vertices[0])
    if normal.GetLength() < 1e-12:
        return None
    normal.Normalize()
    # Nonplanar faces are not sufficient intersection evidence.
    if any(abs(Gf.Dot(v-vertices[0], normal)) > 1e-7 for v in vertices):
        return None
    return normal


def _segment_polygon(a, b, vertices):
    normal = _polygon_normal(vertices)
    if normal is None:
        return False
    denominator = Gf.Dot(b-a, normal)
    if abs(denominator) < 1e-12:
        if abs(Gf.Dot(a-vertices[0], normal)) > 1e-9:
            return False
        if _inside_polygon(a, vertices, normal) or _inside_polygon(b, vertices, normal):
            return True
        axis = max(range(3), key=lambda i: abs(normal[i]))
        axes = [i for i in range(3) if i != axis]
        def orient(p, q, r):
            x, y = axes
            return (q[x]-p[x])*(r[y]-p[y]) - (q[y]-p[y])*(r[x]-p[x])
        for c, d in zip(vertices, vertices[1:]+vertices[:1]):
            if (all(max(min(a[i],b[i]),min(c[i],d[i])) <= min(max(a[i],b[i]),max(c[i],d[i]))+1e-9 for i in axes)
                    and orient(a,b,c)*orient(a,b,d) <= 1e-18
                    and orient(c,d,a)*orient(c,d,b) <= 1e-18):
                return True
        return False
    t = Gf.Dot(vertices[0]-a, normal) / denominator
    return -1e-9 <= t <= 1+1e-9 and _inside_polygon(a+t*(b-a), vertices, normal)


def _segment_box(a, b, lo, hi):
    start, end = 0., 1.
    for axis in range(3):
        delta = b[axis]-a[axis]
        if abs(delta) < 1e-12:
            if a[axis] < lo[axis]-1e-9 or a[axis] > hi[axis]+1e-9:
                return False
        else:
            left, right = sorted(((lo[axis]-a[axis])/delta, (hi[axis]-a[axis])/delta))
            start, end = max(start,left), min(end,right)
            if start > end+1e-9:
                return False
    return True


def _mesh_faces(mesh):
    """Read the same valid, non-hole polygons for surface and volume tests."""
    points = list(mesh.GetPointsAttr().Get() or [])
    counts = list(mesh.GetFaceVertexCountsAttr().Get() or [])
    indices = list(mesh.GetFaceVertexIndicesAttr().Get() or [])
    holes = set(mesh.GetHoleIndicesAttr().Get() or [])
    if (not points or not counts or any(count < 3 for count in counts)
            or sum(counts) != len(indices)
            or any(i < 0 or i >= len(points) for i in indices)
            or any(not all(math.isfinite(x) for x in p) for p in points)):
        return []
    faces, offset = [], 0
    for face, count in enumerate(counts):
        if face not in holes:
            faces.append([Gf.Vec3d(points[i]) for i in indices[offset:offset+count]])
        offset += count
    return faces


def _closed_mesh_contains(polygons, point):
    """Containment requires a closed surface, not overlap with its bounds.

    Exact coincident vertices may be split for face-varying authoring. Weld
    their positions for the closure check only; the USD is never changed.
    Odd/even ray crossings preserve concavities and nested cavity shells.
    Rays hitting an edge are ambiguous, so use independent directions and
    require two unambiguous, agreeing observations before accepting volume.
    """
    if not polygons:
        return False
    points = [p for vertices in polygons for p in vertices]
    if any(point[i] < min(p[i] for p in points) or point[i] > max(p[i] for p in points)
           for i in range(3)):
        return False
    edges, faces = Counter(), []
    for vertices in polygons:
        normal = _polygon_normal(vertices)
        if normal is None:
            return False
        for a, b in zip(vertices, vertices[1:]+vertices[:1]):
            if a == b:
                return False
            edges[tuple(sorted((tuple(a), tuple(b))))] += 1
        faces.append((vertices, normal))
    if not edges or any(count != 2 for count in edges.values()):
        return False

    observations = []
    for direction in (Gf.Vec3d(1,.371,.529), Gf.Vec3d(.193,1,.617), Gf.Vec3d(.419,.233,1)):
        crossings, ambiguous = 0, False
        for vertices, normal in faces:
            denominator = Gf.Dot(direction, normal)
            if abs(denominator) < 1e-12:
                continue
            distance = Gf.Dot(vertices[0]-point, normal) / denominator
            if distance <= 0:
                continue
            hit = point + distance*direction
            if not _inside_polygon(hit, vertices, normal):
                continue
            # A ray on a shared edge/vertex must not count both incident faces.
            if any((hit-a).GetLength() <= 1e-9 or (
                    Gf.Cross(hit-a,b-a).GetLength() <= 1e-9*(b-a).GetLength()
                    and 0 <= Gf.Dot(hit-a,b-a) <= Gf.Dot(b-a,b-a))
                   for a,b in zip(vertices, vertices[1:]+vertices[:1])):
                ambiguous = True
                break
            crossings += 1
        if not ambiguous:
            observations.append(crossings % 2 == 1)
    return len(observations) >= 2 and all(observations)


def _intersects(stage, a, b, guide):
    cache = UsdGeom.XformCache()
    for prim in Usd.PrimRange(stage.GetDefaultPrim(), Usd.TraverseInstanceProxies()):
        if prim == guide or prim.GetName().startswith('grasp_identifier'):
            continue
        imageable = UsdGeom.Imageable(prim)
        if imageable and (imageable.ComputeVisibility() == 'invisible'
                          or imageable.ComputePurpose() == 'guide'):
            continue
        transform = cache.GetLocalToWorldTransform(prim)
        if not math.isfinite(transform.GetDeterminant()) or abs(transform.GetDeterminant()) < 1e-12:
            continue
        inverse = transform.GetInverse()
        local_a, local_b = inverse.Transform(a), inverse.Transform(b)
        if prim.IsA(UsdGeom.Cube):
            size = float(UsdGeom.Cube(prim).GetSizeAttr().Get())/2
            if _segment_box(local_a, local_b, [-size]*3, [size]*3):
                return True
        elif prim.IsA(UsdGeom.Sphere):
            radius = float(UsdGeom.Sphere(prim).GetRadiusAttr().Get())
            direction = local_b-local_a
            t = max(0.,min(1.,-Gf.Dot(local_a,direction)/Gf.Dot(direction,direction)))
            if (local_a+t*direction).GetLength() <= radius+1e-9:
                return True
        elif prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(prim)
            faces = _mesh_faces(mesh)
            if (any(_segment_polygon(local_a, local_b, vertices) for vertices in faces)
                    or _closed_mesh_contains(faces, local_a)):
                return True
    return False


def grasp_vector_issue(stage, prim):
    """Finite, nondegenerate linear segments must intersect asset geometry."""
    curve = UsdGeom.BasisCurves(prim)
    points = list(curve.GetPointsAttr().Get() or [])
    counts = list(curve.GetCurveVertexCountsAttr().Get() or [])
    if curve.GetTypeAttr().Get() != 'linear' or not counts or any(c < 2 for c in counts) or sum(counts) != len(points):
        return 'Grasp vector must be linear BasisCurves with consistent vertex counts of at least two'
    if any(not all(math.isfinite(x) for x in point) for point in points):
        return 'Grasp vector points must be finite'
    transform = UsdGeom.XformCache().GetLocalToWorldTransform(prim)
    if not math.isfinite(transform.GetDeterminant()) or abs(transform.GetDeterminant()) < 1e-12:
        return 'Grasp vector requires a finite, nonsingular composed transform'
    world = [transform.Transform(Gf.Vec3d(point)) for point in points]
    offset = 0
    for count in counts:
        part = world[offset:offset+count]
        offset += count
        nonzero = [(a,b) for a,b in zip(part,part[1:]) if (b-a).GetLength() > 1e-9]
        if not nonzero:
            return 'Grasp vector must have a nonzero segment'
        if not any(_intersects(stage,a,b,prim) for a,b in nonzero):
            return 'Grasp vector must intersect composed asset geometry, not only its bounding box'
    return None

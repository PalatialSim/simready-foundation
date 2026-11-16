from pathlib import Path
from pxr import Gf, Usd, UsdGeom
import importlib.util

path = (
    Path(__file__).resolve().parents[1]
    / "nv_core/sr_specs/docs/capabilities/annotation_contract.py"
)
spec = importlib.util.spec_from_file_location("annotation_contract", path)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def curve(stage, points):
    p = UsdGeom.BasisCurves.Define(stage, "/Asset/grasp_identifier_test")
    p.CreateTypeAttr("linear")
    p.CreateCurveVertexCountsAttr([2])
    p.CreatePointsAttr(points)
    return p.GetPrim()


def fixture(points, guide):
    s = Usd.Stage.CreateInMemory()
    r = UsdGeom.Xform.Define(s, "/Asset")
    s.SetDefaultPrim(r.GetPrim())
    m = UsdGeom.Mesh.Define(s, "/Asset/Mesh")
    m.CreatePointsAttr(points)
    m.CreateFaceVertexCountsAttr([4])
    m.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    return s, curve(s, guide), m


def test_warped_quad_crossing():
    s, g, _ = fixture(
        [(-1, -1, 0), (1, -1, 0), (1, 1, 0.2), (-1, 1, 0)], [(0, 0, -1), (0, 0, 1)]
    )
    assert c.grasp_vector_issue(s, g) is None


def test_warped_quad_bounds_only_miss():
    s, g, _ = fixture(
        [(-1, -1, 0), (1, -1, 0), (1, 1, 0.2), (-1, 1, 0)],
        [(0.9, 0.9, -1), (0.9, 0.9, -0.1)],
    )
    assert c.grasp_vector_issue(s, g) is not None


def test_hidden_geometry_does_not_establish_intersection():
    s, g, m = fixture(
        [(-1, -1, 0), (1, -1, 0), (1, 1, 0.2), (-1, 1, 0)], [(0, 0, -1), (0, 0, 1)]
    )
    m.CreateVisibilityAttr("invisible")
    assert c.grasp_vector_issue(s, g) is not None


def test_concave_warped_face_not_filled_by_fan():
    s, g, _ = fixture(
        [(0, 0, 0), (2, 0, 0), (0.5, 0.5, 0.2), (0, 2, 0)],
        [(1.4, 1.4, -1), (1.4, 1.4, 1)],
    )
    assert c.grasp_vector_issue(s, g) is not None


def test_ambiguous_diagonal_is_not_counted():
    s, g, _ = fixture(
        [(-1, -1, 0), (1, -1, 0), (1, 1, 0.2), (-1, 1, 0)], [(0, 0, 0.08), (0, 0, 0.12)]
    )
    assert c.grasp_vector_issue(s, g) is not None


def test_hidden_guide_purpose_does_not_count():
    s, g, m = fixture(
        [(-1, -1, 0), (1, -1, 0), (1, 1, 0.2), (-1, 1, 0)], [(0, 0, -1), (0, 0, 1)]
    )
    m.CreatePurposeAttr("guide")
    assert c.grasp_vector_issue(s, g) is not None


def test_nonplanar_pentagon_is_not_fan_filled():
    s, g, m = fixture(
        [(-1, -1, 0), (1, -1, 0), (1, 1, 0.2), (-1, 1, 0)], [(0, 0, -1), (0, 0, 1)]
    )
    m.GetPointsAttr().Set([(-1, -1, 0), (1, -1, 0), (1, 0, 0.2), (0, 1, 0), (-1, 0, 0)])
    m.GetFaceVertexCountsAttr().Set([5])
    m.GetFaceVertexIndicesAttr().Set([0, 1, 2, 3, 4])
    assert c.grasp_vector_issue(s, g) is not None

"""Portable GSP.001 checks against equivalent solid representations."""
import importlib.util
from pathlib import Path

import pytest
from pxr import Usd, UsdGeom

PATH = Path(__file__).resolve().parents[1] / "nv_core/sr_specs/docs/capabilities/annotation_contract.py"
spec = importlib.util.spec_from_file_location("annotation_contract", PATH)
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def _stage():
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    return stage


def _box(stage, path, size=.2, *, duplicate_vertices=False):
    mesh = UsdGeom.Mesh.Define(stage, path)
    s = size/2
    points = [(-s,-s,-s),(s,-s,-s),(s,s,-s),(-s,s,-s),
              (-s,-s,s),(s,-s,s),(s,s,s),(-s,s,s)]
    indices = [0,3,2,1,4,5,6,7,0,1,5,4,1,2,6,5,2,3,7,6,3,0,4,7]
    if duplicate_vertices:
        points = [points[i] for i in indices]
        indices = list(range(len(points)))
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr([4]*6)
    mesh.CreateFaceVertexIndicesAttr(indices)
    return mesh


def _issue(stage, points):
    guide = UsdGeom.BasisCurves.Define(stage, "/Asset/grasp_identifier_0")
    guide.CreateTypeAttr("linear")
    guide.CreateCurveVertexCountsAttr([len(points)])
    guide.CreatePointsAttr(points)
    guide.CreatePurposeAttr("guide")
    return contract.grasp_vector_issue(stage, guide.GetPrim())


@pytest.mark.parametrize("representation", ["primitive", "mesh", "split_mesh"])
@pytest.mark.parametrize("points,valid", [
    ([(-.07,0,0),(.07,0,0)], True),
    ([(-.11,0,0),(.11,0,0)], True),
    ([(-.07,.2,0),(.07,.2,0)], False),
])
def test_equivalent_closed_boxes_have_the_same_verdict(representation, points, valid):
    stage = _stage()
    if representation == "primitive":
        UsdGeom.Cube.Define(stage, "/Asset/box").CreateSizeAttr(.2)
    else:
        _box(stage, "/Asset/box", duplicate_vertices=representation == "split_mesh")
    assert (_issue(stage, points) is None) == valid


@pytest.mark.parametrize("hole", [False, True])
def test_an_open_shell_does_not_claim_its_bounding_volume(hole):
    stage = _stage()
    mesh = _box(stage, "/Asset/box")
    if hole:
        mesh.CreateHoleIndicesAttr([1])
    else:
        mesh.GetFaceVertexCountsAttr().Set([4]*5)
        mesh.GetFaceVertexIndicesAttr().Set(list(mesh.GetFaceVertexIndicesAttr().Get())[4:])
    assert _issue(stage, [(-.03,0,0),(.03,0,0)])


def test_a_closed_inner_shell_preserves_a_cavity():
    stage = _stage()
    outer = _box(stage, "/Asset/outer")
    inner = _box(stage, "/Asset/inner", .16)
    points = list(outer.GetPointsAttr().Get()) + list(inner.GetPointsAttr().Get())
    indices = list(outer.GetFaceVertexIndicesAttr().Get()) + [i+8 for i in inner.GetFaceVertexIndicesAttr().Get()]
    outer.GetPointsAttr().Set(points)
    outer.GetFaceVertexCountsAttr().Set([4]*12)
    outer.GetFaceVertexIndicesAttr().Set(indices)
    stage.RemovePrim("/Asset/inner")
    assert _issue(stage, [(-.03,0,0),(.03,0,0)])
    assert _issue(stage, [(.085,-.01,0),(.095,.01,0)]) is None


def test_a_concave_solid_does_not_fill_its_empty_corner():
    stage = _stage()
    mesh = UsdGeom.Mesh.Define(stage, "/Asset/body")
    outline = [(-.1,-.1),(.1,-.1),(.1,0),(0,0),(0,.1),(-.1,.1)]
    mesh.CreatePointsAttr([(x,y,z) for z in [-.1,.1] for x,y in outline])
    sides = [v for i in range(6) for v in [i,(i+1)%6,(i+1)%6+6,i+6]]
    mesh.CreateFaceVertexCountsAttr([6,6]+[4]*6)
    mesh.CreateFaceVertexIndicesAttr([5,4,3,2,1,0,6,7,8,9,10,11]+sides)
    assert _issue(stage, [(.08,.08,-.02),(.08,.08,.02)])
    assert _issue(stage, [(-.08,.08,-.02),(-.08,.08,.02)]) is None


def test_composed_nonuniform_transforms_preserve_containment():
    stage = _stage()
    mesh = _box(stage, "/Asset/box")
    xf = UsdGeom.Xformable(mesh)
    xf.AddTranslateOp().Set((2,3,4))
    xf.AddRotateZOp().Set(90)
    xf.AddScaleOp().Set((-2,.5,3))
    assert _issue(stage, [(2,2.9,4),(2,3.1,4)]) is None
    assert _issue(stage, [(2.2,2.9,4),(2.2,3.1,4)])


def test_contained_guide_uses_composed_instance_geometry():
    stage = _stage()
    UsdGeom.Xform.Define(stage, "/Source")
    _box(stage, "/Source/box")
    instance = stage.DefinePrim("/Asset/instance", "Xform")
    instance.GetReferences().AddInternalReference("/Source")
    instance.SetInstanceable(True)
    assert _issue(stage, [(-.07,0,0),(.07,0,0)]) is None

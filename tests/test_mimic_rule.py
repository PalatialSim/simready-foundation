"""Exercise the vendored rule's actual method without NVIDIA registry imports."""
import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from pxr import Sdf, Usd, UsdGeom, UsdPhysics


class PrimView:
    def __init__(self, prim):
        self.prim = prim

    def __getattr__(self, name):
        return getattr(self.prim, name)

    def HasAPI(self, _):
        return True

    def GetAppliedSchemas(self):
        return self.prim.GetMetadata('apiSchemas').GetAppliedItems()


class Mimic:
    def __init__(self, prim, axis):
        self.prim, self.prefix = prim, f'physxMimicJoint:{axis}:'

    def GetReferenceJointRel(self):
        return self.prim.GetRelationship(self.prefix+'referenceJoint')

    def GetGearingAttr(self):
        return self.prim.GetAttribute(self.prefix+'gearing')

    def GetOffsetAttr(self):
        return self.prim.GetAttribute(self.prefix+'offset')


def check(prim):
    path = Path(__file__).parents[1] / 'nv_core/sr_specs/docs/capabilities/physics_bodies/physics_driven_joints/validation.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MimicAPICheck')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'CheckPrim')
    ns = dict(math=math, Usd=Usd, UsdPhysics=UsdPhysics,
              PhysxSchema=SimpleNamespace(PhysxMimicJointAPI=Mimic),
              DrivenJointsCapReq=SimpleNamespace(DJ_007='DJ.007'),
              get_prismatic_or_revolute_limits=lambda p: (
                  p.GetAttribute('physics:lowerLimit').Get(), p.GetAttribute('physics:upperLimit').Get()))
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), ns)
    errors = []
    checker = SimpleNamespace(_AddFailedCheck=lambda **kw: errors.append(kw['message']),
                              _AddInfo=lambda **kw: None)
    ns['CheckPrim'](checker, PrimView(prim))
    return errors


@pytest.mark.parametrize('meters', [1.0, 0.01, 0.001])
@pytest.mark.parametrize('sign', [1, -1])
@pytest.mark.parametrize('offset_m', [0.0, 0.01])
def test_linear_follower_requires_full_pitch_mapped_rotation(meters, sign, offset_m):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(stage, meters)
    reference = UsdPhysics.RevoluteJoint.Define(stage, '/Rotation')
    reference.CreateLowerLimitAttr().Set(0)
    reference.CreateUpperLimitAttr().Set(720)
    follower = UsdPhysics.PrismaticJoint.Define(stage, '/Travel')
    prim = follower.GetPrim()
    prim.AddAppliedSchema('PhysxMimicJointAPI:rotX')
    prefix = 'physxMimicJoint:rotX:'
    prim.CreateRelationship(prefix+'referenceJoint').SetTargets([reference.GetPath()])
    for name, value in [('gearing', -sign*.001/(360*meters)),
                        ('offset', offset_m/meters), ('naturalFrequency', 0), ('dampingRatio', 1)]:
        prim.CreateAttribute(prefix+name, Sdf.ValueTypeNames.Float).Set(value)
    for travel_m, valid in [(.0002, False), (.001999, False), (.002, True)]:
        lower, upper = sorted((-offset_m/meters, (sign*travel_m-offset_m)/meters))
        follower.CreateLowerLimitAttr().Set(lower)
        follower.CreateUpperLimitAttr().Set(upper)
        assert (check(prim) == []) is valid


def hard_pair():
    stage = Usd.Stage.CreateInMemory()
    reference = UsdPhysics.PrismaticJoint.Define(stage, '/Travel')
    reference.CreateLowerLimitAttr().Set(0)
    reference.CreateUpperLimitAttr().Set(.002)
    follower = UsdPhysics.RevoluteJoint.Define(stage, '/Rotation')
    follower.CreateLowerLimitAttr().Set(0)
    follower.CreateUpperLimitAttr().Set(720)
    prim = follower.GetPrim()
    prim.AddAppliedSchema('PhysxMimicJointAPI:rotX')
    prefix = 'physxMimicJoint:rotX:'
    prim.CreateRelationship(prefix+'referenceJoint').SetTargets([reference.GetPath()])
    for name, value in [('gearing', -360000), ('offset', 0),
                        ('naturalFrequency', 0), ('dampingRatio', 1)]:
        prim.CreateAttribute(prefix+name, Sdf.ValueTypeNames.Float).Set(value)
    return stage, prim


@pytest.mark.parametrize('frequency', [0, 40])
def test_hard_and_soft_coupling_accept_equal_endpoints(frequency):
    stage, prim = hard_pair()
    prim.GetAttribute('physxMimicJoint:rotX:naturalFrequency').Set(frequency)
    assert not check(prim)


@pytest.mark.parametrize('name,value', [('naturalFrequency', -1),
    ('naturalFrequency', math.nan), ('gearing', 0), ('gearing', math.inf),
    ('offset', math.nan)])
def test_invalid_parameters_fail(name, value):
    stage, prim = hard_pair()
    prim.GetAttribute('physxMimicJoint:rotX:'+name).Set(value)
    assert check(prim)


@pytest.mark.parametrize('targets', [[], ['/Missing'], ['/Rotation'], ['/Travel', '/Missing']])
def test_invalid_reference_fails_without_exception(targets):
    stage, prim = hard_pair()
    prim.GetRelationship('physxMimicJoint:rotX:referenceJoint').SetTargets(targets)
    assert check(prim)

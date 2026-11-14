"""Exercise PMT.001 with real USD composition and binding resolution."""
import ast
from pathlib import Path
import types

import pytest
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade


def checker():
    path = Path(__file__).resolve().parents[1] / 'nv_core/sr_specs/docs/capabilities/physics_bodies/physics_materials/validation.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'PhysicsMaterialsCapabilityChecker')
    cls.decorator_list = []
    cls.bases = []
    env = {'Usd': Usd, 'UsdPhysics': UsdPhysics, 'UsdShade': UsdShade,
           'PhysicsMaterialsCapReqs': types.SimpleNamespace(PMT_001='PMT.001')}
    exec(compile(ast.Module([cls], type_ignores=[]), str(path), 'exec'), env)
    obj = env[cls.name]()
    failures = []
    obj._AddFailedCheck = lambda message, **kwargs: failures.append(message)
    return obj, failures


@pytest.mark.parametrize('binding,has_physics,expected', [
    ('inherited', True, True), ('direct', True, True),
    ('missing', True, False), ('direct', False, False),
    ('all_purpose', True, False),
])
def test_resolves_physics_material_binding(binding, has_physics, expected):
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, '/Asset').GetPrim()
    stage.SetDefaultPrim(root)
    collider = UsdGeom.Cube.Define(stage, '/Asset/Collider').GetPrim()
    UsdPhysics.CollisionAPI.Apply(collider)
    material = UsdShade.Material.Define(stage, '/Asset/PhysicsMaterial')
    if has_physics:
        UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    if binding != 'missing':
        owner = root if binding == 'inherited' else collider
        api = UsdShade.MaterialBindingAPI.Apply(owner)
        api.Bind(material, materialPurpose='allPurpose' if binding == 'all_purpose' else 'physics')
    rule, failures = checker()
    rule.CheckStage(stage)
    assert (not failures) == expected, failures


def test_collection_binding_resolves_to_physics_material():
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, '/Asset').GetPrim()
    stage.SetDefaultPrim(root)
    collider = UsdGeom.Cube.Define(stage, '/Asset/Collider').GetPrim()
    UsdPhysics.CollisionAPI.Apply(collider)
    material = UsdShade.Material.Define(stage, '/Asset/Material')
    UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    collection = Usd.CollectionAPI.Apply(root, 'colliders')
    collection.CreateIncludesRel().SetTargets([collider.GetPath()])
    UsdShade.MaterialBindingAPI.Apply(root).Bind(collection, material, 'colliders', materialPurpose='physics')
    rule, failures = checker()
    rule.CheckStage(stage)
    assert failures == []


def test_stronger_ancestor_binding_overrides_invalid_direct_binding():
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, '/Asset').GetPrim()
    stage.SetDefaultPrim(root)
    collider = UsdGeom.Cube.Define(stage, '/Asset/Collider').GetPrim()
    UsdPhysics.CollisionAPI.Apply(collider)
    valid = UsdShade.Material.Define(stage, '/Asset/Valid')
    UsdPhysics.MaterialAPI.Apply(valid.GetPrim())
    invalid = UsdShade.Material.Define(stage, '/Asset/Invalid')
    UsdShade.MaterialBindingAPI.Apply(root).Bind(valid, bindingStrength=UsdShade.Tokens.strongerThanDescendants, materialPurpose='physics')
    UsdShade.MaterialBindingAPI.Apply(collider).Bind(invalid, materialPurpose='physics')
    rule, failures = checker()
    rule.CheckStage(stage)
    assert failures == []

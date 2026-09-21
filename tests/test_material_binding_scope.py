"""Exercise the checker against real USD bindings without requiring the MDL runtime."""
import importlib.util
import sys
import types
from pathlib import Path

import pytest
from pxr import Usd, UsdGeom, UsdShade


@pytest.fixture
def checker(monkeypatch):
    core = types.ModuleType('omni.asset_validator.core')
    core.BaseRuleChecker = object
    core.register_requirements = lambda *args: lambda cls: cls
    capability = types.ModuleType('omni.capabilities')
    capability.MaterialsRequirements = types.SimpleNamespace(**{
        code: code for code in ('VM_BIND_001', 'VM_BIND_002', 'VM_PS_001',
                               'VM_MAT_001', 'VM_MDL_001', 'VM_MDL_002',
                               'VM_TEX_001', 'VM_TEX_002')
    })
    # Only registration and MDL imports are isolated; all binding APIs are real USD.
    for name, mod in {'omni': types.ModuleType('omni'),
                      'omni.asset_validator': types.ModuleType('omni.asset_validator'),
                      'omni.asset_validator.core': core,
                      'omni.capabilities': capability}.items():
        monkeypatch.setitem(sys.modules, name, mod)
    mdl = types.ModuleType('scope_test.util.mdl_helpers')
    mdl.get_mdl_module_parameter_descs = lambda *args: {}
    monkeypatch.setitem(sys.modules, mdl.__name__, mdl)
    path = Path(__file__).resolve().parents[1] / 'nv_core/sr_specs/docs/capabilities/visualization/materials/validation.py'
    spec = importlib.util.spec_from_file_location('scope_test.validation', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.VisualMaterialsCapabilityChecker()


@pytest.mark.parametrize('collection_count', [0, 1, 2])
def test_direct_and_named_collection_bindings_are_checked(checker, collection_count):
    stage = Usd.Stage.CreateInMemory()
    prim = UsdGeom.Cube.Define(stage, '/Asset/Cube').GetPrim()
    material = UsdShade.Material.Define(stage, '/Asset/Looks/Material')
    bindings = UsdShade.MaterialBindingAPI.Apply(prim)
    bindings.Bind(material)
    expected_targets = []
    for i in range(collection_count):
        collection = Usd.CollectionAPI.Apply(prim, f'group{i}')
        collection.CreateIncludesRel().SetTargets([prim.GetPath()])
        bindings.Bind(collection, material, f'binding{i}')
        expected_targets.extend([collection.GetCollectionPath(), material.GetPath()])
    seen = []
    original = checker._is_valid_collection_scope
    checker._is_valid_collection_scope = lambda target: (seen.append(target), original(target))[1]
    assert checker.check_vm_bind_001_material_bind_scope(stage, str(prim.GetPath())) == []
    assert seen == expected_targets

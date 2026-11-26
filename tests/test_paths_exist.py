"""Run NP.008 on real USD composition arcs without an Omniverse install."""
import importlib.util
import sys
import types
from pathlib import Path

import pytest
from pxr import Sdf, Usd


@pytest.fixture
def checker(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "nv_core/sr_specs/docs/capabilities/core/naming_paths/validation.py"
    omni = types.ModuleType("omni")
    omni.asset_validator = types.ModuleType("omni.asset_validator")
    core = omni.asset_validator.core = types.ModuleType("omni.asset_validator.core")
    core.BaseRuleChecker = object
    core.registerRule = core.register_requirements = lambda *args, **kwargs: lambda cls: cls
    omni.capabilities = types.ModuleType("omni.capabilities")
    codes = [f"NP_{index:03d}" for index in range(1, 9)]
    omni.capabilities.NamingPathsRequirements = types.SimpleNamespace(**{code: code for code in codes})
    for module in (omni, omni.asset_validator, core, omni.capabilities):
        monkeypatch.setitem(sys.modules, module.__name__, module)

    spec = importlib.util.spec_from_file_location("paths_exist_validation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PathsExistChecker()


def issues(checker, stage):
    found = []
    checker._AddFailedCheck = lambda **issue: found.append(issue)
    checker.CheckStage(stage)
    return found


@pytest.mark.parametrize(("list_name", "arc_type"), [("referenceList", Sdf.Reference), ("payloadList", Sdf.Payload)])
@pytest.mark.parametrize("operation", ["explicitItems", "prependedItems", "addedItems", "appendedItems"])
@pytest.mark.parametrize("present", [True, False])
def test_authored_asset_paths(checker, tmp_path, list_name, arc_type, operation, present):
    source = Usd.Stage.CreateNew(str(tmp_path / "source.usda"))
    source.SetDefaultPrim(source.DefinePrim("/Asset", "Xform"))
    child = source.DefinePrim("/Asset/Child", "Xform")
    if present:
        dependency = Usd.Stage.CreateNew(str(tmp_path / "dependency.usda"))
        dependency.SetDefaultPrim(dependency.DefinePrim("/Dependency", "Xform"))
        dependency.GetRootLayer().Save()

    prim_spec = source.GetRootLayer().GetPrimAtPath(child.GetPath())
    setattr(getattr(prim_spec, list_name), operation, [arc_type("dependency.usda")])
    found = issues(checker, source)
    if present:
        assert found == []
    else:
        assert [issue["requirement"] for issue in found] == ["NP_008"]
        assert "dependency.usda" in found[0]["message"]
        assert found[0]["at"] == child


def test_internal_reference(checker):
    stage = Usd.Stage.CreateInMemory()
    stage.SetDefaultPrim(stage.DefinePrim("/Asset", "Xform"))
    stage.DefinePrim("/Prototype", "Xform")
    stage.DefinePrim("/Asset/Instance", "Xform").GetReferences().AddInternalReference("/Prototype")
    assert issues(checker, stage) == []

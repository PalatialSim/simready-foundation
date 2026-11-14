# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from enum import Enum

import omni.asset_validator.core
from pxr import Usd, UsdPhysics, UsdShade

from ... import Requirement


class PhysicsMaterialsCapReqs(Requirement, Enum):
    PMT_001 = (
        "PMT.001",
        "collider-materials-binding",
        "Every collider (prim with PhysicsCollisionAPI) must have a material:binding:physics relationship to a physics material.",
    )


@omni.asset_validator.core.registerRule("PhysicsMaterials")
@omni.asset_validator.core.register_requirements(PhysicsMaterialsCapReqs.PMT_001, override=True)
class PhysicsMaterialsCapabilityChecker(omni.asset_validator.core.BaseRuleChecker):
    COLLISION_API_MATERIAL_BINDING_REQUIREMENT = PhysicsMaterialsCapReqs.PMT_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        for prim in Usd.PrimRange(default_prim):
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                # USD resolves bindings through ancestors and collections, including
                # binding strength. Do not confuse all-purpose fallback with an
                # explicit physics-purpose binding required by PMT.001.
                material, binding = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(
                    materialPurpose="physics"
                )
                name = str(binding.GetName()) if binding else ""
                physics_binding = name == "material:binding:physics" or name.startswith(
                    "material:binding:collection:physics:"
                )
                if not physics_binding or not material or not material.GetPrim().HasAPI(UsdPhysics.MaterialAPI):
                    self._AddFailedCheck(
                        "Prim has a collision API but no valid physics material binding through material:binding:physics.",
                        at=prim,
                        requirement=self.COLLISION_API_MATERIAL_BINDING_REQUIREMENT,
                    )
                    return

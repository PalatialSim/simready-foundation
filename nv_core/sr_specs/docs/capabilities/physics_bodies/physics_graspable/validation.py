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
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade

from ... import Requirement


class PhysicsGraspableCapReqs(Requirement, Enum):
    GSP_001 = (
        "GSP.001",
        "graspable-vector-line",
        "Graspable prim must have a vector line for grasping.",
    )


@omni.asset_validator.core.registerRule("PhysicsGraspable")
@omni.asset_validator.core.register_requirements(PhysicsGraspableCapReqs.GSP_001, override=True)
class GraspableVectorLineChecker(omni.asset_validator.core.BaseRuleChecker):

    GRASP_VECTOR_LINE_REQUIREMENT = PhysicsGraspableCapReqs.GSP_001

    def CheckStage(self, stage: Usd.Stage) -> None:
        from ...annotation_contract import grasp_vector_issue
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim, cannot check grasp vectors.",
                                 at=stage, requirement=self.GRASP_VECTOR_LINE_REQUIREMENT)
            return
        guides = [prim for prim in Usd.PrimRange(default_prim)
                  if prim.IsA(UsdGeom.BasisCurves) and prim.GetName().startswith("grasp_identifier")]
        if not guides:
            self._AddFailedCheck("Asset must have at least one grasp vector prim.",
                                 at=default_prim, requirement=self.GRASP_VECTOR_LINE_REQUIREMENT)
        for prim in guides:
            issue = grasp_vector_issue(stage, prim)
            if issue:
                self._AddFailedCheck(issue, at=prim, requirement=self.GRASP_VECTOR_LINE_REQUIREMENT)

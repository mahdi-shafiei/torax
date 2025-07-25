# Copyright 2024 DeepMind Technologies Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Dataclass representing runtime parameter inputs to the pedestal models."""
import dataclasses

import jax
from torax._src import array_typing


@jax.tree_util.register_dataclass
@dataclasses.dataclass(frozen=True)
class DynamicRuntimeParams:
  """Input params for the pedestal model."""

  set_pedestal: array_typing.ScalarBool

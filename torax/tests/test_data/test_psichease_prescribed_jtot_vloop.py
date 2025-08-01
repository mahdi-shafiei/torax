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

"""Identical to test_psichease_ip_chease but V-loop boundary condition."""

import copy

from torax.tests.test_data import test_psichease_prescribed_jtot

CONFIG = copy.deepcopy(test_psichease_prescribed_jtot.CONFIG)
CONFIG['profile_conditions']['use_v_loop_lcfs_boundary_condition'] = True
CONFIG['profile_conditions']['v_loop_lcfs'] = 8.6

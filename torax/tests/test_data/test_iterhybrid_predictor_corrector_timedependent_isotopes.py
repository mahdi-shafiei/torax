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

"""Identical to test_iterhybrid_predictor_corrector but with a time varying DT isotope mix."""
import copy
from torax.tests.test_data import test_iterhybrid_predictor_corrector


CONFIG = copy.deepcopy(test_iterhybrid_predictor_corrector.CONFIG)

# Needed to avoid an odd pytype error
assert isinstance(CONFIG['runtime_params']['plasma_composition'], dict)
CONFIG['runtime_params']['plasma_composition']['main_ion'] = {
    'D': {0: 0.5, 2: 0.5, 3.5: 0.0, 5: 0.5},
    'T': {0: 0.5, 2: 0.5, 3.5: 1.0, 5: 0.5},
}
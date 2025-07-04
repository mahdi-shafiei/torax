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
from unittest import mock

from absl.testing import absltest
import numpy as np
from torax._src import state
from torax._src.config import runtime_params_slice
from torax._src.fvm import cell_variable
from torax._src.geometry import pydantic_model as geometry_pydantic_model
from torax._src.neoclassical import runtime_params as neoclassical_runtime_params
from torax._src.neoclassical.bootstrap_current import sauter


class SauterTest(absltest.TestCase):

  def test_sauter_bootstrap_current_is_correct_shape(self):
    n_rho = 10
    geo = geometry_pydantic_model.CircularConfig(n_rho=n_rho).build_geometry()
    dynamic_bootstap_params = sauter.DynamicRuntimeParams(
        bootstrap_multiplier=1.0
    )
    dynamic_params = mock.create_autospec(
        runtime_params_slice.DynamicRuntimeParamsSlice,
        instance=True,
        neoclassical=mock.create_autospec(
            neoclassical_runtime_params.DynamicRuntimeParams,
            instance=True,
            bootstrap_current=dynamic_bootstap_params,
        ),
    )
    core_profiles = mock.create_autospec(
        state.CoreProfiles,
        T_i=cell_variable.CellVariable(
            value=np.linspace(400, 700, n_rho), dr=geo.drho_norm
        ),
        T_e=cell_variable.CellVariable(
            value=np.linspace(4000, 7000, n_rho), dr=geo.drho_norm
        ),
        psi=cell_variable.CellVariable(
            value=np.linspace(9000, 4000, n_rho), dr=geo.drho_norm
        ),
        n_e=cell_variable.CellVariable(
            value=np.linspace(100, 200, n_rho), dr=geo.drho_norm
        ),
        n_i=cell_variable.CellVariable(
            value=np.linspace(100, 200, n_rho), dr=geo.drho_norm
        ),
        Z_i_face=np.linspace(1000, 2000, n_rho + 1),
        Z_eff_face=np.linspace(1.0, 1.0, n_rho + 1),
        q_face=np.linspace(1, 5, n_rho + 1),
    )

    model = sauter.SauterModel()
    result = model.calculate_bootstrap_current(
        dynamic_params,
        geo,
        core_profiles,
    )
    self.assertEqual(result.j_bootstrap.shape, (n_rho,))
    self.assertEqual(result.j_bootstrap_face.shape, (n_rho + 1,))


if __name__ == '__main__':
  absltest.main()

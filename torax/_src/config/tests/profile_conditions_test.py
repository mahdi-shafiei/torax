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

from absl.testing import absltest
from absl.testing import parameterized
import chex
import jax
import numpy as np
import pydantic
from torax._src import interpolated_param
from torax._src import jax_utils
from torax._src.config import build_runtime_params
from torax._src.config import profile_conditions
from torax._src.geometry import pydantic_model as geometry_pydantic_model
from torax._src.test_utils import default_configs
from torax._src.torax_pydantic import model_config
from torax._src.torax_pydantic import torax_pydantic
import xarray as xr


# pylint: disable=invalid-name
class ProfileConditionsTest(parameterized.TestCase):

  def test_profile_conditions_build_dynamic_params(self):
    pc = profile_conditions.ProfileConditions()
    geo = geometry_pydantic_model.CircularConfig().build_geometry()
    torax_pydantic.set_grid(pc, geo.torax_mesh)
    pc.build_dynamic_params(t=0.0)

  def test_profile_conditions_under_jit(self):
    initial_ip = 1e6
    updated_ip = 2e6
    pc = profile_conditions.ProfileConditions(Ip=initial_ip)
    geo = geometry_pydantic_model.CircularConfig().build_geometry()
    torax_pydantic.set_grid(pc, geo.torax_mesh)

    @jax.jit
    def f(pc_model: profile_conditions.ProfileConditions):
      return pc_model.build_dynamic_params(t=0.0)

    with self.subTest('first_jit_compiles_and_returns_expected_value'):
      output = f(pc)
      chex.assert_trees_all_close(output.Ip, initial_ip)
      self.assertEqual(jax_utils.get_number_of_compiles(f), 1)

    with self.subTest('second_jit_updates_value_without_recompile'):
      pc._update_fields({'Ip': updated_ip})
      output = f(pc)
      chex.assert_trees_all_close(output.Ip, updated_ip)
      self.assertEqual(jax_utils.get_number_of_compiles(f), 1)

  @parameterized.named_parameters(
      ('no boundary condition', None, 2.0, 200.0),
      ('boundary condition provided', 3.0, 3.0, 3.0),
  )
  def test_profile_conditions_sets_T_e_right_bc_correctly(
      self, T_e_right_bc, expected_initial_value, expected_second_value
  ):
    """Tests that T_e_right_bc is set correctly."""
    pc = profile_conditions.ProfileConditions(
        T_e={0: {0: 1.0, 1: 2.0}, 1.5: {0: 100.0, 1: 200.0}},
        T_e_right_bc=T_e_right_bc,
    )
    geo = geometry_pydantic_model.CircularConfig().build_geometry()
    torax_pydantic.set_grid(pc, geo.torax_mesh)
    dcs = pc.build_dynamic_params(t=0.0)
    self.assertEqual(dcs.T_e_right_bc, expected_initial_value)
    dcs = pc.build_dynamic_params(t=1.5)
    self.assertEqual(dcs.T_e_right_bc, expected_second_value)

  @parameterized.named_parameters(
      ('no boundary condition', None, 2.0, 200.0),
      ('boundary condition provided', 3, 3, 3),
  )
  def test_profile_conditions_sets_T_i_right_bc_correctly(
      self, T_i_right_bc, expected_initial_value, expected_second_value
  ):
    """Tests that T_i_right_bc is set correctly."""
    pc = profile_conditions.ProfileConditions(
        T_i={0: {0: 1.0, 1: 2.0}, 1.5: {0: 100.0, 1: 200.0}},
        T_i_right_bc=T_i_right_bc,
    )
    geo = geometry_pydantic_model.CircularConfig().build_geometry()
    torax_pydantic.set_grid(pc, geo.torax_mesh)
    dcs = pc.build_dynamic_params(t=0.0)
    self.assertEqual(dcs.T_i_right_bc, expected_initial_value)
    dcs = pc.build_dynamic_params(t=1.5)
    self.assertEqual(dcs.T_i_right_bc, expected_second_value)

  @parameterized.named_parameters(
      ('no boundary condition', None, 2.0e20, 200.0e20),
      ('boundary condition provided', 3.0e20, 3.0e20, 3.0e20),
  )
  def test_profile_conditions_sets_n_e_right_bc_correctly(
      self, n_e_right_bc, expected_initial_value, expected_second_value
  ):
    """Tests that n_e_right_bc is set correctly."""

    config = default_configs.get_default_config_dict()
    config['profile_conditions'] = {
        'n_e': {0: {0: 1.0e20, 1: 2.0e20}, 1.5: {0: 100.0e20, 1: 200.0e20}},
        'n_e_right_bc': n_e_right_bc,
    }
    torax_config = model_config.ToraxConfig.from_dict(config)
    dcs_provider = (
        build_runtime_params.DynamicRuntimeParamsSliceProvider.from_config(
            torax_config
        )
    )
    dcs = dcs_provider(t=0.0).profile_conditions
    self.assertEqual(dcs.n_e_right_bc, expected_initial_value)
    if n_e_right_bc is None:
      self.assertEqual(dcs.n_e_right_bc_is_fGW, dcs.n_e_nbar_is_fGW)
      self.assertFalse(dcs.n_e_right_bc_is_absolute)
    else:
      self.assertTrue(dcs.n_e_right_bc_is_absolute)
    dcs = dcs_provider(t=1.5).profile_conditions
    self.assertEqual(dcs.n_e_right_bc, expected_second_value)
    if n_e_right_bc is None:
      self.assertEqual(dcs.n_e_right_bc_is_fGW, dcs.n_e_nbar_is_fGW)
      self.assertFalse(dcs.n_e_right_bc_is_absolute)
    else:
      self.assertTrue(dcs.n_e_right_bc_is_absolute)

  @parameterized.named_parameters(
      ('no psi provided', None, None, None),
      (
          'constant psi provided',
          3.0,
          np.array([3.0, 3.0, 3.0, 3.0]),
          np.array([3.0, 3.0, 3.0, 3.0]),
      ),
      (
          'rho dependent, time independent psi provided',
          {0: 1.0, 1: 2.0},
          np.array([1.125, 1.375, 1.625, 1.875]),
          np.array([1.125, 1.375, 1.625, 1.875]),
      ),
      (
          'rho dependent, time dependent psi provided',
          {0: {0: 1.0, 1: 2.0}, 1.5: {0: 100.0, 1: 200.0}},
          np.array([1.125, 1.375, 1.625, 1.875]),
          np.array([112.5, 137.5, 162.5, 187.5]),
      ),
  )
  def test_profile_conditions_sets_psi_correctly(
      self, psi, expected_initial_value, expected_second_value
  ):
    """Tests that psi is set correctly."""
    geo = geometry_pydantic_model.CircularConfig(n_rho=4).build_geometry()
    pc = profile_conditions.ProfileConditions(
        psi=psi,
    )
    torax_pydantic.set_grid(pc, geo.torax_mesh)
    dcs = pc.build_dynamic_params(t=0.0)
    if psi is None:
      self.assertIsNone(dcs.psi)
    else:
      np.testing.assert_allclose(dcs.psi, expected_initial_value)
    dcs = pc.build_dynamic_params(t=1.5)
    if psi is None:
      self.assertIsNone(dcs.psi)
    else:
      np.testing.assert_allclose(dcs.psi, expected_second_value)

  @parameterized.named_parameters(
      dict(testcase_name='float', values=1.0, raises=True),
      dict(testcase_name='int', values=1, raises=True),
      dict(
          testcase_name='invalid dict shortcut',
          values={0.0: 0.1, 0.9: 1.0},
          raises=True,
      ),
      dict(
          testcase_name='valid dict shortcut',
          values={0.0: 0.1, 1.0: 1.0},
          raises=False,
      ),
      dict(
          testcase_name='invalid dict',
          values={0.0: {0.1: 0.1, 0.9: 1.0}},
          raises=True,
      ),
      dict(
          testcase_name='valid dict',
          values={0.0: {0.1: 0.1, 1.0: 1.0}},
          raises=False,
      ),
      dict(
          testcase_name='invalid numpy shortcut',
          values=(np.array([0.1, 0.9]), np.array([0.1, 1.0])),
          raises=True,
      ),
      dict(
          testcase_name='valid numpy shortcut',
          values=(np.array([0.0, 1.0]), np.array([0.1, 1.0])),
          raises=False,
      ),
      dict(
          testcase_name='invalid numpy',
          values=(
              np.array([0.0]),
              np.array([0.0, 0.9]),
              np.array([[0.1, 1.0]]),
          ),
          raises=True,
      ),
      dict(
          testcase_name='valid numpy',
          values=(
              np.array([0.0]),
              np.array([0.0, 1.0]),
              np.array([[1.0, 1.0]]),
          ),
          raises=False,
      ),
      dict(
          testcase_name='invalid xarray',
          values=xr.DataArray(
              data=np.array([[0.1, 1.0]]),
              dims=['time', interpolated_param.RHO_NORM],
              coords={interpolated_param.RHO_NORM: [0.0, 0.9], 'time': [0.0]},
          ),
          raises=True,
      ),
      dict(
          testcase_name='valid xarray',
          values=xr.DataArray(
              data=np.array([[0.1, 1.0]]),
              dims=['time', interpolated_param.RHO_NORM],
              coords={interpolated_param.RHO_NORM: [0.0, 1.0], 'time': [0.0]},
          ),
          raises=False,
      ),
  )
  def test_profile_conditions_raises_error_if_boundary_condition_not_defined(
      self,
      values,
      raises,
  ):
    """Tests that an error is raised if the boundary condition is not defined."""
    if raises:
      with self.assertRaisesRegex(
          pydantic.ValidationError, 'must include a rho=1.0 boundary'
      ):
        profile_conditions.ProfileConditions(
            T_i=values,
            T_i_right_bc=None,
        )
    else:
      profile_conditions.ProfileConditions(
          T_i=values,
          T_i_right_bc=None,
      )

  @parameterized.named_parameters(
      dict(
          testcase_name='valid_Ip',
          config_overrides={'Ip': 1e4},
      ),
      dict(
          testcase_name='invalid_Ip_too_low',
          config_overrides={'Ip': 1e2},
          expected_error_msg='below the minimum threshold',
      ),
      dict(
          testcase_name='invalid_Ip_time_varying_too_low',
          config_overrides={'Ip': {0.0: 5e3, 1.0: 1e2}},
          expected_error_msg='below the minimum threshold',
      ),
  )
  def test_Ip_order_of_magnitude_validation(
      self, config_overrides, expected_error_msg=None
  ):
    if expected_error_msg:
      with self.assertRaisesRegex(ValueError, expected_error_msg):
        profile_conditions.ProfileConditions(**config_overrides)
    else:
      profile_conditions.ProfileConditions(**config_overrides)

  @parameterized.named_parameters(
      dict(
          testcase_name='valid_nbar_m3',
          config_overrides={
              'nbar': 1e20,
              'normalize_n_e_to_nbar': True,
              'n_e_nbar_is_fGW': False,
          },
      ),
      dict(
          testcase_name='invalid_nbar_m3_too_low',
          config_overrides={
              'nbar': 1e9,
              'normalize_n_e_to_nbar': True,
              'n_e_nbar_is_fGW': False,
          },
          expected_error_msg='below the minimum threshold',
      ),
      dict(
          testcase_name='nbar_m3_not_normalized_no_error',
          config_overrides={
              'nbar': 1e9,
              'normalize_n_e_to_nbar': False,
              'n_e_nbar_is_fGW': False,
          },
      ),
      dict(
          testcase_name='valid_nbar_fGW',
          config_overrides={
              'nbar': 0.5,
              'normalize_n_e_to_nbar': True,
              'n_e_nbar_is_fGW': True,
          },
      ),
      dict(
          testcase_name='invalid_nbar_fGW_too_high',
          config_overrides={
              'nbar': 1.1e2,
              'normalize_n_e_to_nbar': True,
              'n_e_nbar_is_fGW': True,
          },
          expected_error_msg='above the maximum threshold',
      ),
      dict(
          testcase_name='nbar_fGW_too_low_but_not_used_so_no_error',
          config_overrides={
              'nbar': 1.1e2,
              'n_e': {0: {0: 0.85, 1: 0.85}},
              'normalize_n_e_to_nbar': False,
              'n_e_nbar_is_fGW': True,
          },
      ),
      dict(
          testcase_name='invalid_nbar_m3_time_varying_too_low',
          config_overrides={
              'nbar': {0: 1e20, 1: 1e9},
              'normalize_n_e_to_nbar': True,
              'n_e_nbar_is_fGW': False,
          },
          expected_error_msg='below the minimum threshold',
      ),
  )
  def test_nbar_order_of_magnitude_validation(
      self, config_overrides, expected_error_msg=None
  ):
    if expected_error_msg:
      with self.assertRaisesRegex(ValueError, expected_error_msg):
        profile_conditions.ProfileConditions(**config_overrides)
    else:
      profile_conditions.ProfileConditions(**config_overrides)

  @parameterized.named_parameters(
      dict(
          testcase_name='valid_ne_m3',
          config_overrides={
              'n_e': {0: {0: 1e20, 1: 1e20}},
              'normalize_n_e_to_nbar': False,
              'n_e_nbar_is_fGW': False,
          },
      ),
      dict(
          testcase_name='invalid_ne_m3_too_low',
          config_overrides={
              'n_e': {0: {0: 1e11, 0.5: 1e9, 1: 1e11}},
              'normalize_n_e_to_nbar': False,
              'n_e_nbar_is_fGW': False,
          },
          expected_error_msg='below the minimum threshold',
      ),
      dict(
          testcase_name='valid_ne_m3_normalized_to_nbar',
          config_overrides={
              'n_e': {0: {0: 1e9, 1: 1e9}},
              'normalize_n_e_to_nbar': True,
              'n_e_nbar_is_fGW': False,
          },
      ),
      dict(
          testcase_name='valid_ne_fGW',
          config_overrides={
              'n_e': {0: {0: 0.5, 1: 0.5}},
              'normalize_n_e_to_nbar': False,
              'n_e_nbar_is_fGW': True,
          },
      ),
      dict(
          testcase_name='invalid_ne_fGW_too_high',
          config_overrides={
              'n_e': {0: {0: 0.5, 0.5: 1.1e2, 1: 0.5}},
              'normalize_n_e_to_nbar': False,
              'n_e_nbar_is_fGW': True,
          },
          expected_error_msg='above the maximum threshold',
      ),
  )
  def test_ne_profile_order_of_magnitude_validation(
      self, config_overrides, expected_error_msg=None
  ):
    if expected_error_msg:
      with self.assertRaisesRegex(ValueError, expected_error_msg):
        profile_conditions.ProfileConditions(**config_overrides)
    else:
      profile_conditions.ProfileConditions(**config_overrides)

  @parameterized.named_parameters(
      dict(
          testcase_name='valid_ne_right_bc_m3',
          config_overrides={'n_e_right_bc': 1e20, 'n_e_right_bc_is_fGW': False},
      ),
      dict(
          testcase_name='invalid_ne_right_bc_m3_too_low',
          config_overrides={'n_e_right_bc': 1e9, 'n_e_right_bc_is_fGW': False},
          expected_error_msg='below the minimum threshold',
      ),
      dict(
          testcase_name='valid_ne_right_bc_fGW',
          config_overrides={'n_e_right_bc': 0.5, 'n_e_right_bc_is_fGW': True},
      ),
      dict(
          testcase_name='invalid_ne_right_bc_fGW_too_high',
          config_overrides={'n_e_right_bc': 1.1e2, 'n_e_right_bc_is_fGW': True},
          expected_error_msg='above the maximum threshold',
      ),
  )
  def test_ne_right_bc_order_of_magnitude_validation(
      self, config_overrides, expected_error_msg=None
  ):
    if expected_error_msg:
      with self.assertRaisesRegex(ValueError, expected_error_msg):
        profile_conditions.ProfileConditions(**config_overrides)
    else:
      profile_conditions.ProfileConditions(**config_overrides)

  @parameterized.named_parameters(
      dict(
          testcase_name='valid_Te',
          config_overrides={'T_e': {0: {0: 10.0, 1: 1.0}}},
      ),
      dict(
          testcase_name='invalid_Te_too_high',
          config_overrides={'T_e': {0: {0: 1.1e3, 1: 1.0}}},
          expected_error_msg='above the maximum threshold',
      ),
      dict(
          testcase_name='invalid_Te_time_varying_too_high',
          config_overrides={
              'T_e': {0: {0: 10.0, 1: 1.0}, 1.0: {0: 1.1e3, 1: 1.0}}
          },
          expected_error_msg='above the maximum threshold',
      ),
      dict(
          testcase_name='valid_Ti',
          config_overrides={'T_i': {0: {0: 10.0, 1: 1.0}}},
      ),
      dict(
          testcase_name='invalid_Ti_too_high',
          config_overrides={'T_i': {0: {0: 1.1e3, 1: 1.0}}},
          expected_error_msg='above the maximum threshold',
      ),
  )
  def test_temperature_profile_order_of_magnitude_validation(
      self, config_overrides, expected_error_msg=None
  ):
    if expected_error_msg:
      with self.assertRaisesRegex(ValueError, expected_error_msg):
        profile_conditions.ProfileConditions(**config_overrides)
    else:
      profile_conditions.ProfileConditions(**config_overrides)

  @parameterized.named_parameters(
      dict(
          testcase_name='valid_Te_right_bc',
          config_overrides={'T_e_right_bc': 0.1},
      ),
      dict(
          testcase_name='invalid_Te_right_bc_too_high',
          config_overrides={'T_e_right_bc': 1e2},
          expected_error_msg='above the maximum threshold',
      ),
      dict(
          testcase_name='valid_Ti_right_bc',
          config_overrides={'T_i_right_bc': 0.1},
      ),
      dict(
          testcase_name='invalid_Ti_right_bc_too_high',
          config_overrides={'T_i_right_bc': 1e2},
          expected_error_msg='above the maximum threshold',
      ),
      dict(
          testcase_name='invalid_Ti_right_bc_time_varying_too_high',
          config_overrides={'T_i_right_bc': {0: 10.0, 1: 1.1e2}},
          expected_error_msg='above the maximum threshold',
      ),
  )
  def test_temperature_bc_order_of_magnitude_validation(
      self, config_overrides, expected_error_msg=None
  ):
    if expected_error_msg:
      with self.assertRaisesRegex(ValueError, expected_error_msg):
        profile_conditions.ProfileConditions(**config_overrides)
    else:
      profile_conditions.ProfileConditions(**config_overrides)

  def test_multiple_validation_errors(self):
    config_overrides = {
        'Ip': 1e2,
        'T_e': {0: {0: 2e3, 1: 1.0}, 1.0: {0: 1e6, 1: 1e10}},
        'T_i_right_bc': 1e2,
    }
    with self.assertRaisesRegex(ValueError, '3 errors were found'):
      profile_conditions.ProfileConditions(**config_overrides)


if __name__ == '__main__':
  absltest.main()

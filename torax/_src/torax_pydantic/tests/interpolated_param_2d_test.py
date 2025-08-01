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
from torax._src import jax_utils
from torax._src.geometry import pydantic_model as geometry_pydantic_model
from torax._src.torax_pydantic import interpolated_param_2d
from torax._src.torax_pydantic import model_base
import xarray as xr

RHO_NORM = 'rho_norm'
TIME_INTERPOLATION_MODE = 'time_interpolation_mode'
RHO_INTERPOLATION_MODE = 'rho_interpolation_mode'

_RHO_NORM_ARRAY = np.array([0.125, 0.375, 0.625, 0.875])
_VALUES_ARRAY = np.array([1.0, 2.0, 3.0, 4.0])


class InterpolatedParam2dTest(parameterized.TestCase):

  @parameterized.named_parameters(
      dict(
          testcase_name='2_tuple_input_t=0',
          time_rho_interpolated_input=(
              _RHO_NORM_ARRAY,
              _VALUES_ARRAY,
          ),
          nx=4,
          dx=0.25,
          time=0.0,
          expected_output=np.array([1.0, 2.0, 3.0, 4.0]),
      ),
      dict(
          testcase_name='2_tuple_input_t=1',
          time_rho_interpolated_input=(
              _RHO_NORM_ARRAY,
              _VALUES_ARRAY,
          ),
          nx=4,
          dx=0.25,
          time=1.0,
          expected_output=np.array([1.0, 2.0, 3.0, 4.0]),
      ),
      dict(
          testcase_name='2_tuple__list_input_t=1',
          time_rho_interpolated_input=(
              _RHO_NORM_ARRAY.tolist(),
              _VALUES_ARRAY.tolist(),
          ),
          nx=4,
          dx=0.25,
          time=1.0,
          expected_output=np.array([1.0, 2.0, 3.0, 4.0]),
      ),
      dict(
          testcase_name='3_tuple_input_t=0',
          time_rho_interpolated_input=(
              np.array([0.0, 1.0]),
              np.array([0.125, 0.375, 0.625, 0.875]),
              np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]),
          ),
          nx=4,
          dx=0.25,
          time=0.0,
          expected_output=np.array([1.0, 2.0, 3.0, 4.0]),
      ),
      dict(
          testcase_name='3_tuple_input_t=1',
          time_rho_interpolated_input=(
              np.array([0.0, 1.0]),
              _RHO_NORM_ARRAY,
              np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]),
          ),
          nx=4,
          dx=0.25,
          time=1.0,
          expected_output=np.array([5.0, 6.0, 7.0, 8.0]),
      ),
      dict(
          testcase_name='3_tuple_list_input_t=1',
          time_rho_interpolated_input=(
              [0.0, 1.0],
              _RHO_NORM_ARRAY,
              [[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]],
          ),
          nx=4,
          dx=0.25,
          time=1.0,
          expected_output=np.array([5.0, 6.0, 7.0, 8.0]),
      ),
      dict(
          testcase_name='3_tuple_input_t=0.5',
          time_rho_interpolated_input=(
              np.array([0.0, 1.0]),
              _RHO_NORM_ARRAY,
              np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]),
          ),
          nx=4,
          dx=0.25,
          time=0.5,
          expected_output=np.array([3.0, 4.0, 5.0, 6.0]),
      ),
      dict(
          testcase_name='3_tuple_rho_time_input_t=0.5',
          time_rho_interpolated_input=(
              np.array([0.0, 1.0]),
              [_RHO_NORM_ARRAY, _RHO_NORM_ARRAY],
              np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]),
          ),
          nx=4,
          dx=0.25,
          time=0.5,
          expected_output=np.array([3.0, 4.0, 5.0, 6.0]),
      ),
      dict(
          testcase_name='3_tuple_input_t=0_time_step_interpolation',
          time_rho_interpolated_input=(
              (
                  np.array([0.0, 1.0]),
                  _RHO_NORM_ARRAY,
                  np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]),
              ),
              {
                  TIME_INTERPOLATION_MODE: 'step',
                  RHO_INTERPOLATION_MODE: 'piecewise_linear',
              },
          ),
          nx=4,
          dx=0.25,
          time=0.0,
          expected_output=np.array([1.0, 2.0, 3.0, 4.0]),
      ),
      dict(
          testcase_name='3_tuple_input_t=1_time_step_interpolation',
          time_rho_interpolated_input=(
              (
                  np.array([0.0, 1.0]),
                  _RHO_NORM_ARRAY,
                  np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]),
              ),
              {
                  TIME_INTERPOLATION_MODE: 'step',
                  RHO_INTERPOLATION_MODE: 'piecewise_linear',
              },
          ),
          nx=4,
          dx=0.25,
          time=1.01,
          expected_output=np.array([5.0, 6.0, 7.0, 8.0]),
      ),
      dict(
          testcase_name='3_tuple_input_t=0.5_time_step_interpolation',
          time_rho_interpolated_input=(
              (
                  np.array([0.0, 1.0]),
                  _RHO_NORM_ARRAY,
                  np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]),
              ),
              {
                  TIME_INTERPOLATION_MODE: 'step',
                  RHO_INTERPOLATION_MODE: 'piecewise_linear',
              },
          ),
          nx=4,
          dx=0.25,
          time=0.5,
          expected_output=np.array([1.0, 2.0, 3.0, 4.0]),
      ),
      dict(
          testcase_name='xarray_input_t=0.0',
          time_rho_interpolated_input=xr.DataArray(
              data=np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]),
              coords={'time': [0.0, 1.0], 'rho_norm': _RHO_NORM_ARRAY},
          ),
          nx=4,
          dx=0.25,
          time=0.0,
          expected_output=np.array([1.0, 2.0, 3.0, 4.0]),
      ),
      dict(
          testcase_name='xarray_input_t=1',
          time_rho_interpolated_input=xr.DataArray(
              data=np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]),
              coords={'time': [0.0, 1.0], 'rho_norm': _RHO_NORM_ARRAY},
          ),
          nx=4,
          dx=0.25,
          time=1.0,
          expected_output=np.array([5.0, 6.0, 7.0, 8.0]),
      ),
      dict(
          testcase_name='xarray_input_t=0.5',
          time_rho_interpolated_input=xr.DataArray(
              data=np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]),
              coords={'time': [0.0, 1.0], 'rho_norm': _RHO_NORM_ARRAY},
          ),
          nx=4,
          dx=0.25,
          time=0.5,
          expected_output=np.array([3.0, 4.0, 5.0, 6.0]),
      ),
      dict(
          testcase_name='xarray_input_full_t=0.5',
          time_rho_interpolated_input=xr.DataArray(
              data=np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]),
              coords={
                  'time': [0.0, 1.0],
                  'rho_norm': (
                      ('time', 'value'),
                      np.array([_RHO_NORM_ARRAY, _RHO_NORM_ARRAY]),
                  ),
              },
              dims=['time', 'value'],
          ),
          nx=4,
          dx=0.25,
          time=0.5,
          expected_output=np.array([3.0, 4.0, 5.0, 6.0]),
      ),
      dict(
          testcase_name='single_dict_t=0',
          time_rho_interpolated_input={
              0.25: 18.0,
              0.95: 5.0,
          },
          nx=4,
          dx=0.5,
          time=0.0,
          expected_output=np.array([18.0, 8.714286, 5.0, 5.0]),
      ),
      # Single dict represents a constant (in time) radial profile.
      dict(
          testcase_name='single_dict_t=0.5',
          time_rho_interpolated_input={
              0.475: 18.0,
              0.9: 5.0,
          },
          nx=4,
          dx=0.95,
          time=0.5,
          expected_output=np.array([18.0, 5.0, 5.0, 5.0]),
      ),
      dict(
          testcase_name='single_dict_t=0.0',
          time_rho_interpolated_input={
              0.475: 18.0,
              0.9: 5.0,
          },
          nx=4,
          dx=0.95,
          time=0.0,
          expected_output=np.array([18.0, 5.0, 5.0, 5.0]),
      ),
      dict(
          testcase_name='nested_dict_t=0.5',
          time_rho_interpolated_input={
              0.0: {0.125: 1.0, 0.375: 2.0, 0.625: 3.0, 0.875: 4.0},
              1.0: {0.125: 5.0, 0.375: 6.0, 0.625: 7.0, 0.875: 8.0},
          },
          nx=4,
          dx=0.25,
          time=0.5,
          expected_output=np.array([3.0, 4.0, 5.0, 6.0]),
      ),
      # Single float represents a constant (in time and rho) profile.
      dict(
          testcase_name='float_t=0.0',
          time_rho_interpolated_input=1.0,
          nx=4,
          dx=0.5,
          time=0.0,
          expected_output=np.array([1.0, 1.0, 1.0, 1.0]),
      ),
      dict(
          testcase_name='float_t=5.0',
          time_rho_interpolated_input=1.0,
          nx=4,
          dx=0.5,
          time=5.0,
          expected_output=np.array([1.0, 1.0, 1.0, 1.0]),
      ),
  )
  def test_time_varying_array_parses_inputs_correctly(
      self, time_rho_interpolated_input, nx, dx, time, expected_output
  ):
    interpolated = interpolated_param_2d.TimeVaryingArray.model_validate(
        time_rho_interpolated_input
    )
    grid = interpolated_param_2d.Grid1D(nx=nx, dx=dx)
    interpolated_param_2d.set_grid(interpolated, grid=grid)

    np.testing.assert_allclose(
        interpolated.get_value(t=time),
        expected_output,
    )

    self.assertEqual(interpolated, interpolated)

  def test_right_boundary_conditions_defined(self):
    """Tests that right_boundary_conditions_defined works correctly."""

    with self.subTest('float_input'):
      # A single float is interpreted as defined at rho=0.
      self.assertFalse(
          interpolated_param_2d.TimeVaryingArray.model_validate(
              1.0
          ).right_boundary_conditions_defined
      )

    with self.subTest('xarray'):
      value = xr.DataArray(
          data=np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
          coords={'time': [0.0, 1.0], 'rho_norm': [0.25, 0.5, 1.0]},
      )
      self.assertTrue(
          interpolated_param_2d.TimeVaryingArray.model_validate(
              value
          ).right_boundary_conditions_defined
      )

  def test_raises_error_when_value_is_not_positive(self):
    class TestModel(model_base.BaseModelFrozen):
      a: interpolated_param_2d.PositiveTimeVaryingArray

    with self.assertRaisesRegex(pydantic.ValidationError, 'be positive.'):
      TestModel.model_validate({'a': {0.0: {0.0: 1.0, 1: -1.0}}})

  def test_set_grid(self):

    class Test1(model_base.BaseModelFrozen):
      x: float
      y: interpolated_param_2d.TimeVaryingArray

    class Test2(model_base.BaseModelFrozen):
      x: Test1  # pytype: disable=invalid-annotation
      y: interpolated_param_2d.TimeVaryingArray
      z: int

    m1 = Test1(
        x=1.0, y=interpolated_param_2d.TimeVaryingArray.model_validate(1.0)
    )
    m2 = Test2(
        x=m1, y=interpolated_param_2d.TimeVaryingArray.model_validate(2.0), z=5
    )
    grid = geometry_pydantic_model.CircularConfig().build_geometry().torax_mesh

    with self.subTest('set_grid_success'):
      interpolated_param_2d.set_grid(m2, grid)
      chex.assert_trees_all_equal(m2.x.y.grid.face_centers, grid.face_centers)  # pytype: disable=attribute-error
      chex.assert_trees_all_equal(m2.x.y.grid.cell_centers, grid.cell_centers)  # pytype: disable=attribute-error
      chex.assert_trees_all_equal(m2.y.grid.face_centers, grid.face_centers)  # pytype: disable=attribute-error
      chex.assert_trees_all_equal(m2.y.grid.cell_centers, grid.cell_centers)  # pytype: disable=attribute-error

    with self.subTest('set_grid_already_set'):
      with self.assertRaisesRegex(RuntimeError, '`grid` is already set'):
        interpolated_param_2d.set_grid(m2, grid)

    with self.subTest('set_grid_already_set_force'):
      grid._update_fields({'nx': grid.nx + 1})
      interpolated_param_2d.set_grid(m2, grid, mode='force')
      chex.assert_trees_all_equal(m2.y.grid.face_centers, grid.face_centers)  # pytype: disable=attribute-error
      # Ensure that setting the grid does not re-use the grid object.
      self.assertTrue(m2._has_unique_submodels)

    with self.subTest('set_grid_already_set_relaxed'):
      interpolated_param_2d.set_grid(m2, grid, mode='relaxed')

  def test_test_equality_cached_property(self):
    array_1 = interpolated_param_2d.TimeVaryingArray.model_validate(1.0)
    array_2 = interpolated_param_2d.TimeVaryingArray.model_validate(1.0)

    grid = geometry_pydantic_model.CircularConfig().build_geometry().torax_mesh
    interpolated_param_2d.set_grid(array_1, grid)
    interpolated_param_2d.set_grid(array_2, grid)

    # Check that the cached property does not break equality.
    self.assertEqual(array_1, array_2)
    array_1.get_value(t=0.0)
    self.assertEqual(array_1, array_2)

  def test_grid1d_cache(self):
    grid_1 = interpolated_param_2d.Grid1D(nx=10, dx=0.1)
    grid_2 = interpolated_param_2d.Grid1D(nx=10, dx=0.1)

    # Ensure cell_centers and face_centers are cached, and use the same
    # underlying NumPy arrays.
    self.assertIs(grid_1.cell_centers, grid_2.cell_centers)
    self.assertIs(grid_1.face_centers, grid_2.face_centers)

  def test_sorted_keys(self):

    value = xr.DataArray(
        data=np.array([[4.0, 5.0, 6.0], [1.0, 2.0, 3.0]]),
        coords={
            'time': [
                1.0,
                0.0,
            ],
            'rho_norm': [0.25, 0.5, 1.0],
        },
    )
    inter = interpolated_param_2d.TimeVaryingArray.model_validate(value)
    times = list(inter.value.keys())
    self.assertEqual(times, sorted(times))

  def test_time_varying_array_under_jit(self):
    time_rho_interpolated_input = (_RHO_NORM_ARRAY, _VALUES_ARRAY)
    interpolated = interpolated_param_2d.TimeVaryingArray.model_validate(
        time_rho_interpolated_input
    )
    grid = interpolated_param_2d.Grid1D(nx=4, dx=0.25)
    interpolated_param_2d.set_grid(interpolated, grid=grid)

    @jax.jit
    def f(
        time_varying_array: interpolated_param_2d.TimeVaryingArray,
        t: chex.Numeric,
    ):
      return time_varying_array.get_value(t)

    with self.subTest('jit_result_matches_non_jit'):
      np.testing.assert_allclose(
          f(interpolated, 0.0), interpolated.get_value(t=0.0)
      )
      self.assertEqual(jax_utils.get_number_of_compiles(f), 1)

    with self.subTest('jit_cache_hit_only_once'):
      values_array_new = _VALUES_ARRAY + 1.0
      time_rho_interpolated_input = (_RHO_NORM_ARRAY, values_array_new)
      interpolated_new = interpolated_param_2d.TimeVaryingArray.model_validate(
          time_rho_interpolated_input
      )
      interpolated_param_2d.set_grid(interpolated_new, grid=grid)
      np.testing.assert_allclose(
          f(interpolated_new, 0.0), interpolated_new.get_value(t=0.0)
      )
      self.assertEqual(jax_utils.get_number_of_compiles(f), 1)

    with self.subTest('changing_shape_causes_new_compile'):
      values_array_new = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
      rho_norm_array_new = np.array([0.125, 0.375, 0.625, 0.875, 0.925])
      time_rho_interpolated_input = (rho_norm_array_new, values_array_new)
      interpolated_new_shape = (
          interpolated_param_2d.TimeVaryingArray.model_validate(
              time_rho_interpolated_input
          )
      )
      interpolated_param_2d.set_grid(interpolated_new_shape, grid=grid)
      np.testing.assert_allclose(
          f(interpolated_new_shape, 0.0),
          interpolated_new_shape.get_value(t=0.0),
      )
      self.assertEqual(jax_utils.get_number_of_compiles(f), 2)

  def test_time_varying_array_has_all_cached_interpolated_params(self):
    time_rho_interpolated_input = (_RHO_NORM_ARRAY, _VALUES_ARRAY)
    interpolated = interpolated_param_2d.TimeVaryingArray.model_validate(
        time_rho_interpolated_input
    )
    grid = interpolated_param_2d.Grid1D(nx=4, dx=0.25)
    interpolated_param_2d.set_grid(interpolated, grid=grid)

    @jax.jit
    def f(
        time_varying_array: interpolated_param_2d.TimeVaryingArray,
        t: chex.Numeric,
    ):
      cell_values = time_varying_array.get_value(t, grid_type='cell')
      face_values = time_varying_array.get_value(t, grid_type='face')
      face_right_values = time_varying_array.get_value(
          t, grid_type='face_right'
      )
      return cell_values, face_values, face_right_values

    cell_values, face_values, face_right_values = f(interpolated, 0.0)
    np.testing.assert_allclose(
        cell_values, interpolated.get_value(t=0.0, grid_type='cell')
    )
    np.testing.assert_allclose(
        face_values, interpolated.get_value(t=0.0, grid_type='face')
    )
    np.testing.assert_allclose(
        face_right_values,
        interpolated.get_value(t=0.0, grid_type='face_right'),
    )


if __name__ == '__main__':
  absltest.main()

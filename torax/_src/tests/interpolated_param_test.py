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

import random

from absl.testing import absltest
from absl.testing import parameterized
import chex
import jax
from jax import numpy as jnp
import numpy as np
from torax._src import interpolated_param
from torax._src import jax_utils
import xarray as xr


class InterpolatedParamTest(parameterized.TestCase):

  @parameterized.parameters(
      (
          (
              np.array([0.0]),
              np.array([
                  42.0,
              ]),
          ),
      ),
      (
          (
              np.array([0.0]),
              np.array([
                  1.0,
              ]),
          ),
      ),
  )
  def test_single_value_param_always_return_constant(self, expected_output):
    """Tests that when passed a single value this is always returned."""
    single_value_param = interpolated_param.InterpolatedVarSingleAxis(
        expected_output
    )
    np.testing.assert_allclose(
        single_value_param.get_value(-1), expected_output[1]
    )
    np.testing.assert_allclose(
        single_value_param.get_value(0), expected_output[1]
    )
    np.testing.assert_allclose(
        single_value_param.get_value(1), expected_output[1]
    )

  @parameterized.parameters(
      (
          (np.array([0.0, 1.0, 2.0, 3.0]), np.array([0.0, 1.0, 2.0, 3.0])),
          1.5,
          1.5,
          interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
      ),
      (
          (np.array([0.0, 1.0, 2.0, 3.0]), np.array([1.0, 2.0, 4.0, 8.0])),
          0.5,
          1.5,
          interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
      ),
      (
          (np.array([0.0, 1.0, 2.0, 3.0]), np.array([1.0, 2.0, 4.0, 8.0])),
          1.5,
          3,
          interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
      ),
      (
          (np.array([1.0, 3.0, 5.0, 7.0]), np.array([1.0, 2.0, 4.0, 8.0])),
          6.5,
          7,
          interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
      ),
      # outside range uses last value.
      (
          (np.array([12.0, 14.0, 18.0, 19.0]), np.array([10.0, 9.0, 8.0, 4.0])),
          20,
          4,
          interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
      ),
      (
          (
              np.array([0.0]),
              np.array([
                  7.0,
              ]),
          ),
          1.0,
          7.0,
          interpolated_param.InterpolationMode.STEP,
      ),
      (
          (np.array([0.0, 2.0, 3.0]), np.array([1.0, 7.0, -1.0])),
          -1.0,
          1.0,
          interpolated_param.InterpolationMode.STEP,
      ),
      (
          (np.array([0.0, 2.0, 3.0]), np.array([1.0, 7.0, -1.0])),
          1.0,
          1.0,
          interpolated_param.InterpolationMode.STEP,
      ),
      (
          (np.array([0.0, 2.0, 3.0]), np.array([1.0, 7.0, -1.0])),
          2.6,
          7.0,
          interpolated_param.InterpolationMode.STEP,
      ),
      (
          (np.array([0.0, 2.0, 3.0]), np.array([1.0, 7.0, -1.0])),
          4.0,
          -1.0,
          interpolated_param.InterpolationMode.STEP,
      ),
      (
          (np.array([0.0, 2.0, 3.0]), np.array([0.0, 1.0, 0.0])),
          1.5,
          0.75,
          interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
      ),
      (
          (np.array([0.0, 2.0, 3.0]), np.array([0.0, 1.0, 0.0])),
          1.0,
          0.0,
          interpolated_param.InterpolationMode.STEP,
      ),
      (
          (np.array([0.0, 2.0, 3.0]), np.array([0.0, 1.0, 0.0])),
          2.5,
          1.0,
          interpolated_param.InterpolationMode.STEP,
      ),
      (
          (np.array([0.0, 1.0]), np.array([[3.0, 4.0, 5.0], [6.0, 7.0, 8.0]])),
          0.5,
          np.array([4.5, 5.5, 6.5]),
          interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
      ),
      (
          (np.array([0.0, 1.0]), np.array([[3.0, 4.0, 5.0], [6.0, 7.0, 8.0]])),
          0.5,
          np.array([3.0, 4.0, 5.0]),
          interpolated_param.InterpolationMode.STEP,
      ),
  )
  def test_multi_value_range_returns_expected_output(
      self,
      values,
      x,
      expected_output,
      interpolation_mode,
  ):
    """Tests that the range returns the expected output."""
    multi_val_range = interpolated_param.InterpolatedVarSingleAxis(
        values, interpolation_mode
    )
    np.testing.assert_allclose(
        multi_val_range.get_value(x=x),
        expected_output,
    )

  @parameterized.parameters(
      (interpolated_param._PiecewiseLinearInterpolatedParam,),
      (interpolated_param._StepInterpolatedParam,),
  )
  def test_interpolated_param_1d_xs_and_1d_or_2d_ys(self, range_class):
    """Tests that the interpolated_param only take 1D inputs."""
    range_class(
        xs=jnp.array([1.0, 2.0, 3.0, 4.0]),
        ys=jnp.array([1.0, 2.0, 3.0, 4.0]),
    )
    range_class(
        xs=jnp.arange(2, dtype=jnp.float64).reshape((2)),
        ys=jnp.arange(6, dtype=jnp.float64).reshape((2, 3)),
    )
    with self.assertRaises(AssertionError):
      range_class(
          xs=jnp.array(1.0),
          ys=jnp.array(2.0),
      )
    with self.assertRaises(ValueError):
      range_class(
          xs=jnp.arange(2).reshape((2)),
          ys=jnp.arange(6).reshape((2, 3, 1)),
      )

  @parameterized.parameters(
      (interpolated_param._PiecewiseLinearInterpolatedParam,),
      (interpolated_param._StepInterpolatedParam,),
  )
  def test_interpolated_param_need_xs_ys_same_shape(self, range_class):
    """Tests the xs and ys inputs have to have the same shape."""
    range_class(
        xs=jnp.array([1.0, 2.0, 3.0, 4.0]),
        ys=jnp.array([1.0, 2.0, 3.0, 4.0]),
    )
    with self.assertRaises(ValueError):
      range_class(
          xs=jnp.array([1.0, 2.0, 3.0, 4.0]),
          ys=jnp.array([1.0, 2.0, 3.0, 4.0, 5.0]),
      )

  @parameterized.parameters(
      interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
      interpolated_param.InterpolationMode.STEP,
  )
  def test_interpolated_param_is_invariant_to_xs_order(
      self,
      interpolation_mode: interpolated_param.InterpolationMode,
  ):
    with self.assertRaises(RuntimeError):
      interpolated_param.InterpolatedVarSingleAxis(
          value=(
              jnp.array([4.0, 2.0, 1.0, 3.0]),
              jnp.array([4.0, 2.0, 1.0, 3.0]),
          ),
          interpolation_mode=interpolation_mode,
      )

  @parameterized.named_parameters(
      # One line cases.
      {
          'testcase_name': 'one_line_case_1',
          'values': {
              1.0: (
                  np.array([0.0, 0.3, 0.9, 1.0]),
                  np.array([0.0, 0.5, 1.0, 1.0]),
              )
          },
          'x': random.uniform(0, 2),
          'y': 0.0,
          'expected_output': 0.0,
      },
      {
          'testcase_name': 'one_line_case_2',
          'values': {
              1.0: (
                  np.array([0.0, 0.3, 0.9, 1.0]),
                  np.array([0.0, 0.5, 1.0, 1.0]),
              )
          },
          'x': random.uniform(0, 2),
          'y': 0.95,
          'expected_output': 1,
      },
      {
          'testcase_name': 'one_line_case_3',
          'values': {
              1.0: (
                  np.array([0.0, 0.3, 0.8, 1.0]),
                  np.array([0.0, 0.5, 1.0, 1.0]),
              )
          },
          'x': random.uniform(0, 2),
          'y': 0.7,
          'expected_output': 0.9,
      },
      # Two lines cases, constant at x=0, linear between 0 and 1 at x=1.
      {
          'testcase_name': 'two_line_case_1',
          'values': {
              0.0: (
                  np.array(
                      [0.0],
                  ),
                  np.array([0.0]),
              ),
              1.0: (
                  np.array(
                      [0.0, 1.0],
                  ),
                  np.array([0.0, 1.0]),
              ),
          },
          'x': 0.0,
          'y': random.randrange(0, 1),
          'expected_output': 0.0,
      },
      {
          'testcase_name': 'two_line_case_2',
          'values': {
              0.0: (np.array([0.0]), np.array([0.0])),
              1.0: (np.array([0.0, 1.0]), np.array([0.0, 1.0])),
          },
          'x': 1.0,
          'y': 0.0,
          'expected_output': 0.0,
      },
      {
          'testcase_name': 'two_line_case_3',
          'values': {
              0.0: (np.array([0.0]), np.array([0.0])),
              1.0: (np.array([0.0, 1.0]), np.array([0.0, 1.0])),
          },
          'x': 1.0,
          'y': 1.0,
          'expected_output': 1.0,
      },
      {
          'testcase_name': 'two_line_case_4',
          'values': {
              0.0: (np.array([0.0]), np.array([0.0])),
              1.0: (np.array([0.0, 1.0]), np.array([0.0, 1.0])),
          },
          'x': 1.0,
          'y': 0.5,
          'expected_output': 0.5,
      },
      {
          'testcase_name': 'two_line_case_5',
          'values': {
              0.0: (np.array([0.0]), np.array([0.0])),
              1.0: (np.array([0.0, 1.0]), np.array([0.0, 1.0])),
          },
          'x': 0.5,
          'y': 0.5,
          'expected_output': 0.25,
      },
      {
          'testcase_name': 'two_line_case_6',
          'values': {
              0.0: (np.array([0.0]), np.array([0.0])),
              1.0: (np.array([0.0, 1.0]), np.array([0.0, 1.0])),
          },
          'x': 0.5,
          'y': 0.75,
          'expected_output': 0.375,
      },
      # Test cases with 4 interpolated lines along the x axis.
      # Case in between the first two lines.
      {
          'testcase_name': 'four_line_case_1',
          'values': {
              0.0: (np.array([0.0, 1.0]), np.array([0.0, 0.0])),
              1.0: (
                  np.array([0.0, 0.3, 0.8, 1.0]),
                  np.array([0.0, 0.5, 1.0, 1.0]),
              ),
              2.0: (np.array([0.0, 0.5]), np.array([1.0, 0.0])),
              3.0: (np.array([0.0, 1.0]), np.array([1.0, 0.0])),
          },
          'x': 0.5,
          'y': 0.5,
          'expected_output': 0.35,
      },
      # Case in between the second and third lines.
      {
          'testcase_name': 'four_line_case_2',
          'values': {
              0.0: (np.array([0.0, 1.0]), np.array([0.0, 0.0])),
              1.0: (
                  np.array([0.0, 0.3, 0.8, 1.0]),
                  np.array([0.0, 0.5, 1.0, 1.0]),
              ),
              2.0: (np.array([0.0, 0.5]), np.array([1.0, 0.0])),
              3.0: (np.array([0.0, 1.0]), np.array([1.0, 0.0])),
          },
          'x': 1.2,
          'y': 0.5,
          'expected_output': 0.56,
      },
      # Case in between the third and fourth lines.
      {
          'testcase_name': 'four_line_case_3',
          'values': {
              0.0: (np.array([0.0, 1.0]), np.array([0.0, 0.0])),
              1.0: (
                  np.array([0.0, 0.3, 0.8, 1.0]),
                  np.array([0.0, 0.5, 1.0, 1.0]),
              ),
              2.0: (np.array([0.0, 0.5]), np.array([1.0, 0.0])),
              3.0: (np.array([0.0, 1.0]), np.array([1.0, 0.0])),
          },
          'x': 2.8,
          'y': 0.5,
          'expected_output': 0.4,
      },
      # Case where y is an array.
      {
          'testcase_name': 'y_array_case',
          'values': {
              2.0: (np.array([0.0, 0.5]), np.array([1.0, 0.0])),
              3.0: (np.array([0.0, 1.0]), np.array([1.0, 0.0])),
          },
          'x': 2.8,
          'y': np.array([0.1, 0.5, 0.6]),
          'expected_output': np.array([
              0.88,
              0.4,
              0.32,
          ]),
      },
  )
  def test_interpolated_var_time_rho(self, values, x, y, expected_output):
    """Tests the doubly interpolated param gives correct outputs on 2D mesh."""
    interpolated_var_time_rho = interpolated_param.InterpolatedVarTimeRho(
        values, rho_norm=y
    )

    output = interpolated_var_time_rho.get_value(x=x)
    np.testing.assert_allclose(output, expected_output, atol=1e-6, rtol=1e-6)

  @parameterized.named_parameters(
      dict(
          testcase_name='xarray',
          values=xr.DataArray(
              data=np.array([1.0, 2.0, 4.0]),
              coords={'time': [0.0, 1.0, 2.0]},
          ),
          expected_output=(
              np.array([0.0, 1.0, 2.0]),
              np.array([1.0, 2.0, 4.0]),
          ),
      ),
      dict(
          testcase_name='constant_float',
          values=42.0,
          expected_output=(np.array([0.0]), np.array([42.0])),
      ),
      dict(
          testcase_name='mapping',
          values={0.0: 0.0, 1.0: 1.0, 2.0: 2.0, 3.0: 3.0},
          expected_output=(
              np.array([0.0, 1.0, 2.0, 3.0]),
              np.array([0.0, 1.0, 2.0, 3.0]),
          ),
      ),
      dict(
          testcase_name='numpy array',
          values=(
              np.array([
                  0.0,
                  1.0,
                  2.0,
              ]),
              np.array([1.0, 2.0, 4.0]),
          ),
          expected_output=(
              np.array([0.0, 1.0, 2.0]),
              np.array([1.0, 2.0, 4.0]),
          ),
      ),
      dict(
          testcase_name='batched numpy array',
          values=(
              np.array([0.0, 1.0]),
              np.array([[3.0, 4.0, 5.0], [6.0, 7.0, 8.0]]),
          ),
          expected_output=(
              np.array([0.0, 1.0]),
              np.array([[3.0, 4.0, 5.0], [6.0, 7.0, 8.0]]),
          ),
      ),
  )
  def test_convert_input_to_xs_ys(self, values, expected_output):
    """Test input conversion to numpy arrays."""
    x, y, _, _ = interpolated_param.convert_input_to_xs_ys(values)
    np.testing.assert_allclose(x, expected_output[0])
    np.testing.assert_allclose(y, expected_output[1])

  @parameterized.parameters(
      interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
      interpolated_param.InterpolationMode.STEP,
  )
  def test_interpolated_param_get_value_is_jittable(
      self, mode: interpolated_param.InterpolationMode
  ):
    """Check we can jit the get_value call."""
    xs = np.array([0.25, 0.5, 0.75])
    ys = np.array([1.0, 2.0, 3.0])
    interpolated_var = interpolated_param.InterpolatedVarSingleAxis(
        value=(xs, ys), interpolation_mode=mode
    )

    jax.jit(interpolated_var.get_value)(x=0.5)

  @parameterized.product(
      is_bool=[True, False],
      interpolation_mode=[
          interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
          interpolated_param.InterpolationMode.STEP,
      ],
  )
  def test_interpolated_param_is_usable_under_jit(
      self,
      is_bool: bool,
      interpolation_mode: interpolated_param.InterpolationMode,
  ):
    var = interpolated_param.InterpolatedVarSingleAxis(
        value=(np.array([0.0, 1.0]), np.array([0.0, 1.0])),
        is_bool_param=is_bool,
        interpolation_mode=interpolation_mode,
    )

    @jax.jit
    def f(x: interpolated_param.InterpolatedVarSingleAxis, t: chex.Numeric):
      return x.get_value(x=t)

    interpolated_output_jit = jax.jit(f)(var, 0.5)
    with self.subTest('jit_and verified'):
      interpolated_output = var.get_value(x=0.5)
      np.testing.assert_allclose(interpolated_output_jit, interpolated_output)

    with self.subTest('new_values_same_compile'):
      var2 = interpolated_param.InterpolatedVarSingleAxis(
          value=(np.array([0.0, 1.0]), np.array([1.0, 2.0])),
          is_bool_param=is_bool,
          interpolation_mode=interpolation_mode,
      )
      interpolated_output_jit = f(var2, 0.5)
      interpolated_output = var2.get_value(x=0.5)
      np.testing.assert_allclose(interpolated_output_jit, interpolated_output)
      self.assertEqual(jax_utils.get_number_of_compiles(f), 1)

  @parameterized.product(
      time_interpolation_mode=[
          interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
          interpolated_param.InterpolationMode.STEP,
      ],
      rho_interpolation_mode=[
          interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
          interpolated_param.InterpolationMode.STEP,
      ],
  )
  def test_interpolated_var_time_rho_is_usable_under_jit(
      self,
      time_interpolation_mode: interpolated_param.InterpolationMode,
      rho_interpolation_mode: interpolated_param.InterpolationMode,
  ):
    values1 = {
        0.0: (np.array([0.0, 1.0]), np.array([0.0, 1.0])),
        1.0: (np.array([0.0, 1.0]), np.array([1.0, 2.0])),
    }
    rho_norm = np.array([0.0, 0.5, 1.0])
    var = interpolated_param.InterpolatedVarTimeRho(
        values=values1,
        rho_norm=rho_norm,
        time_interpolation_mode=time_interpolation_mode,
        rho_interpolation_mode=rho_interpolation_mode,
    )

    @jax.jit
    def f(v: interpolated_param.InterpolatedVarTimeRho, t: chex.Numeric):
      return v.get_value(x=t)

    t = 0.5
    with self.subTest('jit_and_verified'):
      interpolated_output_jit = f(var, t)
      interpolated_output = var.get_value(x=t)
      np.testing.assert_allclose(interpolated_output_jit, interpolated_output)

    with self.subTest('new_values_same_compile'):
      values2 = {
          0.0: (np.array([0.0, 1.0]), np.array([2.0, 3.0])),
          1.0: (np.array([0.0, 1.0]), np.array([3.0, 4.0])),
      }
      var2 = interpolated_param.InterpolatedVarTimeRho(
          values=values2,
          rho_norm=rho_norm,
          time_interpolation_mode=time_interpolation_mode,
          rho_interpolation_mode=rho_interpolation_mode,
      )
      interpolated_output_jit2 = f(var2, t)
      interpolated_output2 = var2.get_value(x=t)
      np.testing.assert_allclose(
          interpolated_output_jit2, interpolated_output2
      )
      self.assertEqual(jax_utils.get_number_of_compiles(f), 1)

    with self.subTest('different_shapes_recompiles'):
      values3 = {
          0.0: (np.array([0.0, 1.0]), np.array([0.0, 1.0])),
          1.0: (np.array([0.0, 1.0]), np.array([1.0, 2.0])),
          2.0: (np.array([0.0, 1.0]), np.array([1.0, 2.0])),
      }
      var3 = interpolated_param.InterpolatedVarTimeRho(
          values=values3,
          rho_norm=rho_norm,
          time_interpolation_mode=time_interpolation_mode,
          rho_interpolation_mode=rho_interpolation_mode,
      )
      t = 1.5
      interpolated_output_jit3 = f(var3, t)
      interpolated_output3 = var3.get_value(x=t)
      np.testing.assert_allclose(
          interpolated_output_jit3, interpolated_output3
      )
      self.assertEqual(jax_utils.get_number_of_compiles(f), 2)

  def test_interpolated_var_single_axis_eq(self):
    var1 = interpolated_param.InterpolatedVarSingleAxis(
        value=(np.array([0.0, 1.0]), np.array([0.0, 1.0])),
        interpolation_mode=interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
    )
    var2 = interpolated_param.InterpolatedVarSingleAxis(
        value=(np.array([0.0, 1.0]), np.array([0.0, 1.0])),
        interpolation_mode=interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
    )
    self.assertEqual(var1, var2)

  def test_interpolated_var_single_axis_eq_false(self):
    var1 = interpolated_param.InterpolatedVarSingleAxis(
        value=(np.array([0.0, 1.0]), np.array([0.0, 1.0])),
        interpolation_mode=interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
    )
    var2 = interpolated_param.InterpolatedVarSingleAxis(
        value=(np.array([0.0, 1.0]), np.array([0.0, 2.0])),
        interpolation_mode=interpolated_param.InterpolationMode.PIECEWISE_LINEAR,
    )
    self.assertNotEqual(var1, var2)


if __name__ == '__main__':
  absltest.main()

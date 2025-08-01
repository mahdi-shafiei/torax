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
import logging
import os

from absl.testing import absltest
from absl.testing import parameterized
import numpy as np
from torax._src.orchestration import run_simulation
from torax._src.output_tools import output
from torax._src.test_utils import sim_test_case
import xarray as xr

_ALL_PROFILES = ('T_i', 'T_e', 'psi', 'q_face', 's_face', 'n_e')


class RunSimulationTest(sim_test_case.SimTestCase):

  def test_change_config(self):
    torax_config = self._get_torax_config('test_iterhybrid_mockup.py')
    simulation_xr, _ = run_simulation.run_simulation(torax_config)

    original_value = torax_config.profile_conditions.nbar
    new_value = original_value.value * 1.1

    torax_config.update_fields({'profile_conditions.nbar': new_value})
    new_simulation_xr, _ = run_simulation.run_simulation(torax_config)

    self.assertFalse(
        np.array_equal(
            simulation_xr.profiles.n_e.values[-1],
            new_simulation_xr.profiles.n_e.values[-1],
        )
    )

  def test_restart(self):
    test_config_state_file = 'test_iterhybrid_rampup.nc'
    restart_config = 'test_iterhybrid_rampup_restart.py'

    torax_config = self._get_torax_config(restart_config)
    data_tree_restart, _ = run_simulation.run_simulation(torax_config)

    # Load the reference dataset.
    datatree_ref = output.load_state_file(
        os.path.join(self.test_data_dir, test_config_state_file)
    )

    # Stitch the restart state file to the beginning of the reference dataset.
    datatree_new = output.stitch_state_files(
        torax_config.restart, data_tree_restart
    )

    # Check equality for all time-dependent variables.
    def check_equality(ds1: xr.Dataset, ds2: xr.Dataset):
      for var_name in ds1.data_vars:
        if 'time' in ds1[var_name].dims:
          with self.subTest(var_name=var_name):
            np.testing.assert_allclose(
                ds1[var_name].values,
                ds2[var_name].values,
                err_msg=f'Mismatch for {var_name} in restart test',
                rtol=1e-6,
            )

    xr.map_over_datasets(check_equality, datatree_ref, datatree_new)

  @parameterized.named_parameters(
      ('static_geometry_QLKNN', 'test_iterhybrid_rampup.py'),
  )
  def test_no_compile_for_second_run(self, config_name: str):
    # Access the jax logger and set its level to DEBUG.
    jax_logger = logging.getLogger('jax')
    jax_logger.setLevel(logging.DEBUG)
    with self.assertLogs(logger=jax_logger, level=logging.DEBUG) as l:
      torax_config = self._get_torax_config(config_name)
      run_simulation.run_simulation(torax_config)
      # Check that the messages we expect to see for tracing and compilation
      # are present in the first run.
      self.assertTrue(any('Finished tracing' in line for line in l.output))
      self.assertTrue(any('Compiling' in line for line in l.output))
      self.assertTrue(
          any('Finished XLA compilation' in line for line in l.output)
      )
    with self.assertLogs(jax_logger, level=logging.DEBUG) as l:
      jax_logger.debug('Second run')
      torax_config = self._get_torax_config(config_name)
      run_simulation.run_simulation(torax_config)
      # Check that the same messages are not present in the second run.
      self.assertFalse(
          any('Finished tracing' in line for line in l.output), msg=l
      )
      self.assertFalse(any('Compiling f' in line for line in l.output), msg=l)
      self.assertFalse(
          any('Finished XLA compilation' in line for line in l.output),
          msg=l,
      )


if __name__ == '__main__':
  absltest.main()

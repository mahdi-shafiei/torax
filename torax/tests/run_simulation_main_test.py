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

import io
import os
import pathlib
import shutil
from typing import Final
from unittest import mock

from absl import app
from absl import logging
from absl.testing import absltest
from absl.testing import flagsaver
from absl.testing import parameterized
import numpy as np
from torax import run_simulation_main
from torax._src import simulation_app
from torax._src.output_tools import output as output_lib
from torax._src.test_utils import paths
import xarray as xr

_TMP_DIR: Final[str] = "/tmp/torax_test_output"


class RunSimulationMainTest(parameterized.TestCase):

  # These tests will make extensive use of access to private members of the
  # run_simulation_main module.
  # pylint: disable=protected-access

  @mock.patch("builtins.input", side_effect=["r"])
  def test_prompt_user_good_input(self, mock_input):
    """Test that prompt_user accepts the 'r' command."""
    del mock_input  # Needed for @patch interface but not used in this test
    path = pathlib.Path("tests/test_data/test_implicit.py")
    # The @patch decorator overrides the `input` function so that when
    # `prompt_user` calls `input`, it will receive an "r". That is a valid
    # command and it should return it.
    user_command = run_simulation_main._prompt_user(path)
    self.assertEqual(user_command, run_simulation_main._UserCommand.RUN)

  @mock.patch("builtins.input", side_effect=["invalid", "q"])
  def test_prompt_user_bad_input(self, mock_input):
    """Test that prompt_user rejects invalid input."""
    del mock_input  # Needed for @patch interface but not used in this test
    path = pathlib.Path("tests/test_data/test_implicit.py")
    # The @patch decorator overrides the `input` function so that when
    # `prompt_user` calls `input`, it will receive "invalid". That is not
    # a valid command so it should be rejected. The `prompt_user` function
    # re-prompts forever until a valid input is received so we next send
    # a valid "q" for quit.
    user_command = run_simulation_main._prompt_user(path)
    self.assertEqual(user_command, run_simulation_main._UserCommand.QUIT)

  @flagsaver.flagsaver(
      (
          run_simulation_main._CONFIG_PATH,
          "tests/test_data/test_implicit.py",
      ),
      (
          run_simulation_main._OUTPUT_DIR,
          _TMP_DIR,
      ),
  )
  @mock.patch("builtins.input", side_effect=["q"])
  def test_main_app_runs(self, mock_input):
    """Test that main app runs without errors."""
    del mock_input  # Needed for @patch interface but not used in this test

    # In this test we run the whole app. We send a mocked 'q' input to quit the
    # app after it is done running. The app quits an explicit SystemExit that
    # we need to catch to avoid bringing down the tests. To make sure that the
    # app really ran as expected, we check that the output state file exists and
    # equals the reference output.
    with self.assertRaises(SystemExit) as cm:
      app.run(run_simulation_main.main)
    # Make sure the app ran successfully
    self.assertIsNone(cm.exception.code)

    output_file = os.listdir(_TMP_DIR)[-1]
    output_path = os.path.join(_TMP_DIR, output_file)

    output = output_lib.load_state_file(output_path)
    reference = output_lib.load_state_file(
        os.path.join(paths.test_data_dir(), "test_implicit.nc")
    )

    xr.map_over_datasets(xr.testing.assert_allclose, output, reference)

  def test_main_app_cc(self):
    """Test that the main app successfully changes the config."""

    # Read only source directory containing the tests
    test_data_dir = pathlib.Path(paths.test_data_dir())
    # Path of the "before" config we will run first
    before = test_data_dir.joinpath("test_changing_config_before.py")
    # Path of the "after" config we will run second
    after = test_data_dir.joinpath("test_changing_config_after.py")

    ground_truth_before = before.with_suffix(".nc")
    ground_truth_after = after.with_suffix(".nc")

    in_use = self.create_tempfile("test_changing_config.py")

    # Copy the "before" config to the active location
    shutil.copy(before, in_use)
    # Sync if os.sync() is available (e.g. not available on Windows)
    if hasattr(os, "sync"):
      os.sync()

    with flagsaver.flagsaver((
        run_simulation_main._CONFIG_PATH,
        in_use,
    )):

      # Redirect stdout to this string buffer
      captured_stdout = io.StringIO()
      handler = logging.PythonHandler(captured_stdout)

      call_count = 0
      filepaths = []

      def mock_input(prompt):
        """Overrides the system `input` function to simulate user input."""
        nonlocal call_count

        logging.error("Calling mock_input")

        if call_count == 0:
          self.assertEqual(prompt, run_simulation_main.CHOICE_PROMPT)
          # The first run on the simulation just completed. Fetch its output.
          filepaths.append(get_latest_filepath(captured_stdout))
          # After the first run of the main program, we copy over the
          # changed config, then send the 'cc' response
          os.remove(in_use)
          shutil.copy(after, in_use)
          # Sync if os.sync() is available (e.g. not available on Windows)
          if hasattr(os, "sync"):
            os.sync()
          response = "mc"
        elif call_count == 1:
          self.assertEqual(prompt, run_simulation_main.Y_N_PROMPT)
          # The second call to `input` is confirming that we should run with
          # this config.
          response = "y"
        elif call_count == 2:
          # After changing the config, we go back to the main menu.
          # Now we need to send an 'r' to run the config.
          self.assertEqual(prompt, run_simulation_main.CHOICE_PROMPT)
          response = "r"
        else:
          # The second run on the simulation just completed. Fetch its output.
          filepaths.append(get_latest_filepath(captured_stdout))
          self.assertEqual(prompt, run_simulation_main.CHOICE_PROMPT)
          # After the second run, we quit
          response = "q"

        call_count += 1
        return response

      # Run the app with the modified `input` and stdout
      with mock.patch("builtins.input", side_effect=mock_input):
        try:
          logging.get_absl_logger().addHandler(handler)
          with self.assertRaises(SystemExit) as cm:
            app.run(run_simulation_main.main)
          # Make sure the app ran successfully
          self.assertIsNone(cm.exception.code)
        finally:
          logging.get_absl_logger().removeHandler(handler)

      # We should have received 2 runs, the before change and after change runs
      self.assertLen(filepaths, 2)
      self.assertNotEqual(filepaths[0], filepaths[1])

      def check(output_path, ground_truth_path):
        output = output_lib.load_state_file(output_path)
        ground_truth = output_lib.load_state_file(ground_truth_path)

        def check_equality(result: xr.Dataset, ground_truth: xr.Dataset):
          for key in ground_truth:
            self.assertIn(key, result)

          for key in result:
            self.assertIn(key, ground_truth)

            ov = result[key].to_numpy()
            gv = ground_truth[key].to_numpy()

            if not np.allclose(
                ov,
                gv,
                # GitHub CI behaves very differently from Google internal for
                # the mode=zero case, needing looser tolerance for this than
                # for other tests.
                # rtol=0.0,
                atol=5.0e-5,
                # This is required to allow one of psi_right_grad_constraint and
                # psi_right_constraint to be None
                equal_nan=True,
            ):
              diff = ov - gv
              max_diff = np.abs(diff).max()
              raise AssertionError(
                  f"{key} does not match. "
                  f"Output: {ov}. "
                  f"Ground truth: {gv}."
                  f"Diff: {diff}"
                  f"Max diff: {max_diff}"
              )

        xr.map_over_datasets(check_equality, output, ground_truth)

      check(filepaths[0], ground_truth_before)
      check(filepaths[1], ground_truth_after)


def get_latest_filepath(stream: io.StringIO) -> str:
  """Returns the last filepath written to by the app."""
  value = stream.getvalue()
  assert simulation_app.WRITE_PREFIX in value
  chunks = value.split(simulation_app.WRITE_PREFIX)
  last = chunks[-1]
  suffix = ".nc"
  end = last.index(suffix)
  assert end != -1
  end += len(suffix)
  path = last[:end]
  return path


if __name__ == "__main__":
  absltest.main()

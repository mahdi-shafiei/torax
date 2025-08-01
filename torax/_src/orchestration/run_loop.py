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

"""run_loop for iterating over the simulation step function."""

import time

from absl import logging
import jax
import numpy as np
from torax._src import state
from torax._src.config import build_runtime_params
from torax._src.orchestration import sim_state
from torax._src.orchestration import step_function
from torax._src.output_tools import post_processing
import tqdm


def run_loop(
    dynamic_runtime_params_slice_provider: build_runtime_params.DynamicRuntimeParamsSliceProvider,
    initial_state: sim_state.ToraxSimState,
    initial_post_processed_outputs: post_processing.PostProcessedOutputs,
    step_fn: step_function.SimulationStepFn,
    log_timestep_info: bool = False,
    progress_bar: bool = True,
) -> tuple[
    tuple[sim_state.ToraxSimState, ...],
    tuple[post_processing.PostProcessedOutputs, ...],
    state.SimError,
]:
  """Runs the simulation loop.

  Iterates over the step function until the time_step_calculator tells us we are
  done or the simulation hits an error state.

  Performs logging and updates the progress bar if requested.

  Args:
    dynamic_runtime_params_slice_provider: Provides a DynamicRuntimeParamsSlice
      to use as input for each time step. See static_runtime_params_slice and
      the runtime_params_slice module docstring for runtime_params_slice to
      understand why we need the dynamic and static config slices and what they
      control.
    initial_state: The starting state of the simulation. This includes both the
      state variables which the solver.Solver will evolve (like ion temp, psi,
      etc.) as well as other states that need to be be tracked, like time.
    initial_post_processed_outputs: The post-processed outputs at the start of
      the simulation. This is used to calculate cumulative quantities.
    step_fn: Callable which takes in ToraxSimState and outputs the ToraxSimState
      after one timestep. Note that step_fn determines dt (how long the timestep
      is). The state_history that run_simulation() outputs comes from these
      ToraxSimState objects.
    log_timestep_info: If True, logs basic timestep info, like time, dt, on
      every step.
    progress_bar: If True, displays a progress bar.

  Returns:
    A tuple of:
      - the simulation history, consisting of a tuple of ToraxSimState objects,
        one for each time step. There are N+1 objects returned, where N is the
        number of simulation steps taken. The first object in the tuple is for
        the initial state. If the sim error state is 1, then a trunctated
        simulation history is returned up until the last valid timestep.
      - the post-processed outputs history, consisting of a tuple of
        PostProcessedOutputs objects, one for each time step. There are N+1
        objects returned, where N is the number of simulation steps taken. The
        first object in the tuple is for the initial state. If the sim error
        state is 1, then a trunctated simulation history is returned up until
        the last valid timestep.
      - The sim error state.
  """

  # Provide logging information on precision setting
  if jax.config.read('jax_enable_x64'):
    logging.info('Precision is set at float64')
  else:
    logging.info('Precision is set at float32')

  logging.info('Starting simulation.')
  # Python while loop implementation.
  # Not efficient for grad, jit of grad.
  # Uses time_step_calculator.not_done to decide when to stop.
  # Note: can't use a jax while loop due to appending to history.

  running_main_loop_start_time = time.time()
  wall_clock_step_times = []

  current_state = initial_state
  state_history = [current_state]
  post_processing_history = [initial_post_processed_outputs]

  # Set the sim_error to NO_ERROR. If we encounter an error, we will set it to
  # the appropriate error code.
  sim_error = state.SimError.NO_ERROR

  # Some of the dynamic params are not time-dependent, so we can get them once
  # before the loop.
  initial_dynamic_runtime_params_slice = dynamic_runtime_params_slice_provider(
      initial_state.t
  )
  time_step_calculator_dynamic_params = (
      initial_dynamic_runtime_params_slice.time_step_calculator
  )

  with tqdm.tqdm(
      total=100,  # This makes it so that the progress bar measures a percentage
      desc='Simulating',
      disable=not progress_bar,
      leave=True,
  ) as pbar:
    # Advance the simulation until the time_step_calculator tells us we are done
    while step_fn.time_step_calculator.not_done(
        current_state.t,
        dynamic_runtime_params_slice_provider.numerics.t_final,
        time_step_calculator_dynamic_params,
    ):
      # Measure how long in wall clock time each simulation step takes.
      step_start_time = time.time()
      if log_timestep_info:
        _log_timestep(current_state)

      current_state, post_processed_outputs = step_fn(
          current_state,
          post_processing_history[-1],
      )
      sim_error = step_function.check_for_errors(
          initial_dynamic_runtime_params_slice.numerics,
          current_state,
          post_processed_outputs,
      )

      wall_clock_step_times.append(time.time() - step_start_time)

      # Checks if sim_state is valid. If not, exit simulation early.
      # We don't raise an Exception because we want to return the truncated
      # simulation history to the user for inspection.
      if sim_error != state.SimError.NO_ERROR:
        sim_error.log_error()
        break
      else:
        state_history.append(current_state)
        post_processing_history.append(post_processed_outputs)
        # Calculate progress ratio and update pbar.n
        progress_ratio = (
            float(current_state.t)
            - dynamic_runtime_params_slice_provider.numerics.t_initial
        ) / (
            dynamic_runtime_params_slice_provider.numerics.t_final
            - dynamic_runtime_params_slice_provider.numerics.t_initial
        )
        pbar.n = int(progress_ratio * pbar.total)
        pbar.set_description(f'Simulating (t={current_state.t:.5f})')
        pbar.refresh()

  # Log final timestep
  if log_timestep_info and sim_error == state.SimError.NO_ERROR:
    # The "sim_state" here has been updated by the loop above.
    _log_timestep(current_state)

  # If the first step of the simulation was very long, call it out. It might
  # have to do with tracing the jitted step_fn.
  std_devs = 2  # Check if the first step is more than 2 std devs longer.
  if wall_clock_step_times and wall_clock_step_times[0] > (
      np.mean(wall_clock_step_times) + std_devs * np.std(wall_clock_step_times)
  ):
    long_first_step = True
    logging.info(
        'The first step took more than %.1f std devs longer than other steps. '
        'It likely was tracing and compiling the step_fn. It took %.2fs '
        'of wall clock time.',
        std_devs,
        wall_clock_step_times[0],
    )
  else:
    long_first_step = False

  wall_clock_time_elapsed = time.time() - running_main_loop_start_time
  simulation_time = state_history[-1].t - state_history[0].t
  if long_first_step:
    # Don't include the long first step in the total time logged.
    wall_clock_time_elapsed -= wall_clock_step_times[0]
  logging.info(
      'Simulated %.2fs of physics in %.2fs of wall clock time.',
      simulation_time,
      wall_clock_time_elapsed,
  )
  return tuple(state_history), tuple(post_processing_history), sim_error


def _log_timestep(
    current_state: sim_state.ToraxSimState,
) -> None:
  """Logs basic timestep info."""
  log_str = (
      f'Simulation time: {current_state.t:.5f}, previous dt:'
      f' {current_state.dt:.6f}, previous solver iterations:'
      f' {current_state.solver_numeric_outputs.outer_solver_iterations}'
  )
  # TODO(b/330172917): once tol and coarse_tol are configurable in the
  # runtime_params, also log the value of tol and coarse_tol below
  match current_state.solver_numeric_outputs.solver_error_state:
    case 0:
      pass
    case 1:
      log_str += ' Solver did not converge in previous step.'
    case 2:
      log_str += (
          ' Solver converged only within coarse tolerance in previous step.'
      )
  tqdm.tqdm.write(log_str)

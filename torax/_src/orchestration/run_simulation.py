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
"""Contains the main programmatic entry point for running a TORAX simulation.

The intended use is
```
torax_config = torax.ToraxConfig.from_dict(config_dict)
sim_outputs = torax.run_simulation(torax_config)

# Update the config to run a new simulation with different parameters.
torax_config.update(updated_fields)
new_sim_outputs = torax.run_simulation(torax_config)
```
"""

from torax._src.config import build_runtime_params
from torax._src.orchestration import initial_state as initial_state_lib
from torax._src.orchestration import run_loop
from torax._src.orchestration import step_function
from torax._src.output_tools import output
from torax._src.sources import source_models as source_models_lib
from torax._src.torax_pydantic import model_config
import xarray as xr


def run_simulation(
    torax_config: model_config.ToraxConfig,
    log_timestep_info: bool = False,
    progress_bar: bool = True,
) -> tuple[xr.DataTree, output.StateHistory]:
  """Runs a TORAX simulation using the config and returns the outputs.

  Args:
    torax_config: The TORAX config to use for the simulation.
    log_timestep_info: Whether to log the timestep information.
    progress_bar: Whether to show a progress bar.

  Returns:
    A tuple of the simulation outputs in the form of a DataTree and the state
    history which is intended for helpful use with debugging as it contains
    the `CoreProfiles`, `CoreTransport`, `CoreSources`, `Geometry`, and
    `PostProcessedOutputs` dataclasses for each step of the simulation.
  """
  # TODO(b/384767453): Remove the need for the step_fn and solver to take the
  # transport model and pedestal model.
  transport_model = torax_config.transport.build_transport_model()
  pedestal_model = torax_config.pedestal.build_pedestal_model()

  geometry_provider = torax_config.geometry.build_provider
  source_models = source_models_lib.SourceModels(
      torax_config.sources, neoclassical=torax_config.neoclassical
  )

  static_runtime_params_slice = (
      build_runtime_params.build_static_params_from_config(torax_config)
  )

  solver = torax_config.solver.build_solver(
      static_runtime_params_slice=static_runtime_params_slice,
      transport_model=transport_model,
      source_models=source_models,
      pedestal_model=pedestal_model,
  )

  mhd_models = torax_config.mhd.build_mhd_models(
      static_runtime_params_slice=static_runtime_params_slice,
      transport_model=transport_model,
      source_models=source_models,
      pedestal_model=pedestal_model,
  )

  step_fn = step_function.SimulationStepFn(
      solver=solver,
      time_step_calculator=torax_config.time_step_calculator.time_step_calculator,
      transport_model=transport_model,
      pedestal_model=pedestal_model,
      mhd_models=mhd_models,
  )

  dynamic_runtime_params_slice_provider = (
      build_runtime_params.DynamicRuntimeParamsSliceProvider.from_config(
          torax_config
      )
  )

  if torax_config.restart and torax_config.restart.do_restart:
    initial_state, post_processed_outputs = (
        initial_state_lib.get_initial_state_and_post_processed_outputs_from_file(
            t_initial=torax_config.numerics.t_initial,
            file_restart=torax_config.restart,
            static_runtime_params_slice=static_runtime_params_slice,
            dynamic_runtime_params_slice_provider=dynamic_runtime_params_slice_provider,
            geometry_provider=geometry_provider,
            step_fn=step_fn,
        )
    )
    restart_case = True
  else:
    initial_state, post_processed_outputs = (
        initial_state_lib.get_initial_state_and_post_processed_outputs(
            t=torax_config.numerics.t_initial,
            static_runtime_params_slice=static_runtime_params_slice,
            dynamic_runtime_params_slice_provider=dynamic_runtime_params_slice_provider,
            geometry_provider=geometry_provider,
            step_fn=step_fn,
        )
    )
    restart_case = False

  state_history, post_processed_outputs_history, sim_error = run_loop.run_loop(
      static_runtime_params_slice=static_runtime_params_slice,
      dynamic_runtime_params_slice_provider=dynamic_runtime_params_slice_provider,
      geometry_provider=geometry_provider,
      initial_state=initial_state,
      initial_post_processed_outputs=post_processed_outputs,
      restart_case=restart_case,
      step_fn=step_fn,
      log_timestep_info=log_timestep_info,
      progress_bar=progress_bar,
  )
  state_history = output.StateHistory(
      state_history=state_history,
      post_processed_outputs_history=post_processed_outputs_history,
      sim_error=sim_error,
      torax_config=torax_config,
  )

  return (
      state_history.simulation_output_to_xr(torax_config.restart),
      state_history,
  )

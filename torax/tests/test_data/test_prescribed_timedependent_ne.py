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

"""Tests time dependent boundary conditions and sources.

Ip from parameters. implicit + pereverzev-corrigan, Ti+Te+Psi, Pei standard
dens, pedestal, chi from QLKNN. Includes time dependent Ip, Ptot, and
pedestal, mocking up current-overshoot and an LH transition
"""

import dataclasses
from torax import geometry
from torax import sim as sim_lib
from torax.config import runtime_params as general_runtime_params
from torax.sources import default_sources
from torax.sources import runtime_params as source_runtime_params
from torax.sources import source_models as source_models_lib
from torax.stepper import linear_theta_method
from torax.stepper import runtime_params as stepper_runtime_params
from torax.transport_model import qlknn_wrapper


def get_runtime_params() -> general_runtime_params.GeneralRuntimeParams:
  return general_runtime_params.GeneralRuntimeParams(
      profile_conditions=general_runtime_params.ProfileConditions(
          Ti_bound_left=10,
          Te_bound_left=10,
          Ip={0: 5, 4: 15, 6: 12, 8: 12},
          Tiped={0: 2, 4: 2, 6: 5, 8: 4},
          Teped={0: 2, 4: 2, 6: 5, 8: 4},
      ),
      numerics=general_runtime_params.Numerics(
          current_eq=True,
          resistivity_mult=50,  # to shorten current diffusion time for the test
          dtmult=150,
          maxdt=0.5,
          t_final=10,
          enable_prescribed_profile_evolution=True,
      ),
  )


def get_geometry(
    runtime_params: general_runtime_params.GeneralRuntimeParams,
) -> geometry.Geometry:
  return geometry.build_chease_geometry(
      runtime_params,
      geometry_file="ITER_hybrid_citrin_equil_cheasedata.mat2cols",
      Ip_from_parameters=True,
  )


def get_transport_model() -> qlknn_wrapper.QLKNNTransportModel:
  return qlknn_wrapper.QLKNNTransportModel(
      runtime_params=qlknn_wrapper.RuntimeParams(
          apply_inner_patch=True,
          chii_inner=2.0,
          chie_inner=2.0,
          rho_inner=0.3,
      ),
  )


def get_sources() -> source_models_lib.SourceModels:
  """Returns the source models used in the simulation."""
  source_models = default_sources.get_default_sources()
  # remove bootstrap current
  source_models.j_bootstrap.runtime_params.bootstrap_mult = 0.0
  # pylint: disable=unexpected-keyword-arg
  source_models.sources["generic_ion_el_heat_source"].runtime_params = (
      dataclasses.replace(
          source_models.sources["generic_ion_el_heat_source"].runtime_params,
          # Gaussian width in normalized radial coordinate r
          w=0.18202270915319393,
          # total heating (including accounting for radiation) r
          Ptot={
              0: 20e6,
              9: 20e6,
              10: 120e6,
              15: 120e6,
          },  # in W
      )
  )
  # total pellet particles/s (continuous pellet model)
  source_models.sources["pellet_source"].runtime_params.S_pellet_tot = 0.0
  # total pellet particles/s
  source_models.sources["gas_puff_source"].runtime_params.S_puff_tot = 0
  # NBI total particle source
  source_models.sources["nbi_particle_source"].runtime_params.S_nbi_tot = 0.0
  source_models.sources["fusion_heat_source"].runtime_params.mode = (
      source_runtime_params.Mode.ZERO
  )
  source_models.sources["ohmic_heat_source"].runtime_params.mode = (
      source_runtime_params.Mode.ZERO
  )
  return source_models


def get_stepper_builder() -> linear_theta_method.LinearThetaMethodBuilder:
  """Returns a builder for the stepper that includes its runtime params."""
  builder = linear_theta_method.LinearThetaMethodBuilder(
      runtime_params=stepper_runtime_params.RuntimeParams(
          predictor_corrector=False,
          use_pereverzev=True,
      )
  )
  return builder


def get_sim() -> sim_lib.Sim:
  # This approach is currently lightweight because so many objects require
  # config for construction, but over time we expect to transition to most
  # config taking place via constructor args in this function.
  runtime_params = get_runtime_params()
  geo = get_geometry(runtime_params)
  return sim_lib.build_sim_from_config(
      runtime_params=runtime_params,
      geo=geo,
      stepper_builder=get_stepper_builder(),
      source_models=get_sources(),
      transport_model=get_transport_model(),
  )
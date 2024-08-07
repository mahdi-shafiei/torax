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

"""General runtime input parameters used throughout TORAX simulations."""

from __future__ import annotations

from collections.abc import Mapping
import dataclasses
import logging
from typing import TypeAlias

import chex
from torax import geometry
from torax import interpolated_param
from torax.config import config_args


# Type-alias for clarity. While the InterpolatedVarSingleAxis can vary across
# any field, in here, we mainly use it to handle time-dependent parameters.
TimeInterpolated: TypeAlias = interpolated_param.TimeInterpolated
# Type-alias for clarity for time-and-rho-dependent parameters.
TimeRhoInterpolated: TypeAlias = (
    interpolated_param.TimeRhoInterpolated
)


# pylint: disable=invalid-name


@chex.dataclass
class PlasmaComposition:
  """Configuration for the plasma composition."""
  # amu of main ion (if multiple isotope, make average)
  Ai: float = 2.5
  # charge of main ion
  Zi: float = 1.0
  # needed for qlknn and fusion power
  Zeff: TimeInterpolated = 1.0
  Zimp: TimeInterpolated = (
      10.0  # impurity charge state assumed for dilution
  )

  def build_dynamic_params(
      self,
      t: chex.Numeric,
  ) -> DynamicPlasmaComposition:
    """Builds a DynamicPlasmaComposition."""
    return DynamicPlasmaComposition(
        **config_args.get_init_kwargs(
            input_config=self,
            output_type=DynamicPlasmaComposition,
            t=t,
        )
    )


@chex.dataclass
class DynamicPlasmaComposition:
  # amu of main ion (if multiple isotope, make average)
  Ai: float
  # charge of main ion
  Zi: float
  # needed for qlknn and fusion power
  Zeff: float
  Zimp: float  # impurity charge state assumed for dilution


@chex.dataclass
class ProfileConditions:
  """Prescribed values and boundary conditions for the core profiles."""

  # total plasma current in MA
  # Note that if Ip_from_parameters=False in geometry, then this Ip will be
  # overwritten by values from the geometry data
  Ip: TimeInterpolated = 15.0

  # Temperature boundary conditions at r=Rmin. If provided this will override
  # the temperature boundary conditions being taken from the
  # `TimeRhoInterpolated`s.
  Ti_bound_right: TimeInterpolated | None = None
  Te_bound_right: TimeInterpolated | None = None
  # Prescribed or evolving values for temperature at different times.
  # The outer mapping is for times and the inner mapping is for values of
  # temperature along the rho grid.
  Ti: TimeRhoInterpolated = dataclasses.field(
      default_factory=lambda: {0: {0: 15.0, 1: 1.0}}
  )
  Te: TimeRhoInterpolated = dataclasses.field(
      default_factory=lambda: {0: {0: 15.0, 1: 1.0}}
  )

  # Prescribed or evolving values for electron density at different times.
  # The outer mapping is for times and the inner mapping is for values of
  # density along the rho grid.
  ne: TimeRhoInterpolated = dataclasses.field(
      default_factory=lambda: {0: {0: 1.5, 1: 1.0}}
  )
  # Whether to renormalize the density profile to have the desired line averaged
  # density `nbar`.
  normalize_to_nbar: bool = True

  # Line averaged density.
  # In units of reference density if ne_is_fGW = False.
  # In Greenwald fraction if ne_is_fGW = True.
  # nGW = Ip/(pi*a^2) with a in m, nGW in 10^20 m-3, Ip in MA
  nbar: TimeInterpolated = 0.85
  # Toggle units of nbar
  ne_is_fGW: bool = True

  # Density boundary condition for r=Rmin.
  # In units of reference density if ne_bound_right_is_fGW = False.
  # In Greenwald fraction if ne_bound_right_is_fGW = True.
  ne_bound_right: TimeInterpolated | None = None
  ne_bound_right_is_fGW: bool = False

  # Internal boundary condition (pedestal)
  # Do not set internal boundary condition if this is False
  set_pedestal: TimeInterpolated = True
  # ion pedestal top temperature in keV
  Tiped: TimeInterpolated = 5.0
  # electron pedestal top temperature in keV
  Teped: TimeInterpolated = 5.0
  # pedestal top electron density
  # In units of reference density if neped_is_fGW = False.
  # In Greenwald fraction if neped_is_fGW = True.
  neped: TimeInterpolated = 0.7
  neped_is_fGW: bool = False
  # Set ped top location.
  Ped_top: TimeInterpolated = 0.91

  # current profiles (broad "Ohmic" + localized "external" currents)
  # peaking factor of "Ohmic" current: johm = j0*(1 - r^2/a^2)^nu
  nu: float = 3.0
  # toggles if "Ohmic" current is treated as total current upon initialization,
  # or if non-inductive current should be included in initial jtot calculation
  initial_j_is_total_current: bool = False
  # toggles if the initial psi calculation is based on the "nu" current formula,
  # or from the psi available in the numerical geometry file. This setting is
  # ignored for the ad-hoc circular geometry, which has no numerical geometry.
  initial_psi_from_j: bool = False

  def build_dynamic_params(
      self,
      t: chex.Numeric,
      geo: geometry.Geometry,
      output_logs: bool = False,
  ) -> DynamicProfileConditions:
    """Builds a DynamicProfileConditions."""
    dynamic_profile_conditions_kwargs = config_args.get_init_kwargs(
        input_config=self,
        output_type=DynamicProfileConditions,
        t=t,
        geo=geo,
        skip=('ne_bound_right_is_absolute',),
    )
    if self.Te_bound_right is None:
      if output_logs:
        logging.info(
            'Setting electron temperature boundary condition using Te.'
        )
      dynamic_profile_conditions_kwargs['Te_bound_right'] = float(
          config_args.interpolate_var_2d(
              self.Te,
              t,
              geo.torax_mesh.face_centers[-1],
          )
      )
    if self.Ti_bound_right is None:
      if output_logs:
        logging.info('Setting ion temperature boundary condition using Ti.')
      dynamic_profile_conditions_kwargs['Ti_bound_right'] = float(
          config_args.interpolate_var_2d(
              self.Ti,
              t,
              geo.torax_mesh.face_centers[-1],
          )
      )
    if self.ne_bound_right is None:
      if output_logs:
        logging.info('Setting electron density boundary condition using ne.')
      dynamic_profile_conditions_kwargs['ne_bound_right'] = float(
          config_args.interpolate_var_2d(
              self.ne,
              t,
              geo.torax_mesh.face_centers[-1],
          ),
      )
      dynamic_profile_conditions_kwargs['ne_bound_right_is_fGW'] = (
          dynamic_profile_conditions_kwargs['ne_is_fGW']
      )
      dynamic_profile_conditions_kwargs['ne_bound_right_is_absolute'] = False
    else:
      dynamic_profile_conditions_kwargs['ne_bound_right_is_absolute'] = True

    dynamic_profile_conditions = DynamicProfileConditions(
        **dynamic_profile_conditions_kwargs
    )
    return dynamic_profile_conditions


@chex.dataclass
class DynamicProfileConditions:
  """Prescribed values and boundary conditions for the core profiles."""

  # total plasma current in MA
  # Note that if Ip_from_parameters=False in geometry, then this Ip will be
  # overwritten by values from the geometry data
  Ip: float

  # Temperature boundary conditions at r=Rmin.
  Ti_bound_right: float
  Te_bound_right: float
  # Radial array used for initial conditions, and prescribed time-dependent
  # conditions when not evolving variable with PDE defined on the cell grid.
  Te: chex.Array
  Ti: chex.Array

  # Electron density profile on the cell grid.
  # If density evolves with PDE (dens_eq=True), then is initial condition
  ne: chex.Array
  # Whether to renormalize the density profile.
  normalize_to_nbar: bool

  # Initial line averaged density.
  # In units of reference density if ne_is_fGW = False.
  # In Greenwald fraction if ne_is_fGW = True.
  # nGW = Ip/(pi*a^2) with a in m, nGW in 10^20 m-3, Ip in MA
  nbar: float
  # Toggle units of nbar
  ne_is_fGW: bool

  # Density boundary condition for r=Rmin, units of nref
  # In units of reference density if ne_bound_right_is_fGW = False.
  # In Greenwald fraction if ne_bound_right_is_fGW = True.
  ne_bound_right: float
  ne_bound_right_is_fGW: bool
  # If `ne_bound_right` is set using `ne` then this flag should be `False`.
  ne_bound_right_is_absolute: bool

  # Internal boundary condition (pedestal)
  # Do not set internal boundary condition if this is False
  set_pedestal: bool
  # ion pedestal top temperature in keV for Ti and Te
  Tiped: float
  # electron pedestal top temperature in keV for Ti and Te
  Teped: float
  # pedestal top electron density
  # In units of reference density if neped_is_fGW = False.
  # In Greenwald fraction if neped_is_fGW = True.
  neped: float
  neped_is_fGW: bool
  # Set ped top location.
  Ped_top: float

  # current profiles (broad "Ohmic" + localized "external" currents)
  # peaking factor of prescribed (initial) "Ohmic" current:
  # johm = j0*(1 - r^2/a^2)^nu
  nu: float
  # toggles if "Ohmic" current is treated as total current upon initialization,
  # or if non-inductive current should be included in initial jtot calculation
  initial_j_is_total_current: bool
  # toggles if the initial psi calculation is based on the "nu" current formula,
  # or from the psi available in the numerical geometry file. This setting is
  # ignored for the ad-hoc circular geometry, which has no numerical geometry.
  initial_psi_from_j: bool


@chex.dataclass
class Numerics:
  """Generic numeric parameters for the simulation."""

  # simulation control
  # start of simulation, in seconds
  t_initial: float = 0.0
  # end of simulation, in seconds
  t_final: float = 5.0
  # If True, ensures that if the simulation runs long enough, one step
  # occurs exactly at `t_final`.
  exact_t_final: bool = False

  # maximum and minimum timesteps allowed in simulation
  maxdt: float = 1e-1  #  only used with chi_time_step_calculator
  mindt: float = 1e-8  #  if adaptive timestep is True, error raised if dt<mindt

  # prefactor in front of chi_timestep_calculator base timestep dt=dx^2/(2*chi).
  # In most use-cases can be increased further above this conservative default
  dtmult: float = 0.9 * 10

  fixed_dt: float = 1e-2  # timestep used for fixed_time_step_calculator

  # Iterative reduction of dt if nonlinear step does not converge,
  # If nonlinear step does not converge, then the step is redone
  # iteratively at successively lower dt until convergence is reached
  adaptive_dt: bool = True
  dt_reduction_factor: float = 3

  # Solve the ion heat equation (ion temperature evolves over time)
  ion_heat_eq: bool = True
  # Solve the electron heat equation (electron temperature evolves over time)
  el_heat_eq: bool = True
  # Solve the current equation (psi evolves over time driven by the solver;
  # q and s evolve over time as a function of psi)
  current_eq: bool = False
  # Solve the density equation (n evolves over time)
  dens_eq: bool = False
  # Enable time-dependent prescribed profiles.
  # This option is provided to allow initialization of density profiles scaled
  # to a Greenwald fraction, and freeze this density even if the current is time
  # evolving. Otherwise the density will evolve to always maintain that GW frac.
  enable_prescribed_profile_evolution: bool = True

  # Calculate Phibdot in the geometry dataclasses. This is used in calc_coeffs
  # to calculate terms related to time-dependent geometry. Can set to false to
  # zero out for testing purposes.
  calcphibdot: bool = True

  # q-profile correction factor. Used only in ad-hoc circular geometry model
  q_correction_factor: float = 1.25
  # 1/multiplication factor for sigma (conductivity) to reduce current
  # diffusion timescale to be closer to heat diffusion timescale
  resistivity_mult: TimeInterpolated = 1.0

  # density profile info
  # Reference value for normalization
  nref: float = 1e20

  # numerical (e.g. no. of grid points, other info needed by solver)
  # effective source to dominate PDE in internal boundary condtion location
  # if T != Tped
  largeValue_T: float = 2.0e10
  # effective source to dominate density PDE in internal boundary condtion
  # location if n != neped
  largeValue_n: float = 2.0e8

  def build_dynamic_params(
      self,
      t: chex.Numeric,
  ) -> DynamicNumerics:
    """Builds a DynamicNumerics."""
    return DynamicNumerics(
        **config_args.get_init_kwargs(
            input_config=self,
            output_type=DynamicNumerics,
            t=t,
        )
    )


@chex.dataclass
class DynamicNumerics:
  """Generic numeric parameters for the simulation."""

  # simulation control
  # start of simulation, in seconds
  t_initial: float
  # end of simulation, in seconds
  t_final: float
  # If True, ensures that if the simulation runs long enough, one step
  # occurs exactly at `t_final`.
  exact_t_final: bool

  # maximum and minimum timesteps allowed in simulation
  maxdt: float  #  only used with chi_time_step_calculator
  mindt: float  #  if adaptive timestep is True, error raised if dt<mindt

  # prefactor in front of chi_timestep_calculator base timestep dt=dx^2/(2*chi).
  # In most use-cases can be increased further above this conservative default
  dtmult: float

  fixed_dt: float  # timestep used for fixed_time_step_calculator
  dt_reduction_factor: float

  # q-profile correction factor. Used only in ad-hoc circular geometry model
  q_correction_factor: float
  # 1/multiplication factor for sigma (conductivity) to reduce current
  # diffusion timescale to be closer to heat diffusion timescale
  resistivity_mult: float

  # density profile info
  # Reference value for normalization
  nref: float

  # numerical (e.g. no. of grid points, other info needed by solver)
  # effective source to dominate PDE in internal boundary condtion location
  # if T != Tped
  largeValue_T: float
  # effective source to dominate density PDE in internal boundary condtion
  # location if n != neped
  largeValue_n: float

  # Enable time-dependent prescribed profiles.
  # This option is provided to allow initialization of density profiles scaled
  # to a Greenwald fraction, and freeze this density even if the current is time
  # evolving. Otherwise the density will evolve to always maintain that GW frac.
  enable_prescribed_profile_evolution: bool

  # Calculate Phibdot in the geometry dataclasses. This is used in calc_coeffs
  # to calculate terms related to time-dependent geometry. Can set to false to
  # zero out for testing purposes.
  calcphibdot: bool


# NOMUTANTS -- It's expected for the tests to pass with different defaults.
@chex.dataclass
class GeneralRuntimeParams:
  """General runtime input parameters for the `torax` module."""

  plasma_composition: PlasmaComposition = dataclasses.field(
      default_factory=PlasmaComposition
  )
  profile_conditions: ProfileConditions = dataclasses.field(
      default_factory=ProfileConditions
  )
  numerics: Numerics = dataclasses.field(default_factory=Numerics)

  # 'File directory where the simulation outputs will be saved. If not '
  # 'provided, this will default to /tmp/torax_results_<YYYYMMDD_HHMMSS>/.',
  output_dir: str | None = None

  # pylint: enable=invalid-name

  def _sanity_check_profile_boundary_conditions(
      self, var: TimeRhoInterpolated, var_name: str,
  ):
    """Check that the profile is defined at rho=1.0."""
    if isinstance(var, interpolated_param.InterpolatedVarTimeRho):
      values = var.values
    else:
      values = var

    for time in values:
      if isinstance(values[time], Mapping):
        if 1.0 not in values[time]:
          raise ValueError(
              f'As no right boundary condition was set for {var_name}, the'
              f' profile for {var_name} must include a value at rho=1.0 for'
              ' every provided time.'
          )
      else:
        raise ValueError(
            f'As no right boundary condition was set for {var_name}, the '
            f'profile for {var_name} must include a rho=1.0 boundary condition.'
        )

  def sanity_check(self) -> None:
    """Checks that various configuration parameters are valid."""
    # TODO(b/330172917) do more extensive config parameter sanity checking

    # These are floats, not jax types, so we can use direct asserts.
    assert self.numerics.dtmult > 0.0
    assert isinstance(self.plasma_composition, PlasmaComposition)
    assert isinstance(self.numerics, Numerics)
    if self.profile_conditions.Ti_bound_right is None:
      self._sanity_check_profile_boundary_conditions(
          self.profile_conditions.Ti,
          'Ti',
      )
    if self.profile_conditions.Te_bound_right is None:
      self._sanity_check_profile_boundary_conditions(
          self.profile_conditions.Te,
          'Te',
      )
    if self.profile_conditions.ne_bound_right is None:
      self._sanity_check_profile_boundary_conditions(
          self.profile_conditions.ne,
          'ne',
      )

  def __post_init__(self):
    self.sanity_check()

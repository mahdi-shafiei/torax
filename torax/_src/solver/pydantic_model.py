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

"""Pydantic config for Solver."""
import abc
import dataclasses
import functools
from typing import Annotated, Literal

import pydantic
from torax._src import physics_models as physics_models_lib
from torax._src.config import runtime_params_slice
from torax._src.fvm import enums
from torax._src.solver import linear_theta_method
from torax._src.solver import nonlinear_theta_method
from torax._src.solver import runtime_params
from torax._src.solver import solver as solver_lib
from torax._src.torax_pydantic import torax_pydantic

# pylint: disable=invalid-name


class BaseSolver(torax_pydantic.BaseModelFrozen, abc.ABC):
  """Base class for solver configs.

  Attributes:
    theta_implicit: The theta value in the theta method 0 = explicit, 1 = fully
      implicit, 0.5 = Crank-Nicolson.
    use_predictor_corrector: Enables use_predictor_corrector iterations with the
      linear solver. If False, compilation is faster.
    n_corrector_steps: The number of corrector steps for the predictor-corrector
      linear solver. 0 means a pure linear solve with no corrector steps.
    convection_dirichlet_mode: See `fvm.convection_terms` docstring,
      `dirichlet_mode` argument.
    convection_neumann_mode: See `fvm.convection_terms` docstring,
      `neumann_mode` argument.
    use_pereverzev: Use pereverzev terms for linear solver. Is only applied in
      the nonlinear solver for the optional initial guess from the linear solver
    chi_pereverzev: (deliberately) large heat conductivity for Pereverzev rule.
    D_pereverzev: (deliberately) large particle diffusion for Pereverzev rule.
  """

  theta_implicit: Annotated[
      torax_pydantic.UnitInterval, torax_pydantic.JAX_STATIC
  ] = 1.0
  use_predictor_corrector: Annotated[bool, torax_pydantic.JAX_STATIC] = False
  n_corrector_steps: pydantic.PositiveInt = 10
  convection_dirichlet_mode: Annotated[
      Literal['ghost', 'direct', 'semi-implicit'], torax_pydantic.JAX_STATIC
  ] = 'ghost'
  convection_neumann_mode: Annotated[
      Literal['ghost', 'semi-implicit'], torax_pydantic.JAX_STATIC
  ] = 'ghost'
  use_pereverzev: Annotated[bool, torax_pydantic.JAX_STATIC] = False
  chi_pereverzev: pydantic.PositiveFloat = 30.0
  D_pereverzev: pydantic.NonNegativeFloat = 15.0

  @property
  @abc.abstractmethod
  def build_dynamic_params(self) -> runtime_params.DynamicRuntimeParams:
    """Builds dynamic runtime params from the config."""

  def build_static_params(self) -> runtime_params.StaticRuntimeParams:
    """Builds static runtime params from the config."""
    return runtime_params.StaticRuntimeParams(
        theta_implicit=self.theta_implicit,
        convection_dirichlet_mode=self.convection_dirichlet_mode,
        convection_neumann_mode=self.convection_neumann_mode,
        use_pereverzev=self.use_pereverzev,
        use_predictor_corrector=self.use_predictor_corrector,
    )

  @abc.abstractmethod
  def build_solver(
      self,
      static_runtime_params_slice: runtime_params_slice.StaticRuntimeParamsSlice,
      physics_models: physics_models_lib.PhysicsModels,
  ) -> solver_lib.Solver:
    """Builds a solver from the config."""


class LinearThetaMethod(BaseSolver):
  """Model for the linear solver.

  Attributes:
    solver_type: The type of solver to use, hardcoded to 'linear'.
  """

  solver_type: Annotated[Literal['linear'], torax_pydantic.JAX_STATIC] = (
      'linear'
  )

  @functools.cached_property
  def build_dynamic_params(self) -> runtime_params.DynamicRuntimeParams:
    return runtime_params.DynamicRuntimeParams(
        chi_pereverzev=self.chi_pereverzev,
        D_pereverzev=self.D_pereverzev,
        n_corrector_steps=self.n_corrector_steps,
    )

  def build_solver(
      self,
      static_runtime_params_slice: runtime_params_slice.StaticRuntimeParamsSlice,
      physics_models: physics_models_lib.PhysicsModels,
  ) -> solver_lib.Solver:
    return linear_theta_method.LinearThetaMethod(
        static_runtime_params_slice=static_runtime_params_slice,
        physics_models=physics_models,
    )


class NewtonRaphsonThetaMethod(BaseSolver):
  """Model for nonlinear Newton-Raphson solver.

  Attributes:
    solver_type: The type of solver to use, hardcoded to 'newton_raphson'.
    log_iterations: If True, log internal iterations in Newton-Raphson solver.
    initial_guess_mode: The initial guess mode for the Newton-Raphson solver.
    n_max_iterations: The maximum number of iterations for the Newton-Raphson
      solver.
    residual_tol: The tolerance for the Newton-Raphson solver.
    residual_coarse_tol: The coarse tolerance for the Newton-Raphson solver.
    delta_reduction_factor: The delta reduction factor for the Newton-Raphson
      solver.
    tau_min: The minimum value of tau for the Newton-Raphson solver.
  """

  solver_type: Annotated[
      Literal['newton_raphson'], torax_pydantic.JAX_STATIC
  ] = 'newton_raphson'
  log_iterations: Annotated[bool, torax_pydantic.JAX_STATIC] = False
  initial_guess_mode: Annotated[
      enums.InitialGuessMode, torax_pydantic.JAX_STATIC
  ] = enums.InitialGuessMode.LINEAR
  n_max_iterations: pydantic.NonNegativeInt = 30
  residual_tol: float = 1e-5
  residual_coarse_tol: float = 1e-2
  delta_reduction_factor: float = 0.5
  tau_min: float = 0.01

  def build_static_params(
      self,
  ) -> nonlinear_theta_method.StaticNewtonRaphsonRuntimeParams:
    """Builds static runtime params from the config."""
    base_params = super().build_static_params()
    return nonlinear_theta_method.StaticNewtonRaphsonRuntimeParams(
        **dataclasses.asdict(base_params),
        initial_guess_mode=self.initial_guess_mode.value,
        log_iterations=self.log_iterations,
    )

  @functools.cached_property
  def build_dynamic_params(
      self,
  ) -> nonlinear_theta_method.DynamicNewtonRaphsonRuntimeParams:
    return nonlinear_theta_method.DynamicNewtonRaphsonRuntimeParams(
        chi_pereverzev=self.chi_pereverzev,
        D_pereverzev=self.D_pereverzev,
        maxiter=self.n_max_iterations,
        residual_tol=self.residual_tol,
        residual_coarse_tol=self.residual_coarse_tol,
        n_corrector_steps=self.n_corrector_steps,
        delta_reduction_factor=self.delta_reduction_factor,
        tau_min=self.tau_min,
    )

  def build_solver(
      self,
      static_runtime_params_slice: runtime_params_slice.StaticRuntimeParamsSlice,
      physics_models: physics_models_lib.PhysicsModels,
  ) -> nonlinear_theta_method.NewtonRaphsonThetaMethod:
    return nonlinear_theta_method.NewtonRaphsonThetaMethod(
        static_runtime_params_slice=static_runtime_params_slice,
        physics_models=physics_models,
    )


class OptimizerThetaMethod(BaseSolver):
  """Model for nonlinear OptimizerThetaMethod solver.

  Attributes:
    solver_type: The type of solver to use, hardcoded to 'optimizer'.
    initial_guess_mode: The initial guess mode for the optimizer.
    n_max_iterations: The maximum number of iterations for the optimizer.
    residual_tol: The tolerance for the optimizer.
  """

  solver_type: Annotated[Literal['optimizer'], torax_pydantic.JAX_STATIC] = (
      'optimizer'
  )
  initial_guess_mode: Annotated[
      enums.InitialGuessMode, torax_pydantic.JAX_STATIC
  ] = enums.InitialGuessMode.LINEAR
  n_max_iterations: pydantic.NonNegativeInt = 100
  loss_tol: float = 1e-10

  def build_static_params(
      self,
  ) -> nonlinear_theta_method.StaticOptimizerRuntimeParams:
    """Builds static runtime params from the config."""
    base_params = super().build_static_params()
    return nonlinear_theta_method.StaticOptimizerRuntimeParams(
        **dataclasses.asdict(base_params),
        initial_guess_mode=self.initial_guess_mode.value,
    )

  @functools.cached_property
  def build_dynamic_params(
      self,
  ) -> nonlinear_theta_method.DynamicOptimizerRuntimeParams:
    return nonlinear_theta_method.DynamicOptimizerRuntimeParams(
        chi_pereverzev=self.chi_pereverzev,
        D_pereverzev=self.D_pereverzev,
        n_max_iterations=self.n_max_iterations,
        loss_tol=self.loss_tol,
        n_corrector_steps=self.n_corrector_steps,
    )

  def build_solver(
      self,
      static_runtime_params_slice: runtime_params_slice.StaticRuntimeParamsSlice,
      physics_models: physics_models_lib.PhysicsModels,
  ) -> nonlinear_theta_method.OptimizerThetaMethod:
    return nonlinear_theta_method.OptimizerThetaMethod(
        static_runtime_params_slice=static_runtime_params_slice,
        physics_models=physics_models,
    )


SolverConfig = (
    LinearThetaMethod | NewtonRaphsonThetaMethod | OptimizerThetaMethod
)
